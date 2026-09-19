import React from "react";
import { RotateCw } from "lucide-react";

const DEFAULT_COPY = {
    landscapeTitle: "This photo is landscape — is the ceiling up?",
    exifTitle: "We straightened this from your phone — is the ceiling up?",
    ambiguousTitle: "Quick check: is the ceiling at the top?",
    body: "Ceiling fans and lights should sit at the top of the frame. Windows should look like windows, not the floor.",
    rotate: "Rotate",
    confirm: "Ceiling is up",
};

export default function PhotoOrientationNudge({
    previewUrl,
    reason = "landscape",
    copy,
    onRotate,
    onConfirm,
}) {
    const c = { ...DEFAULT_COPY, ...copy };
    const title =
        reason === "exif" ? c.exifTitle : reason === "ambiguous" ? c.ambiguousTitle : c.landscapeTitle;

    return (
        <div
            className="rounded-2xl border border-emerald-200 bg-emerald-50/80 p-4 shadow-sm"
            data-testid="photo-orientation-nudge"
        >
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
                {previewUrl && (
                    <div className="relative mx-auto h-36 w-36 shrink-0 overflow-hidden rounded-xl border border-slate-200 bg-white sm:mx-0">
                        <img
                            src={previewUrl}
                            alt="Check that the ceiling is at the top"
                            className="h-full w-full object-contain"
                            data-testid="photo-orientation-preview"
                        />
                    </div>
                )}
                <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-slate-900" data-testid="photo-orientation-title">
                        {title}
                    </p>
                    <p className="mt-1 text-xs leading-relaxed text-slate-600">{c.body}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                        <button
                            type="button"
                            onClick={onRotate}
                            className="inline-flex items-center rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:border-emerald-400 hover:text-emerald-800"
                            data-testid="photo-orientation-rotate"
                        >
                            <RotateCw className="mr-1.5 h-3.5 w-3.5" />
                            {c.rotate}
                        </button>
                        <button
                            type="button"
                            onClick={onConfirm}
                            className="inline-flex items-center rounded-full bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700"
                            data-testid="photo-orientation-confirm"
                        >
                            {c.confirm}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
