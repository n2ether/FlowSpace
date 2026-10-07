import React from "react";
import { Link } from "react-router-dom";
import { TextField } from "./fields";
import {
    BUDGETS,
    KEEP_OPTIONS,
    KIDS_ACTIVITIES,
    KIDS_STAGES,
    MEASURE_UNITS,
    PALETTES,
    PLAN_SCOPE,
    PRIORITIES,
    PRODUCT_NAME,
    ROOM_FLOW_COPY,
    STYLES,
    VISUAL_MODES,
    acceptedPhotos,
    coverageLimitations,
    isConceptual,
    labelFor,
    limitsText,
    photoLabel,
    planLine,
    roomFlowMode,
    spaceLabel,
    spaceQuestion,
} from "../../lib/intake/model";

function Row({ term, children }) {
    return (
        <div className="grid grid-cols-1 gap-1 py-2 sm:grid-cols-[10rem_1fr] sm:gap-4">
            <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{term}</dt>
            <dd className="min-w-0 break-words text-sm text-slate-900">{children}</dd>
        </div>
    );
}

function Section({ id, title, onEdit, editLabel, children }) {
    return (
        <section aria-labelledby={`${id}-title`} className="rounded-2xl border border-slate-200 p-4" data-testid={`review-${id}`}>
            <div className="flex items-center justify-between gap-3">
                <h2 id={`${id}-title`} className="text-sm font-semibold text-slate-900">
                    {title}
                </h2>
                {onEdit && (
                    <button
                        type="button"
                        onClick={onEdit}
                        className="rounded-full px-3 py-1.5 text-sm font-medium text-emerald-700 hover:bg-emerald-50"
                        aria-label={editLabel}
                        data-testid={`review-edit-${id}`}
                    >
                        Edit
                    </button>
                )}
            </div>
            <dl className="mt-2 divide-y divide-slate-100">{children}</dl>
        </section>
    );
}

function spaceDetail(form) {
    const q = spaceQuestion(form.space_type);
    const a = form.space_answers;
    if (q?.kind === "kids") {
        const acts = a.activities.map((x) => labelFor(KIDS_ACTIVITIES, x)).join(", ");
        const stage = a.stage ? ` · ${labelFor(KIDS_STAGES, a.stage)}` : "";
        return acts ? `${acts}${stage}` : "";
    }
    if (q?.kind === "garage") {
        const v = a.vehicle === "yes" ? "Vehicle parks here" : a.vehicle === "no" ? "No vehicle" : "";
        return [v, a.large_items.trim()].filter(Boolean).join(" · ");
    }
    return a.text.trim();
}

