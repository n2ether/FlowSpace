import { useNavigate } from "react-router-dom";

const Check = ({ tone = "emerald" }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="20"
    height="20"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={`mt-0.5 h-5 w-5 shrink-0 ${tone === "emerald" ? "text-emerald-500" : "text-sky-600"}`}
    aria-hidden="true"
  >
    <path d="M20 6 9 17l-5-5" />
  </svg>
);

export default function PricingCard({ plan, highlighted = false, testId }) {
  const navigate = useNavigate();

  const handleStart = () => {
    navigate(`/intake?plan=${plan.id}`);
  };

  return (
    <div
      className={`relative flex flex-col rounded-3xl border p-8 transition-all ${
        highlighted
          ? "border-emerald-500 bg-white shadow-xl shadow-emerald-100 lg:scale-[1.02]"
          : "border-slate-200 bg-white hover:border-emerald-200 hover:shadow-md"
      }`}
      data-testid={testId}
    >
      {highlighted && (
        <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-emerald-500 px-3 py-1 text-[11px] font-medium uppercase tracking-wider text-white shadow-sm">
          Most popular
        </span>
      )}
      <div className="flex flex-col gap-1">
        <h3 className="font-display text-2xl font-medium text-slate-900">{plan.name}</h3>
        <p className="text-sm text-slate-500">{plan.tagline}</p>
      </div>
      <div className="mt-6 flex items-baseline gap-1">
        <span className="font-display text-5xl font-light text-slate-900">
          ${plan.price}
        </span>
        {plan.price > 0 && <span className="text-sm text-slate-500">one-time</span>}
      </div>
      <ul className="mt-6 flex-1 space-y-3">
        {plan.features.map((f, i) => (
          <li key={i} className="flex items-start gap-3 text-slate-700">
            <Check tone={highlighted ? "emerald" : "emerald"} />
            <span>{f}</span>
          </li>
        ))}
      </ul>
      <button
        onClick={handleStart}
        className={`mt-8 inline-flex items-center justify-center gap-2 rounded-full px-6 py-3 text-base font-medium transition-colors ${
          highlighted
            ? "bg-emerald-500 text-white hover:bg-emerald-600 shadow-sm"
            : "border border-slate-200 bg-white text-slate-800 hover:border-emerald-300 hover:text-emerald-700"
        }`}
        data-testid={`${testId}-cta`}
      >
        {plan.price === 0 ? "Start free" : `Choose ${plan.name}`}
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M5 12h14" />
          <path d="m12 5 7 7-7 7" />
        </svg>
      </button>
    </div>
  );
}
