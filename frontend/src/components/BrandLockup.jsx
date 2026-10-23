export const TAGLINE = "Clear space. Create flow. Live better.";

// Same mark the Design Plan board draws (backend/image_board.py `_lockup`): a
// muted line house with two green flow lines inside, on a 48-unit grid.
export function BrandMark({ className = "h-8 w-8", title }) {
    return (
        <svg
            viewBox="0 0 48 48"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2.2"
            className={className}
            role={title ? "img" : undefined}
            aria-hidden={title ? undefined : "true"}
            aria-label={title}
        >
            <path d="M4 22 24 4l20 18" stroke="#5E625F" />
            <path d="M9 18v26h30V18" stroke="#5E625F" />
            <path d="M15 32c4-5 8-5 12 0" stroke="#2F5D50" />
            <path d="M22 36c4-5 8-5 12 0" stroke="#2F5D50" />
        </svg>
    );
}

export default function BrandLockup({ size = "md", showTagline = false, inverse = false }) {
    const mark = size === "lg" ? "h-11 w-11" : "h-8 w-8";
    const word = size === "lg" ? "text-2xl" : "text-lg";
    return (
        <span className="inline-flex items-center gap-2.5">
            <BrandMark className={mark} />
            <span className="flex flex-col leading-none">
                <span className={`${word} font-normal tracking-tight ${inverse ? "text-white" : "text-slate-900"}`}>
                    FlowSpace
                </span>
                {showTagline && (
                    <span
                        className={`mt-1.5 text-[11px] font-medium tracking-wide ${
                            inverse ? "text-emerald-100" : "text-slate-600"
                        }`}
                    >
                        {TAGLINE}
                    </span>
                )}
            </span>
        </span>
    );
}
