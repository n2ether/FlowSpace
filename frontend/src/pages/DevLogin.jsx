import { useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";
import Header from "@/components/Header";
import Footer from "@/components/Footer";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const TEST_USERS = [
  { email: "tester1@flowspace.solutions", note: "Fresh user — 2 free projects available" },
  { email: "tester2@flowspace.solutions", note: "Use this to test the Plus paid flow" },
  { email: "tester3@flowspace.solutions", note: "Use this to test the Premium paid flow" },
  { email: "tester4@flowspace.solutions", note: "Use this to test free-cap → upgrade" },
];

export default function DevLogin() {
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const [email, setEmail] = useState("tester1@flowspace.solutions");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e) => {
    e?.preventDefault?.();
    try {
      setBusy(true);
      await axios.post(`${API}/auth/dev-login`, { email, password });
      await refresh();
      toast.success(`Signed in as ${email}`);
      navigate("/projects");
    } catch (err) {
      const status = err?.response?.status;
      toast.error(
        status === 404
          ? "Dev login is disabled in this environment."
          : status === 401
          ? "Wrong dev password."
          : "Could not sign in."
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <Header />
      <main className="container-app py-16" data-testid="dev-login-page">
        <div className="mx-auto max-w-md rounded-2xl border border-amber-200 bg-white p-8 shadow-sm">
          <span className="inline-block rounded-full bg-amber-100 px-3 py-1 text-[11px] font-semibold uppercase tracking-widest text-amber-800">
            Dev workflow login
          </span>
          <h1 className="mt-4 font-display text-3xl font-light tracking-tight text-slate-900">
            Sign in for testing
          </h1>
          <p className="mt-2 text-sm text-slate-600">
            Preview-only. Disabled on production. Real users sign in via Google.
          </p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-3">
            <div>
              <label className="text-xs font-medium text-slate-600">Email (test account)</label>
              <select
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100"
                data-testid="dev-login-email"
              >
                {TEST_USERS.map((u) => (
                  <option key={u.email} value={u.email}>
                    {u.email}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-[11px] text-slate-500">
                {TEST_USERS.find((u) => u.email === email)?.note}
              </p>
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600">Dev password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••"
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100"
                data-testid="dev-login-password"
                required
              />
            </div>
            <button
              type="submit"
              disabled={busy || !password}
              className="btn-primary w-full"
              data-testid="dev-login-submit"
            >
              {busy ? "Signing in…" : "Sign in for testing"}
            </button>
          </form>

          <div className="mt-7 rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-600">
            <p className="font-semibold text-slate-900">Stripe test cards</p>
            <ul className="mt-2 space-y-1.5 font-mono">
              <li>✅ <code>4242 4242 4242 4242</code> — Visa, succeeds</li>
              <li>✅ <code>5555 5555 5555 4444</code> — Mastercard, succeeds</li>
              <li>🔐 <code>4000 0025 0000 3155</code> — 3DS authentication required</li>
              <li>❌ <code>4000 0000 0000 9995</code> — Declined (insufficient funds)</li>
            </ul>
            <p className="mt-3 text-slate-500">
              Any future expiry (e.g. 12/34), any CVC (e.g. 123), any ZIP (e.g. 12345).
            </p>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
