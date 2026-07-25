// All calls to the AIVOA FastAPI backend. Base URL comes from
// VITE_API_BASE_URL (see .env.example) so it's easy to point at a
// different host/port without touching code.

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

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

/**
 * POST /api/complaint/process — new complaint intake, either free text or a
 * PDF file (multipart/form-data, matching the backend's Form/File params).
 */
export async function processComplaint({ rawText, file }) {
  const formData = new FormData();
  if (rawText) formData.append("raw_text", rawText);
  if (file) formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/complaint/process`, {
    method: "POST",
    body: formData,
  });
  return handle(response);
}

/**
 * POST /api/complaint/chat — a follow-up correction/question. `state` must
 * match the backend's ComplaintGraphState shape exactly.
 */
export async function chatCorrection({ message, state }) {
  const response = await fetch(`${API_BASE_URL}/api/complaint/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, state }),
  });
  return handle(response);
}

/**
 * POST /api/complaint/commit — persist the finalized complaint to Postgres.
 */
export async function commitComplaint({ extracted_data, risk_assessment, raw_input, chat_history }) {
  const response = await fetch(`${API_BASE_URL}/api/complaint/commit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ extracted_data, risk_assessment, raw_input, chat_history }),
  });
  return handle(response);
}
