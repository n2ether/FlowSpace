import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { adminClient } from "../lib/api";

const BACKEND = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "");

function mediaUrl(url) {
    if (!url) return "";
    if (/^https?:\/\//i.test(url)) return url;
    if (!BACKEND) return url;
    return `${BACKEND}${url.startsWith("/") ? "" : "/"}${url}`;
}

function Section({ title, testId, children }) {
    return (
        <section className="mt-4 rounded-2xl bg-white p-4 shadow-sm" data-testid={testId}>
            <h2 className="text-sm font-semibold uppercase tracking-[0.14em] text-[#1F3D2C]">{title}</h2>
            <div className="mt-3 space-y-3 text-base leading-relaxed text-[#2a2622]">{children}</div>
        </section>
    );
}

function RoomPlan({ plan }) {
    const places = Array.isArray(plan?.places) ? plan.places : [];
    const legend = Array.isArray(plan?.legend) ? plan.legend : [];
    const path = Array.isArray(plan?.path) ? plan.path : [];
    const points = path
        .filter((point) => Array.isArray(point) && point.length >= 2)
        .map(([x, y]) => `${Number(x) * 100},${Number(y) * 100}`)
        .join(" ");
    const doorY = path[0] && Array.isArray(path[0]) ? Number(path[0][1]) * 100 : 32;
    return (
        <Section title="Room flow" testId="blueprint-plan">
            <div className="relative mx-auto aspect-[5/4] w-full overflow-hidden rounded-2xl border-[3px] border-[#1F3D2C] bg-[#faf6ef]">
                <p className="absolute left-1/2 top-2 -translate-x-1/2 text-xs font-semibold tracking-wide text-[#C17B4A]">
                    {plan?.window || "Window"}
                </p>
                <p
                    className="absolute left-2 text-xs font-semibold text-[#1F3D2C]"
                    style={{ top: `calc(${doorY}% - 0.9rem)` }}
                >
                    {plan?.door || "Door"}
                </p>
                {points ? (
                    <svg
                        className="pointer-events-none absolute inset-0 h-full w-full"
                        viewBox="0 0 100 100"
                        preserveAspectRatio="none"
                        aria-hidden="true"
                    >
                        <polyline
                            points={points}
                            fill="none"
                            stroke="#C17B4A"
                            strokeWidth="1.6"
                            strokeLinejoin="round"
                            strokeLinecap="round"
                            vectorEffect="non-scaling-stroke"
                        />
                    </svg>
                ) : null}
                {places.map((place) => {
                    const box = Array.isArray(place.box) ? place.box : [0.08, 0.08, 0.32, 0.28];
                    const [l, t, r, b] = box;
                    const zone = place.zone || place.label;
                    return (
                        <div
                            key={place.id || place.label}
                            className="absolute flex items-center justify-center gap-1 rounded-xl border-2 border-[#1F3D2C] bg-[#cfe2d7] px-1 text-center text-xs font-semibold leading-tight text-[#1F3D2C]"
                            style={{
                                left: `${l * 100}%`,
                                top: `${t * 100}%`,
                                width: `${Math.max(8, (r - l) * 100)}%`,
                                height: `${Math.max(8, (b - t) * 100)}%`,
                            }}
                        >
                            {place.number ? (
                                <span className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-[#1F3D2C] text-[10px] text-white">
                                    {place.number}
                                </span>
                            ) : null}
                            <span>{zone}</span>
                        </div>
                    );
                })}
                <p className="pointer-events-none absolute left-[8%] top-[40%] text-xs font-semibold text-[#C17B4A]">
                    {plan?.circulation || "Clear path"}
                </p>
            </div>
            {legend.length ? (
                <ol className="grid grid-cols-2 gap-x-3 gap-y-1 text-sm" data-testid="blueprint-zone-legend">
                    {legend.map((item) => (
                        <li key={`${item.number}-${item.name}`}>
                            <span className="font-semibold text-[#1F3D2C]">{item.number}.</span> {item.name}
                        </li>
                    ))}
                </ol>
            ) : null}
            {plan?.caption ? <p className="text-base text-[#6e655c]">{plan.caption}</p> : null}
        </Section>
    );
}

function Gallery({ items, onOpen }) {
    const [index, setIndex] = useState(0);
    const startX = useRef(null);
    const count = items.length;
    const current = items[Math.min(index, count - 1)] || items[0];

    const go = (delta) => setIndex((value) => Math.min(count - 1, Math.max(0, value + delta)));

    if (!current) return null;

    return (
        <section className="mt-4" data-testid="blueprint-gallery">
            <h2 className="text-sm font-semibold uppercase tracking-[0.14em] text-[#1F3D2C]">Room views</h2>
            <p className="mt-1 text-base text-[#6e655c]">One complete after for each photo. Swipe, or use the buttons.</p>
            <div
                className="mt-3 overflow-hidden rounded-2xl bg-[#e7e1d6]"
                style={{ touchAction: "pan-y" }}
                onTouchStart={(event) => {
                    startX.current = event.touches[0].clientX;
                }}
                onTouchEnd={(event) => {
                    if (startX.current == null) return;
                    const dx = event.changedTouches[0].clientX - startX.current;
                    if (dx < -40) go(1);
                    if (dx > 40) go(-1);
                    startX.current = null;
                }}
            >
                <button
                    type="button"
                    className="flex h-72 w-full items-center justify-center"
                    onClick={() => current.after_url && onOpen(current)}
                    data-testid="blueprint-gallery-slide"
                >
                    {current.after_url ? (
                        <img
                            src={mediaUrl(current.after_url)}
                            alt={current.caption || "Organized view"}
                            className="max-h-72 max-w-full object-contain"
                        />
                    ) : (
                        <span className="px-6 text-center text-base text-[#1F3D2C]">
                            {current.caption || "This view is still coming"}. This angle is not filled from another photo.
                        </span>
                    )}
                </button>
            </div>
            <p className="mt-3 text-center text-sm text-[#6e655c]">
                {current.caption || "Organized view"} · {index + 1} / {count}
            </p>
            <div className="mt-2 grid grid-cols-2 gap-3">
                <button
                    type="button"
                    className="min-h-[44px] rounded-full border border-[#1F3D2C] px-4 text-base text-[#1F3D2C]"
                    onClick={() => go(-1)}
                    disabled={index === 0}
                >
                    Previous
                </button>
                <button
                    type="button"
                    className="min-h-[44px] rounded-full border border-[#1F3D2C] px-4 text-base text-[#1F3D2C]"
                    onClick={() => go(1)}
                    disabled={index >= count - 1}
                >
                    Next
                </button>
            </div>
        </section>
    );
}

export default function BlueprintPreview() {
    const { leadId } = useParams();
    const navigate = useNavigate();
    const location = useLocation();
    const token = typeof window !== "undefined" ? localStorage.getItem("cs_admin_token") : "";
    const [doc, setDoc] = useState(null);
    const [error, setError] = useState("");
    const [reviewVisible, setReviewVisible] = useState(true);
    const [open, setOpen] = useState(null);

    useEffect(() => {
        if (!token) {
            navigate(`/admin/login?next=${encodeURIComponent(location.pathname)}`);
            return;
        }
        let cancelled = false;
        adminClient(token)
            .get(`/admin/leads/${leadId}/deliverable/presentation`)
            .then((res) => {
                if (!cancelled) setDoc(res.data);
            })
            .catch((err) => {
                if (cancelled) return;
                if (err?.response?.status === 401) {
                    localStorage.removeItem("cs_admin_token");
                    navigate(`/admin/login?next=${encodeURIComponent(location.pathname)}`);
                    return;
                }
                setError("This preview could not be loaded.");
            });
        return () => {
            cancelled = true;
        };
    }, [leadId, navigate, location.pathname, token]);

    const heroItem = (doc?.gallery || []).find((item) => item.after_url) || null;

    return (
        <div className="min-h-screen overflow-x-hidden bg-[#f3eee6] text-[#2a2622]" data-testid="blueprint-preview">
            {reviewVisible ? (
                <div className="bg-[#1F3D2C] px-4 py-3 text-white" data-testid="blueprint-review-bar">
                    <div className="mx-auto flex w-full max-w-[430px] items-start justify-between gap-3">
                        <p className="min-w-0 text-sm leading-snug">
                            Review preview. Nothing has been sent, and this does not mark the package final.
                        </p>
                        <button type="button" className="shrink-0 text-sm underline" onClick={() => setReviewVisible(false)}>
                            Hide
                        </button>
                    </div>
                </div>
            ) : null}

            <main className="mx-auto w-full max-w-[430px] px-4 pb-16 pt-5">
                {!doc && !error ? <p className="text-base text-[#6e655c]">Loading the Blueprint…</p> : null}
                {error ? <p className="text-base text-[#1F3D2C]">{error}</p> : null}
                {doc ? (
                    <>
                        <header>
                            <p className="font-display text-2xl text-[#1F3D2C]">FlowSpace</p>
                            <p className="text-sm text-[#6e655c]">Clear space. Create flow. Live better.</p>
                            <h1 className="mt-4 font-display text-3xl leading-tight text-[#2a2622]" data-testid="blueprint-title">
                                {doc.headline}
                            </h1>
                            <p className="mt-2 text-sm font-semibold uppercase tracking-[0.12em] text-[#1F3D2C]">
                                Boutique · Functional · Intentional · Affordable
                            </p>
                            {doc.tagline ? <p className="mt-2 text-base text-[#6e655c]">{doc.tagline}</p> : null}
                        </header>

                        <div className="mt-4 overflow-hidden rounded-2xl bg-[#e7e1d6]" data-testid="blueprint-hero">
                            {heroItem ? (
                                <button type="button" className="block w-full" onClick={() => setOpen(heroItem)}>
                                    <img
                                        src={mediaUrl(heroItem.after_url)}
                                        alt={doc.hero_label || "Organized view"}
                                        className="max-h-[28rem] w-full object-contain"
                                    />
                                </button>
                            ) : (
                                <p className="px-4 py-16 text-center text-base text-[#1F3D2C]">
                                    {doc.hero_label || "Organized view unavailable"}
                                </p>
                            )}
                        </div>
                        <p className="mt-3 text-base leading-relaxed" data-testid="blueprint-outcome">
                            {doc.outcome || doc.intro}
                        </p>

                        {(doc.gallery || []).length ? <Gallery items={doc.gallery} onOpen={setOpen} /> : null}

                        <Section title="What changed and why" testId="blueprint-changes">
                            {(doc.changes || []).length ? (
                                doc.changes.map((change, index) => (
                                    <article key={`${change.title}-${index}`}>
                                        <p className="font-semibold text-[#1F3D2C]">
                                            {index + 1}. {change.title}
                                        </p>
                                        <p>{change.body}</p>
                                    </article>
                                ))
                            ) : (
                                <p>The companion guide lists each change.</p>
                            )}
                        </Section>

                        <RoomPlan plan={doc.plan} />

                        <Section title="Palette" testId="blueprint-palette">
                            <div className="flex flex-wrap gap-3">
                                {(doc.palette || []).map((swatch) => (
                                    <div key={swatch.hex + swatch.name} className="w-24">
                                        <div className="h-12 rounded-lg border border-[#e7e1d6]" style={{ background: swatch.hex }} />
                                        <p className="mt-1 text-sm font-semibold">{swatch.name}</p>
                                        {swatch.note ? <p className="text-sm text-[#6e655c]">{swatch.note}</p> : null}
                                    </div>
                                ))}
                            </div>
                        </Section>

                        <Section title="Shopping" testId="blueprint-shopping">
                            {(doc.shopping || []).length ? (
                                doc.shopping.map((item) => (
                                    <p key={item.name}>
                                        <span className="font-semibold">{item.name}</span>
                                        <span className="text-[#6e655c]"> · Qty {item.qty} · {item.price}</span>
                                    </p>
                                ))
                            ) : (
                                <p>The shopping list is in the companion guide.</p>
                            )}
                            <p className="font-semibold text-[#1F3D2C]">List total {doc.shopping_total}</p>
                        </Section>

                        <Section title="Roadmap" testId="blueprint-roadmap">
                            {(doc.roadmap || []).map((step, index) => (
                                <p key={step.title || index}>
                                    <span className="font-semibold text-[#1F3D2C]">
                                        {index + 1}. {step.title}
                                    </span>{" "}
                                    {step.body}
                                </p>
                            ))}
                        </Section>

                        <Section title="Safety" testId="blueprint-safety">
                            {(doc.safety || []).map((line) => (
                                <p key={line}>{line}</p>
                            ))}
                        </Section>

                        <Section title="Climate" testId="blueprint-climate">
                            {(doc.climate || []).map((line) => (
                                <p key={line}>{line}</p>
                            ))}
                        </Section>

                        <Section title="Weekly reset" testId="blueprint-reset">
                            <p>{doc.reset}</p>
                        </Section>
                    </>
                ) : null}
            </main>

            {open ? (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4"
                    role="dialog"
                    aria-modal="true"
                    data-testid="blueprint-fullscreen"
                >
                    <button
                        type="button"
                        className="absolute right-4 top-4 min-h-11 rounded-full bg-white px-4 text-base text-[#1F3D2C]"
                        onClick={() => setOpen(null)}
                    >
                        Close
                    </button>
                    <img
                        src={mediaUrl(open.after_url)}
                        alt={open.caption || "Organized view"}
                        className="max-h-[100dvh] max-w-[100vw] object-contain"
                    />
                </div>
            ) : null}
        </div>
    );
}
