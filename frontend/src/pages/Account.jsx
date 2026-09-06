import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { useAuth } from "../context/AuthContext";
import { api, apiErrorMessage } from "../lib/api";

const SPACE_LABELS = {
    closet: "Closet",
    garage: "Garage",
    laundry_room: "Laundry room",
    pantry: "Pantry",
    mudroom: "Mudroom",
    storage: "Storage area",
    kids_room: "Kids' room",
    home_office: "Home office",
    living_room: "Living room",
    bedroom: "Bedroom",
    other: "Other",
};

const STATUS_STYLES = {
    new: "bg-slate-100 text-slate-700",
    processing: "bg-amber-50 text-amber-800",
    paid: "bg-sky-50 text-sky-800",
    pdf_ready: "bg-emerald-50 text-emerald-800",
    delivered: "bg-emerald-50 text-emerald-800",
    error: "bg-rose-50 text-rose-800",
};

function photoSrc(url) {
    if (!url) return null;
    if (url.startsWith("http")) return url;
    return `${process.env.REACT_APP_BACKEND_URL || ""}${url}`;
}

export default function Account() {
    const { member, loading } = useAuth();
    const navigate = useNavigate();
    const [spaces, setSpaces] = useState([]);
    const [usage, setUsage] = useState(member?.usage || null);
    const [fetching, setFetching] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        if (loading) return;
        if (!member) {
            navigate("/login?next=/account");
            return;
        }
        let cancelled = false;
        (async () => {
            try {
                const { data } = await api.get("/me/spaces");
                if (cancelled) return;
                setSpaces(data.spaces || []);
                setUsage(data.usage || member.usage);
            } catch (err) {
                if (!cancelled) setError(apiErrorMessage(err, "Could not load your spaces."));
            } finally {
                if (!cancelled) setFetching(false);
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [loading, member, navigate]);

    if (loading || !member) {
        return (
            <div className="min-h-screen bg-slate-50">
                <Header />
                <main className="container-app py-20 text-center text-slate-500">Loading your account…</main>
            </div>
        );
    }

    const canFree = usage?.can_generate_free !== false && (usage?.free_generations_used || 0) < 1;
    const used = usage?.free_generations_used ?? 0;

    return (
        <div className="min-h-screen bg-slate-50">
            <Header />
            <main className="container-app py-12 md:py-16" data-testid="account-page">
                <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
                    <div>
                        <span className="eyebrow">Your account</span>
                        <h1 className="mt-4 font-display text-4xl font-light tracking-tight text-slate-900">
                            Welcome back, {member.name?.split(" ")[0] || "there"}
                        </h1>
                        <p className="mt-2 text-slate-600">
                            Every space you create stays here. We email the PDF Blueprint when it&apos;s ready.
                        </p>
                    </div>
                    {canFree ? (
                        <Link to="/intake?plan=free" className="btn-primary" data-testid="account-new-space">
                            Create a space
                        </Link>
                    ) : (
                        <a href="/#packages" className="btn-primary" data-testid="account-upgrade">
                            Organize another space
                        </a>
                    )}
                </div>

                <div
                    className={`mt-8 rounded-2xl border p-5 ${
                        canFree ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"
                    }`}
                    data-testid="account-usage"
                >
                    <p className={`text-sm font-medium ${canFree ? "text-emerald-900" : "text-amber-950"}`}>
                        {canFree
                            ? `Free plan: ${used} of 1 Blueprint used. Your first space is included.`
                            : "You've used your free Blueprint. Plus ($10) and Premium ($20) unlock another space."}
                    </p>
                    {!canFree && (
                        <p className="mt-1 text-sm text-amber-800">
                            Paid plans still go through Stripe checkout. Your existing spaces stay in this account.
                        </p>
                    )}
                </div>

                <section className="mt-12">
                    <h2 className="font-display text-2xl font-medium text-slate-900">Your spaces</h2>
                    {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}
                    {fetching ? (
                        <p className="mt-6 text-slate-500">Loading spaces…</p>
                    ) : spaces.length === 0 ? (
                        <div
                            className="mt-6 rounded-3xl border border-dashed border-slate-300 bg-white px-8 py-14 text-center"
                            data-testid="account-empty"
                        >
                            <p className="font-display text-2xl font-light text-slate-900">No spaces yet</p>
                            <p className="mt-2 text-slate-600">
                                Upload a closet, garage, laundry room, pantry, or mudroom to get your first plan.
                            </p>
                            <Link to="/intake?plan=free" className="btn-primary mt-6" data-testid="account-empty-cta">
                                Start my free Blueprint
                            </Link>
                        </div>
                    ) : (
                        <div className="mt-6 grid grid-cols-1 gap-5 md:grid-cols-2" data-testid="account-spaces">
                            {spaces.map((space) => {
                                const thumb =
                                    photoSrc(space.deliverable?.front_view_url) ||
                                    photoSrc(
                                        typeof space.photos?.[0] === "string"
                                            ? space.photos[0]
                                            : space.photos?.[0]?.url
                                    );
                                const status = space.status || "new";
                                return (
                                    <article
                                        key={space.id}
                                        className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm"
                                        data-testid={`space-card-${space.id}`}
                                    >
                                        <div className="h-40 bg-slate-100">
                                            {thumb ? (
                                                <img
                                                    src={thumb}
                                                    alt=""
                                                    className="h-full w-full object-cover"
                                                />
                                            ) : (
                                                <div className="flex h-full items-center justify-center text-sm text-slate-400">
                                                    Photos processing
                                                </div>
                                            )}
                                        </div>
                                        <div className="p-5">
                                            <div className="flex items-start justify-between gap-3">
                                                <h3 className="font-display text-xl font-medium text-slate-900">
                                                    {SPACE_LABELS[space.space_type] || space.space_type}
                                                </h3>
                                                <span
                                                    className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${
                                                        STATUS_STYLES[status] || STATUS_STYLES.new
                                                    }`}
                                                >
                                                    {status.replace("_", " ")}
                                                </span>
                                            </div>
                                            <p className="mt-2 text-sm text-slate-600">
                                                {(space.package_id || "free").replace(/^./, (ch) => ch.toUpperCase())} plan
                                                {space.created_at
                                                    ? ` · ${new Date(space.created_at).toLocaleDateString()}`
                                                    : ""}
                                            </p>
                                            <p className="mt-3 text-sm text-slate-500">
                                                {space.email_sent
                                                    ? "Blueprint emailed to you."
                                                    : "We'll email the PDF when it's ready."}
                                            </p>
                                        </div>
                                    </article>
                                );
                            })}
                        </div>
                    )}
                </section>
            </main>
            <Footer />
        </div>
    );
}
