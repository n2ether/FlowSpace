import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import axios from "axios";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import BeforeAfterSlider from "@/components/BeforeAfterSlider";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Result() {
  const { submissionId } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    axios
      .get(`${API}/submissions/${submissionId}`)
      .then((r) => setData(r.data))
      .catch(() => setErr("Submission not found."));
  }, [submissionId]);

  return (
    <div className="min-h-screen bg-slate-50">
      <Header />
      <main className="container-app section-pad" data-testid="result-page">
        <Link
          to="/"
          className="text-sm text-slate-500 hover:text-emerald-600"
          data-testid="result-back-link"
        >
          ← Back to home
        </Link>
        <div className="mt-4 max-w-2xl">
          <span className="eyebrow">Your transformation</span>
          <h1 className="mt-3 font-display text-4xl font-light tracking-tight text-slate-900 sm:text-5xl">
            Here’s your space, reorganized.
          </h1>
          <p className="mt-3 text-slate-600">
            Drag the slider to compare. A copy has been emailed to you.
          </p>
        </div>

        {err && <p className="mt-10 text-red-600">{err}</p>}

        {!data && !err && (
          <p className="mt-10 text-slate-500">Loading your results…</p>
        )}

        {data && (
          <div className="mt-10 grid grid-cols-1 gap-8 lg:grid-cols-2">
            {data.results.map((r, i) => (
              <div key={i} data-testid={`result-photo-${i}`}>
                {r.after ? (
                  <BeforeAfterSlider
                    beforeSrc={`data:image/png;base64,${r.before}`}
                    afterSrc={`data:image/png;base64,${r.after}`}
                    aspect="4/3"
                    testId={`result-slider-${i}`}
                  />
                ) : (
                  <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white">
                    <img
                      src={`data:image/png;base64,${r.before}`}
                      alt={`Photo ${i + 1}`}
                      className="aspect-[4/3] w-full object-cover"
                    />
                    <p className="p-3 text-sm text-amber-700 bg-amber-50">
                      AI transformation is still processing — check your email
                      shortly.
                    </p>
                  </div>
                )}
                <p className="mt-3 text-sm font-medium text-slate-700">
                  Photo {i + 1}
                </p>
              </div>
            ))}
          </div>
        )}

        {data && (data.plan_id === "plus" || data.plan_id === "premium") && (
          <div
            className="mt-12 rounded-2xl border border-emerald-200 bg-emerald-50 p-6 text-emerald-900 max-w-2xl"
            data-testid="result-pdf-placeholder"
          >
            <p className="font-medium">PDF deliverable</p>
            <p className="mt-1 text-sm text-emerald-800/90">
              Your custom organization PDF will be generated as part of this
              plan and emailed to you shortly. We’ll define the full PDF layout
              with you in the next phase.
            </p>
          </div>
        )}

        <div className="mt-12">
          <a href="/" className="btn-primary" data-testid="result-home-cta">
            Transform another room
          </a>
        </div>
      </main>
      <Footer />
    </div>
  );
}
