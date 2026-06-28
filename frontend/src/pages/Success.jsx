import { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import axios from "axios";
import Header from "@/components/Header";
import Footer from "@/components/Footer";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const MAX_ATTEMPTS = 12;

export default function Success() {
  const [params] = useSearchParams();
  const sessionId = params.get("session_id");
  const navigate = useNavigate();
  const [statusText, setStatusText] = useState("Verifying your payment…");
  const [error, setError] = useState(sessionId ? "" : "Missing payment session.");

  useEffect(() => {
    let cancelled = false;
    let attempts = 0;

    if (!sessionId) return () => {};

    const tryConfirm = async () => {
      if (cancelled) return;
      attempts += 1;
      try {
        const status = await axios.get(`${API}/checkout/status/${sessionId}`);
        if (status.data.payment_status === "paid") {
          // Find submission tied to this checkout
          const list = await axios.get(`${API}/submissions`);
          const sub = (list.data.items || []).find(
            (s) => s.status === "awaiting_payment" || s.status === "pending" || s.status === "processing"
          );
          if (!sub) {
            setError("Payment confirmed but we couldn't find your submission. Please contact support.");
            return;
          }
          // Tell the backend to start processing
          try {
            await axios.post(`${API}/submissions/${sub.id}/confirm-payment`);
          } catch {
            /* idempotent — server returns current state */
          }
          setStatusText("Payment confirmed. Loading your transformation…");
          setTimeout(() => navigate(`/result/${sub.id}`, { replace: true }), 500);
          return;
        }
        if (status.data.status === "expired") {
          setError("Your payment session expired. Please choose your plan again.");
          return;
        }
        if (attempts >= MAX_ATTEMPTS) {
          setError("Couldn't verify payment in time. Check your email or contact support.");
          return;
        }
        setStatusText(`Verifying your payment… (${attempts}/${MAX_ATTEMPTS})`);
        setTimeout(tryConfirm, 2000);
      } catch {
        if (attempts >= MAX_ATTEMPTS) {
          setError("Could not reach the server. Please contact support.");
          return;
        }
        setTimeout(tryConfirm, 2000);
      }
    };
    tryConfirm();
    return () => {
      cancelled = true;
    };
  }, [sessionId, navigate]);

  return (
    <div className="min-h-screen bg-white">
      <Header />
      <main
        className="container-app section-pad flex flex-col items-center text-center"
        data-testid="success-page"
      >
        {!error ? (
          <>
            <div className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 mb-6 animate-pulse">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="h-7 w-7"
                aria-hidden="true"
              >
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <path d="m9 11 3 3L22 4" />
              </svg>
            </div>
            <h1 className="font-display text-4xl text-slate-900 mb-3">
              Thank you!
            </h1>
            <p className="text-slate-600 max-w-md" data-testid="success-status-text">
              {statusText}
            </p>
          </>
        ) : (
          <>
            <h1 className="font-display text-4xl text-slate-900 mb-3">Hmm.</h1>
            <p className="text-slate-600 max-w-md" data-testid="success-error-text">
              {error}
            </p>
            <a href="/#packages" className="btn-primary mt-6" data-testid="success-back-cta">
              Back to plans
            </a>
          </>
        )}
      </main>
      <Footer />
    </div>
  );
}
