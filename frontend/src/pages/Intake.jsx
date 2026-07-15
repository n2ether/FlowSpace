import React, { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { api } from "../lib/api";

const PLANS = {
    free:    { name: "Free",    price: 0,  maxPhotos: 2 },
    plus:    { name: "Plus",    price: 10, maxPhotos: 3 },
    premium: { name: "Premium", price: 20, maxPhotos: 4 },
};

const SPACE_TYPES = [
    { id: "living_room",  label: "Living room" },
    { id: "bedroom",      label: "Bedroom" },
    { id: "closet",       label: "Closet" },
    { id: "garage",       label: "Garage" },
    { id: "pantry",       label: "Pantry" },
    { id: "laundry_room", label: "Laundry room" },
    { id: "home_office",  label: "Home office" },
    { id: "kids_room",    label: "Kids' room" },
    { id: "other",        label: "Other" },
];

const STYLES = [
    { id: "modern",       label: "Modern" },
    { id: "minimal",      label: "Minimal" },
    { id: "scandinavian", label: "Scandinavian" },
    { id: "farmhouse",    label: "Farmhouse" },
    { id: "cozy_layered", label: "Cozy & layered" },
    { id: "natural",      label: "Natural / organic" },
];

const COLORS = [
    { id: "warm_neutrals", label: "Warm neutrals" },
    { id: "white",         label: "White & light" },
    { id: "sage",          label: "Sage green" },
    { id: "earth",         label: "Earth tones" },
    { id: "blue",          label: "Soft blues" },
    { id: "wood",          label: "Wood tones" },
];

export default function Intake() {
    const navigate = useNavigate();
    const [search] = useSearchParams();
    const planId = (search.get("plan") || "free").toLowerCase();
    const plan = PLANS[planId] || PLANS.free;

    const [form, setForm] = useState({
        name: "",
        email: "",
        space_type: "",
        style: "",
        colors: "",
        problem: "",
    });
    const [photos, setPhotos] = useState([]);
    const [uploading, setUploading] = useState(false);
    const [submitting, setSubmitting] = useState(false);

    const canSubmit = useMemo(
        () =>
            form.name.trim() &&
            form.email.trim() &&
            form.space_type &&
            form.style &&
            form.colors &&
            form.problem.trim().length >= 5,
        [form]
    );

    const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

    const handleFiles = async (e) => {
        const files = Array.from(e.target.files || []).slice(0, plan.maxPhotos - photos.length);
        if (!files.length) return;
        setUploading(true);
        try {
            const uploaded = [];
            const backend = process.env.REACT_APP_BACKEND_URL || "";
            for (const file of files) {
                const fd = new FormData();
                fd.append("file", file);
                // Native fetch — the browser will set multipart/form-data with the
                // correct boundary automatically. Do NOT set Content-Type manually.
                const res = await fetch(`${backend}/api/uploads/photo`, {
                    method: "POST",
                    body: fd,
                });
                if (!res.ok) {
                    let msg = `Upload failed (${res.status})`;
                    try {
                        const errJson = await res.json();
                        if (errJson?.detail) msg = errJson.detail;
                    } catch (_) {
                        /* body wasn't JSON */
                    }
                    throw new Error(msg);
                }
                const data = await res.json();
                uploaded.push({ id: data.id, url: data.url });
            }
            setPhotos((prev) => [...prev, ...uploaded]);
        } catch (err) {
            const detail =
                err?.response?.data?.detail ||
                err?.message ||
                "Photo upload failed. Please try again.";
            toast.error(String(detail));
        } finally {
            setUploading(false);
            e.target.value = "";
        }
    };

    const removePhoto = (id) =>
        setPhotos((prev) => prev.filter((p) => p.id !== id));

    const submit = async () => {
        if (!canSubmit) return;
        setSubmitting(true);
        try {
            // Map the streamlined intake to the backend's Lead schema
            const payload = {
                name: form.name.trim(),
                email: form.email.trim(),
                space_type: form.space_type,
                package_id: planId,
                style_prefs: [form.style],
                color_prefs: [form.colors],
                biggest_challenge: form.problem.trim(),
                goals: form.problem.trim(),
                photos: photos.map((p) => p.url),
                language: "en",
            };

            const { data: lead } = await api.post("/leads", payload);

            // Free tier: automation fires immediately on the backend
            if (plan.price === 0) {
                navigate(`/success?plan=free&lead=${lead.id}`);
                return;
            }

            // Paid tier: hand off to Stripe
            const origin = window.location.origin;
            const { data: checkout } = await api.post("/checkout/session", {
                package_id: planId,
                origin_url: origin,
                email: form.email.trim(),
                metadata: { lead_id: lead.id },
            });
            window.location.href = checkout.url;
        } catch (err) {
            const msg =
                err?.response?.data?.detail ||
                err?.message ||
                "Something went wrong. Please try again.";
            toast.error(String(msg));
            setSubmitting(false);
        }
    };

    return (
        <div className="min-h-screen bg-slate-50">
            <Header />
            <main className="container-app py-12 md:py-20">
                <div className="mx-auto max-w-2xl">
                    <div className="mb-10">
                        <span className="eyebrow">Step 1 of 1</span>
                        <h1 className="mt-4 font-display text-4xl font-light tracking-tight text-slate-900 sm:text-5xl">
                            Tell us about your space
                        </h1>
                        <p className="mt-3 text-slate-600">
                            Five quick questions and you're done. We'll build your
                            personalized FlowSpace Blueprint&trade; and email it to you
                            in about two minutes.
                        </p>
                        <div className="mt-6 inline-flex items-center gap-3 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm">
                            <span className="h-2 w-2 rounded-full bg-emerald-500" />
                            <span className="font-medium text-emerald-900">
                                {plan.name} plan
                            </span>
                            <span className="text-emerald-700">
                                {plan.price === 0 ? "Free" : `$${plan.price}`}
                            </span>
                        </div>
                    </div>

                    <div className="space-y-6 rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
                        {/* 1. Space */}
                        <Field label="What kind of space are we working on?">
                            <select
                                value={form.space_type}
                                onChange={set("space_type")}
                                className="input"
                                data-testid="intake-space"
                            >
                                <option value="">Choose one…</option>
                                {SPACE_TYPES.map((s) => (
                                    <option key={s.id} value={s.id}>{s.label}</option>
                                ))}
                            </select>
                        </Field>

                        {/* 2. Style */}
                        <Field label="Which style feels most like you?">
                            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                                {STYLES.map((s) => (
                                    <Choice
                                        key={s.id}
                                        active={form.style === s.id}
                                        onClick={() => setForm((f) => ({ ...f, style: s.id }))}
                                        label={s.label}
                                        testId={`intake-style-${s.id}`}
                                    />
                                ))}
                            </div>
                        </Field>

                        {/* 3. Colors */}
                        <Field label="Pick a color palette you love">
                            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                                {COLORS.map((c) => (
                                    <Choice
                                        key={c.id}
                                        active={form.colors === c.id}
                                        onClick={() => setForm((f) => ({ ...f, colors: c.id }))}
                                        label={c.label}
                                        testId={`intake-color-${c.id}`}
                                    />
                                ))}
                            </div>
                        </Field>

                        {/* 4. Problem */}
                        <Field label="What's the main problem you want to solve?">
                            <textarea
                                rows={3}
                                value={form.problem}
                                onChange={set("problem")}
                                placeholder="e.g. Too much visual clutter, no place for my kids' art supplies, garage feels overwhelming…"
                                className="input"
                                data-testid="intake-problem"
                            />
                        </Field>

                        {/* 5. Photos (optional) */}
                        <Field
                            label={`Add photos of your space (optional — up to ${plan.maxPhotos})`}
                            hint="Helps the AI produce a more accurate render. You can skip this."
                        >
                            <div className="flex flex-wrap gap-3">
                                {photos.map((p) => (
                                    <div key={p.id} className="relative h-24 w-24 overflow-hidden rounded-xl border border-slate-200">
                                        <img
                                            src={`${process.env.REACT_APP_BACKEND_URL || ""}${p.url}`}
                                            alt="Uploaded"
                                            className="h-full w-full object-cover"
                                        />
                                        <button
                                            onClick={() => removePhoto(p.id)}
                                            className="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded-full bg-white/90 text-xs text-slate-700 shadow"
                                            aria-label="Remove"
                                        >
                                            ×
                                        </button>
                                    </div>
                                ))}
                                {photos.length < plan.maxPhotos && (
                                    <label className="flex h-24 w-24 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 text-xs text-slate-500 hover:border-emerald-400 hover:text-emerald-600">
                                        <input
                                            type="file"
                                            accept="image/*"
                                            multiple
                                            onChange={handleFiles}
                                            className="hidden"
                                            disabled={uploading}
                                        />
                                        {uploading ? "…uploading" : "+ Add photo"}
                                    </label>
                                )}
                            </div>
                        </Field>

                        {/* Contact */}
                        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                            <Field label="Your name">
                                <input
                                    value={form.name}
                                    onChange={set("name")}
                                    className="input"
                                    placeholder="Jane Doe"
                                    data-testid="intake-name"
                                />
                            </Field>
                            <Field label="Email (where we'll send your Blueprint)">
                                <input
                                    type="email"
                                    value={form.email}
                                    onChange={set("email")}
                                    className="input"
                                    placeholder="jane@example.com"
                                    data-testid="intake-email"
                                />
                            </Field>
                        </div>

                        <div className="border-t border-slate-100 pt-6">
                            <button
                                onClick={submit}
                                disabled={!canSubmit || submitting}
                                className={`btn-primary w-full justify-center ${(!canSubmit || submitting) ? "opacity-50 cursor-not-allowed" : ""}`}
                                data-testid="intake-submit"
                            >
                                {submitting
                                    ? "Submitting…"
                                    : plan.price === 0
                                    ? "Get my free Blueprint"
                                    : `Continue to payment — $${plan.price}`}
                            </button>
                            <p className="mt-3 text-center text-xs text-slate-500">
                                {plan.price === 0
                                    ? "No payment. Your Blueprint arrives by email in about 2 minutes."
                                    : "Secure payment via Stripe. Blueprint delivered by email after payment."}
                            </p>
                        </div>
                    </div>
                </div>
            </main>
            <Footer />
        </div>
    );
}

function Field({ label, hint, children }) {
    return (
        <div>
            <label className="mb-2 block text-sm font-medium text-slate-800">{label}</label>
            {children}
            {hint && <p className="mt-1.5 text-xs text-slate-500">{hint}</p>}
        </div>
    );
}

function Choice({ active, onClick, label, testId }) {
    return (
        <button
            type="button"
            onClick={onClick}
            data-testid={testId}
            className={`rounded-xl border px-4 py-3 text-sm font-medium transition-colors ${
                active
                    ? "border-emerald-500 bg-emerald-50 text-emerald-800"
                    : "border-slate-200 bg-white text-slate-700 hover:border-emerald-300 hover:text-emerald-700"
            }`}
        >
            {label}
        </button>
    );
}
