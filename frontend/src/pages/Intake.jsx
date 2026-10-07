import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { useAuth } from "../context/AuthContext";
import { api, apiErrorCode, apiErrorMessage } from "../lib/api";
import { usePhotoUploadQueue } from "../lib/usePhotoUploadQueue";
import { ErrorSummary } from "../components/intake/fields";
import StepSpace from "../components/intake/StepSpace";
import StepPhotos from "../components/intake/StepPhotos";
import StepNeeds from "../components/intake/StepNeeds";
import StepReview from "../components/intake/StepReview";
import { measurePhoto, withIssues } from "../lib/intake/photoChecks";
import {
    DRAFT_KEY,
    PRODUCT_NAME,
    STEPS,
    buildLeadPayload,
    emptyForm,
    firstInvalidStep,
    parseDraft,
    photoLabel,
    priceLabel,
    resolveContradiction,
    resolvePlan,
    serializeDraft,
    submitLabel,
    validateStep,
} from "../lib/intake/model";

function readDraft() {
    try {
        return parseDraft(localStorage.getItem(DRAFT_KEY));
    } catch {
        return null;
    }
}

function draftHasAnswers(draft) {
    if (!draft) return false;
    return Boolean(draft.form.space_type || draft.form.priority || draft.photos.length || draft.step > 0);
}

