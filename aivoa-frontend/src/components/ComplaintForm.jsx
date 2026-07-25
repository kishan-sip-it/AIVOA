import { useEffect } from "react";
import { AlertTriangle, ArrowRight, CheckCircle2, ClipboardCheck, LockKeyhole, RotateCcw, Sparkles } from "lucide-react";
import { useDispatch, useSelector } from "react-redux";
import {
  clearHighlights,
  resetComplaint,
  setCommitSuccess,
  setCommitting,
  setComplaintError,
  updateField,
} from "../store/complaintSlice";
import { addMessage, resetChat } from "../store/chatSlice";
import { commitComplaint } from "../api/complaintApi";
import { COMPLAINT_SOURCES, SITE_BLOCKS, COMPLAINT_CATEGORIES, PRIORITY_LEVELS } from "../lib/complaintFields";

// FIX: field-level building blocks must live at MODULE scope, not be
// redefined inside ComplaintForm's render body. Defining a component
// function inside another component means React sees a brand-new function
// reference on every re-render (every keystroke), treats it as a different
// component type, and unmounts/remounts the underlying <input> — which is
// exactly what was causing focus to drop after a single character. Keeping
// them here, taking value/highlighted/onChange as plain props, keeps their
// identity stable across renders.

const fieldBaseClass = (highlighted) =>
  `mt-1.5 block w-full rounded-xl border px-3.5 py-2.5 text-sm text-slate-800 outline-none transition duration-500 placeholder:text-slate-300 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100 ${
    highlighted ? "border-emerald-300 bg-emerald-50 ring-4 ring-emerald-100" : "border-slate-200 bg-white"
  }`;

function SectionTitle({ index, title }) {
  return (
    <div className="mb-4 flex items-center gap-2">
      <span className="grid h-5 w-5 place-items-center rounded-md bg-slate-100 text-[10px] font-bold text-slate-500">
        {index}
      </span>
      <h3 className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">{title}</h3>
    </div>
  );
}

function TextField({ label, placeholder, type = "text", required, value, highlighted, onChange }) {
  return (
    <label className="block">
      <span className="text-xs font-semibold text-slate-600">
        {label}
        {required && <span className="ml-0.5 text-rose-500">*</span>}
      </span>
      <input
        type={type}
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={fieldBaseClass(highlighted)}
      />
    </label>
  );
}

// FIX (dropdown showing blank after an AI update): a native <select> only
// shows a value if it exactly matches one of its <option> values. If the
// AI (or a manual edit) sets a value that isn't byte-for-byte identical to
// one of our predefined options, the <select> silently falls back to blank
// — even though the Redux value did update (hence the green highlight
// firing with no visible selection change). Appending the current value as
// an extra option when it isn't already in the list guarantees the
// dropdown always visibly reflects whatever value is actually stored.
function SelectField({ label, required, value, highlighted, onChange, options, placeholder }) {
  const hasExactMatch = !value || options.includes(value);
  return (
    <label className="block">
      <span className="text-xs font-semibold text-slate-600">
        {label}
        {required && <span className="ml-0.5 text-rose-500">*</span>}
      </span>
      <select value={value || ""} onChange={(e) => onChange(e.target.value)} className={fieldBaseClass(highlighted)}>
        <option value="">{placeholder}</option>
        {options.map((opt) => (
          <option key={opt}>{opt}</option>
        ))}
        {!hasExactMatch && <option value={value}>{value}</option>}
      </select>
    </label>
  );
}

