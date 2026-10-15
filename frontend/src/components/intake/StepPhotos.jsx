import React, { useRef } from "react";
import { Link } from "react-router-dom";
import PhotoOrientationNudge from "../PhotoOrientationNudge";
import { ChoiceGroup, ErrorText, TextField } from "./fields";
import {
    COVERAGE_OPTIONS,
    SHOT_TYPES,
    angleTip,
    blockingIssues,
    needsAcknowledgement,
    photoLabel,
} from "../../lib/intake/model";

const BACKEND = process.env.REACT_APP_BACKEND_URL || "";

function PhotoCard({ photo, index, onChange, onReplace, onRemove, disabled }) {
    const replaceRef = useRef(null);
    const label = photoLabel(index);
    const blocks = blockingIssues(photo);
    const warns = (photo.issues || []).filter((i) => i.severity === "warn");
    const status = blocks.length
        ? { text: "Needs replacing", tone: "text-red-700" }
        : needsAcknowledgement(photo)
          ? { text: "Check this photo", tone: "text-amber-700" }
          : { text: "Accepted", tone: "text-emerald-700" };
    const issueId = `photo-${index}-issues`;
    return (
        <li
            className="rounded-2xl border border-slate-200 bg-white p-4"
            aria-labelledby={`photo-${index}-title`}
            data-testid={`photo-card-${index}`}
        >
            <div className="flex flex-col gap-4 sm:flex-row">
                <div className="h-40 w-full shrink-0 overflow-hidden rounded-xl border border-slate-200 bg-slate-100 sm:h-28 sm:w-28">
                    <img
                        src={`${BACKEND}${photo.url}`}
                        alt={`${label}${photo.label ? ` — ${photo.label}` : ""}`}
                        className="h-full w-full object-cover"
                    />
                </div>
                <div className="min-w-0 flex-1 space-y-3">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <h3 id={`photo-${index}-title`} className="text-sm font-semibold text-slate-900">
                            {label}
                        </h3>
                        <span className={`text-xs font-medium ${status.tone}`} data-testid={`photo-status-${index}`}>
                            {status.text}
                        </span>
                    </div>
                    {(blocks.length > 0 || warns.length > 0) && (
                        <ul id={issueId} className="space-y-1 text-sm" data-testid={`photo-issues-${index}`}>
                            {[...blocks, ...warns].map((issue) => (
                                <li
                                    key={issue.code}
                                    className={issue.severity === "block" ? "text-red-700" : "text-amber-800"}
                                >
                                    {issue.message}
                                </li>
                            ))}
                        </ul>
                    )}
                    <TextField
                        id={`photo-${index}-label`}
                        label={`Label for ${label}`}
                        optional
                        hint="e.g. “Closet left wall”. Leave blank if you like."
                        value={photo.label || ""}
                        onChange={(v) => onChange({ label: v })}
                        maxLength={40}
                    />
                    <ChoiceGroup
                        id={`photo-${index}-shot`}
                        legend={`What does ${label} show?`}
                        options={SHOT_TYPES}
                        value={photo.shot || "wide"}
                        onChange={(v) => onChange({ shot: v })}
                    />
                    <div className="flex flex-wrap gap-2">
                        {needsAcknowledgement(photo) && blocks.length === 0 && (
                            <button
                                type="button"
                                className="btn-ghost !px-4 !py-2 text-sm"
                                onClick={() => onChange({ acknowledged: true })}
                                aria-describedby={issueId}
                                data-testid={`photo-keep-${index}`}
                            >
                                Keep this photo
                            </button>
                        )}
                        <button
                            type="button"
                            className="btn-ghost !px-4 !py-2 text-sm"
                            onClick={() => replaceRef.current?.click()}
                            disabled={disabled}
                            data-testid={`photo-replace-${index}`}
                        >
                            Replace {label}
                        </button>
                        <input
                            ref={replaceRef}
                            type="file"
                            accept="image/*"
                            className="sr-only"
                            tabIndex={-1}
                            aria-hidden="true"
                            onChange={(e) => {
                                const file = e.target.files?.[0];
                                e.target.value = "";
                                if (file) onReplace(index, file);
                            }}
                            data-testid={`photo-replace-input-${index}`}
                        />
                        <button
                            type="button"
                            className="inline-flex items-center rounded-full px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50"
                            onClick={() => onRemove(index)}
                            disabled={disabled}
                            data-testid={`photo-remove-${index}`}
                        >
                            Remove {label}
                        </button>
                    </div>
                </div>
            </div>
        </li>
    );
}

