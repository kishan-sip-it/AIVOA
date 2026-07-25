"""
schemas.py
----------
Pydantic models used for:
  1. Structured LLM output (crucial for reliable JSON parsing from gemma2-9b-it
     via `with_structured_output`).
  2. FastAPI request/response validation.
  3. The typed LangGraph state definition.

Field-level descriptions are intentionally verbose — they double as the
extraction instructions the LLM sees when we bind this schema with
`with_structured_output`, which meaningfully improves gemma2-9b-it's
extraction accuracy.
"""

from typing import Optional, List, Literal, TypedDict
from pydantic import BaseModel, Field

MANDATORY_FIELDS = [
    "complaint_source",
    "customer_name",
    "product_name",
    "batch_number",
    "originating_site_block",
    "complaint_category",
    "complaint_description",
]

COMPLAINT_SOURCES = ["Physician", "Pharmacist", "Patient", "Distributor", "Regulatory Body", "Sales Rep", "Other"]
SITE_BLOCKS = ["Block A - Oral Solids", "Block B - Sterile/Injectables", "Block C - Packaging", "Block D - Warehouse/NPM", "Block E - R&D Pilot"]
COMPLAINT_CATEGORIES = ["Product Quality Defect", "Packaging Defect", "Adverse Event/Reaction", "Counterfeit Suspected", "Labeling Error", "No Effect/Efficacy Complaint", "Foreign Particulate", "Other"]
PRIORITY_LEVELS = ["Low", "Medium", "High", "Urgent"]


# ---------------------------------------------------------------------------
# 1. Structured LLM extraction output
# ---------------------------------------------------------------------------

class ExtractedComplaintData(BaseModel):
    """Structured extraction target for parse_input_node. All fields optional
    since raw input (voice transcript, email, PDF) rarely contains every field."""

    complaint_source: Optional[str] = Field(
        default=None,
        description=f"Who raised the complaint. Must be one of: {COMPLAINT_SOURCES}. Infer from context if not explicit."
    )
    customer_name: Optional[str] = Field(default=None, description="Full name of the customer, physician, or reporting party.")
    product_name: Optional[str] = Field(default=None, description="Name of the pharmaceutical product involved.")
    product_strength: Optional[str] = Field(default=None, description="Strength or grade of the product, e.g. '500mg', '10mg/ml'.")
    batch_number: Optional[str] = Field(default=None, description="Batch or lot number referenced in the complaint.")
    affected_quantity: Optional[str] = Field(default=None, description="Quantity of units affected, e.g. '3 tablets', '1 vial'.")
    manufacturing_date: Optional[str] = Field(default=None, description="Manufacturing date in YYYY-MM-DD if stated or inferable.")
    expiry_date: Optional[str] = Field(default=None, description="Expiry date in YYYY-MM-DD if stated or inferable.")
    originating_site_block: Optional[str] = Field(
        default=None,
        description=f"Manufacturing site/block believed responsible. Must be one of: {SITE_BLOCKS}."
    )
    impacted_npm: Optional[str] = Field(default=None, description="Any non-product materials impacted, e.g. packaging insert, vial stopper, blister foil.")
    complaint_category: Optional[str] = Field(
        default=None,
        description=f"Category of the complaint. Must be one of: {COMPLAINT_CATEGORIES}."
    )
    complaint_date: Optional[str] = Field(default=None, description="Date the complaint was reported/filed, in YYYY-MM-DD if stated or inferable (defaults to today if the input implies 'just now'/'today').")
    priority: Optional[str] = Field(
        default=None,
        description=f"Handling priority for the QA team. Must be one of: {PRIORITY_LEVELS}. Infer from severity/urgency language in the complaint (e.g. patient harm or widespread batch impact -> Urgent/High)."
    )
    complaint_description: Optional[str] = Field(default=None, description="A clear, concise narrative summary of the complaint in professional QMS language.")


class RiskAssessmentOutput(BaseModel):
    """Structured output for risk_assessment_node."""

    severity_suggested: Literal["Critical", "Major", "Minor"] = Field(
        description="Severity classification. Critical = patient safety risk (e.g. adverse event, sterility breach, wrong active ingredient). Major = product does not meet quality attributes but no immediate safety risk (e.g. dissolution failure, mislabeling). Minor = cosmetic or non-functional defect."
    )
    suggested_next_action: str = Field(
        description="A concise, actionable next step for the QA team, e.g. 'Initiate CAPA and quarantine remaining batch stock' or 'Log for trend monitoring, no immediate action required.'"
    )
    initial_risk_assessment: str = Field(
        description="A 2-4 sentence professional risk narrative explaining the reasoning behind the severity rating, referencing patient safety, batch impact, and regulatory reporting obligations (e.g. potential need for a Field Alert Report)."
    )


class CorrectionOutput(BaseModel):
    """Structured output for correction_node — the LLM decides which fields to
    change based on a natural-language chat instruction."""

    updated_fields: dict = Field(
        default_factory=dict,
        description="Dictionary of only the field names (matching ExtractedComplaintData field names) and their new values that should be changed, based on the user's instruction. Use an empty object {} if the instruction is just a question and nothing needs to change."
    )
    confirmation_message: str = Field(
        description="A short, friendly confirmation message to show the user in chat, e.g. 'Updated batch number to XYZ-123.'"
    )


# ---------------------------------------------------------------------------
# 2. LangGraph state
# ---------------------------------------------------------------------------

class ChatMessage(TypedDict):
    role: Literal["user", "ai"]
    content: str


class ComplaintGraphState(TypedDict):
    raw_input: str
    extracted_data: dict
    chat_history: List[ChatMessage]
    risk_assessment: dict
    is_complete: bool
    status: str          # "pending" | "ready"
    last_message: str    # newest incoming chat message routed to correction_node


# ---------------------------------------------------------------------------
# 3. API request / response bodies
# ---------------------------------------------------------------------------

class ProcessComplaintRequest(BaseModel):
    raw_text: Optional[str] = Field(default=None, description="Free-text complaint narrative (email, call transcript, etc.)")
    # NOTE: file upload is handled via multipart/form-data in the endpoint,
    # not through this JSON body — see main.py.


class ChatRequest(BaseModel):
    message: str
    state: ComplaintGraphState


class ProcessComplaintResponse(BaseModel):
    extracted_data: dict
    risk_assessment: dict
    is_complete: bool
    status: str
    chat_history: List[ChatMessage]


class ChatResponse(BaseModel):
    extracted_data: dict
    risk_assessment: dict
    is_complete: bool
    status: str
    chat_history: List[ChatMessage]
    ai_message: str


class CommitComplaintRequest(BaseModel):
    extracted_data: dict
    risk_assessment: dict
    raw_input: Optional[str] = None
    chat_history: Optional[List[ChatMessage]] = None


class CommitComplaintResponse(BaseModel):
    id: str
    status: str
    message: str