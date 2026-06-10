import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Check, Loader2, Settings, Sparkles } from "lucide-react";
import AppHeader from "../components/AppHeader";
import { Button } from "../components/ui/button";
import { authApi } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useLang } from "../context/LanguageContext";
import { toast } from "sonner";

const PLAN_FEATURES = {
    free: ["1 transformation total", "1 photo", "Watermarked image", "Basic recommendations"],
    pro: ["10 transformations / month", "Up to 3 photos per project", "HD image downloads", "PDF organization report", "Full shopping list"],
    premium: ["Unlimited transformations*", "Unlimited photos per project", "HD downloads", "Detailed plans + PDF", "Affiliate recommendations", "Multiple style variations"],
};

const Billing = () => {
    const { user, checkAuth } = useAuth();
    const { t } = useLang();
    const navigate = useNavigate();
    const [params] = useSearchParams();
    const [busy, setBusy] = useState(null);
    const [verifying, setVerifying] = useState(false);

    const currentPlan = user?.subscription_plan || "free";

    useEffect(() => {
        const sessionId = params.get("session_id");
        if (params.get("canceled")) {
            toast.info("Checkout canceled.");
            return;
        }
        if (!sessionId) return;
        setVerifying(true);
        let attempts = 0;
        const poll = async () => {
            try {
                const r = await authApi.get(`/billing/status/${sessionId}`);
                if (r.data.payment_status === "paid") {
                    await checkAuth();
                    toast.success("Subscription active! Enjoy your new plan.");
                    setVerifying(false);
                    navigate("/app/billing", { replace: true });
                    return;
                }
                if (attempts++ < 8) setTimeout(poll, 2000);
                else setVerifying(false);
            } catch {
                setVerifying(false);
            }
        };
        poll();
    }, []);

    const upgrade = async (plan) => {
        setBusy(plan);
        try {
            const r = await authApi.post("/billing/checkout", {
                plan, origin_url: window.location.origin,
            });
            window.location.href = r.data.url;
        } catch {
            toast.error("Could not start checkout. Please try again.");
            setBusy(null);
        }
    };

    const openPortal = async () => {
        setBusy("portal");
        try {
            const r = await authApi.post("/billing/portal", { origin_url: window.location.origin });
            window.location.href = r.data.url;
        } catch {
            toast.error("Billing portal unavailable.");
            setBusy(null);
        }
    };

    const plans = [
        { id: "free", name: "Free", price: 0 },
        { id: "pro", name: "Pro", price: 9.99, featured: true },
        { id: "premium", name: "Premium", price: 19.99 },
    ];

    return (
        <div className="min-h-screen bg-slate-50">
            <AppHeader active="billing" />
            <main className="container-app py-10">
                <div className="mx-auto max-w-2xl text-center">
                    <h1 className="font-heading text-3xl font-light tracking-tight text-slate-900 sm:text-4xl"
                        data-testid="billing-title">
                        {t.app.billingTitle}
                    </h1>
                    <p className="mt-3 text-slate-600">{t.app.billingSub}</p>
                    {verifying && (
                        <p className="mt-4 inline-flex items-center gap-2 text-sm text-emerald-700">
                            <Loader2 className="h-4 w-4 animate-spin" /> Verifying your payment…
                        </p>
                    )}
                </div>

                <div className="mt-12 grid grid-cols-1 gap-6 lg:grid-cols-3">
                    {plans.map((p) => {
                        const isCurrent = currentPlan === p.id;
                        return (
                            <div key={p.id}
                                className={`relative flex flex-col rounded-2xl border bg-white p-8 transition-all ${p.featured ? "border-emerald-500 shadow-lg ring-4 ring-emerald-50" : "border-slate-200"}`}
                                data-testid={`billing-plan-${p.id}`}>
                                {p.featured && (
                                    <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-emerald-500 px-3 py-1 text-xs font-medium uppercase tracking-widest text-white shadow-sm">
                                        ★ {t.app.mostPopular}
                                    </span>
                                )}
                                <h3 className="font-heading text-2xl font-medium text-slate-900">{p.name}</h3>
                                <div className="mt-4 flex items-baseline gap-1">
                                    <span className="font-heading text-4xl font-light text-slate-900">${p.price}</span>
                                    {p.price > 0 && <span className="text-sm text-slate-500">{t.app.perMonth}</span>}
                                </div>
                                <ul className="mt-6 flex flex-1 flex-col gap-3">
                                    {PLAN_FEATURES[p.id].map((f, i) => (
                                        <li key={i} className="flex items-start gap-2 text-slate-700">
                                            <Check className={`mt-0.5 h-5 w-5 shrink-0 ${p.featured ? "text-emerald-500" : "text-blue-600"}`} strokeWidth={2.2} />
                                            {f}
                                        </li>
                                    ))}
                                </ul>
                                {isCurrent ? (
                                    <Button disabled className="mt-8 w-full rounded-full" variant="outline" data-testid={`billing-current-${p.id}`}>
                                        {t.app.currentBtn}
                                    </Button>
                                ) : p.id === "free" ? (
                                    <Button disabled className="mt-8 w-full rounded-full opacity-50" variant="outline">—</Button>
                                ) : (
                                    <Button onClick={() => upgrade(p.id)} disabled={busy === p.id}
                                        className={`mt-8 w-full rounded-full py-6 ${p.featured ? "bg-emerald-500 text-white hover:bg-emerald-600" : "bg-slate-900 text-white hover:bg-slate-700"}`}
                                        data-testid={`billing-choose-${p.id}`}>
                                        {busy === p.id ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                                        {t.app.choosePlan} {p.name}
                                    </Button>
                                )}
                            </div>
                        );
                    })}
                </div>

                {currentPlan !== "free" && (
                    <div className="mt-10 text-center">
                        <Button onClick={openPortal} disabled={busy === "portal"} variant="outline"
                            className="rounded-full" data-testid="billing-portal-btn">
                            <Settings className="mr-2 h-4 w-4" /> {t.app.manageSub}
                        </Button>
                    </div>
                )}
            </main>
        </div>
    );
};

export default Billing;