export default function Intake() {
    const navigate = useNavigate();
    const [search] = useSearchParams();
    const planId = (search.get("plan") || "free").toLowerCase();
    const plan = resolvePlan(planId);
    const { member, signup, login, refresh } = useAuth();

    const [initialDraft] = useState(readDraft);
    const [form, setForm] = useState(() => initialDraft?.form || emptyForm());
    const [photos, setPhotos] = useState(() => initialDraft?.photos || []);
    const [step, setStep] = useState(() => initialDraft?.step || 0);
    const [showRestored, setShowRestored] = useState(() => draftHasAnswers(initialDraft));
    const [errors, setErrors] = useState({});
    const [returnToReview, setReturnToReview] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [blocked, setBlocked] = useState(false);
    const [photoStatus, setPhotoStatus] = useState("");
    const headingRef = useRef(null);
    const summaryRef = useRef(null);
    const replaceIndexRef = useRef(null);
    const stepChanged = useRef(false);

    const checked = useMemo(() => withIssues(photos), [photos]);
    const update = useCallback((patch) => setForm((f) => ({ ...f, ...patch })), []);

    useEffect(() => {
        try {
            localStorage.setItem(DRAFT_KEY, serializeDraft({ form, photos, step }));
        } catch {
            /* storage full or private mode — the flow still works without a draft */
        }
    }, [form, photos, step]);

    useEffect(() => {
        refresh();
    }, [refresh]);

    useEffect(() => {
        if (!member) return;
        setForm((f) => ({ ...f, name: f.name || member.name || "", email: member.email || f.email }));
        setBlocked(plan.price === 0 && member.usage?.can_generate_free === false);
    }, [member, plan.price]);

    useEffect(() => {
        if (!stepChanged.current) return;
        window.scrollTo({ top: 0 });
        headingRef.current?.focus();
    }, [step]);

    const uploadFile = useCallback(async (file) => {
        const replaceIndex = replaceIndexRef.current;
        replaceIndexRef.current = null;
        setPhotoStatus("Uploading photo…");
        const metrics = await measurePhoto(file);
        const fd = new FormData();
        fd.append("file", file);
        const backend = process.env.REACT_APP_BACKEND_URL || "";
        try {
            const res = await fetch(`${backend}/api/uploads/photo`, { method: "POST", body: fd });
            if (!res.ok) {
                let msg = `Upload failed (${res.status}).`;
                try {
                    const body = await res.json();
                    if (body?.detail) msg = String(body.detail);
                } catch {
                    /* not JSON */
                }
                throw new Error(msg);
            }
            const data = await res.json();
            const next = { id: data.id, url: data.url, label: "", shot: "wide", metrics, acknowledged: false };
            setPhotos((prev) => {
                if (replaceIndex !== null && replaceIndex < prev.length) {
                    const copy = [...prev];
                    copy[replaceIndex] = { ...next, label: prev[replaceIndex].label, shot: prev[replaceIndex].shot };
                    return copy;
                }
                return [...prev, next];
            });
            setForm((f) => (f.photo_mode === "conceptual" ? { ...f, photo_mode: "photos", conceptual_ack: false } : f));
            setPhotoStatus(replaceIndex !== null ? `${photoLabel(replaceIndex)} replaced.` : "Photo added.");
            setErrors((e) => {
                const { photos: _p, ...rest } = e;
                return rest;
            });
        } catch (err) {
            const message = `That photo couldn't be added: ${err?.message || "upload failed"} Try another file.`;
            setPhotoStatus(message);
            setErrors((e) => ({ ...e, photos: message }));
        }
    }, []);

    const { uploading, pending, handleFiles, rotatePending, confirmPending } = usePhotoUploadQueue({
        uploadFile,
        remainingSlots: plan.maxPhotos - photos.length,
    });

    const ctx = { form, photos: checked, plan, pending: Boolean(pending), signedIn: Boolean(member) };

    const showErrors = (errs) => {
        setErrors(errs);
        if (errs.style || errs.palette) update({ visual_open: true });
        requestAnimationFrame(() => summaryRef.current?.focus());
    };

    const goTo = (index) => {
        stepChanged.current = true;
        setErrors({});
        setStep(index);
    };

    const next = () => {
        const errs = validateStep(step, ctx);
        if (Object.keys(errs).length) {
            showErrors(errs);
            return;
        }
        if (returnToReview) {
            setReturnToReview(false);
            goTo(3);
            return;
        }
        goTo(Math.min(step + 1, STEPS.length - 1));
    };

    const back = () => {
        if (step === 0) return;
        goTo(step - 1);
    };

    const editFromReview = (index) => {
        setReturnToReview(true);
        goTo(index);
    };

    const startOver = () => {
        try {
            localStorage.removeItem(DRAFT_KEY);
        } catch {
            /* ignore */
        }
        setForm({ ...emptyForm(), name: member?.name || "", email: member?.email || "" });
        setPhotos([]);
        setShowRestored(false);
        goTo(0);
    };

    const submit = async () => {
        const invalid = firstInvalidStep(ctx);
        if (invalid >= 0) {
            setReturnToReview(true);
            goTo(invalid);
            requestAnimationFrame(() => showErrors(validateStep(invalid, ctx)));
            return;
        }
        const contactErrs = validateStep(3, ctx);
        if (Object.keys(contactErrs).length) {
            showErrors(contactErrs);
            return;
        }
        setSubmitting(true);
        setErrors({});
        try {
            if (!member) {
                let nextMember;
                const creds = { email: form.email.trim(), password: form.password };
                try {
                    nextMember = await signup({ ...creds, name: form.name.trim() });
                } catch (authErr) {
                    if (apiErrorCode(authErr) !== "EMAIL_IN_USE") throw authErr;
                    nextMember = await login(creds);
                }
                if (plan.price === 0 && nextMember?.usage?.can_generate_free === false) {
                    setBlocked(true);
                    setSubmitting(false);
                    return;
                }
            }

            const payload = buildLeadPayload(form, checked, plan, member);
            const { data: lead } = await api.post("/leads", payload);
            try {
                localStorage.removeItem(DRAFT_KEY);
            } catch {
                /* ignore */
            }

            if (plan.price === 0) {
                navigate(`/success?plan=free&lead=${lead.id}`);
                return;
            }
            const { data: checkout } = await api.post("/checkout/session", {
                package_id: plan.id,
                origin_url: window.location.origin,
                email: (member?.email || form.email).trim(),
                metadata: { lead_id: lead.id },
            });
            window.location.href = checkout.url;
        } catch (err) {
            const code = apiErrorCode(err);
            if (code === "FREE_TIER_LIMIT") setBlocked(true);
            const detail = err?.response?.data?.detail;
            if (code === "PHOTO_REQUIRED" || code === "INTAKE_INVALID") {
                const fieldErrors = {};
                (detail?.errors || []).forEach((e) => {
                    fieldErrors[e.field || "submit"] = e.message;
                });
                showErrors(Object.keys(fieldErrors).length ? fieldErrors : { submit: apiErrorMessage(err) });
            } else {
                showErrors({ submit: apiErrorMessage(err) });
            }
            setSubmitting(false);
        }
    };

    const current = STEPS[step];
    const isReview = step === STEPS.length - 1;

    return (
        <div className="min-h-screen overflow-x-hidden bg-slate-50">
            <Header />
            <main className="container-app py-10 md:py-16">
                <div className="mx-auto max-w-2xl">
                    <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
                        <div
                            className="inline-flex items-center gap-3 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm"
                            data-testid="intake-plan-badge"
                        >
                            <span className="h-2 w-2 rounded-full bg-emerald-500" aria-hidden="true" />
                            <span className="font-medium text-emerald-900">
                                {PRODUCT_NAME} · {plan.name}
                            </span>
                            <span className="text-emerald-700">
                                {priceLabel(plan)}
                                {plan.price > 0 ? " one-time" : ""}
                            </span>
                        </div>
                    </div>

                    {blocked ? (
                        <div className="rounded-3xl border border-amber-200 bg-white p-8 shadow-sm" data-testid="intake-upgrade-wall">
                            <span className="eyebrow">Free plan used</span>
                            <h1 className="mt-4 font-display text-3xl font-light text-slate-900">
                                Your free Design Plan is already in your account
                            </h1>
                            <p className="mt-3 text-slate-600">
                                The Free plan includes one Design Plan per account. Your answers are saved — choose Plus or
                                Premium to continue with this space.
                            </p>
                            <div className="mt-8 flex flex-wrap gap-3">
                                <Link to="/intake?plan=plus" className="btn-primary" data-testid="intake-upgrade-cta">
                                    Continue with Plus — $10
                                </Link>
                                <Link to="/intake?plan=premium" className="btn-ghost">
                                    Continue with Premium — $20
                                </Link>
                                <Link to="/account" className="btn-ghost" data-testid="intake-view-spaces">
                                    View my spaces
                                </Link>
                            </div>
                        </div>
                    ) : (
                        <>
                            <nav aria-label="Intake progress" className="mb-6">
                                <p className="eyebrow" data-testid="intake-step-label">
                                    Step {step + 1} of {STEPS.length}
                                </p>
                                <div
                                    role="progressbar"
                                    aria-label={`Step ${step + 1} of ${STEPS.length}: ${current.title}`}
                                    aria-valuemin={1}
                                    aria-valuemax={STEPS.length}
                                    aria-valuenow={step + 1}
                                    className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-slate-200"
                                >
                                    <div
                                        className="h-full rounded-full bg-emerald-500 transition-all"
                                        style={{ width: `${((step + 1) / STEPS.length) * 100}%` }}
                                    />
                                </div>
                                <ol className="mt-3 grid grid-cols-4 gap-2 text-[11px] font-medium text-slate-500 sm:text-xs">
                                    {STEPS.map((s, i) => (
                                        <li
                                            key={s.id}
                                            aria-current={i === step ? "step" : undefined}
                                            className={i === step ? "text-emerald-700" : i < step ? "text-slate-700" : ""}
                                        >
                                            {s.title}
                                        </li>
                                    ))}
                                </ol>
                            </nav>

                            {showRestored && (
                                <div
                                    className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900"
                                    data-testid="intake-draft-restored"
                                >
                                    <span>We saved your answers on this device. Continue where you left off.</span>
                                    <span className="flex gap-2">
                                        <button type="button" className="font-medium underline" onClick={() => setShowRestored(false)}>
                                            Continue
                                        </button>
                                        <button
                                            type="button"
                                            className="font-medium underline"
                                            onClick={startOver}
                                            data-testid="intake-start-over"
                                        >
                                            Start over
                                        </button>
                                    </span>
                                </div>
                            )}

                            <form
                                noValidate
                                onSubmit={(e) => {
                                    e.preventDefault();
                                    if (isReview) submit();
                                    else next();
                                }}
                                className="space-y-6 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-8"
                                aria-labelledby="intake-heading"
                                data-testid="intake-form"
                            >
                                <h1
                                    id="intake-heading"
                                    ref={headingRef}
                                    tabIndex={-1}
                                    className="font-display text-3xl font-light tracking-tight text-slate-900 focus:outline-none sm:text-4xl"
                                >
                                    {current.heading}
                                </h1>

                                <ErrorSummary ref={summaryRef} errors={errors} />

                                {step === 0 && <StepSpace form={form} update={update} errors={errors} />}
                                {step === 1 && (
                                    <StepPhotos
                                        form={form}
                                        update={update}
                                        plan={plan}
                                        photos={checked}
                                        errors={errors}
                                        uploading={uploading}
                                        pending={pending}
                                        statusMessage={photoStatus}
                                        onAddFiles={(files) => handleFiles(files)}
                                        onReplace={(index, file) => {
                                            replaceIndexRef.current = index;
                                            handleFiles([file], { limit: 1 });
                                        }}
                                        onRemove={(index) => {
                                            setPhotos((prev) => prev.filter((_, i) => i !== index));
                                            setPhotoStatus(`${photoLabel(index)} removed.`);
                                        }}
                                        onPhotoChange={(index, patch) =>
                                            setPhotos((prev) => prev.map((p, i) => (i === index ? { ...p, ...patch } : p)))
                                        }
                                        rotatePending={rotatePending}
                                        confirmPending={confirmPending}
                                    />
                                )}
                                {step === 2 && (
                                    <StepNeeds
                                        form={form}
                                        update={update}
                                        plan={plan}
                                        errors={errors}
                                        onResolve={(cid, oid) => setForm((f) => resolveContradiction(f, cid, oid))}
                                    />
                                )}
                                {isReview && (
                                    <StepReview
                                        form={form}
                                        update={update}
                                        plan={plan}
                                        photos={checked}
                                        errors={errors}
                                        member={member}
                                        planId={plan.id}
                                        onEdit={editFromReview}
                                    />
                                )}

                                <div className="flex flex-col-reverse gap-3 border-t border-slate-100 pt-6 sm:flex-row sm:justify-between">
                                    {step > 0 ? (
                                        <button type="button" onClick={back} className="btn-ghost justify-center" data-testid="intake-back">
                                            Back
                                        </button>
                                    ) : (
                                        <span />
                                    )}
                                    <button
                                        type="submit"
                                        disabled={submitting || (step === 1 && (uploading || Boolean(pending)))}
                                        className={`btn-primary justify-center ${submitting ? "cursor-wait opacity-60" : ""}`}
                                        data-testid={isReview ? "intake-submit" : "intake-next"}
                                    >
                                        {submitting
                                            ? "Submitting…"
                                            : isReview
                                              ? submitLabel(plan)
                                              : returnToReview
                                                ? "Save and return to review"
                                                : "Continue"}
                                    </button>
                                </div>
                            </form>
                        </>
                    )}
                </div>
            </main>
            <Footer />
        </div>
    );
}
