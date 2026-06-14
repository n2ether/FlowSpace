import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import BeforeAfterSlider from "@/components/BeforeAfterSlider";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Result() {
  const { submissionId } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    axios
      .get(`${API}/submissions/${submissionId}`)
      .then((r) => setData(r.data))
      .catch(() => setErr("Submission not found."));
  }, [submissionId]);

  const isPaid = data && (data.plan_id === "plus" || data.plan_id === "premium");
  const pdfReady = data && data.pdf_available;

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
      console.error(e);
      const msg = e?.response?.status === 402
        ? "Upgrade to Plus or Premium to unlock your full PDF Design Plan."
        : "Could not download the PDF — please try again in a moment.";
      toast.error(msg);
    } finally {
      setDownloading(false);
    }
  };

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
            <span className="eyebrow">Your transformation</span>
            <h1 className="mt-3 font-display text-4xl font-light tracking-tight text-slate-900 sm:text-5xl">
              Here&rsquo;s your space, reorganized.
            </h1>
            <p className="mt-3 text-slate-600">
              Drag any slider to compare. {isPaid ? "Your PDF Design Plan is attached to the confirmation email — or download it here." : "A copy of your transformation has been emailed to you."}
            </p>
          </div>
          {isPaid && pdfReady && (
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

        {data && isPaid && pdfReady && (
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

        {data && isPaid && !pdfReady && (
          <div
            className="mt-12 rounded-2xl border border-amber-200 bg-amber-50 p-6 max-w-2xl text-amber-900"
            data-testid="result-pdf-pending"
          >
            <p className="font-medium">Generating your PDF Design Plan…</p>
            <p className="mt-1 text-sm">
              Refresh the page in a moment — your full plan will be available
              for download here.
            </p>
          </div>
        )}

        {data && !isPaid && (
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
                See Plus & Premium
              </a>
            </div>
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
