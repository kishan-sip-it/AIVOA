"""
graph.py
--------
LangGraph stateful workflow for the AIVOA Copilot.

Intake graph:
  parse_input_node -> duplicate_check_node -> risk_assessment_node
  -> enrichment_node -> completeness_checker -> END

Correction graph:
  correction_node -> duplicate_check_node -> risk_assessment_node
  -> enrichment_node -> completeness_checker -> END
"""

import os
import json
import logging
from dotenv import load_dotenv
load_dotenv()

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from sqlalchemy import or_

from app.schemas import (
    ComplaintGraphState,
    ExtractedComplaintData,
    RiskAssessmentOutput,
    CorrectionOutput,
    EnrichmentOutput,
    MANDATORY_FIELDS,
)

logger = logging.getLogger("uvicorn.error")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY not found in environment. Check that your .env file "
        "exists in the project root and contains GROQ_API_KEY=gsk_..."
    )

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0.1,
    api_key=GROQ_API_KEY,
)

extraction_llm = llm.with_structured_output(ExtractedComplaintData, method="json_mode")
risk_llm = llm.with_structured_output(RiskAssessmentOutput, method="json_mode")
correction_llm = llm.with_structured_output(CorrectionOutput, method="json_mode")
enrichment_llm = llm.with_structured_output(EnrichmentOutput, method="json_mode")

# Shown to the user whenever an LLM call fails or refuses to generate valid
# output — e.g. the model's own safety filter declines a request, or it
# otherwise can't produce valid JSON. Instead of leaking a raw
# groq.BadRequestError / stack trace to the UI, every node that calls the
# LLM catches the failure and falls back to this message.
GENERATION_FAILURE_NOTICE = (
    "I wasn't able to process that message. This usually happens when the "
    "input can't be converted into a structured QMS record — for example if "
    "it contains language unrelated to a product complaint. Please rephrase "
    "using professional, factual language describing the product, batch, "
    "and issue, and I'll extract the details."
)


def _to_dict(result) -> dict:
    """ChatGroq.with_structured_output is currently in beta and, depending on
    the langchain-groq version, can return either the Pydantic model
    instance OR a plain dict for the same call. Normalize both cases here
    instead of assuming .model_dump() always exists."""
    if hasattr(result, "model_dump"):
        return result.model_dump()
    if isinstance(result, dict):
        return result
    raise TypeError(f"Unexpected structured output type: {type(result)}")


def _safe_invoke(chain, inputs: dict, node_name: str):
    """Runs an LLM chain and returns (result_dict, None) on success, or
    (None, error_message) on failure — covering both API-level refusals
    (e.g. Groq's safety filter declining a request) and malformed output.
    Callers use this to degrade gracefully instead of propagating a raw
    exception up to a 500 response."""
    try:
        result = chain.invoke(inputs)
        return _to_dict(result), None
    except Exception as exc:
        logger.error(f"[{node_name}] LLM call failed: {type(exc).__name__}: {exc}")
        return None, GENERATION_FAILURE_NOTICE


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def parse_input_node(state: ComplaintGraphState) -> ComplaintGraphState:
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a pharmaceutical quality assurance intake specialist. "
         "Extract complaint details from the input into a JSON object with "
         f"exactly these keys: {list(ExtractedComplaintData.model_fields.keys())}. "
         "Only populate fields you have reasonable evidence for; set others to null. "
         "Write complaint_description as a clean, professional QMS-style narrative, "
         "not a verbatim copy of casual input. "
         "Respond with ONLY the JSON object, no other text."),
        ("human", "{raw_input}"),
    ])

    chain = prompt | extraction_llm
    data, error = _safe_invoke(chain, {"raw_input": state["raw_input"]}, "parse_input_node")

    if error:
        state["notice"] = error
        return state

    extracted = dict(state.get("extracted_data") or {})
    for field, value in data.items():
        if value is not None:
            extracted[field] = value

    state["extracted_data"] = extracted
    return state


