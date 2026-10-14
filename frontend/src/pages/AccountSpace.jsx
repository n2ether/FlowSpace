import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Download, Loader2 } from "lucide-react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { useAuth } from "../context/AuthContext";
import { api, apiErrorMessage } from "../lib/api";

function photoSrc(url) {
    if (!url) return null;
    if (url.startsWith("http")) return url;
    return `${process.env.REACT_APP_BACKEND_URL || ""}${url}`;
}

export function filenameFrom(disposition, fallback) {
    const match = /filename="?([^";]+)"?/i.exec(disposition || "");
    return (match && match[1]) || fallback;
}

function formatPrice(value) {
    const n = Number(value);
    if (!Number.isFinite(n) || n <= 0) return "";
    return `$${n.toFixed(2).replace(/\.00$/, "")}`;
}

export default function AccountSpace() {
    const { leadId } = useParams();
    const { member, loading } = useAuth();
    const navigate = useNavigate();
    const [plan, setPlan] = useState(null);
    const [boardUrl, setBoardUrl] = useState(null);
    const [boardState, setBoardState] = useState("loading");
    const [state, setState] = useState("loading");
    const [error, setError] = useState("");
    const [downloading, setDownloading] = useState(false);
    const [downloadError, setDownloadError] = useState("");

    useEffect(() => {
        window.scrollTo({ top: 0, left: 0, behavior: "instant" });
    }, [leadId]);

    useEffect(() => {
        if (loading) return;
        if (!member) {
            navigate(`/login?next=${encodeURIComponent(`/account/spaces/${leadId}`)}`);
            return;
        }
        let cancelled = false;
        let objectUrl = null;
        (async () => {
            try {
                const { data } = await api.get(`/me/spaces/${encodeURIComponent(leadId)}/plan`);
                if (cancelled) return;
                setPlan(data);
                setState("ready");
            } catch (err) {
                if (cancelled) return;
                setState(err?.response?.status === 404 ? "missing" : "error");
                setError(apiErrorMessage(err, "We couldn't load this plan."));
                return;
            }
            try {
                const res = await api.get(`/me/spaces/${encodeURIComponent(leadId)}/board`, {
                    responseType: "blob",
                });
                if (cancelled) return;
                objectUrl = URL.createObjectURL(res.data);
                setBoardUrl(objectUrl);
                setBoardState("ready");
            } catch {
                if (!cancelled) setBoardState("error");
            }
        })();
        return () => {
            cancelled = true;
            if (objectUrl) URL.revokeObjectURL(objectUrl);
        };
    }, [loading, member, navigate, leadId]);

    async function downloadPdf() {
        setDownloading(true);
        setDownloadError("");
        try {
            const res = await api.get(`/me/spaces/${encodeURIComponent(leadId)}/pdf`, { responseType: "blob" });
            const url = URL.createObjectURL(res.data);
            const a = document.createElement("a");
            a.href = url;
            a.download = filenameFrom(res.headers?.["content-disposition"], "FlowSpace_Design_Plan.pdf");
            document.body.appendChild(a);
            a.click();
            a.remove();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch {
            setDownloadError("The PDF didn't download. Please try again in a moment.");
        } finally {
            setDownloading(false);
        }
    }

    const isDraft = plan && !(plan.approved && plan.status === "delivered");
    const afters = plan?.afters || [];

    return (
        <div className="fs-editorial min-h-screen">
            <Header />
            <main className="mx-auto w-full max-w-3xl px-5 pb-16 pt-6 sm:px-8 sm:pt-10" data-testid="space-plan-page">
                <Link
                    to="/account"
                    className="fs-muted inline-flex min-h-[44px] items-center gap-2 text-sm font-medium hover:text-[#2b2520]"
                    data-testid="space-plan-back"
                >
                    <ArrowLeft className="h-4 w-4" aria-hidden="true" />
                    My Spaces
                </Link>

                {(loading || state === "loading") && (
                    <p className="fs-muted mt-10 flex items-center gap-2 text-sm" data-testid="space-plan-loading">
                        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                        Opening your plan…
                    </p>
                )}

                {state === "missing" && (
                    <div className="fs-panel mt-8 px-6 py-10 text-center" data-testid="space-plan-missing">
                        <p className="fs-title text-2xl">We couldn&apos;t find this plan</p>
                        <p className="fs-muted mt-2 text-sm">It may still be in progress, or it belongs to another account.</p>
                        <Link to="/account" className="fs-btn-warm mt-6">
                            Back to My Spaces
                        </Link>
                    </div>
                )}

                {state === "error" && (
                    <div className="fs-panel mt-8 px-6 py-10 text-center" data-testid="space-plan-error">
                        <p className="fs-title text-2xl">Something went wrong</p>
                        <p className="fs-muted mt-2 text-sm">{error}</p>
                    </div>
                )}

                {state === "ready" && plan && (
                    <>
                        <header className="mt-6">
                            <p className="fs-kicker">Your Design Plan</p>
                            <h1 className="fs-title mt-3 text-3xl sm:text-4xl" data-testid="space-plan-title">
                                {plan.title || "Your space"}
                            </h1>
                        </header>

                        {isDraft && (
                            <div
                                className="mt-6 rounded-2xl border border-[#e3d3bf] bg-[#f1e7da] px-5 py-4"
                                role="status"
                                data-testid="space-plan-draft-banner"
                            >
                                <p className="text-sm font-semibold uppercase tracking-[0.14em] text-[#6b5643]">
                                    In review – draft
                                </p>
                                <p className="mt-1 text-sm leading-relaxed text-[#6b5643]">
                                    Our beta team is still reviewing this plan. Details may change before we email
                                    your final version.
                                </p>
                            </div>
                        )}

                        {plan.summary && (
                            <p className="mt-6 text-base leading-relaxed" data-testid="space-plan-summary">
                                {plan.summary}
                            </p>
                        )}

                        <section className="mt-8" aria-labelledby="board-heading">
                            <h2 id="board-heading" className="fs-kicker">
                                Design board
                            </h2>
                            <div className="fs-panel mt-3 overflow-hidden">
                                {boardState === "ready" && boardUrl ? (
                                    <img
                                        src={boardUrl}
                                        alt={`Design board for ${plan.title || "your space"}`}
                                        className="block h-auto w-full"
                                        data-testid="space-plan-board"
                                    />
                                ) : boardState === "error" ? (
                                    <p className="fs-muted px-5 py-10 text-center text-sm" data-testid="space-plan-board-error">
                                        The board image isn&apos;t available right now.
                                    </p>
                                ) : (
                                    <p className="fs-muted flex items-center justify-center gap-2 px-5 py-16 text-sm">
                                        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                                        Preparing your board…
                                    </p>
                                )}
                            </div>
                        </section>

                        {afters.length > 0 && (
                            <section className="mt-10" aria-labelledby="afters-heading">
                                <h2 id="afters-heading" className="fs-kicker">
                                    Your space, reimagined
                                </h2>
                                <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2" data-testid="space-plan-afters">
                                    {afters.map((after, index) => (
                                        <figure key={`${after.after_url}-${index}`} className="fs-panel overflow-hidden">
                                            <img
                                                src={photoSrc(after.after_url)}
                                                alt={`Organized view ${index + 1}`}
                                                loading="lazy"
                                                className="block h-auto w-full"
                                            />
                                        </figure>
                                    ))}
                                </div>
                            </section>
                        )}

                        {plan.zones?.length > 0 && (
                            <section className="mt-10" aria-labelledby="zones-heading">
                                <h2 id="zones-heading" className="fs-kicker">
                                    Zones
                                </h2>
                                <ul className="fs-panel mt-3 divide-y divide-[#eee6dc]">
                                    {plan.zones.map((zone, index) => (
                                        <li key={`${zone.title}-${index}`} className="px-5 py-4">
                                            <p className="font-medium text-[#2b2520]">{zone.title}</p>
                                            {zone.desc && <p className="fs-muted mt-1 text-sm leading-relaxed">{zone.desc}</p>}
                                        </li>
                                    ))}
                                </ul>
                            </section>
                        )}

                        {plan.shopping_list?.length > 0 && (
                            <section className="mt-10" aria-labelledby="shopping-heading">
                                <h2 id="shopping-heading" className="fs-kicker">
                                    Shopping list
                                </h2>
                                <ul className="fs-panel mt-3 divide-y divide-[#eee6dc]">
                                    {plan.shopping_list.map((item, index) => (
                                        <li key={`${item.name}-${index}`} className="flex items-baseline justify-between gap-4 px-5 py-3 text-sm">
                                            <span>
                                                {item.name}
                                                {item.qty > 1 ? <span className="fs-muted"> × {item.qty}</span> : null}
                                            </span>
                                            <span className="fs-muted shrink-0">{formatPrice(item.price)}</span>
                                        </li>
                                    ))}
                                </ul>
                            </section>
                        )}

                        <div className="mt-10">
                            <button
                                type="button"
                                onClick={downloadPdf}
                                disabled={downloading}
                                className="fs-btn-warm w-full sm:w-auto"
                                data-testid="space-plan-download"
                            >
                                {downloading ? (
                                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                                ) : (
                                    <Download className="h-4 w-4" aria-hidden="true" />
                                )}
                                {downloading ? "Preparing PDF…" : "Download PDF"}
                            </button>
                            {downloadError && (
                                <p className="mt-3 text-sm text-[#9a4b3c]" role="alert">
                                    {downloadError}
                                </p>
                            )}
                        </div>
                    </>
                )}
            </main>
            <Footer />
        </div>
    );
}
