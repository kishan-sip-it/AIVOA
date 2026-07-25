"""
routers/complaint.py
---------------------
All /api/complaint/* endpoints. Kept separate from main.py so main.py stays
a thin app-factory/wiring file, per the "separate routers, services, models"
requirement.
"""
import sys
import traceback
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Complaint
from app.services.pdf_service import extract_text_from_pdf

from app.graph import intake_graph, correction_graph
from app.schemas import (
    ChatRequest,
    ProcessComplaintResponse,
    ChatResponse,
    CommitComplaintRequest,
    CommitComplaintResponse,
)

router = APIRouter(prefix="/api/complaint", tags=["complaint"])


@router.post("/process", response_model=ProcessComplaintResponse)
async def process_complaint(
    raw_text: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
):
    """
    Accepts either free text (`raw_text` form field) or a PDF file upload.
    Runs the LangGraph intake workflow: parse_input_node -> risk_assessment_node
    -> completeness_checker.
    """
    if not raw_text and not file:
        raise HTTPException(status_code=400, detail="Provide either raw_text or a file.")

    input_text = raw_text or ""

    if file:
        if file.content_type != "application/pdf" and not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF file uploads are supported.")
        file_bytes = await file.read()
        try:
            pdf_text = extract_text_from_pdf(file_bytes)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        input_text = f"{input_text}\n\n{pdf_text}".strip()

    initial_state = {
        "raw_input": input_text,
        "extracted_data": {},
        "chat_history": [],
        "risk_assessment": {},
        "is_complete": False,
        "status": "pending",
        "last_message": "",
    }

    result_state = intake_graph.invoke(initial_state)

    return ProcessComplaintResponse(
        extracted_data=result_state["extracted_data"],
        risk_assessment=result_state["risk_assessment"],
        is_complete=result_state["is_complete"],
        status=result_state["status"],
        chat_history=result_state.get("chat_history", []),
    )


@router.post("/chat", response_model=ChatResponse)
async def chat_with_copilot(payload: ChatRequest):
    """
    Accepts a follow-up chat instruction plus the current graph state.
    Routes through correction_node -> risk_assessment_node -> completeness_checker.
    The frontend is expected to send back the full current state on every
    call since LangGraph itself is stateless between HTTP requests here
    (no checkpointer is attached — state lives in Redux on the client).
    """
    state = dict(payload.state)
    state["last_message"] = payload.message

    result_state = correction_graph.invoke(state)

    ai_message = result_state.pop("_last_ai_message", "Updated.")

    return ChatResponse(
        extracted_data=result_state["extracted_data"],
        risk_assessment=result_state["risk_assessment"],
        is_complete=result_state["is_complete"],
        status=result_state["status"],
        chat_history=result_state.get("chat_history", []),
        ai_message=ai_message,
    )


@router.post("/commit", response_model=CommitComplaintResponse)
async def commit_complaint(payload: CommitComplaintRequest, db: Session = Depends(get_db)):
    """Persists the finalized complaint to the PostgreSQL QMS ledger."""

    data = payload.extracted_data
    risk = payload.risk_assessment

    required = ["complaint_source", "customer_name", "product_name", "batch_number",
                "originating_site_block", "complaint_category", "complaint_description"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        raise HTTPException(status_code=400, detail=f"Cannot commit — missing fields: {missing}")

    complaint = Complaint(
        complaint_source=data.get("complaint_source"),
        customer_name=data.get("customer_name"),
        product_name=data.get("product_name"),
        product_strength=data.get("product_strength"),
        batch_number=data.get("batch_number"),
        affected_quantity=data.get("affected_quantity"),
        manufacturing_date=data.get("manufacturing_date"),
        expiry_date=data.get("expiry_date"),
        originating_site_block=data.get("originating_site_block"),
        impacted_npm=data.get("impacted_npm"),
        complaint_category=data.get("complaint_category"),
        complaint_description=data.get("complaint_description"),
        severity_suggested=risk.get("severity_suggested"),
        suggested_next_action=risk.get("suggested_next_action"),
        initial_risk_assessment=risk.get("initial_risk_assessment"),
        raw_input=payload.raw_input,
        chat_history=payload.chat_history,
        status="committed",
    )

    db.add(complaint)
    db.commit()
    db.refresh(complaint)

    return CommitComplaintResponse(
        id=str(complaint.id),
        status="committed",
        message=f"Complaint committed to QMS Ledger with ID {complaint.id}",
    )
