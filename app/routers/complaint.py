"""
routers/complaint.py
---------------------
All /api/complaint/* endpoints with bonus features.
"""

import sys
import traceback
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models import Complaint
from app.services.document_service import extract_text, SUPPORTED_EXTENSIONS
from app.graph import intake_graph, correction_graph
from app.schemas import (
    ChatRequest,
    ProcessComplaintResponse,
    ChatResponse,
    CommitComplaintRequest,
    CommitComplaintResponse,
)

router = APIRouter(prefix="/api/complaint", tags=["complaint"])


def check_duplicate(batch_number: str, customer_name: str) -> bool:
    """Check if a complaint with same batch and customer already exists."""
    if not batch_number or not customer_name:
        return False
    
    with SessionLocal() as db:
        existing = db.query(Complaint).filter(
            Complaint.batch_number == batch_number,
            Complaint.customer_name == customer_name
        ).first()
        return existing is not None


@router.post("/process", response_model=ProcessComplaintResponse)
async def process_complaint(
    raw_text: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
):
    """
    Accepts either free text or PDF file upload.
    Runs LangGraph intake workflow with duplicate detection and error handling.
    """
    print("🔥 [DEBUG] /process endpoint HIT!", file=sys.stderr, flush=True)
    
    if not raw_text and not file:
        raise HTTPException(status_code=400, detail="Provide either raw_text or a file.")

    input_text = raw_text or ""

    if file and file.filename:
        if not file.filename.lower().endswith(SUPPORTED_EXTENSIONS):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}.",
            )
        file_bytes = await file.read()
        try:
            doc_text = extract_text(file.filename, file_bytes)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        input_text = f"{input_text}\n\n{doc_text}".strip()

    initial_state = {
        "raw_input": input_text,
        "extracted_data": {},
        "chat_history": [],
        "risk_assessment": {},
        "is_complete": False,
        "status": "pending",
        "last_message": "",
        "duplicate_warning": "",
        "complaint_summary": "",
        "root_cause_recommendation": "",
        "capa_recommendation": "",
    }

    try:
        print("🚀 [DEBUG] Invoking LangGraph intake_graph...", file=sys.stderr, flush=True)
        result_state = intake_graph.invoke(initial_state)
        print("✅ [DEBUG] LangGraph completed successfully!", file=sys.stderr, flush=True)
        
        # Check for duplicates
        extracted = result_state.get("extracted_data", {})
        batch = extracted.get("batch_number", "")
        customer = extracted.get("customer_name", "")
        
        if check_duplicate(batch, customer):
            result_state["duplicate_warning"] = "⚠️ Potential Duplicate Complaint Detected: A complaint with this batch number and customer already exists in the QMS ledger."
            print("️ [DEBUG] Duplicate detected!", file=sys.stderr, flush=True)
        
    except Exception as e:
        print(f"❌ [DEBUG] LANGGRAPH FAILED: {str(e)}", file=sys.stderr, flush=True)
        print(traceback.format_exc(), file=sys.stderr, flush=True)
        
        # Graceful error handling
        error_msg = str(e)
        if "I'm sorry" in error_msg or "can't help" in error_msg.lower() or "Failed to generate JSON" in error_msg:
            result_state = {
                **initial_state,
                "last_message": "️ I wasn't able to process that message. Please rephrase using professional, factual language so I can assist you with your complaint.",
                "status": "error",
                "is_complete": False,
            }
        else:
            result_state = {
                **initial_state,
                "last_message": f"⚠️ Error processing complaint: {str(e)[:100]}",
                "status": "error",
                "is_complete": False,
            }

    return ProcessComplaintResponse(
        extracted_data=result_state.get("extracted_data", {}),
        risk_assessment=result_state.get("risk_assessment", {}),
        is_complete=result_state.get("is_complete", False),
        status=result_state.get("status", "pending"),
        chat_history=result_state.get("chat_history", []),
        duplicate_warning=result_state.get("duplicate_warning", ""),
        complaint_summary=result_state.get("complaint_summary", ""),
        root_cause_recommendation=result_state.get("root_cause_recommendation", ""),
        capa_recommendation=result_state.get("capa_recommendation", ""),
    )


@router.post("/chat", response_model=ChatResponse)
async def chat_with_copilot(payload: ChatRequest):
    """
    Accepts a follow-up chat instruction plus the current graph state.
    Routes through correction_node -> risk_assessment_node -> completeness_checker.
    """
    state = dict(payload.state)
    state["last_message"] = payload.message

    try:
        result_state = correction_graph.invoke(state)
        ai_message = result_state.pop("_last_ai_message", "Updated.")
    except Exception as e:
        error_msg = str(e)
        if "I'm sorry" in error_msg or "can't help" in error_msg.lower():
            ai_message = "⚠️ I wasn't able to process that message. Please rephrase using professional, factual language."
        else:
            ai_message = f"⚠️ Error: {str(e)[:100]}"
        result_state = state

    return ChatResponse(
        extracted_data=result_state.get("extracted_data", {}),
        risk_assessment=result_state.get("risk_assessment", {}),
        is_complete=result_state.get("is_complete", False),
        status=result_state.get("status", "pending"),
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
        complaint_date=data.get("complaint_date"),
        priority=data.get("priority"),
        complaint_description=data.get("complaint_description"),
        complaint_summary=payload.complaint_summary if hasattr(payload, 'complaint_summary') else None,
        root_cause_recommendation=payload.root_cause_recommendation if hasattr(payload, 'root_cause_recommendation') else None,
        capa_recommendation=payload.capa_recommendation if hasattr(payload, 'capa_recommendation') else None,
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