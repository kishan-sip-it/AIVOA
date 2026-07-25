import { useEffect, useRef, useState } from "react";
import { ArrowUp, Bot, CloudUpload, FileText, Paperclip, Sparkles, UserRound } from "lucide-react";
import { useDispatch, useSelector } from "react-redux";
import { addMessage } from "../store/chatSlice";
import { applyWorkflowResult, setProcessing, setRawInput } from "../store/complaintSlice";
import { processComplaint, chatCorrection } from "../api/complaintApi";
import { MANDATORY_FIELDS, FIELD_LABELS } from "../lib/complaintFields";

const now = () => new Date().toISOString();

// Builds a specific, useful reply after intake extraction — naming exactly
// what was picked up and what's still missing — instead of a generic line
// that reads the same regardless of how much the model actually extracted.
function buildIntakeReply(extractedData) {
  const filled = MANDATORY_FIELDS.filter((f) => Boolean(extractedData[f]));
  const missing = MANDATORY_FIELDS.filter((f) => !extractedData[f]);

  if (missing.length === 0) {
    return "Got everything I need — all required fields are filled in. Review the form on the left and commit when you're ready.";
  }

  const missingLabels = missing.map((f) => FIELD_LABELS[f] || f).join(", ");

  if (filled.length === 0) {
    return `I couldn't pick up any complaint details from that — could you share the product, batch number, and a description of what happened? Still needed: ${missingLabels}.`;
  }

  const filledLabels = filled.map((f) => FIELD_LABELS[f] || f).join(", ");
  return `I've filled in ${filledLabels} from that. Still missing: ${missingLabels} — add those in the form, or tell me the details here.`;
}

