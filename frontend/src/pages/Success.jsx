import { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import axios from "axios";
import Header from "@/components/Header";
import Footer from "@/components/Footer";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const MAX_ATTEMPTS = 8;

export default function Success() {
  const [params] = useSearchParams();
  const sessionId = params.get("session_id");
  const navigate = useNavigate();
  const [statusText, setStatusText] = useState("Verifying your payment…");
  const [error, setError] = useState(sessionId ? "" : "Missing payment session.");

  useEffect(() => {
    let cancelled = false;
    let attempts = 0;

    if (!sessionId) {
      return () => {};
    }

    const poll = async () => {
      if (cancelled) return;
      attempts += 1;
      try {
        const res = await axios.get(`${API}/checkout/status/${sessionId}`);
        if (res.data.payment_status === "paid") {
          const planId = res.data.plan_id || "plus";
          setStatusText("Payment confirmed. Redirecting to upload…");
          setTimeout(() => navigate(`/upload/${planId}?session_id=${sessionId}`), 600);
          return;
        }
        if (res.data.status === "expired") {
          setError("Your session expired. Please choose your plan again.");
          return;
        }
        if (attempts >= MAX_ATTEMPTS) {
          setError("Couldn't verify payment in time. Check your email or contact support.");
          return;
        }
        setStatusText(`Verifying your payment… (${attempts}/${MAX_ATTEMPTS})`);
        setTimeout(poll, 2000);
      } catch {
        if (attempts >= MAX_ATTEMPTS) {
          setError("Could not reach the server. Please contact support.");
          return;
        }
        setTimeout(poll, 2000);
      }
    };
    poll();
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