def duplicate_check_node(state: ComplaintGraphState) -> ComplaintGraphState:
    """Bonus feature: Duplicate Complaint Detection. Looks in the committed
    QMS ledger for existing complaints on the same batch, or the same
    product + customer, and surfaces them so the analyst can check before
    logging a possible duplicate."""
    extracted = state.get("extracted_data") or {}
    batch_number = extracted.get("batch_number")
    product_name = extracted.get("product_name")
    customer_name = extracted.get("customer_name")

    logger.info(
        f"[duplicate_check_node] checking batch_number={batch_number!r} "
        f"product_name={product_name!r} customer_name={customer_name!r}"
    )

    if not batch_number and not (product_name and customer_name):
        logger.info("[duplicate_check_node] skipped — not enough data to check yet")
        state["duplicate_matches"] = []
        return state

    try:
        # Imported lazily to avoid a circular import (database.py doesn't
        # import graph.py, but this keeps the dependency one-directional
        # and obvious at the call site).
        from app.database import SessionLocal
        from app.models import Complaint

        db = SessionLocal()
        try:
            filters = []
            if batch_number:
                filters.append(Complaint.batch_number == batch_number)
            if product_name and customer_name:
                filters.append((Complaint.product_name == product_name) & (Complaint.customer_name == customer_name))

            matches = db.query(Complaint).filter(or_(*filters)).order_by(Complaint.created_at.desc()).limit(5).all()
            logger.info(f"[duplicate_check_node] query returned {len(matches)} match(es)")

            state["duplicate_matches"] = [
                {
                    "id": str(m.id),
                    "product_name": m.product_name,
                    "batch_number": m.batch_number,
                    "customer_name": m.customer_name,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in matches
            ]
        finally:
            db.close()
    except Exception as exc:
        # If this fires, it'll be logged clearly here — e.g. a missing
        # column from a DB migration that wasn't applied would show up as a
        # ProgrammingError right in this line, instead of silently vanishing.
        logger.error(f"[duplicate_check_node] DB lookup failed: {type(exc).__name__}: {exc}")
        state["duplicate_matches"] = []

    return state


def risk_assessment_node(state: ComplaintGraphState) -> ComplaintGraphState:
    extracted = state.get("extracted_data") or {}

    if not extracted.get("product_name") or not extracted.get("complaint_description"):
        state["risk_assessment"] = {
            "severity_suggested": None,
            "suggested_next_action": None,
            "initial_risk_assessment": None,
        }
        return state

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a senior pharmacovigilance and quality risk assessor. "
         "Based on the structured complaint data below, respond with a JSON "
         "object with exactly these keys: severity_suggested (one of "
         "\"Critical\", \"Major\", \"Minor\"), suggested_next_action (string), "
         "initial_risk_assessment (string, 2-4 sentences). Consider patient "
         "safety, batch-wide impact, and regulatory reporting obligations. "
         "Respond with ONLY the JSON object, no other text."),
        ("human", "Complaint data:\n{data}"),
    ])

    chain = prompt | risk_llm
    data, error = _safe_invoke(chain, {"data": json.dumps(extracted, indent=2)}, "risk_assessment_node")

    if error:
        state["notice"] = state.get("notice") or error
        state["risk_assessment"] = {
            "severity_suggested": None,
            "suggested_next_action": None,
            "initial_risk_assessment": None,
        }
        return state

    state["risk_assessment"] = data
    return state


def enrichment_node(state: ComplaintGraphState) -> ComplaintGraphState:
    """Bonus features: Complaint Summary + Root Cause Recommendation + CAPA
    Recommendation, generated together from the same context in one call."""
    extracted = state.get("extracted_data") or {}

    if not extracted.get("product_name") or not extracted.get("complaint_description"):
        state["complaint_summary"] = None
        state["root_cause_recommendation"] = None
        state["capa_recommendation"] = None
        return state

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a QA analyst assistant. Based on the complaint data and "
         "risk assessment below, respond with a JSON object with exactly "
         "these keys: complaint_summary, root_cause_recommendation, "
         "capa_recommendation — all strings. Respond with ONLY the JSON "
         "object, no other text."),
        ("human", "Complaint data:\n{data}\n\nRisk assessment:\n{risk}"),
    ])

    chain = prompt | enrichment_llm
    data, error = _safe_invoke(
        chain,
        {
            "data": json.dumps(extracted, indent=2),
            "risk": json.dumps(state.get("risk_assessment") or {}, indent=2),
        },
        "enrichment_node",
    )

    if error:
        state["notice"] = state.get("notice") or error
        state["complaint_summary"] = None
        state["root_cause_recommendation"] = None
        state["capa_recommendation"] = None
        return state

    state["complaint_summary"] = data.get("complaint_summary")
    state["root_cause_recommendation"] = data.get("root_cause_recommendation")
    state["capa_recommendation"] = data.get("capa_recommendation")
    return state


