import { useEffect, useState, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import BeforeAfterSlider from "@/components/BeforeAfterSlider";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const POLL_MS = 3500;
const MAX_WAIT_MS = 8 * 60 * 1000; // 8 min hard ceiling

export default function Result() {
  const { submissionId } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [downloading, setDownloading] = useState(false);
  const pollTimer = useRef(null);
  const startedAt = useRef(Date.now());

  useEffect(() => {
    let cancelled = false;

    const fetchOnce = async () => {
      try {
        const r = await axios.get(`${API}/submissions/${submissionId}`);
        if (cancelled) return;
        setData(r.data);
        if (
          r.data.status === "completed" ||
          r.data.status === "failed" ||
          Date.now() - startedAt.current > MAX_WAIT_MS
        ) {
          return; // stop polling
        }
        pollTimer.current = setTimeout(fetchOnce, POLL_MS);
      } catch (e) {
        if (cancelled) return;
        if (e?.response?.status === 404) {
          setErr("We couldn't find that submission. It may have expired.");
        } else {
          // transient — keep polling
          pollTimer.current = setTimeout(fetchOnce, POLL_MS);
        }
      }
    };

    fetchOnce();
    return () => {
      cancelled = true;
      if (pollTimer.current) clearTimeout(pollTimer.current);
    };
  }, [submissionId]);

  const isPaid = data && (data.plan_id === "plus" || data.plan_id === "premium");
  const pdfReady = data && data.pdf_available;
  const inProgress = data && (data.status === "pending" || data.status === "processing");
  const failed = data && data.status === "failed";
  const completed = data && data.status === "completed";

  const handleDownload = async () => {
    try {
      setDownloading(true);
      const res = await axios.get(`${API}/submissions/${submissionId}/pdf`, {
        responseType: "blob",
      });
      const url = URL.createObjectURL(res.data);
      const link = document.createElement("a");
      link.href = url;
      const room = (data?.room_type || "Room").toString();
      const roomPretty =
        room.charAt(0).toUpperCase() + room.slice(1).toLowerCase();
      link.download = `FlowSpace-${roomPretty}-Design-Plan.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (e) {
      const msg =
        e?.response?.status === 402
          ? "Upgrade to Plus or Premium to unlock your full PDF Design Plan."
          : "Could not download the PDF — please try again in a moment.";
      toast.error(msg);
    } finally {
      setDownloading(false);
    }
  };

  // Progress percent (photos + a chunk for PDF if applicable)
  const total = data?.photos_total || 0;
  const done = data?.photos_done || 0;
  const photoPct = total > 0 ? done / total : 0;
  const pdfPctSlot = isPaid ? 0.15 : 0; // PDF is roughly the last 15% of the work
  const rawPct = photoPct * (1 - pdfPctSlot) + (pdfReady ? pdfPctSlot : 0);
  const pctLabel = Math.min(99, Math.round(rawPct * 100));

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
        <div className="mt-4 flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <span className="eyebrow">
              {completed ? "Your transformation" : inProgress ? "Generating…" : "Result"}
            </span>
            <h1 className="mt-3 font-display text-4xl font-light tracking-tight text-slate-900 sm:text-5xl">
              {err
                ? "We couldn\u2019t find that."
                : completed
                ? "Here\u2019s your space, reorganized."
                : inProgress
                ? "Working on your transformation…"
                : failed
                ? "We hit a snag."
                : "Loading…"}
            </h1>
            {completed && (
              <p className="mt-3 text-slate-600">
                Drag any slider to compare.{" "}
                {isPaid
                  ? "Your PDF Design Plan is attached to the confirmation email — or download it here."
                  : "A copy of your transformation has been emailed to you."}
              </p>
            )}
          </div>
          {completed && isPaid && pdfReady && (
            <button
              onClick={handleDownload}
              disabled={downloading}
              className="btn-primary self-start lg:self-end"
              data-testid="result-download-pdf-btn"
            >
              {downloading ? "Preparing…" : "Download My Design Plan"}
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" x2="12" y1="15" y2="3" />
              </svg>
            </button>
          )}
        </div>

        {err && (
          <p className="mt-10 text-red-600" data-testid="result-error">
            {err}
          </p>
        )}

        {!data && !err && (
          <p className="mt-10 text-slate-500">Loading your results…</p>
        )}

        {/* PROGRESS STATE */}
        {inProgress && (
          <div
            className="mt-10 rounded-2xl border border-emerald-200 bg-white p-8 shadow-sm max-w-2xl"
            data-testid="result-progress-card"
          >
            <div className="flex items-center justify-between text-sm font-medium text-slate-700">
              <span>
                {done} of {total} photo{total === 1 ? "" : "s"} transformed
                {isPaid && done === total && !pdfReady && " · finalizing PDF…"}
              </span>
              <span className="text-emerald-700 tabular-nums" data-testid="result-progress-pct">
                {pctLabel}%
              </span>
            </div>
            <div className="mt-3 h-2.5 w-full overflow-hidden rounded-full bg-emerald-100">
              <div
                className="h-full bg-emerald-500 transition-all duration-700 ease-out"
                style={{ width: `${pctLabel}%` }}
              />
            </div>
            <p className="mt-5 text-sm text-slate-600">
              Your AI room transformation takes roughly{" "}
              <strong>30–60 seconds per photo</strong>. Feel free to keep this
              tab open — we&rsquo;ll show your results here the moment
              they&rsquo;re ready, and a copy is being emailed to you.
            </p>
            <div className="mt-5 flex items-center gap-3 text-xs text-slate-500">
              <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-emerald-500" />
              Still working… please don&rsquo;t refresh.
            </div>
          </div>
        )}

        {/* FAILED STATE */}
        {failed && (
          <div
            className="mt-10 rounded-2xl border border-red-200 bg-red-50 p-6 max-w-2xl"
            data-testid="result-failed-card"
          >
            <p className="font-medium text-red-900">
              Something went wrong while generating your transformation.
            </p>
            <p className="mt-1 text-sm text-red-800">
              {data?.error || "Please try again — or contact us at contact@flowspace.solutions if it keeps happening."}
            </p>
            <a
              href="/#packages"
              className="btn-primary mt-4 inline-flex"
              data-testid="result-retry-cta"
            >
              Try again
            </a>
          </div>
        )}

        {/* RESULTS */}
        {data && completed && (
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
                      AI transformation failed for this photo — please retry
                      this room.
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

        {data && completed && isPaid && pdfReady && (
          <div
            className="mt-12 rounded-2xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-white p-6 max-w-3xl"
            data-testid="result-pdf-ready"
          >
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-xs uppercase tracking-widest font-semibold text-emerald-700">
                  PDF Design Plan
                </p>
                <p className="mt-1 font-display text-2xl text-slate-900">
                  Your custom design plan is ready.
                </p>
                <p className="mt-1 text-sm text-slate-600 max-w-md">
                  Floor plan, room needs, shopping list, wall color, action
                  plan — all in one polished printable PDF.
                </p>
              </div>
              <button
                onClick={handleDownload}
                disabled={downloading}
                className="btn-primary shrink-0"
                data-testid="result-download-pdf-btn-secondary"
              >
                {downloading ? "Preparing…" : "Download PDF"}
              </button>
            </div>
          </div>
        )}

        {data && completed && !isPaid && (
          <div
            className="mt-12 rounded-2xl border border-slate-200 bg-white p-6 max-w-3xl shadow-sm"
            data-testid="result-upgrade-prompt"
          >
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-xs uppercase tracking-widest font-semibold text-emerald-700">
                  Unlock the full plan
                </p>
                <p className="mt-1 font-display text-2xl text-slate-900">
                  Upgrade to Plus or Premium to unlock your full PDF Design
                  Plan.
                </p>
                <p className="mt-1 text-sm text-slate-600 max-w-md">
                  Floor plan, shopping list, wall colors, action steps —
                  everything you need to make this space real.
                </p>
              </div>
              <a
                href="/#packages"
                className="btn-primary shrink-0"
                data-testid="result-upgrade-cta"
              >
                See Plus &amp; Premium
              </a>
            </div>
          </div>
        )}

        {completed && (
          <div className="mt-12">
            <a href="/" className="btn-primary" data-testid="result-home-cta">
              Transform another room
            </a>
          </div>
        )}
      </main>
      <Footer />
    </div>
  );
}