export default function CopilotChat() {
  const dispatch = useDispatch();
  const { messages } = useSelector((state) => state.chat);
  const { extractedData, riskAssessment, isComplete, status, rawInput, isProcessing } = useSelector(
    (state) => state.complaint
  );
  const [message, setMessage] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [progress, setProgress] = useState(0);
  const fileInputRef = useRef(null);
  const dragCounterRef = useRef(0);

  // No backend progress stream exists (a single /process call either
  // resolves or doesn't), so this animates toward — but never quite
  // reaches — 90% while waiting, then snaps to 100% on completion. It's an
  // honest "still working" signal, not a fabricated precise measurement.
  useEffect(() => {
    if (!isProcessing) {
      if (progress !== 0) {
        setProgress(100);
        const t = setTimeout(() => setProgress(0), 500);
        return () => clearTimeout(t);
      }
      return;
    }
    setProgress(8);
    const interval = setInterval(() => {
      setProgress((p) => (p < 90 ? p + (90 - p) * 0.15 : p));
    }, 350);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isProcessing]);

  // Anything already extracted means intake has started — from here on,
  // follow-ups route through /chat (correction_node) instead of /process,
  // so previously confirmed fields aren't wiped.
  const hasStarted = Object.values(extractedData).some((v) => Boolean(v));

  function buildGraphState() {
    return {
      raw_input: rawInput,
      extracted_data: extractedData,
      chat_history: messages
        .filter((m) => m.id !== "welcome")
        .map((m) => ({ role: m.role === "assistant" ? "ai" : "user", content: m.content })),
      risk_assessment: riskAssessment,
      is_complete: isComplete,
      status,
      last_message: "",
    };
  }

  async function send(text) {
    const content = text.trim();
    if (!content || isProcessing) return;

    dispatch(addMessage({ id: crypto.randomUUID(), role: "user", content, timestamp: now() }));
    setMessage("");
    dispatch(setProcessing(true));

    try {
      if (!hasStarted) {
        dispatch(setRawInput(content));
        const result = await processComplaint({ rawText: content });
        dispatch(applyWorkflowResult(result));
        dispatch(
          addMessage({
            id: crypto.randomUUID(),
            role: "assistant",
            content: buildIntakeReply(result.extracted_data),
            timestamp: now(),
          })
        );
      } else {
        const result = await chatCorrection({ message: content, state: buildGraphState() });
        dispatch(applyWorkflowResult(result));
        dispatch(addMessage({ id: crypto.randomUUID(), role: "assistant", content: result.ai_message, timestamp: now() }));
      }
    } catch (err) {
      dispatch(
        addMessage({
          id: crypto.randomUUID(),
          role: "assistant",
          content: err.message || "Something went wrong while processing that request.",
          timestamp: now(),
        })
      );
    } finally {
      dispatch(setProcessing(false));
    }
  }

  async function onFileChosen(file) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      dispatch(
        addMessage({
          id: crypto.randomUUID(),
          role: "assistant",
          content: "Only PDF attachments are supported right now — please attach a .pdf, or paste the complaint text directly.",
          timestamp: now(),
        })
      );
      return;
    }

    dispatch(
      addMessage({
        id: crypto.randomUUID(),
        role: "user",
        content: "",
        fileName: file.name,
        timestamp: now(),
      })
    );
    dispatch(setProcessing(true));
    try {
      const result = await processComplaint({ file });
      dispatch(applyWorkflowResult(result));
      dispatch(
        addMessage({
          id: crypto.randomUUID(),
          role: "assistant",
          content: buildIntakeReply(result.extracted_data),
          timestamp: now(),
        })
      );
    } catch (err) {
      dispatch(
        addMessage({
          id: crypto.randomUUID(),
          role: "assistant",
          content: err.message || "I couldn't read that PDF — try a text-based export rather than a scanned image.",
          timestamp: now(),
        })
      );
    } finally {
      dispatch(setProcessing(false));
    }
  }

  function handleDragEnter(e) {
    e.preventDefault();
    dragCounterRef.current += 1;
    setIsDragging(true);
  }

  function handleDragOver(e) {
    e.preventDefault();
  }

  function handleDragLeave(e) {
    e.preventDefault();
    dragCounterRef.current -= 1;
    if (dragCounterRef.current <= 0) {
      dragCounterRef.current = 0;
      setIsDragging(false);
    }
  }

  function handleDrop(e) {
    e.preventDefault();
    dragCounterRef.current = 0;
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    onFileChosen(file);
  }

  return (
    <aside
      className="relative flex min-h-0 flex-col bg-[#101827] text-white"
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {isDragging && (
        <div className="pointer-events-none absolute inset-2 z-20 flex flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-indigo-300 bg-slate-950/90 backdrop-blur-sm">
          <CloudUpload className="h-8 w-8 text-indigo-300" />
          <p className="text-sm font-semibold text-white">Drop your complaint document here</p>
          <p className="text-xs text-slate-400">PDF only, right now</p>
        </div>
      )}

      <div className="border-b border-white/10 px-6 py-5 sm:px-7">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-indigo-400 to-cyan-300 text-slate-950 shadow-lg shadow-indigo-500/20">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold">AIVOA Copilot</h2>
              <span
                className={`h-2 w-2 rounded-full ${
                  isProcessing
                    ? "animate-pulse bg-indigo-400"
                    : status === "ready"
                    ? "bg-emerald-400"
                    : "bg-sky-400"
                }`}
              />
            </div>
            <p className="mt-0.5 text-xs text-slate-400">Pharmacovigilance intake assistant</p>
          </div>
        </div>
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto px-5 py-6 sm:px-6">
        <div className="rounded-xl border border-indigo-400/20 bg-indigo-400/10 px-3.5 py-3 text-xs leading-5 text-indigo-100">
          <span className="font-bold text-indigo-200">Secure workspace.</span> AI suggestions support QA review and do
          not replace required quality procedures.
        </div>
        {messages.map((item) => (
          <div className={`flex gap-2.5 ${item.role === "user" ? "flex-row-reverse" : ""}`} key={item.id}>
            <div
              className={`mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg ${
                item.role === "assistant" ? "bg-indigo-400/20 text-indigo-200" : "bg-slate-700 text-slate-300"
              }`}
            >
              {item.role === "assistant" ? <Bot className="h-4 w-4" /> : <UserRound className="h-3.5 w-3.5" />}
            </div>
            {item.fileName ? (
              <div className="flex max-w-[85%] items-center gap-3 rounded-2xl rounded-tr-sm border border-white/10 bg-white/[0.07] px-3.5 py-3">
                <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-rose-400/20 text-rose-300">
                  <FileText className="h-4.5 w-4.5" />
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-white">{item.fileName}</p>
                  <p className="text-xs text-slate-400">PDF Document</p>
                </div>
              </div>
            ) : (
              <div
                className={`max-w-[85%] rounded-2xl px-3.5 py-3 text-sm leading-5 ${
                  item.role === "assistant"
                    ? "rounded-tl-sm border border-white/10 bg-white/[0.07] text-slate-200"
                    : "rounded-tr-sm bg-indigo-500 text-white"
                }`}
              >
                {item.content.split("\n").map((line, i) => (
                  <p className={i ? "mt-2" : ""} key={i}>
                    {line}
                  </p>
                ))}
              </div>
            )}
          </div>
        ))}
        {isProcessing && (
          <div className="rounded-2xl border border-white/10 bg-white/[0.07] p-4">
            <div className="mb-2 flex items-center justify-between text-[10px] font-bold uppercase tracking-[0.12em] text-slate-400">
              <span>Extraction progress</span>
              <span className="text-indigo-200">{Math.round(progress)}%</span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
              <div
                className="h-full rounded-full bg-gradient-to-r from-indigo-400 to-cyan-300 transition-all duration-300"
                style={{ width: `${Math.round(progress)}%` }}
              />
            </div>
            <p className="mt-2.5 text-xs leading-5 text-slate-400">
              Analyzing content and extracting key details… this may take a few moments.
            </p>
          </div>
        )}
      </div>

      <div className="border-t border-white/10 bg-slate-950/20 px-5 py-4 sm:px-6">
        <div className="rounded-2xl border border-white/15 bg-white/[0.07] p-2 shadow-lg">
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(message);
              }
            }}
            placeholder="Paste a complaint, ask a correction…"
            rows={2}
            className="block w-full resize-none bg-transparent px-2 py-1 text-sm leading-5 text-white outline-none placeholder:text-slate-500"
          />
          <div className="mt-1 flex items-center justify-between">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => {
                onFileChosen(e.target.files?.[0]);
                e.currentTarget.value = "";
              }}
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-medium text-slate-400 transition hover:bg-white/10 hover:text-white"
            >
              <Paperclip className="h-3.5 w-3.5" />
              Attach PDF
            </button>
            <button
              type="button"
              disabled={!message.trim() || isProcessing}
              onClick={() => send(message)}
              className="grid h-8 w-8 place-items-center rounded-lg bg-indigo-400 text-slate-950 transition hover:bg-indigo-300 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-500"
            >
              <ArrowUp className="h-4 w-4" />
            </button>
          </div>
        </div>
        <div className="mt-3 flex items-center justify-center gap-1.5 text-[10px] text-slate-500">
          <FileText className="h-3 w-3" />
          AI outputs are captured in the complaint audit record — or drag & drop a PDF anywhere in this panel
        </div>
        <div className="mt-1.5 text-center text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">
          Powered by LangGraph
        </div>
      </div>
    </aside>
  );
}