export default function StepReview({ form, update, plan, photos, errors, member, onEdit, planId }) {
    const accepted = acceptedPhotos(photos);
    const conceptual = isConceptual(form, plan);
    const flow = roomFlowMode(form, plan);
    const limitations = coverageLimitations(form, photos, plan);
    const visual = labelFor(VISUAL_MODES, form.visual_mode) || "Match my current space";
    const visualDetail =
        form.visual_mode === "choose_style"
            ? ` — ${[labelFor(STYLES, form.style), labelFor(PALETTES, form.palette)].filter(Boolean).join(", ")}`
            : "";
    const detail = spaceDetail(form);
    const m = form.measurements;

    return (
        <div className="space-y-5">
            <Section id="space" title="Space & goal" onEdit={() => onEdit(0)} editLabel="Edit space and goal">
                <Row term="Space">{spaceLabel(form)}</Row>
                <Row term="Main priority">{labelFor(PRIORITIES, form.priority)}</Row>
                {form.specifics.trim() && <Row term="Specifics">{form.specifics.trim()}</Row>}
            </Section>

            <Section id="photos" title="Photos & coverage" onEdit={() => onEdit(1)} editLabel="Edit photos">
                {conceptual ? (
                    <Row term="Photos">None — conceptual plan</Row>
                ) : (
                    <>
                        <Row term="Accepted photos">
                            <ul className="space-y-0.5">
                                {accepted.map((p, i) => (
                                    <li key={p.id || i}>
                                        {photoLabel(photos.indexOf(p))}
                                        {p.label ? ` — ${p.label}` : ""}
                                        <span className="text-slate-500"> ({p.shot === "detail" ? "close-up" : "wide view"})</span>
                                    </li>
                                ))}
                            </ul>
                        </Row>
                        <Row term="Area covered">
                            {form.coverage === "whole" ? "The whole area" : "Only the areas shown in the photos"}
                        </Row>
                    </>
                )}
            </Section>

            <Section id="needs" title="What the plan works around" onEdit={() => onEdit(2)} editLabel="Edit essentials">
                <Row term="Keep">
                    {labelFor(KEEP_OPTIONS, form.keep)}
                    {form.keep === "keep_selected" && form.keep_items.trim() ? `: ${form.keep_items.trim()}` : ""}
                </Row>
                <Row term="Limits">
                    {limitsText(form)}
                    {form.layout_within_current ? " (improve within the current layout)" : ""}
                </Row>
                {form.change_avoid.trim() && <Row term="Change or avoid">{form.change_avoid.trim()}</Row>}
                <Row term="Budget for changes">{labelFor(BUDGETS, form.budget)}</Row>
                <Row term="Visual">{`${visual}${visualDetail}`}</Row>
                {detail && <Row term="How it's used">{detail}</Row>}
                {form.measure_mode === "provided" && (
                    <Row term="Measurements">
                        {m.width} × {m.length} {labelFor(MEASURE_UNITS, m.unit)}
                        {m.fixed.trim() ? ` · Fixed: ${m.fixed.trim()}` : ""}
                        {m.items.trim() ? ` · Must fit: ${m.items.trim()}` : ""}
                    </Row>
                )}
            </Section>

            <section
                aria-labelledby="scope-title"
                className="rounded-2xl border border-emerald-200 bg-emerald-50/60 p-4"
                data-testid="review-scope"
            >
                <h2 id="scope-title" className="text-sm font-semibold text-slate-900">
                    What you&apos;ll receive — {PRODUCT_NAME}, {plan.name}
                </h2>
                <ul className="mt-2 space-y-1.5 text-sm text-slate-700">
                    {PLAN_SCOPE[plan.id].map((s) => (
                        <li key={s.title}>
                            <span className="font-medium text-slate-900">{s.title}:</span> {s.body}
                        </li>
                    ))}
                </ul>
                <p className="mt-3 text-sm font-medium text-slate-900" data-testid="room-flow-mode">
                    Room Flow: {ROOM_FLOW_COPY[flow]}
                </p>
                <h3 className="mt-3 text-sm font-semibold text-slate-900">Coverage and limitations</h3>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-700" data-testid="review-limitations">
                    {limitations.map((n) => (
                        <li key={n}>{n}</li>
                    ))}
                </ul>
                <p className="mt-3 text-xs text-slate-600">
                    During the beta, every plan is reviewed by our team before it&apos;s sent. We&apos;ll email you when
                    yours is ready.
                </p>
            </section>

            <section aria-labelledby="contact-title" className="rounded-2xl border border-slate-200 p-4" data-testid="review-contact">
                <h2 id="contact-title" className="text-sm font-semibold text-slate-900">
                    Contact
                </h2>
                <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <TextField
                        id="name"
                        label="Your name"
                        value={form.name}
                        onChange={(v) => update({ name: v })}
                        autoComplete="name"
                        error={errors.name}
                    />
                    {member ? (
                        <div>
                            <p className="mb-2 text-sm font-medium text-slate-800">Email</p>
                            <p className="text-sm text-slate-700">{member.email}</p>
                        </div>
                    ) : (
                        <TextField
                            id="email"
                            label="Email"
                            hint="Where we'll send your Design Plan."
                            type="email"
                            value={form.email}
                            onChange={(v) => update({ email: v })}
                            autoComplete="email"
                            error={errors.email}
                        />
                    )}
                </div>
            </section>

            <section aria-labelledby="account-title" className="rounded-2xl border border-slate-200 p-4" data-testid="review-account">
                <h2 id="account-title" className="text-sm font-semibold text-slate-900">
                    Account
                </h2>
                {member ? (
                    <p className="mt-2 text-sm text-slate-600" data-testid="intake-signed-in">
                        Signed in as {member.email}. This plan will be saved to your account.
                    </p>
                ) : (
                    <>
                        <TextField
                            id="password"
                            className="mt-3"
                            label="Create a password to keep this plan"
                            hint="At least 8 characters. Your account keeps every space you plan."
                            type="password"
                            value={form.password}
                            onChange={(v) => update({ password: v })}
                            autoComplete="new-password"
                            error={errors.password}
                        />
                        <p className="mt-3 text-xs text-slate-600">
                            Already a member?{" "}
                            <Link
                                to={`/login?next=${encodeURIComponent(`/intake?plan=${planId}`)}`}
                                className="font-medium text-emerald-700 hover:text-emerald-800"
                                data-testid="intake-login-link"
                            >
                                Log in
                            </Link>{" "}
                            — your answers stay saved.
                        </p>
                    </>
                )}
            </section>

            <section aria-labelledby="payment-title" className="rounded-2xl border border-slate-200 p-4" data-testid="review-payment">
                <h2 id="payment-title" className="text-sm font-semibold text-slate-900">
                    {plan.price === 0 ? "Plan" : "Payment"}
                </h2>
                <p className="mt-2 text-base font-medium text-slate-900" data-testid="review-plan-line">
                    {planLine(plan)}
                </p>
                <p className="mt-1 text-sm text-slate-600">
                    {plan.price === 0
                        ? "No payment needed."
                        : "Secure checkout with Stripe on the next page. You'll only be charged once."}
                </p>
            </section>
        </div>
    );
}