export default function ComplaintForm() {
  const dispatch = useDispatch();
  const {
    extractedData,
    riskAssessment,
    highlightedFields,
    updateToken,
    status,
    isCommitting,
    qmsReference,
    error,
    rawInput,
  } = useSelector((state) => state.complaint);
  const chatMessages = useSelector((state) => state.chat.messages);

  // Highlighted fields (AI-driven update) fade back to normal after 2s.
  useEffect(() => {
    if (!updateToken) return;
    const timer = window.setTimeout(() => dispatch(clearHighlights()), 2000);
    return () => window.clearTimeout(timer);
  }, [dispatch, updateToken]);

  const setField = (field, value) => dispatch(updateField({ field, value }));
  const isHighlighted = (field) => highlightedFields.includes(field);

  const severity = riskAssessment.severity_suggested;
  const severityStyle =
    severity === "Critical"
      ? "bg-rose-50 text-rose-700 border-rose-200"
      : severity === "Major"
      ? "bg-orange-50 text-orange-700 border-orange-200"
      : severity === "Minor"
      ? "bg-amber-50 text-amber-700 border-amber-200"
      : "bg-slate-50 text-slate-500 border-slate-200";

  function handleReset() {
    dispatch(resetComplaint());
    dispatch(resetChat());
  }

  async function handleCommit() {
    dispatch(setCommitting(true));
    dispatch(setComplaintError(null));
    try {
      const chat_history = chatMessages
        .filter((m) => m.id !== "welcome")
        .map((m) => ({ role: m.role === "assistant" ? "ai" : "user", content: m.content }));

      const result = await commitComplaint({
        extracted_data: extractedData,
        risk_assessment: riskAssessment,
        raw_input: rawInput,
        chat_history,
      });

      dispatch(setCommitSuccess(result.id));
      dispatch(
        addMessage({
          id: crypto.randomUUID(),
          role: "assistant",
          content: `Complaint committed to the QMS ledger. Record ID: ${result.id}. This intake is now locked for quality review.`,
          timestamp: new Date().toISOString(),
        })
      );
    } catch (err) {
      dispatch(setComplaintError(err.message || "Unable to commit the complaint."));
    } finally {
      dispatch(setCommitting(false));
    }
  }

  return (
    <section className="flex min-h-0 flex-col bg-white">
      <div className="border-b border-slate-100 px-6 py-5 sm:px-8">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-indigo-600">New quality event</p>
            <h1 className="mt-1 text-xl font-bold tracking-tight text-slate-900">Log Customer Complaint</h1>
          </div>
          <div className="rounded-xl bg-slate-50 p-2.5 text-slate-500">
            <ClipboardCheck className="h-5 w-5" />
          </div>
        </div>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          Capture an audit-ready complaint record. Fields marked <span className="font-bold text-rose-500">*</span> are
          required for QMS commitment.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-6 sm:px-8">
        <div className="space-y-8">
          <div>
            <SectionTitle index="01" title="Origin & customer" />
            <div className="grid gap-4 sm:grid-cols-2">
              <SelectField
                label="Complaint source"
                required
                placeholder="Select source"
                options={COMPLAINT_SOURCES}
                value={extractedData.complaint_source}
                highlighted={isHighlighted("complaint_source")}
                onChange={(v) => setField("complaint_source", v)}
              />
              <TextField
                label="Customer name"
                placeholder="e.g. Northstar Pharmacy"
                required
                value={extractedData.customer_name}
                highlighted={isHighlighted("customer_name")}
                onChange={(v) => setField("customer_name", v)}
              />
            </div>
          </div>

          <div>
            <SectionTitle index="02" title="Product & batch" />
            <div className="grid gap-4 sm:grid-cols-2">
              <TextField
                label="Product name"
                placeholder="e.g. Acetafen"
                required
                value={extractedData.product_name}
                highlighted={isHighlighted("product_name")}
                onChange={(v) => setField("product_name", v)}
              />
              <TextField
                label="Product strength / grade"
                placeholder="e.g. 500 mg"
                value={extractedData.product_strength}
                highlighted={isHighlighted("product_strength")}
                onChange={(v) => setField("product_strength", v)}
              />
              <TextField
                label="Batch / lot number"
                placeholder="e.g. ATF-24-1038"
                required
                value={extractedData.batch_number}
                highlighted={isHighlighted("batch_number")}
                onChange={(v) => setField("batch_number", v)}
              />
              <TextField
                label="Affected quantity"
                placeholder="e.g. 24 bottles"
                value={extractedData.affected_quantity}
                highlighted={isHighlighted("affected_quantity")}
                onChange={(v) => setField("affected_quantity", v)}
              />
              <TextField
                label="Manufacturing date"
                type="date"
                value={extractedData.manufacturing_date}
                highlighted={isHighlighted("manufacturing_date")}
                onChange={(v) => setField("manufacturing_date", v)}
              />
              <TextField
                label="Expiry date"
                type="date"
                value={extractedData.expiry_date}
                highlighted={isHighlighted("expiry_date")}
                onChange={(v) => setField("expiry_date", v)}
              />
            </div>
          </div>

          <div>
            <SectionTitle index="03" title="Facility & material" />
            <div className="grid gap-4 sm:grid-cols-2">
              <SelectField
                label="Originating site block"
                required
                placeholder="Select site block"
                options={SITE_BLOCKS}
                value={extractedData.originating_site_block}
                highlighted={isHighlighted("originating_site_block")}
                onChange={(v) => setField("originating_site_block", v)}
              />
              <TextField
                label="Impacted non-product materials (NPM)"
                placeholder="e.g. blister foil, label stock"
                value={extractedData.impacted_npm}
                highlighted={isHighlighted("impacted_npm")}
                onChange={(v) => setField("impacted_npm", v)}
              />
            </div>
          </div>

          <div>
            <SectionTitle index="04" title="Defect analysis" />
            <div className="grid gap-4 sm:grid-cols-2">
              <SelectField
                label="Complaint category"
                required
                placeholder="Select category"
                options={COMPLAINT_CATEGORIES}
                value={extractedData.complaint_category}
                highlighted={isHighlighted("complaint_category")}
                onChange={(v) => setField("complaint_category", v)}
              />
              <TextField
                label="Complaint date"
                type="date"
                value={extractedData.complaint_date}
                highlighted={isHighlighted("complaint_date")}
                onChange={(v) => setField("complaint_date", v)}
              />
              <SelectField
                label="Priority"
                placeholder="Select priority"
                options={PRIORITY_LEVELS}
                value={extractedData.priority}
                highlighted={isHighlighted("priority")}
                onChange={(v) => setField("priority", v)}
              />
            </div>
            <div className="mt-4 grid gap-4">
              <label className="block">
                <span className="text-xs font-semibold text-slate-600">
                  Complaint description<span className="text-rose-500">*</span>
                </span>
                <textarea
                  value={extractedData.complaint_description || ""}
                  onChange={(e) => setField("complaint_description", e.target.value)}
                  placeholder="Describe the observed defect, timing, and any customer or patient impact…"
                  rows={5}
                  className={`${fieldBaseClass(isHighlighted("complaint_description"))} resize-y leading-6`}
                />
              </label>
            </div>
          </div>

          <div className="rounded-2xl border border-indigo-100 bg-indigo-50/40 p-4 sm:p-5">
            <div className="mb-4 flex items-center gap-2">
              <span className="grid h-7 w-7 place-items-center rounded-lg bg-indigo-600 text-white">
                <Sparkles className="h-3.5 w-3.5" />
              </span>
              <div>
                <h3 className="text-sm font-bold text-slate-800">AI Copilot Risk Assessment</h3>
                <p className="text-xs text-slate-500">Suggested, read-only assessment based on supplied facts.</p>
              </div>
            </div>
            <div className="grid gap-3">
              <div className="rounded-xl border border-white bg-white/80 p-3">
                <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-400">Severity · suggested</p>
                <span className={`mt-2 inline-flex rounded-lg border px-2.5 py-1 text-xs font-bold ${severityStyle}`}>
                  {severity || "Pending analysis"}
                </span>
              </div>
              <div className="rounded-xl border border-white bg-white/80 p-3">
                <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-400">Suggested next action</p>
                <p className="mt-1.5 text-sm leading-5 text-slate-700">
                  {riskAssessment.suggested_next_action || "Fill in product and description to get a suggestion."}
                </p>
              </div>
              <div className="rounded-xl border border-white bg-white/80 p-3">
                <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-400">Initial risk assessment</p>
                <p className="mt-1.5 text-sm leading-5 text-slate-700">
                  {riskAssessment.initial_risk_assessment || "—"}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="border-t border-slate-100 bg-slate-50/80 px-6 py-4 sm:px-8">
        {qmsReference && (
          <div className="mb-3 flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-700">
            <CheckCircle2 className="h-4 w-4" />
            Committed as <strong>{qmsReference}</strong>
          </div>
        )}
        {error && (
          <div className="mb-3 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-medium text-rose-700">
            <AlertTriangle className="h-4 w-4" />
            {error}
          </div>
        )}
        <div className="flex items-center justify-between gap-4">
          <div className="hidden items-center gap-2 text-xs text-slate-500 sm:flex">
            <LockKeyhole className="h-3.5 w-3.5" />
            Audit trail enabled
          </div>
          <div className="ml-auto flex items-center gap-3">
            <button
              type="button"
              onClick={handleReset}
              disabled={isCommitting}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <RotateCcw className="h-4 w-4" />
              Reset form
            </button>
            <button
              type="button"
              disabled={status !== "ready" || isCommitting}
              onClick={handleCommit}
              className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              <CheckCircle2 className="h-4 w-4" />
              {isCommitting ? "Committing…" : "Commit to QMS Ledger"}
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}