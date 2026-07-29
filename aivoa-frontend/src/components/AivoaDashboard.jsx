import { Bell, Building2, ChevronDown, CircleHelp, ShieldCheck } from "lucide-react";
import ComplaintForm from "./ComplaintForm.jsx";
import CopilotChat from "./CopilotChat.jsx";
import StatusBadge from "./StatusBadge.jsx";

export default function AivoaDashboard() {
  return (
    <main className="flex h-screen flex-col overflow-hidden bg-[#eef2f7] text-slate-900">
      <header className="border-b border-slate-200/80 bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[1600px] items-center justify-between gap-4 px-5 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-slate-900 text-white">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-bold tracking-tight text-slate-900">AIVOA</span>
                <span className="hidden text-xs text-slate-400 sm:inline">/ Quality Intelligence</span>
              </div>
              <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-slate-400">Customer complaints</p>
            </div>
          </div>
          <div className="flex items-center gap-2 sm:gap-4">
            <StatusBadge />
            <button className="hidden rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700 sm:block" aria-label="Help">
              
            </button>
            <button className="hidden rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700 sm:block" aria-label="Notifications">
              
            </button>
            <div className="hidden h-7 w-px bg-slate-200 sm:block" />
            <button className="flex items-center gap-2 rounded-lg py-1 pl-1 pr-0.5 text-xs font-semibold text-slate-600 hover:bg-slate-50">
              <span className="grid h-7 w-7 place-items-center rounded-md bg-indigo-100 text-indigo-700">
                <Building2 className="h-3.5 w-3.5" />
              </span>
              <span className="hidden lg:inline">Quality Operations</span>
              <ChevronDown className="hidden h-3.5 w-3.5 lg:block" />
            </button>
          </div>
        </div>
      </header>

      {/* FIX: this wrapper used to be min-h-[...] (grows with content, causing
          the whole page — including the chat input — to scroll away). It's
          now flex-1 + overflow-hidden, so it's locked to exactly the
          remaining viewport height and never grows past it. */}
      <div className="mx-auto min-h-0 w-full max-w-[1600px] flex-1 overflow-hidden p-3 sm:p-5 lg:p-7">
        {/* FIX: h-full (not min-h-full) — this grid is now bounded to the
            wrapper's fixed height above, so ComplaintForm/CopilotChat (each
            already flex-col with an internal overflow-y-auto section) scroll
            independently instead of pushing the page taller. */}
        <div className="grid h-full overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_20px_55px_rgba(15,23,42,0.08)] lg:grid-cols-[3fr_2fr]">
          <ComplaintForm />
          <CopilotChat />
        </div>
      </div>
    </main>
  );
}
