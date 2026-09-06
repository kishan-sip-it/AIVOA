// All calls to the AIVOA FastAPI backend. Base URL comes from
// VITE_API_BASE_URL (see .env.example) so it's easy to point at a
// different host/port without touching code.

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

// Keep a lightweight in-memory copy of the current workflow state. This is
// especially useful when the backend needs to handle a follow-up even if the
// frontend has not extracted any fields yet; Redux can still update normally,
// while this module guarantees the next message reaches the intent-aware
// follow-up endpoint instead of restarting intake.
let conversationStarted = false;
let conversationState = null;

function emptyWorkflowState() {
  return {
    raw_input: "",
    extracted_data: {},
    chat_history: [],
    risk_assessment: {},
    is_complete: false,
    status: "pending",
    last_message: "",
    complaint_summary: null,
    root_cause_recommendation: null,
    capa_recommendation: null,
    duplicate_matches: [],
    notice: null,
  };
}

function rememberWorkflowState(result) {
  conversationStarted = true;
  conversationState = {
    ...emptyWorkflowState(),
    raw_input: result?.raw_input || conversationState?.raw_input || "",
    extracted_data: result?.extracted_data || {},
    chat_history: result?.chat_history || [],
    risk_assessment: result?.risk_assessment || {},
    is_complete: Boolean(result?.is_complete),
    status: result?.status || "pending",
    complaint_summary: result?.complaint_summary ?? null,
    root_cause_recommendation: result?.root_cause_recommendation ?? null,
    capa_recommendation: result?.capa_recommendation ?? null,
    duplicate_matches: result?.duplicate_matches || [],
    notice: result?.notice ?? null,
  };
}

async function handle(response) {
  if (!response.ok) {
    let detail = "Request failed.";
    try {
      const body = await response.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      detail = await response.text();
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return response.json();
}

async function postFollowUp(message, state = conversationState || emptyWorkflowState()) {
  const response = await fetch(`${API_BASE_URL}/api/complaint/follow-up`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, state }),
  });
  const result = await handle(response);
  rememberWorkflowState(result);
  return result;
}

function isConciseFieldEdit(text) {
  return /^(add|change|update|set|correct|replace|edit|modify)\s+name\s+(to|as)\s+.+$/i.test(text || "");
}

function isCasualOnlyMessage(text) {
  return /^(hi|hello|hey|how are you|how's your day|how is your day|good morning|good evening|thanks|thank you)\s*[!?.,]*$/i.test(
    (text || "").trim()
  );
}

/**
 * POST /api/complaint/process — initial complaint intake or document upload.
 * If a text conversation has already started, or the first message is a
 * concise field edit/casual message, route through the intent-aware follow-up
 * endpoint so the request is not forced through extraction again.
 */
export async function processComplaint({ rawText, file }) {
  const text = (rawText || "").trim();

  if (text && conversationStarted) {
    return postFollowUp(text);
  }

  // A concise edit such as "add name to Kishan" should work even when the
  // user starts from a fresh page with an otherwise empty complaint state.
  if (text && (isConciseFieldEdit(text) || isCasualOnlyMessage(text))) {
    return postFollowUp(text, conversationState || emptyWorkflowState());
  }

  const formData = new FormData();
  if (rawText) formData.append("raw_text", rawText);
  if (file) formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/complaint/process`, {
    method: "POST",
    body: formData,
  });
  const result = await handle(response);
  rememberWorkflowState(result);
  return result;
}

/**
 * POST /api/complaint/follow-up — intent-aware follow-up chat.
 * Field edits use the LangGraph correction workflow; questions, application
 * help and casual conversation use natural-language response generation.
 */
export async function chatCorrection({ message, state }) {
  const response = await fetch(`${API_BASE_URL}/api/complaint/follow-up`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, state }),
  });
  const result = await handle(response);
  rememberWorkflowState(result);
  return result;
}

/**
 * POST /api/complaint/commit — persist the finalized complaint to Postgres.
 */
export async function commitComplaint({
  extracted_data,
  risk_assessment,
  raw_input,
  chat_history,
  complaint_summary,
  root_cause_recommendation,
  capa_recommendation,
}) {
  const response = await fetch(`${API_BASE_URL}/api/complaint/commit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      extracted_data,
      risk_assessment,
      raw_input,
      chat_history,
      complaint_summary,
      root_cause_recommendation,
      capa_recommendation,
    }),
  });
  return handle(response);
}
