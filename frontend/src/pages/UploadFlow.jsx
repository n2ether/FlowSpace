import { useState, useCallback, useEffect } from "react";
import { useDropzone } from "react-dropzone";
import { useParams, useNavigate, useSearchParams, Link } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import BudgetModal from "@/components/BudgetModal";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const fileToBase64 = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });

export default function UploadFlow() {
  const { planId } = useParams();
  const [params] = useSearchParams();
  const sessionId = params.get("session_id");
  const navigate = useNavigate();

  const [plan, setPlan] = useState(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [roomType, setRoomType] = useState("");
  const [notes, setNotes] = useState("");
  const [photos, setPhotos] = useState([]); // { dataUrl, file }
  const [submitting, setSubmitting] = useState(false);
  const [showBudget, setShowBudget] = useState(false);

  useEffect(() => {
    axios.get(`${API}/plans`).then((r) => {
      const p = r.data[planId];
      if (!p) {
        toast.error("Invalid plan");
        navigate("/");
        return;
      }
      setPlan({ id: planId, ...p });
    });
  }, [planId, navigate]);

  const maxPhotos = plan?.max_photos || 0;

  const onDrop = useCallback(
    async (accepted) => {
      const remaining = maxPhotos - photos.length;
      const files = accepted.slice(0, remaining);
      const next = [];
      for (const f of files) {
        const dataUrl = await fileToBase64(f);
        next.push({ dataUrl, name: f.name });
      }
      setPhotos((prev) => [...prev, ...next]);
      if (accepted.length > remaining) {
        toast.warning(`Only ${maxPhotos} photos allowed on ${plan?.name}`);
      }
    },
    [maxPhotos, photos.length, plan]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/jpeg": [], "image/png": [], "image/webp": [] },
    multiple: true,
    disabled: !plan || photos.length >= maxPhotos,
  });

  const removePhoto = (idx) => {
    setPhotos((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleSubmit = () => {
    if (!email) return toast.error("Please enter your email");
    if (photos.length === 0) return toast.error("Upload at least one photo");
    setShowBudget(true);
  };

  const handleConfirmBudget = async (budget) => {
    try {
      setSubmitting(true);
      toast.info("Generating your AI transformation… this can take 20–60s.");
      const res = await axios.post(`${API}/submissions`, {
        name: name || null,
        email,
        plan_id: planId,
        room_type: roomType || null,
        notes: notes || null,
        budget: budget || null,
        photos_base64: photos.map((p) => p.dataUrl),
        session_id: sessionId || null,
      });
      toast.success("Done! Here's your transformation.");
      navigate(`/result/${res.data.id}`);
    } catch (e) {
      const msg = e?.response?.data?.detail || "Could not submit. Please try again.";
      toast.error(msg);
      setSubmitting(false);
      setShowBudget(false);
    }
  };

  if (!plan) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center text-slate-500">
        Loading…
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <Header />
      <main className="container-app py-12 md:py-16" data-testid="upload-page">
        <Link
          to="/"
          className="text-sm text-slate-500 hover:text-emerald-600"
          data-testid="upload-back-link"
        >
          ← Back to home
        </Link>
        <div className="mt-4 grid grid-cols-1 gap-10 lg:grid-cols-[1.4fr_1fr]">
          <div>
            <span className="eyebrow">Upload your photos</span>
            <h1 className="mt-3 font-display text-4xl font-light tracking-tight text-slate-900 sm:text-5xl">
              {plan.name} plan: up to {plan.max_photos} photos
            </h1>
            <p className="mt-3 text-slate-600 max-w-xl">
              Drop in JPG, PNG or WebP photos of the room you want organized.
              Shoot in landscape if possible, with the full room in frame.
            </p>

            <div
              {...getRootProps()}
              className={`mt-8 cursor-pointer rounded-2xl border-2 border-dashed p-10 text-center transition-colors ${
                isDragActive
                  ? "border-emerald-500 bg-emerald-50"
                  : "border-slate-300 bg-white hover:border-emerald-400 hover:bg-emerald-50/40"
              } ${photos.length >= maxPhotos ? "opacity-50 cursor-not-allowed" : ""}`}
              data-testid="upload-dropzone"
            >
              <input {...getInputProps()} data-testid="upload-input" />
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="mx-auto mb-3 h-10 w-10 text-emerald-500"
                aria-hidden="true"
              >
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" x2="12" y1="3" y2="15" />
              </svg>
              <p className="font-medium text-slate-800">
                {isDragActive ? "Drop them here…" : "Click or drag photos here"}
              </p>
              <p className="mt-1 text-sm text-slate-500">
                {photos.length} of {maxPhotos} uploaded · JPG, PNG, WebP
              </p>
            </div>

            {photos.length > 0 && (
              <div
                className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3"
                data-testid="upload-previews"
              >
                {photos.map((p, i) => (
                  <div
                    key={i}
                    className="relative group rounded-xl overflow-hidden border border-slate-200 bg-white"
                    data-testid={`upload-preview-${i}`}
                  >
                    <img
                      src={p.dataUrl}
                      alt={p.name}
                      className="aspect-[4/3] w-full object-cover"
                    />
                    <button
                      onClick={() => removePhoto(i)}
                      className="absolute right-2 top-2 inline-flex h-7 w-7 items-center justify-center rounded-full bg-white/95 text-slate-700 shadow hover:bg-red-50 hover:text-red-600"
                      data-testid={`upload-remove-${i}`}
                      aria-label="Remove photo"
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        className="h-4 w-4"
                      >
                        <path d="M18 6 6 18" />
                        <path d="m6 6 12 12" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* SIDEBAR */}
          <aside className="lg:sticky lg:top-24 self-start">
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <p className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">
                Selected plan
              </p>
              <div className="mt-2 flex items-baseline gap-2">
                <h2 className="font-display text-3xl text-slate-900">
                  {plan.name}
                </h2>
                <span className="text-sm text-slate-500">
                  {plan.price === 0 ? "Free" : `$${plan.price.toFixed(0)}`}
                </span>
              </div>
              <ul className="mt-4 space-y-2 text-sm text-slate-600">
                <li>✓ Up to {plan.max_photos} photos</li>
                <li>✓ AI-generated organized rooms</li>
                {plan.pdf && (
                  <li className="text-slate-500" data-testid="upload-pdf-placeholder">
                    ✓ Your custom organization PDF will be generated as part of
                    this plan.
                  </li>
                )}
              </ul>

              <div className="mt-6 space-y-3">
                <div>
                  <label className="text-xs font-medium text-slate-600">
                    Your name (optional)
                  </label>
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Jane Doe"
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100"
                    data-testid="upload-name-input"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-600">
                    Email for delivery
                  </label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100"
                    data-testid="upload-email-input"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-600">
                    Room type
                  </label>
                  <select
                    value={roomType}
                    onChange={(e) => setRoomType(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100"
                    data-testid="upload-roomtype-input"
                  >
                    <option value="">Choose a room…</option>
                    <option value="bedroom">Bedroom</option>
                    <option value="garage">Garage</option>
                    <option value="closet">Closet</option>
                    <option value="laundry">Laundry room</option>
                    <option value="kitchen">Kitchen / Pantry</option>
                    <option value="living">Living room</option>
                    <option value="office">Home office</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                {plan.pdf && (
                  <div>
                    <label className="text-xs font-medium text-slate-600">
                      Notes (optional)
                    </label>
                    <textarea
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      rows={2}
                      placeholder="e.g. coastal calm, budget around $200, two kids"
                      className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100"
                      data-testid="upload-notes-input"
                    />
                  </div>
                )}
              </div>

              <button
                onClick={handleSubmit}
                disabled={submitting || photos.length === 0 || !email}
                className="btn-primary mt-6 w-full"
                data-testid="upload-submit-btn"
              >
                {submitting ? "Generating…" : "Transform my room"}
              </button>
              <p className="mt-3 text-center text-[11px] text-slate-400">
                AI processing usually takes 20–60 seconds.
              </p>
            </div>
          </aside>
        </div>
      </main>
      <Footer />
      <BudgetModal
        open={showBudget}
        submitting={submitting}
        onClose={() => !submitting && setShowBudget(false)}
        onConfirm={handleConfirmBudget}
      />
    </div>
  );
}
