import React from "react";
import { ChoiceGroup, ErrorText, SelectField, TextField } from "./fields";
import {
    BUDGETS,
    CLIMATE_OPTIONS,
    KEEP_OPTIONS,
    KIDS_ACTIVITIES,
    KIDS_STAGES,
    LIMIT_OPTIONS,
    MEASURE_MODES,
    MEASURE_UNITS,
    PALETTES,
    SHOP_COUNTRIES,
    STYLES,
    VISUAL_MODES,
    climateMentioned,
    contradictions,
    measurementReasons,
    measurementsNeeded,
    shoppingLocationNeeded,
    spaceQuestion,
} from "../../lib/intake/model";

function SpaceQuestion({ form, update, errors }) {
    const q = spaceQuestion(form.space_type);
    if (!q) return null;
    const answers = form.space_answers;
    const set = (patch) => update({ space_answers: { ...answers, ...patch } });
    if (q.kind === "kids") {
        return (
            <div className="space-y-4">
                <ChoiceGroup
                    id="space_activities"
                    legend={q.legend}
                    multiple
                    options={KIDS_ACTIVITIES}
                    value={answers.activities}
                    onChange={(v) => set({ activities: v })}
                    error={errors.space_activities}
                />
                <SelectField
                    id="space_stage"
                    label="Child's stage"
                    optional
                    hint="Helps us set reach heights. We never need birth dates."
                    value={answers.stage}
                    onChange={(v) => set({ stage: v })}
                    options={KIDS_STAGES}
                    placeholder="Prefer not to say"
                />
            </div>
        );
    }
    if (q.kind === "garage") {
        return (
            <div className="space-y-4">
                <ChoiceGroup
                    id="space_vehicle"
                    legend="Does a vehicle need to park here?"
                    options={[
                        { id: "yes", label: "Yes" },
                        { id: "no", label: "No" },
                    ]}
                    value={answers.vehicle}
                    onChange={(v) => set({ vehicle: v })}
                    error={errors.space_vehicle}
                />
                <TextField
                    id="space_large_items"
                    label="What large items must fit?"
                    optional
                    hint="e.g. two bikes, a dog bath, a lawn mower."
                    value={answers.large_items}
                    onChange={(v) => set({ large_items: v })}
                    maxLength={160}
                />
            </div>
        );
    }
    return (
        <TextField
            id="space_text"
            label={q.legend}
            optional
            hint="A few words is enough."
            value={answers.text}
            onChange={(v) => set({ text: v })}
            maxLength={160}
        />
    );
}

function Measurements({ form, update, errors }) {
    const m = form.measurements;
    const set = (patch) => update({ measurements: { ...m, ...patch } });
    const reasons = measurementReasons(form);
    return (
        <section
            aria-labelledby="measure-heading"
            className="space-y-4 rounded-2xl border border-sky-200 bg-sky-50/60 p-4"
            data-testid="measurements"
        >
            <div>
                <h2 id="measure-heading" className="text-sm font-semibold text-slate-900">
                    Can you add the measurements for the area we&apos;re changing?
                </h2>
                <p className="mt-1 text-sm text-slate-600">
                    We&apos;re asking because {reasons.join(" and ")}. A photo alone can&apos;t confirm sizes.
                </p>
            </div>
            <ChoiceGroup
                id="measure_mode"
                legend="Measurements"
                options={MEASURE_MODES}
                value={form.measure_mode}
                onChange={(v) => update({ measure_mode: v })}
                error={errors.measure_mode}
                columns=""
            />
            {form.measure_mode === "provided" && (
                <div className="space-y-4">
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                        <TextField
                            id="measure_width"
                            label="Width"
                            inputMode="decimal"
                            value={m.width}
                            onChange={(v) => set({ width: v })}
                            error={errors.measure_width}
                        />
                        <TextField
                            id="measure_length"
                            label="Length"
                            inputMode="decimal"
                            value={m.length}
                            onChange={(v) => set({ length: v })}
                            error={errors.measure_length}
                        />
                        <SelectField
                            id="measure_unit"
                            label="Unit"
                            value={m.unit}
                            onChange={(v) => set({ unit: v })}
                            options={MEASURE_UNITS}
                        />
                    </div>
                    <TextField
                        id="measure_fixed"
                        label="Doors, windows and fixed items"
                        hint="Where they are and anything that can't move, e.g. “door on the left wall, 30 in from the corner; water heater back right”."
                        multiline
                        rows={2}
                        value={m.fixed}
                        onChange={(v) => set({ fixed: v })}
                        error={errors.measure_fixed}
                        maxLength={300}
                    />
                    <TextField
                        id="measure_items"
                        label="Sizes of the items or spot that must fit"
                        hint="e.g. “car 15 ft long”, “niche 30 in wide × 80 in tall”."
                        multiline
                        rows={2}
                        value={m.items}
                        onChange={(v) => set({ items: v })}
                        error={errors.measure_items}
                        maxLength={300}
                    />
                </div>
            )}
            {form.measure_mode === "not_to_scale" && (
                <p className="text-sm text-slate-700" data-testid="not-to-scale-note">
                    Your Room Flow will be a functional map, not to scale. We won&apos;t claim exact fits — check sizes
                    before you buy or install.
                </p>
            )}
        </section>
    );
}

