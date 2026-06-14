import { useNavigate } from "react-router-dom";
import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

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

export default function PricingCard({
  plan,
  highlighted = false,
  testId,
}) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const handleStart = async () => {
    if (plan.price === 0) {
      navigate(`/upload/${plan.id}`);
      return;
    }
    try {
      setLoading(true);
      const origin = window.location.origin;
      const res = await axios.post(`${API}/checkout/session`, {
        plan_id: plan.id,
        origin_url: origin,
      });
      window.location.href = res.data.url;
    } catch (e) {
      console.error(e);
      toast.error("Could not start checkout. Please try again.");
      setLoading(false);
    }
  };

  return (
    <div
      className={`relative flex flex-col rounded-2xl border bg-white p-8 transition-all card-hover ${
        highlighted ? "border-emerald-500 shadow-lg ring-4 ring-emerald-50" : "border-slate-200"
      }`}
      data-testid={testId}
    >
      {highlighted && (
        <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-emerald-500 px-3 py-1 text-[11px] font-semibold uppercase tracking-widest text-white shadow-sm">
          ★ Most popular
        </span>
      )}
      <h3 className="font-display text-2xl font-medium text-slate-900">
        {plan.name}
      </h3>
      <p className="mt-1 text-sm text-slate-500">{plan.tagline}</p>
      <div className="mt-6 flex items-baseline gap-2">
        <span className="font-display text-5xl font-light text-slate-900">
          {plan.price === 0 ? "$0" : `$${plan.price.toFixed(0)}`}
        </span>
        <span className="text-sm text-slate-500">
          {plan.price === 0 ? "free forever" : "one-time"}
        </span>
      </div>
      <ul className="mt-6 flex flex-col gap-3">
        {plan.features.map((f, i) => (
          <li
            key={i}
            className="flex items-start gap-2 text-slate-700"
            data-testid={`${testId}-feature-${i}`}
          >
            <Check tone={highlighted ? "emerald" : "sky"} />
            <span>{f}</span>
          </li>
        ))}
      </ul>
      <button
        onClick={handleStart}
        disabled={loading}
        className={`mt-8 w-full rounded-full py-3.5 text-base font-medium shadow transition-all ${
          highlighted
            ? "bg-emerald-500 text-white hover:bg-emerald-600"
            : "bg-slate-900 text-white hover:bg-slate-700"
        } disabled:opacity-60`}
        data-testid={`${testId}-cta`}
      >
        {loading
          ? "Loading…"
          : plan.price === 0
          ? "Try it free"
          : "Choose this plan"}
      </button>
      {plan.pdf && (
        <p
          className="mt-3 text-center text-xs text-slate-500"
          data-testid={`${testId}-pdf-note`}
        >
          Includes a custom PDF organization plan
        </p>
      )}
    </div>
  );
}
