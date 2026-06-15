import { useEffect, useState } from "react";

const OPTIONS = [
  { id: "under-100",  label: "Under $100",        value: "Under $100",       hint: "Quick refresh" },
  { id: "100-300",    label: "$100 – $300",       value: "$100 – $300",      hint: "Most popular" },
  { id: "300-500",    label: "$300 – $500",       value: "$300 – $500",      hint: "Real impact" },
  { id: "500-1000",   label: "$500 – $1,000",     value: "$500 – $1,000",    hint: "Whole-room overhaul" },
  { id: "1000-plus",  label: "$1,000+",           value: "$1,000+",          hint: "Premium build-out" },
  { id: "flexible",   label: "I'm flexible",      value: "Not specified",    hint: "Surprise me" },
];

export default function BudgetModal({ open, onConfirm, onClose, submitting }) {
  const [selected, setSelected] = useState("100-300");

  useEffect(() => {
    const handler = (e) => {
      if (e.key === "Escape" && !submitting) onClose?.();
    };
    if (open) {
      window.addEventListener("keydown", handler);
    }
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose, submitting]);

  if (!open) return null;

  const handleConfirm = () => {
    const opt = OPTIONS.find((o) => o.id === selected);
    onConfirm?.(opt?.value || null);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 fade-in"
      data-testid="budget-modal"
      onClick={(e) => {
        if (e.target === e.currentTarget && !submitting) onClose?.();
      }}
    >
      <div className="relative w-full max-w-lg rounded-3xl bg-white p-7 shadow-2xl sm:p-9">
        {!submitting && (
          <button
            onClick={onClose}
            aria-label="Close"
            className="absolute right-4 top-4 inline-flex h-9 w-9 items-center justify-center rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            data-testid="budget-modal-close"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-5 w-5"
            >
              <path d="M18 6 6 18" />
              <path d="m6 6 12 12" />
            </svg>
          </button>
        )}

        <span className="eyebrow" data-testid="budget-modal-eyebrow">
          One quick question
        </span>
        <h2 className="mt-3 font-display text-3xl font-light leading-tight text-slate-900 sm:text-4xl">
          How much are you budgeting for this project?
        </h2>
        <p className="mt-2 text-sm text-slate-600">
          We&rsquo;ll tailor your shopping list and recommendations so your
          design plan fits the spend you have in mind.
        </p>

        <div
          className="mt-6 grid grid-cols-1 gap-2.5 sm:grid-cols-2"
          data-testid="budget-modal-options"
        >
          {OPTIONS.map((opt) => {
            const isActive = selected === opt.id;
            return (
              <button
                key={opt.id}
                type="button"
                onClick={() => setSelected(opt.id)}
                disabled={submitting}
                className={`group flex items-center justify-between rounded-xl border px-4 py-3 text-left transition-all ${
                  isActive
                    ? "border-emerald-500 bg-emerald-50 ring-2 ring-emerald-200"
                    : "border-slate-200 bg-white hover:border-emerald-300"
                } disabled:opacity-60`}
                data-testid={`budget-option-${opt.id}`}
              >
                <div>
                  <div className="text-sm font-semibold text-slate-900">
                    {opt.label}
                  </div>
                  <div className="text-[11px] text-slate-500">{opt.hint}</div>
                </div>
                <span
                  className={`inline-block h-4 w-4 rounded-full border-2 transition-all ${
                    isActive
                      ? "border-emerald-500 bg-emerald-500"
                      : "border-slate-300 group-hover:border-emerald-300"
                  }`}
                />
              </button>
            );
          })}
        </div>

        <div className="mt-7 flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="text-sm font-medium text-slate-500 hover:text-slate-800 disabled:opacity-50"
            data-testid="budget-modal-cancel"
          >
            ← Back to edit photos
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={submitting}
            className="btn-primary w-full sm:w-auto"
            data-testid="budget-modal-confirm"
          >
            {submitting ? "Generating…" : "Confirm & generate my plan"}
          </button>
        </div>

        <p className="mt-4 text-center text-[11px] text-slate-400">
          AI image generation usually takes 20–60 seconds.
        </p>
      </div>
    </div>
  );
}
