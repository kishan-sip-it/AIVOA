"""
graph.py
--------
LangGraph stateful workflow for the AIVOA Copilot.
"""

import os
import json
from dotenv import load_dotenv
load_dotenv()

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END

from app.schemas import (
    ComplaintGraphState,
    ExtractedComplaintData,
    RiskAssessmentOutput,
    CorrectionOutput,
    MANDATORY_FIELDS,
)

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

# FIX: these were commented out — parse_input_node / risk_assessment_node /
# correction_node all reference these names directly, so leaving them
# commented caused a NameError on every single request (the actual cause
# of your 500s).
# FIX: default method="function_calling" (tool-calling) was flaky on
# openai/gpt-oss-20b — it sometimes omitted required fields entirely
# ("Tool call validation failed: missing properties") or refused to call
# the tool at all when the input had little extractable info ("Tool choice
# is required, but model did not call a tool"). json_mode is more reliable
# here: the model just has to emit a JSON object matching the schema,
# with no separate "should I call this tool at all" decision to get wrong.
extraction_llm = llm.with_structured_output(ExtractedComplaintData, method="json_mode")
risk_llm = llm.with_structured_output(RiskAssessmentOutput, method="json_mode")
correction_llm = llm.with_structured_output(CorrectionOutput, method="json_mode")


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
    result = chain.invoke({"raw_input": state["raw_input"]})
    data = _to_dict(result)

    extracted = dict(state.get("extracted_data") or {})
    for field, value in data.items():
        if value is not None:
            extracted[field] = value

    state["extracted_data"] = extracted
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
    result = chain.invoke({"data": json.dumps(extracted, indent=2)})

    state["risk_assessment"] = _to_dict(result)
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
    result = chain.invoke({
        "data": json.dumps(extracted, indent=2),
        "message": message,
    })
    data = _to_dict(result)
    updated_fields = data.get("updated_fields", {}) or {}
    confirmation_message = data.get("confirmation_message") or (
        f"Updated {', '.join(updated_fields.keys())}."
        if updated_fields
        else "I'm the AIVOA intake copilot — happy to help fill in or correct any complaint fields. Let me know what you'd like to add or change."
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
    graph.add_node("risk_assessment_node", risk_assessment_node)
    graph.add_node("completeness_checker", completeness_checker)

    graph.set_entry_point("parse_input_node")
    graph.add_edge("parse_input_node", "risk_assessment_node")
    graph.add_edge("risk_assessment_node", "completeness_checker")
    graph.add_edge("completeness_checker", END)
    return graph.compile()


def _build_correction_graph():
    graph = StateGraph(ComplaintGraphState)
    graph.add_node("correction_node", correction_node)
    graph.add_node("risk_assessment_node", risk_assessment_node)
    graph.add_node("completeness_checker", completeness_checker)

    graph.set_entry_point("correction_node")
    graph.add_edge("correction_node", "risk_assessment_node")
    graph.add_edge("risk_assessment_node", "completeness_checker")
    graph.add_edge("completeness_checker", END)
    return graph.compile()


intake_graph = _build_intake_graph()
correction_graph = _build_correction_graph()