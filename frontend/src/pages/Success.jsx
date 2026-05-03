import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Check, Loader2, AlertCircle } from "lucide-react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { Button } from "../components/ui/button";
import { api } from "../lib/api";
import { useLang } from "../context/LanguageContext";

const Success = () => {
    const { t } = useLang();
    const [params] = useSearchParams();
    const sessionId = params.get("session_id");
    const navigate = useNavigate();
    const [status, setStatus] = useState("checking");
    const [amount, setAmount] = useState(null);
    const [currency, setCurrency] = useState("usd");
    const attempts = useRef(0);

    useEffect(() => {
        if (!sessionId) {
            setStatus("expired");
            return;
        }
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
                if (attempts.current >= 10) {
                    setStatus("pending");
                    return;
                }
                setTimeout(poll, 2000);
            } catch (e) {
                console.error(e);
                attempts.current += 1;
                if (attempts.current >= 6) {
                    setStatus("expired");
                    return;
                }
                setTimeout(poll, 2000);
            }
        };
        poll();
    }, [sessionId]);

    return (
        <div className="App min-h-screen bg-slate-50">
            <Header />
            <main className="container-app flex min-h-[calc(100vh-10rem)] items-center justify-center py-16">
                <div
                    className="w-full max-w-lg rounded-3xl border border-slate-200 bg-white p-10 text-center shadow-sm"
                    data-testid="success-card"
                >
                    {status === "checking" && (
                        <>
                            <Loader2 className="mx-auto h-10 w-10 animate-spin text-emerald-600" />
                            <h1 className="mt-6 font-heading text-3xl font-light text-slate-900">
                                {t.success.checking}
                            </h1>
                        </>
                    )}
                    {status === "paid" && (
                        <>
                            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500 text-white">
                                <Check className="h-7 w-7" />
                            </div>
                            <h1 className="mt-6 font-heading text-3xl font-light text-slate-900">
                                {t.success.paid}
                            </h1>
                            <p className="mt-3 text-slate-600">{t.success.paidSub}</p>
                            {amount !== null && (
                                <p className="mt-2 text-sm text-slate-400">
                                    {(amount / 100).toFixed(2)} {currency.toUpperCase()}
                                </p>
                            )}
                            <Button
                                onClick={() => navigate("/intake")}
                                className="mt-6 rounded-full bg-emerald-500 px-6 text-white hover:bg-emerald-600"
                                data-testid="success-continue"
                            >
                                {t.success.continue}
                            </Button>
                        </>
                    )}
                    {status === "pending" && (
                        <>
                            <Loader2 className="mx-auto h-10 w-10 animate-spin text-blue-600" />
                            <h1 className="mt-6 font-heading text-3xl font-light text-slate-900">
                                {t.success.pending}
                            </h1>
                            <Button
                                onClick={() => navigate("/")}
                                variant="outline"
                                className="mt-6 rounded-full"
                                data-testid="success-back"
                            >
                                {t.success.backHome}
                            </Button>
                        </>
                    )}
                    {status === "expired" && (
                        <>
                            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-red-50 text-red-600">
                                <AlertCircle className="h-7 w-7" />
                            </div>
                            <h1 className="mt-6 font-heading text-3xl font-light text-slate-900">
                                {t.success.expired}
                            </h1>
                            <Button
                                onClick={() => navigate("/")}
                                className="mt-6 rounded-full bg-slate-900 text-white hover:bg-slate-700"
                                data-testid="success-expired-back"
                            >
                                {t.success.backHome}
                            </Button>
                        </>
                    )}
                </div>
            </main>
            <Footer />
        </div>
    );
};

export default Success;
