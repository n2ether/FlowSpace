import React, { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Check, Clock, Inbox, Mail, PenLine, ShieldCheck } from "lucide-react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { useAuth } from "../context/AuthContext";
import { api, apiErrorMessage } from "../lib/api";
import {
    PAYMENT_KEYS,
    STATUS_STYLES,
    displayStatus,
    estimateMinutes,
    recordProgressStart,
    serverClockOffset,
    spaceThumbnail,
    spaceTitle,
} from "../lib/projectStatus";
import { useNow } from "../lib/useNow";

const POLL_IN_PROGRESS_MS = 20000;
const POLL_IN_REVIEW_MS = 60000;

const STEPS = [
    { id: "received", label: "Request received", Icon: Inbox },
    { id: "preparing", label: "Preparing your Design Plan", Icon: PenLine },
    { id: "review", label: "Team review", Icon: ShieldCheck },
    { id: "emailed", label: "Emailed to you", Icon: Mail },
];

function activeStep(key) {
    if (PAYMENT_KEYS.has(key)) return 0;
    if (key === "in_progress") return 1;
    if (key === "in_review") return 2;
    return 3;
}

function StatusSteps({ statusKey, delayed }) {
    const active = activeStep(statusKey);
    const done = statusKey === "delivered";
    return (
        <ol className="mt-8 space-y-4" aria-label="Project progress" data-testid="project-steps">
            {STEPS.map(({ id, label, Icon }, i) => {
                const complete = done || i < active;
                const current = !done && i === active;
                return (
                    <li
                        key={id}
                        className="flex items-center gap-3"
                        aria-current={current ? "step" : undefined}
                        data-testid={`project-step-${id}`}
                    >
                        <span
                            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full border ${
                                complete
                                    ? "border-emerald-500 bg-emerald-500 text-white"
                                    : current
                                      ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                                      : "border-slate-200 bg-white text-slate-400"
                            }`}
                        >
                            {complete ? (
                                <Check className="h-4 w-4" strokeWidth={2} aria-hidden="true" />
                            ) : (
                                <Icon className="h-4 w-4" strokeWidth={1.75} aria-hidden="true" />
                            )}
                        </span>
                        <span className={`text-sm ${current ? "font-semibold text-slate-900" : complete ? "text-slate-700" : "text-slate-500"}`}>
                            {label}
                            {current && delayed && id === "preparing" ? (
                                <span className="block text-xs font-medium text-amber-700">Taking a little longer than usual</span>
                            ) : null}
                            <span className="sr-only">{complete ? " (done)" : current ? " (current step)" : ""}</span>
                        </span>
                    </li>
                );
            })}
        </ol>
    );
}

function StatusMessage({ status, space, email }) {
    const inbox = email ? <strong className="font-semibold text-slate-900 [overflow-wrap:anywhere]">{email}</strong> : "your inbox";
    if (status.key === "in_progress" && status.delayed) {
        return (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5" role="status" data-testid="project-delayed">
                <div className="flex items-start gap-3">
                    <Clock className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" strokeWidth={1.75} aria-hidden="true" />
                    <div>
                        <p className="font-semibold text-amber-900">Taking a little longer than usual</p>
                        <p className="mt-1 text-sm leading-relaxed text-amber-900">
                            Your Design Plan is still being prepared. There&apos;s nothing you need to do, and no need to keep
                            this page open. Our team reviews every plan, and we&apos;ll email it to {inbox} when it&apos;s ready.
                        </p>
                    </div>
                </div>
            </div>
        );
    }
    if (status.key === "in_progress") {
        return (
            <div className="rounded-2xl border border-sky-200 bg-sky-50 p-5" role="status" data-testid="project-in-progress">
                <p className="font-semibold text-sky-900">We&apos;re preparing your Design Plan</p>
                <p className="mt-1 text-sm leading-relaxed text-sky-900">
                    This step usually takes up to {estimateMinutes(space)} minutes. After that, our team reviews every plan
                    before we email it to {inbox}. You can close this page; nothing is lost.
                </p>
            </div>
        );
    }
    if (status.key === "in_review") {
        return (
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5" role="status" data-testid="project-in-review">
                <p className="font-semibold text-emerald-900">Your Design Plan is with our team</p>
                <p className="mt-1 text-sm leading-relaxed text-emerald-900">
                    We review every plan before it&apos;s sent, so you get one that fits your space. We&apos;ll email it to{" "}
                    {inbox} as soon as it&apos;s ready. There&apos;s nothing you need to do.
                </p>
            </div>
        );
    }
    if (status.key === "delivered") {
        return (
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5" role="status" data-testid="project-delivered">
                <p className="font-semibold text-emerald-900">Your Design Plan is in your inbox</p>
                <p className="mt-1 text-sm leading-relaxed text-emerald-900">
                    We emailed it to {inbox}. If you can&apos;t find it, check your spam folder or reply to any FlowSpace
                    email and we&apos;ll send it again.
                </p>
            </div>
        );
    }
    return (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5" role="status" data-testid="project-payment">
            <p className="font-semibold text-amber-900">{status.label}</p>
            <p className="mt-1 text-sm leading-relaxed text-amber-900">{status.note}</p>
            <a href="/#packages" className="btn-primary mt-4" data-testid="project-choose-plan">
                Choose a plan
            </a>
        </div>
    );
}

export default function ProjectStatus() {
    const { leadId } = useParams();
    const { member, loading } = useAuth();
    const navigate = useNavigate();
    const [space, setSpace] = useState(null);
    const [missing, setMissing] = useState(false);
    const [error, setError] = useState("");
    const [clockOffset, setClockOffset] = useState(0);
    const now = useNow(15000) + clockOffset;

    const load = useCallback(async () => {
        try {
            const { data } = await api.get("/me/spaces");
            const found = (data.spaces || []).find((s) => s.id === leadId) || null;
            setClockOffset(serverClockOffset(data.server_time));
            setSpace(found);
            setMissing(!found);
            setError("");
            return found;
        } catch (err) {
            setError(apiErrorMessage(err, "We couldn't load this project. Please try again."));
            return null;
        }
    }, [leadId]);

    useEffect(() => {
        if (loading) return;
        if (!member) navigate(`/login?next=${encodeURIComponent(`/account/spaces/${leadId}`)}`);
    }, [loading, member, leadId, navigate]);

    useEffect(() => {
        if (loading || !member) return;
        load();
    }, [loading, member, load]);

    const statusKey = space ? displayStatus(space, now).key : null;

    useEffect(() => {
        if (statusKey === "in_progress") recordProgressStart(leadId);
        const wait = statusKey === "in_progress" ? POLL_IN_PROGRESS_MS : statusKey === "in_review" ? POLL_IN_REVIEW_MS : 0;
        if (!wait) return undefined;
        const id = setInterval(load, wait);
        return () => clearInterval(id);
    }, [statusKey, leadId, load]);

    const status = space ? displayStatus(space, now) : null;
    const thumb = space ? spaceThumbnail(space, status) : null;

    return (
        <div className="min-h-screen bg-slate-50">
            <Header />
            <main className="container-app py-8 md:py-14" data-testid="project-page">
                <div className="mx-auto max-w-2xl">
                    <Link
                        to="/account"
                        className="inline-flex min-h-[44px] items-center gap-2 text-sm font-semibold text-emerald-700 hover:text-emerald-800"
                        data-testid="project-back"
                    >
                        <ArrowLeft className="h-4 w-4" strokeWidth={1.75} aria-hidden="true" />
                        My spaces
                    </Link>

                    {loading || (!space && !missing && !error) ? (
                        <p className="mt-8 text-slate-600">Loading your project…</p>
                    ) : missing ? (
                        <div className="mt-6 rounded-3xl border border-slate-200 bg-white p-6 sm:p-8" data-testid="project-missing">
                            <h1 className="font-display text-2xl font-light text-slate-900">We couldn&apos;t find this project</h1>
                            <p className="mt-2 text-slate-600">
                                It may belong to a different account. Your spaces are listed in My spaces.
                            </p>
                            <Link to="/account" className="btn-primary mt-6">
                                Go to My spaces
                            </Link>
                        </div>
                    ) : !space ? (
                        <p className="mt-8 text-sm text-rose-700" role="alert">
                            {error}
                        </p>
                    ) : (
                        <article className="mt-4 overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
                            {thumb ? (
                                <div className="h-48 bg-slate-100 sm:h-60">
                                    <img src={thumb} alt="Your space" className="h-full w-full object-contain" />
                                </div>
                            ) : null}
                            <div className="p-5 sm:p-8">
                                <span className="eyebrow">FlowSpace Design Plan</span>
                                <div className="mt-3 flex flex-wrap items-start justify-between gap-3">
                                    <h1
                                        className="font-display text-3xl font-light tracking-tight text-slate-900 sm:text-4xl"
                                        data-testid="project-title"
                                    >
                                        {spaceTitle(space)}
                                    </h1>
                                    <span
                                        className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide ${
                                            STATUS_STYLES[status.delayed ? "delayed" : status.key]
                                        }`}
                                        data-testid="project-status"
                                    >
                                        {status.label}
                                    </span>
                                </div>
                                <p className="mt-2 text-sm text-slate-600">
                                    {(space.package_id || "free").replace(/^./, (ch) => ch.toUpperCase())} plan
                                </p>

                                <div className="mt-6">
                                    <StatusMessage status={status} space={space} email={space.email || member?.email} />
                                </div>

                                <StatusSteps statusKey={status.key} delayed={status.delayed} />

                                {error ? (
                                    <p className="mt-6 text-sm text-slate-600" role="status">
                                        We couldn&apos;t refresh just now. We&apos;ll keep trying.
                                    </p>
                                ) : null}

                                <p className="mt-8 border-t border-slate-200 pt-6 text-sm text-slate-600">
                                    Questions? Write to{" "}
                                    <a href="mailto:help@flowspace.solutions" className="font-semibold text-emerald-700 underline">
                                        help@flowspace.solutions
                                    </a>{" "}
                                    or reply to any FlowSpace email.
                                </p>
                            </div>
                        </article>
                    )}
                </div>
            </main>
            <Footer />
        </div>
    );
}