function Contradictions({ form, onResolve, error }) {
    const list = contradictions(form);
    if (!list.length) return null;
    return (
        <section
            id="contradictions"
            tabIndex={-1}
            aria-labelledby="contradictions-heading"
            className="space-y-3 rounded-2xl border border-amber-300 bg-amber-50 p-4"
            data-testid="contradictions"
        >
            <h2 id="contradictions-heading" className="text-sm font-semibold text-amber-900">
                Quick check before we continue
            </h2>
            {list.map((c) => (
                <div key={c.id} role="group" aria-labelledby={`conflict-${c.id}`} data-testid={`conflict-${c.id}`}>
                    <p id={`conflict-${c.id}`} className="text-sm text-amber-900">
                        {c.message}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2">
                        {c.options.map((o) => (
                            <button
                                key={o.id}
                                type="button"
                                className="btn-ghost !px-4 !py-2 text-sm"
                                onClick={() => onResolve(c.id, o.id)}
                                data-testid={`resolve-${c.id}-${o.id}`}
                            >
                                {o.label}
                            </button>
                        ))}
                    </div>
                </div>
            ))}
            <ErrorText id="contradictions" error={error} />
        </section>
    );
}

export default function StepNeeds({ form, update, plan, errors, onResolve }) {
    const choose = form.visual_mode === "choose_style";
    return (
        <div className="space-y-7">
            <ChoiceGroup
                id="keep"
                legend="What needs to stay?"
                options={KEEP_OPTIONS}
                value={form.keep}
                onChange={(v) => update({ keep: v })}
                error={errors.keep}
                columns=""
            />
            {form.keep === "keep_selected" && (
                <TextField
                    id="keep_items"
                    label="Which items need to stay?"
                    hint="A short list is fine. You can point to a photo, e.g. “the white dresser in Photo 1”."
                    multiline
                    rows={2}
                    value={form.keep_items}
                    onChange={(v) => update({ keep_items: v })}
                    error={errors.keep_items}
                    maxLength={300}
                />
            )}

            <ChoiceGroup
                id="limits"
                legend="Any limits we should respect?"
                hint="Choose all that apply."
                multiple
                options={LIMIT_OPTIONS}
                value={form.limits}
                onChange={(v) => update({ limits: v })}
                error={errors.limits}
            />
            {form.limits.includes("other") && (
                <TextField
                    id="limit_other"
                    label="Other limit"
                    value={form.limit_other}
                    onChange={(v) => update({ limit_other: v })}
                    error={errors.limit_other}
                    maxLength={160}
                />
            )}

            <TextField
                id="change_avoid"
                label="Anything you want to change or avoid?"
                optional
                hint="e.g. “avoid open cubes”, “move the desk away from the window”."
                multiline
                rows={2}
                value={form.change_avoid}
                onChange={(v) => update({ change_avoid: v })}
                error={errors.change_avoid}
                maxLength={300}
            />

            <ChoiceGroup
                id="budget"
                legend="What's your budget for changes and purchases?"
                hint="This is what you'd spend on the space itself — not the FlowSpace price."
                options={BUDGETS}
                value={form.budget}
                onChange={(v) => update({ budget: v })}
                error={errors.budget}
                columns="grid-cols-2 sm:grid-cols-3"
            />
            {form.budget === "not_sure" && (
                <p className="-mt-4 text-sm text-slate-600">
                    No problem — we&apos;ll focus on reorganizing what you have and show purchases as optional.
                </p>
            )}

            <label className="flex items-start gap-3 text-sm text-slate-800">
                <input
                    type="checkbox"
                    id="needs_exact_fit"
                    className="mt-0.5 h-4 w-4 accent-emerald-600"
                    checked={form.needs_exact_fit}
                    onChange={(e) => update({ needs_exact_fit: e.target.checked })}
                    data-testid="needs-exact-fit"
                />
                <span>
                    Something new needs to fit an exact spot
                    <span className="block text-xs text-slate-500">e.g. a niche, a wall section, or between fixtures.</span>
                </span>
            </label>

            <SpaceQuestion form={form} update={update} errors={errors} />

            {measurementsNeeded(form) && <Measurements form={form} update={update} errors={errors} />}

            {climateMentioned(form) && (
                <SelectField
                    id="climate"
                    label="Which condition should we account for?"
                    optional
                    hint="For practical tips only — not a technical inspection of your home."
                    value={form.climate}
                    onChange={(v) => update({ climate: v })}
                    options={CLIMATE_OPTIONS}
                    placeholder="Choose one…"
                />
            )}

            {shoppingLocationNeeded(form, plan) && (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <SelectField
                        id="shop_country"
                        label="Where will you shop?"
                        hint="So shopping links match your market."
                        value={form.shop_country}
                        onChange={(v) => update({ shop_country: v })}
                        options={SHOP_COUNTRIES}
                        placeholder="Choose a country…"
                        error={errors.shop_country}
                    />
                    <TextField
                        id="shop_postal"
                        label="ZIP / postal code"
                        optional
                        hint="Only if local availability matters. No street address needed."
                        value={form.shop_postal}
                        onChange={(v) => update({ shop_postal: v })}
                        maxLength={12}
                        autoComplete="postal-code"
                    />
                </div>
            )}

            <div className="rounded-2xl border border-slate-200">
                <h2 className="m-0">
                    <button
                        type="button"
                        className="flex w-full items-center justify-between gap-3 rounded-2xl px-4 py-3 text-left text-sm font-medium text-slate-800"
                        aria-expanded={form.visual_open}
                        aria-controls="visual-panel"
                        onClick={() => update({ visual_open: !form.visual_open })}
                        data-testid="visual-toggle"
                    >
                        <span>
                            Any visual preferences? <span className="font-normal text-slate-500">(optional)</span>
                        </span>
                        <span aria-hidden="true">{form.visual_open ? "−" : "+"}</span>
                    </button>
                </h2>
                {form.visual_open && (
                    <div id="visual-panel" className="space-y-5 border-t border-slate-100 p-4">
                        <ChoiceGroup
                            id="visual_mode"
                            legend="Visual direction"
                            hint="By default we keep your existing items and walls. A palette never means repainting or replacing furniture unless you ask."
                            options={VISUAL_MODES}
                            value={form.visual_mode}
                            onChange={(v) => update({ visual_mode: v })}
                            columns=""
                        />
                        {choose && (
                            <>
                                <ChoiceGroup
                                    id="style"
                                    legend="Style"
                                    options={STYLES}
                                    value={form.style}
                                    onChange={(v) => update({ style: v })}
                                    error={errors.style}
                                    columns="grid-cols-2 sm:grid-cols-3"
                                />
                                <ChoiceGroup
                                    id="palette"
                                    legend="Palette"
                                    options={PALETTES}
                                    value={form.palette}
                                    onChange={(v) => update({ palette: v })}
                                    error={errors.palette}
                                    columns="grid-cols-2 sm:grid-cols-3"
                                />
                            </>
                        )}
                    </div>
                )}
            </div>

            <Contradictions form={form} onResolve={onResolve} error={errors.contradictions} />
        </div>
    );
}
