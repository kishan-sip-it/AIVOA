import { createSlice } from "@reduxjs/toolkit";
import { EMPTY_EXTRACTED_DATA, EMPTY_RISK_ASSESSMENT, isComplaintComplete } from "../lib/complaintFields";

const initialState = {
  rawInput: "",
  extractedData: { ...EMPTY_EXTRACTED_DATA },
  riskAssessment: { ...EMPTY_RISK_ASSESSMENT },
  complaintSummary: null,
  rootCauseRecommendation: null,
  capaRecommendation: null,
  duplicateMatches: [],
  status: "pending", // "pending" | "ready" — mirrors backend ComplaintGraphState.status
  isComplete: false,
  highlightedFields: [], // field names to flash green for 2s (AI-driven updates)
  updateToken: null, // bumped on every AI update so the highlight-clear effect re-fires
  isProcessing: false, // true while /process or /chat is in flight
  isCommitting: false,
  qmsReference: null,
  error: null,
};

const complaintSlice = createSlice({
  name: "complaint",
  initialState,
  reducers: {
    setRawInput(state, action) {
      state.rawInput = action.payload;
    },

    // Manual edit by the user typing directly into a form field.
    updateField(state, action) {
      const { field, value } = action.payload;
      state.extractedData[field] = value;
      state.isComplete = isComplaintComplete(state.extractedData);
      state.status = state.isComplete ? "ready" : "pending";
    },

    // Applied after a successful /process or /chat call — merges the
    // backend's extracted_data/risk_assessment into state and flags which
    // fields actually changed so the UI can highlight them green.
    applyWorkflowResult(state, action) {
      const {
        extracted_data,
        risk_assessment,
        is_complete,
        status,
        complaint_summary,
        root_cause_recommendation,
        capa_recommendation,
        duplicate_matches,
      } = action.payload;
      const changed = [];

      Object.entries(extracted_data || {}).forEach(([field, value]) => {
        if (value !== undefined && value !== null && state.extractedData[field] !== value) {
          changed.push(field);
        }
      });

      state.extractedData = { ...state.extractedData, ...extracted_data };
      state.riskAssessment = { ...state.riskAssessment, ...risk_assessment };
      state.complaintSummary = complaint_summary ?? state.complaintSummary;
      state.rootCauseRecommendation = root_cause_recommendation ?? state.rootCauseRecommendation;
      state.capaRecommendation = capa_recommendation ?? state.capaRecommendation;
      state.duplicateMatches = duplicate_matches ?? state.duplicateMatches;
      state.isComplete = Boolean(is_complete);
      state.status = status || (state.isComplete ? "ready" : "pending");
      state.highlightedFields = changed;
      state.updateToken = Date.now();
    },

    clearHighlights(state) {
      state.highlightedFields = [];
    },

    setProcessing(state, action) {
      state.isProcessing = action.payload;
    },

    setCommitting(state, action) {
      state.isCommitting = action.payload;
    },

    setCommitSuccess(state, action) {
      state.qmsReference = action.payload;
      state.error = null;
    },

    setComplaintError(state, action) {
      state.error = action.payload;
    },

    resetComplaint() {
      return initialState;
    },
  },
});

export const {
  setRawInput,
  updateField,
  applyWorkflowResult,
  clearHighlights,
  setProcessing,
  setCommitting,
  setCommitSuccess,
  setComplaintError,
  resetComplaint,
} = complaintSlice.actions;

export default complaintSlice.reducer;