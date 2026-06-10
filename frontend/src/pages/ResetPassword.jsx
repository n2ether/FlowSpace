import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, Loader2 } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { authApi, formatApiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useLang } from "../context/LanguageContext";

const ResetPassword = () => {
    const [params] = useSearchParams();
    const token = params.get("token");
    const { setUser } = useAuth();
    const { t } = useLang();
    const a = t.app;
    const navigate = useNavigate();

    const [password, setPassword] = useState("");
    const [confirm, setConfirm] = useState("");
    const [error, setError] = useState("");
    const [busy, setBusy] = useState(false);

    useEffect(() => {
        if (!token) navigate("/login");
    }, [token, navigate]);

    const submit = async (e) => {
        e.preventDefault();
        setError("");
        if (password !== confirm) {
            setError(a.pwMismatch);
            return;
        }
        setBusy(true);
        try {
            const r = await authApi.post("/auth/reset-password", { token, password });
            setUser(r.data);
            navigate("/app");
        } catch (err) {
            setError(formatApiError(err.response?.data?.detail) || err.message);
        } finally {
            setBusy(false);
        }
    };

    return (
        <div className="relative min-h-screen overflow-hidden bg-white">
            <div className="pointer-events-none absolute inset-0 -z-10">
                <div className="absolute left-1/2 top-[-10%] h-[520px] w-[520px] -translate-x-1/2 rounded-full bg-emerald-100/60 blur-3xl" />
            </div>
            <div className="container-app flex min-h-screen items-center justify-center py-16">
                <div className="w-full max-w-md rounded-3xl border border-slate-200 bg-white/80 p-9 shadow-xl backdrop-blur"
                    data-testid="reset-card">
                    <h1 className="text-center font-heading text-3xl font-light tracking-tight text-slate-900"
                        data-testid="reset-title">
                        {a.resetTitle}
                    </h1>
                    <p className="mt-2 text-center text-slate-600">{a.resetSub}</p>
                    <form onSubmit={submit} className="mt-7 space-y-4">
                        <div>
                            <Label htmlFor="np">{a.newPassword}</Label>
                            <Input id="np" type="password" required minLength={8} value={password}
                                onChange={(e) => setPassword(e.target.value)} placeholder="••••••••"
                                className="mt-1.5" data-testid="reset-password" />
                        </div>
                        <div>
                            <Label htmlFor="cp">{a.confirmPassword}</Label>
                            <Input id="cp" type="password" required minLength={8} value={confirm}
                                onChange={(e) => setConfirm(e.target.value)} placeholder="••••••••"
                                className="mt-1.5" data-testid="reset-confirm" />
                        </div>
                        {error && <p className="rounded-xl bg-red-50 p-3 text-sm text-red-600" data-testid="reset-error">{error}</p>}
                        <Button type="submit" disabled={busy}
                            className="w-full rounded-full bg-emerald-500 py-6 text-base text-white hover:bg-emerald-600 disabled:opacity-60"
                            data-testid="reset-submit">
                            {busy && <Loader2 className="mr-2 h-5 w-5 animate-spin" />}
                            {a.updatePassword}
                        </Button>
                    </form>
                    <button onClick={() => navigate("/login")}
                        className="mt-6 inline-flex w-full items-center justify-center gap-1.5 text-sm text-slate-500 hover:text-emerald-600"
                        data-testid="reset-back">
                        <ArrowLeft className="h-4 w-4" /> {a.backToSignIn}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default ResetPassword;
