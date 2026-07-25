import { CheckCircle2, Clock3 } from "lucide-react";
import { useSelector } from "react-redux";

export default function StatusBadge() {
  const status = useSelector((state) => state.complaint.status);
  const ready = status === "ready";

  return (
    <div
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold ${
        ready ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-amber-200 bg-amber-50 text-amber-700"
      }`}
    >
      {ready ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Clock3 className="h-3.5 w-3.5" />}
      {ready ? "Ready to Commit" : "Pending Triage"}
    </div>
  );
}