def correction_node(state: ComplaintGraphState) -> ComplaintGraphState:
    message = state.get("last_message", "")
    extracted = state.get("extracted_data") or {}

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are the AIVOA Copilot assisting a QA analyst editing a complaint "
         "record. The current extracted data is shown below. The user has sent "
         "a follow-up instruction. Respond with a JSON object with exactly "
         "these keys: updated_fields (an object containing ONLY the field(s) "
         "that need to change and their new values, using ONLY these exact "
         f"field names: {list(ExtractedComplaintData.model_fields.keys())} — "
         "use an empty object {{}} if nothing needs to change), and "
         "confirmation_message (a short, friendly string reply for the user — "
         "this field is REQUIRED and must never be empty). "
         "If the instruction is a correction (e.g. 'change batch number to X'), "
         "set updated_fields accordingly and confirm the change in confirmation_message. "
         "If the instruction is a question about the complaint, set updated_fields "
         "to {{}} and answer it in confirmation_message. "
         "If the instruction is unrelated small talk or a greeting (e.g. 'hi', "
         "'how are you'), set updated_fields to {{}} and reply warmly and briefly "
         "in confirmation_message, then steer back to the complaint task — e.g. "
         "'Doing well, thanks! Let me know if any complaint details need adding or correcting.' "
         "Respond with ONLY the JSON object, no other text."),
        ("human", "Current data:\n{data}\n\nUser instruction: {message}"),
    ])

    chain = prompt | correction_llm
    data, error = _safe_invoke(
        chain,
        {"data": json.dumps(extracted, indent=2), "message": message},
        "correction_node",
    )

    if error:
        confirmation_message = error
        updated_fields = {}
        state["notice"] = error
    else:
        updated_fields = data.get("updated_fields", {}) or {}

        if updated_fields:
            # FIX: don't trust the model's own confirmation_message text here
            # — in testing, gpt-oss-20b frequently collapsed it to a lazy,
            # context-free "Updated." even for a fully-specified correction.
            # Build the confirmation deterministically from what actually
            # changed instead, so it's always accurate and specific.
            changes = ", ".join(f"{k.replace('_', ' ')} to '{v}'" for k, v in updated_fields.items())
            confirmation_message = f"Updated {changes}."
        else:
            # Nothing changed — this is chit-chat, a question, or an
            # off-topic/refused message. The model's own reply is fine here
            # *if* it's substantive; filter out lazy one-word junk like
            # "Updated." or "Done." that doesn't actually answer anything.
            model_reply = (data.get("confirmation_message") or "").strip()
            is_junk = len(model_reply) < 10 or model_reply.lower().rstrip(".") in {"updated", "done", "ok", "sure"}
            confirmation_message = model_reply if model_reply and not is_junk else (
                "I'm the AIVOA intake copilot — happy to help fill in or correct any complaint fields. "
                "Let me know what you'd like to add or change."
            )

    extracted.update({k: v for k, v in updated_fields.items() if v is not None})
    state["extracted_data"] = extracted

    history = list(state.get("chat_history") or [])
    history.append({"role": "user", "content": message})
    history.append({"role": "ai", "content": confirmation_message})
    state["chat_history"] = history
    state["_last_ai_message"] = confirmation_message
    return state


def completeness_checker(state: ComplaintGraphState) -> ComplaintGraphState:
    extracted = state.get("extracted_data") or {}
    missing = [f for f in MANDATORY_FIELDS if not extracted.get(f)]

    is_complete = len(missing) == 0
    state["is_complete"] = is_complete
    state["status"] = "ready" if is_complete else "pending"
    return state


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def _build_intake_graph():
    graph = StateGraph(ComplaintGraphState)
    graph.add_node("parse_input_node", parse_input_node)
    graph.add_node("duplicate_check_node", duplicate_check_node)
    graph.add_node("risk_assessment_node", risk_assessment_node)
    graph.add_node("enrichment_node", enrichment_node)
    graph.add_node("completeness_checker", completeness_checker)

    graph.set_entry_point("parse_input_node")
    graph.add_edge("parse_input_node", "duplicate_check_node")
    graph.add_edge("duplicate_check_node", "risk_assessment_node")
    graph.add_edge("risk_assessment_node", "enrichment_node")
    graph.add_edge("enrichment_node", "completeness_checker")
    graph.add_edge("completeness_checker", END)
    return graph.compile()


def _build_correction_graph():
    graph = StateGraph(ComplaintGraphState)
    graph.add_node("correction_node", correction_node)
    graph.add_node("duplicate_check_node", duplicate_check_node)
    graph.add_node("risk_assessment_node", risk_assessment_node)
    graph.add_node("enrichment_node", enrichment_node)
    graph.add_node("completeness_checker", completeness_checker)

    graph.set_entry_point("correction_node")
    graph.add_edge("correction_node", "duplicate_check_node")
    graph.add_edge("duplicate_check_node", "risk_assessment_node")
    graph.add_edge("risk_assessment_node", "enrichment_node")
    graph.add_edge("enrichment_node", "completeness_checker")
    graph.add_edge("completeness_checker", END)
    return graph.compile()


intake_graph = _build_intake_graph()
correction_graph = _build_correction_graph()

print(
    "[graph.py] Loaded. Correction graph nodes: "
    "correction_node -> duplicate_check_node -> risk_assessment_node -> "
    "enrichment_node -> completeness_checker",
    flush=True,
)