export default function StepPhotos({
    form,
    update,
    plan,
    photos,
    errors,
    uploading,
    pending,
    statusMessage,
    onAddFiles,
    onReplace,
    onRemove,
    onPhotoChange,
    rotatePending,
    confirmPending,
}) {
    const full = photos.length >= plan.maxPhotos;
    const busy = uploading || Boolean(pending);
    const conceptual = form.photo_mode === "conceptual";

    return (
        <div className="space-y-7">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
                <p className="font-medium text-slate-900">
                    Upload one clear, wide view to start. Add other angles to show the areas you want included.
                </p>
                <ul className="mt-2 list-disc space-y-1 pl-5">
                    <li>Shoot from a corner or the entrance, in good light.</li>
                    <li>Show the walls and furniture that matter — no need to tidy first.</li>
                    <li>Add another angle when an important area is outside the first photo.</li>
                </ul>
                <p className="mt-2 text-slate-600">{angleTip(form.space_type)}</p>
            </div>

            <section aria-labelledby="photos-heading" id="photos">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <h2 id="photos-heading" className="text-sm font-medium text-slate-800">
                        Your photos
                    </h2>
                    <p className="text-xs text-slate-500" data-testid="photo-count">
                        {photos.length} of {plan.maxPhotos} added — the {plan.name} plan includes up to {plan.maxPhotos}
                    </p>
                </div>

                {photos.length > 0 && (
                    <ol className="mt-3 space-y-3" data-testid="photo-list">
                        {photos.map((p, i) => (
                            <PhotoCard
                                key={p.id || i}
                                photo={p}
                                index={i}
                                disabled={busy}
                                onChange={(patch) => onPhotoChange(i, patch)}
                                onReplace={onReplace}
                                onRemove={onRemove}
                            />
                        ))}
                    </ol>
                )}

                {!full && (
                    <div className="mt-3">
                        <label
                            htmlFor="photo-input"
                            className={`flex min-h-[56px] cursor-pointer items-center justify-center rounded-2xl border-2 border-dashed px-4 py-4 text-sm font-medium focus-within:ring-2 focus-within:ring-emerald-500 ${
                                busy
                                    ? "cursor-wait border-slate-200 text-slate-400"
                                    : "border-slate-300 text-slate-700 hover:border-emerald-400 hover:text-emerald-700"
                            }`}
                        >
                            {uploading && !pending ? "Uploading…" : photos.length ? "Add another angle" : "Add a photo"}
                            <input
                                id="photo-input"
                                type="file"
                                accept="image/*"
                                multiple
                                className="sr-only"
                                disabled={busy}
                                aria-describedby={errors.photos ? "photos-error" : undefined}
                                onChange={(e) => {
                                    const files = e.target.files;
                                    onAddFiles(files);
                                    e.target.value = "";
                                }}
                                data-testid="intake-photo-input"
                            />
                        </label>
                    </div>
                )}
                <p className="sr-only" aria-live="polite" data-testid="photo-live">
                    {statusMessage}
                </p>
                {pending && (
                    <div className="mt-3">
                        <PhotoOrientationNudge
                            previewUrl={pending.previewUrl}
                            reason={pending.inspection.reason}
                            onRotate={rotatePending}
                            onConfirm={confirmPending}
                        />
                    </div>
                )}
                <ErrorText id="photos" error={errors.photos} />
            </section>

            {photos.length > 0 && (
                <ChoiceGroup
                    id="coverage"
                    legend="Do these photos show the whole area you want planned?"
                    hint="One wide photo can support a plan for the area it shows. It doesn't guarantee the whole room."
                    options={COVERAGE_OPTIONS}
                    value={form.coverage}
                    onChange={(v) => update({ coverage: v })}
                    error={errors.coverage}
                    columns=""
                />
            )}

            {photos.length === 0 && (
                <section
                    aria-labelledby="no-photos-heading"
                    className="rounded-2xl border border-slate-200 p-4 text-sm text-slate-700"
                    data-testid="no-photos"
                >
                    <h2 id="no-photos-heading" className="font-medium text-slate-900">
                        Don&apos;t have a photo right now?
                    </h2>
                    <p className="mt-1">
                        Your answers are saved on this device. Come back to this page when you have a photo and pick up
                        where you left off.
                    </p>
                    {plan.price > 0 ? (
                        <p className="mt-2">
                            We only charge for a personalized {plan.name} plan once we have a usable photo of your space.
                            Want to try the idea first?{" "}
                            <Link to="/intake?plan=free" className="font-medium text-emerald-700 underline">
                                Switch to Free
                            </Link>{" "}
                            for a conceptual plan.
                        </p>
                    ) : (
                        <div className="mt-3 space-y-3">
                            <label className="flex items-start gap-3">
                                <input
                                    type="checkbox"
                                    id="photo_mode_conceptual"
                                    className="mt-0.5 h-4 w-4 accent-emerald-600"
                                    checked={conceptual}
                                    onChange={(e) =>
                                        update({
                                            photo_mode: e.target.checked ? "conceptual" : "photos",
                                            conceptual_ack: false,
                                        })
                                    }
                                    data-testid="photo-mode-conceptual"
                                />
                                <span>Continue without photos and get a conceptual plan</span>
                            </label>
                            {conceptual && (
                                <div className="rounded-xl border border-amber-200 bg-amber-50 p-3">
                                    <p className="font-medium text-amber-900">Conceptual plan — not your room</p>
                                    <p className="mt-1 text-amber-900">
                                        Without a photo we can only suggest ideas for this type of space. Images are
                                        illustrations, not an “after” of your home, and the Room Flow is an abstract zone
                                        diagram.
                                    </p>
                                    <label className="mt-3 flex items-start gap-3">
                                        <input
                                            type="checkbox"
                                            id="conceptual_ack"
                                            className="mt-0.5 h-4 w-4 accent-emerald-600"
                                            checked={form.conceptual_ack}
                                            onChange={(e) => update({ conceptual_ack: e.target.checked })}
                                            aria-describedby={errors.conceptual_ack ? "conceptual_ack-error" : undefined}
                                            aria-invalid={errors.conceptual_ack ? "true" : undefined}
                                            data-testid="conceptual-ack"
                                        />
                                        <span>I understand this is a conceptual plan, not a transformation of my room.</span>
                                    </label>
                                    <ErrorText id="conceptual_ack" error={errors.conceptual_ack} />
                                </div>
                            )}
                        </div>
                    )}
                </section>
            )}
        </div>
    );
}
