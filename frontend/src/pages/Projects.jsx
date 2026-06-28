import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { useAuth } from "@/contexts/AuthContext";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const PLAN_BADGE = {
  free: "bg-slate-100 text-slate-700",
  plus: "bg-emerald-100 text-emerald-800",
  premium: "bg-amber-100 text-amber-800",
};

const STATUS_LABEL = {
  awaiting_payment: "Awaiting payment",
  pending: "Queued",
  processing: "Generating…",
  completed: "Completed",
  failed: "Failed",
};

export default function Projects() {
  const { user, signIn, loading } = useAuth();
  const [items, setItems] = useState(null);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      setItems([]);
      return;
    }
    axios.get(`${API}/submissions`).then((r) => setItems(r.data.items || []));
  }, [user, loading]);

  return (
    <div className="min-h-screen bg-slate-50">
      <Header />
      <main className="container-app section-pad" data-testid="projects-page">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <span className="eyebrow">Your projects</span>
            <h1 className="mt-3 font-display text-4xl font-light tracking-tight text-slate-900 sm:text-5xl">
              {user ? "Every room you\u2019ve transformed" : "Sign in to see your projects"}
            </h1>
            {user && (
              <p className="mt-3 text-slate-600">
                {user.free_remaining > 0
                  ? `${user.free_remaining} of ${user.free_cap} free projects remaining.`
                  : "You\u2019ve used all your free projects. Plus and Premium are unlimited."}
              </p>
            )}
          </div>
          {user && (
            <Link to="/#packages" className="btn-primary" data-testid="projects-new-cta">
              Start a new project
            </Link>
          )}
        </div>

        {!user && (
          <div
            className="mt-10 rounded-2xl border border-slate-200 bg-white p-8 max-w-2xl shadow-sm"
            data-testid="projects-signin-card"
          >
            <p className="text-slate-700">
              Sign in with Google to save your transformations and pick up where you left off.
            </p>
            <button
              onClick={() => signIn("/projects")}
              className="btn-primary mt-5"
              data-testid="projects-signin-btn"
            >
              Sign in with Google
            </button>
          </div>
        )}

        {user && items === null && (
          <p className="mt-10 text-slate-500">Loading your projects…</p>
        )}

        {user && items?.length === 0 && (
          <div
            className="mt-10 rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center"
            data-testid="projects-empty"
          >
            <p className="font-display text-2xl text-slate-900">No projects yet</p>
            <p className="mt-2 text-slate-600">Pick a plan and upload your first room.</p>
            <Link to="/#packages" className="btn-primary mt-5 inline-flex" data-testid="projects-empty-cta">
              Choose a plan
            </Link>
          </div>
        )}

        {user && items && items.length > 0 && (
          <div className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="projects-grid">
            {items.map((p) => (
              <Link
                to={`/result/${p.id}`}
                key={p.id}
                className="group rounded-2xl border border-slate-200 bg-white p-5 transition-all hover:-translate-y-0.5 hover:border-emerald-300 hover:shadow-md"
                data-testid={`projects-item-${p.id}`}
              >
                <div className="flex items-center justify-between">
                  <span
                    className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-widest ${
                      PLAN_BADGE[p.plan_id] || "bg-slate-100 text-slate-700"
                    }`}
                  >
                    {p.plan_id}
                  </span>
                  <span className="text-[10px] uppercase tracking-widest text-slate-400">
                    {STATUS_LABEL[p.status] || p.status}
                  </span>
                </div>
                <p className="mt-4 font-display text-xl text-slate-900 capitalize">
                  {p.room_type || "Room"}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {p.photos_total} photo{p.photos_total === 1 ? "" : "s"} ·{" "}
                  {p.created_at?.slice(0, 10)}
                </p>
                <p className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-emerald-700 group-hover:translate-x-0.5 transition-transform">
                  Open
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
                  >
                    <path d="M5 12h14" />
                    <path d="m12 5 7 7-7 7" />
                  </svg>
                </p>
              </Link>
            ))}
          </div>
        )}
      </main>
      <Footer />
    </div>
  );
}
