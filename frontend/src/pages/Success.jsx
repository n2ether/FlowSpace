import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { Check, Loader2, AlertCircle, Mail } from "lucide-react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { api } from "../lib/api";

const Success = () => {
    const [params] = useSearchParams();
    const sessionId = params.get("session_id");
    const planParam = (params.get("plan") || "").toLowerCase();
    const navigate = useNavigate();
    const [status, setStatus] = useState(sessionId ? "checking" : (planParam === "free" ? "free" : "expired"));
    const [amount, setAmount] = useState(null);
    const [currency, setCurrency] = useState("usd");
    const attempts = useRef(0);

    useEffect(() => {
        if (!sessionId) return; // free flow — nothing to poll
        const poll = async () => {
            try {
                const res = await api.get(`/checkout/status/${sessionId}`);
                const ps = res.data.payment_status;
                if (ps === "paid") {
                    setStatus("paid");
                    setAmount(res.data.amount_total);
                    setCurrency(res.data.currency);
                    return;
                }
                if (res.data.status === "expired") {
                    setStatus("expired");
                    return;
                }
                attempts.current += 1;
                if (attempts.current >= 10) { setStatus("pending"); return; }
                setTimeout(poll, 2000);
            } catch (e) {
                attempts.current += 1;
                if (attempts.current >= 6) { setStatus("expired"); return; }
                setTimeout(poll, 2000);
            }
        };
        poll();
    }, [sessionId]);

    const fmt = (n) => n == null ? null : new Intl.NumberFormat("en-US", { style: "currency", currency: (currency || "usd").toUpperCase() }).format(n / 100);

    return (
        <div className="min-h-screen bg-slate-50">
            <Header />
            <main className="container-app flex min-h-[calc(100vh-10rem)] items-center justify-center py-16">
                <div className="w-full max-w-lg rounded-3xl border border-slate-200 bg-white p-10 text-center shadow-sm" data-testid="success-card">

                    {status === "checking" && (
                        <>
                            <Loader2 className="mx-auto h-10 w-10 animate-spin text-emerald-600" />
                            <h1 className="mt-6 font-display text-3xl font-light text-slate-900">Confirming your payment…</h1>
                            <p className="mt-3 text-slate-600">Hang tight, this takes a few seconds.</p>
                        </>
                    )}

                    {(status === "paid" || status === "free") && (
                        <>
                            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500 text-white">
                                <Check className="h-7 w-7" />
                            </div>
                            <h1 className="mt-6 font-display text-3xl font-light text-slate-900">
                                {status === "paid" ? "You're all set!" : "Your Blueprint is on the way!"}
                            </h1>
                            {status === "paid" && amount != null && (
                                <p className="mt-2 text-sm text-slate-500">Payment received: <strong>{fmt(amount)}</strong></p>
                            )}
                            <div className="mt-6 rounded-2xl border border-emerald-200 bg-emerald-50 p-5 text-left">
                                <div className="flex items-start gap-3">
                                    <Mail className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
                                    <div>
                                        <p className="font-medium text-emerald-900">Check your email in ~2 minutes</p>
                                        <p className="mt-1 text-sm text-emerald-800">
                                            We're generating your personalized FlowSpace Blueprint™ right now.
                                            It includes your room rendering, shopping list, action plan, and color palette —
                                            delivered as a PDF straight to your inbox.
                                        </p>
                                    </div>
                                </div>
                            </div>
                            <p className="mt-6 text-xs text-slate-500">
                                Don't see it? Check your spam folder, or reply to any of our emails to reach us.
                            </p>
                            <Link to="/" className="btn-primary mt-8 w-full justify-center">Back to homepage</Link>
                        </>
                    )}

                    {status === "pending" && (
                        <>
                            <Loader2 className="mx-auto h-10 w-10 animate-spin text-amber-500" />
                            <h1 className="mt-6 font-display text-3xl font-light text-slate-900">Payment still processing</h1>
                            <p className="mt-3 text-slate-600">
                                Your Blueprint will start generating as soon as the payment clears.
                                You'll receive an email confirmation.
                            </p>
                            <Link to="/" className="btn-ghost mt-8 inline-flex">Return home</Link>
                        </>
                    )}

                    {status === "expired" && (
                        <>
                            <AlertCircle className="mx-auto h-10 w-10 text-amber-500" />
                            <h1 className="mt-6 font-display text-3xl font-light text-slate-900">Session expired</h1>
                            <p className="mt-3 text-slate-600">
                                Looks like this checkout link isn't valid anymore. No worries — you can start fresh.
                            </p>
                            <button onClick={() => navigate("/#packages")} className="btn-primary mt-8 w-full justify-center">
                                Pick a plan
                            </button>
                        </>
                    )}
                </div>
            </main>
            <Footer />
        </div>
    );
};

export default Success;
