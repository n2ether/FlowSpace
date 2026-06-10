import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Loader2, Mail, CheckCircle2 } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { authApi, formatApiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useLang } from "../context/LanguageContext";

const Brand = () => (
    <span className="mx-auto flex h-12 w-12 items-center justify-center">
        <svg viewBox="0 0 64 64" className="h-12 w-12" fill="none" stroke="#5C7A65"
            strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10 32 L32 10 L54 32 L54 56 L10 56 Z" />
            <path d="M14 42 C24 34, 30 50, 40 42 C46 37, 50 42, 54 42" strokeWidth="2.4" />
        </svg>
    </span>
);

const Login = () => {
    const { user, login, register, loading } = useAuth();
    const { t } = useLang();
    const navigate = useNavigate();

    const [mode, setMode] = useState("signin"); // signin | signup | forgot
    const [name, setName] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [busy, setBusy] = useState(false);
    const [forgotSent, setForgotSent] = useState(false);

    useEffect(() => {
        if (!loading && user) navigate("/app");
    }, [user, loading, navigate]);

    const a = t.app;

    const submit = async (e) => {
        e.preventDefault();
        setError("");
        setBusy(true);
        try {
            if (mode === "signin") {
                await login(email, password);
                navigate("/app");
            } else if (mode === "signup") {
                await register(email, password, name);
                navigate("/app");
            } else {
                await authApi.post("/auth/forgot-password", { email, origin_url: window.location.origin });
                setForgotSent(true);
            }
        } catch (err) {
            setError(formatApiError(err.response?.data?.detail) || err.message);
        } finally {
            setBusy(false);
        }
    };

    const switchMode = (m) => {
        setMode(m);
        setError("");
        setForgotSent(false);
    };

    const title = mode === "signin" ? a.signIn : mode === "signup" ? a.signUp : a.forgotTitle;
    const sub = mode === "signin" ? a.signInSub : mode === "signup" ? a.signUpSub : a.forgotSub;

    return (
        <div className="relative min-h-screen overflow-hidden bg-white">
            <div className="pointer-events-none absolute inset-0 -z-10">
                <div className="absolute left-1/2 top-[-10%] h-[520px] w-[520px] -translate-x-1/2 rounded-full bg-emerald-100/60 blur-3xl" />
                <div className="absolute right-[-10%] top-[40%] h-[420px] w-[420px] rounded-full bg-blue-100/50 blur-3xl" />
            </div>
            <div className="container-app flex min-h-screen items-center justify-center py-16">
                <div className="w-full max-w-md rounded-3xl border border-slate-200 bg-white/80 p-9 shadow-xl backdrop-blur"
                    data-testid="login-card">
                    <Brand />
                    <h1 className="mt-5 text-center font-heading text-3xl font-light tracking-tight text-slate-900"
                        data-testid="login-title">
                        {title}
                    </h1>
                    <p className="mt-2 text-center text-slate-600">{sub}</p>

                    {forgotSent ? (
                        <div className="mt-8 rounded-2xl border border-emerald-200 bg-emerald-50 p-6 text-center" data-testid="forgot-sent">
                            <CheckCircle2 className="mx-auto h-8 w-8 text-emerald-600" />
                            <p className="mt-3 text-sm text-emerald-800">{a.forgotSent}</p>
                            <button onClick={() => switchMode("signin")}
                                className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-emerald-700 hover:underline"
                                data-testid="forgot-back">
                                <ArrowLeft className="h-4 w-4" /> {a.backToSignIn}
                            </button>
                        </div>
                    ) : (
                        <form onSubmit={submit} className="mt-7 space-y-4">
                            {mode === "signup" && (
                                <div>
                                    <Label htmlFor="name">{a.nameLabel}</Label>
                                    <Input id="name" value={name} onChange={(e) => setName(e.target.value)}
                                        placeholder="Jane Doe" className="mt-1.5" data-testid="auth-name" />
                                </div>
                            )}
                            <div>
                                <Label htmlFor="email">{a.emailLabel}</Label>
                                <Input id="email" type="email" required value={email}
                                    onChange={(e) => setEmail(e.target.value)} placeholder="you@email.com"
                                    className="mt-1.5" data-testid="auth-email" />
                            </div>
                            {mode !== "forgot" && (
                                <div>
                                    <div className="flex items-center justify-between">
                                        <Label htmlFor="password">{a.passwordLabel}</Label>
                                        {mode === "signin" && (
                                            <button type="button" onClick={() => switchMode("forgot")}
                                                className="text-xs font-medium text-emerald-700 hover:underline"
                                                data-testid="auth-forgot-link">
                                                {a.forgotPassword}
                                            </button>
                                        )}
                                    </div>
                                    <Input id="password" type="password" required minLength={8} value={password}
                                        onChange={(e) => setPassword(e.target.value)} placeholder="••••••••"
                                        className="mt-1.5" data-testid="auth-password" />
                                    {mode === "signup" && <p className="mt-1 text-xs text-slate-400">{a.pwMin}</p>}
                                </div>
                            )}

                            {error && (
                                <p className="rounded-xl bg-red-50 p-3 text-sm text-red-600" data-testid="auth-error">{error}</p>
                            )}

                            <Button type="submit" disabled={busy}
                                className="w-full rounded-full bg-emerald-500 py-6 text-base text-white hover:bg-emerald-600 disabled:opacity-60"
                                data-testid="auth-submit">
                                {busy ? <Loader2 className="mr-2 h-5 w-5 animate-spin" /> : (mode === "forgot" && <Mail className="mr-2 h-5 w-5" />)}
                                {mode === "signin" ? a.signIn : mode === "signup" ? a.createAccount : a.sendReset}
                            </Button>
                        </form>
                    )}

                    {!forgotSent && mode !== "forgot" && (
                        <p className="mt-6 text-center text-sm text-slate-600" data-testid="auth-switch">
                            {mode === "signin" ? a.needAccount : a.haveAccount}{" "}
                            <button onClick={() => switchMode(mode === "signin" ? "signup" : "signin")}
                                className="font-semibold text-emerald-700 hover:underline" data-testid="auth-switch-btn">
                                {mode === "signin" ? a.signUp : a.signIn}
                            </button>
                        </p>
                    )}
                    {!forgotSent && mode === "forgot" && (
                        <button onClick={() => switchMode("signin")}
                            className="mt-6 inline-flex w-full items-center justify-center gap-1.5 text-sm text-slate-500 hover:text-emerald-600"
                            data-testid="forgot-cancel">
                            <ArrowLeft className="h-4 w-4" /> {a.backToSignIn}
                        </button>
                    )}

                    <button onClick={() => navigate("/")}
                        className="mt-5 inline-flex w-full items-center justify-center gap-1.5 text-xs text-slate-400 hover:text-slate-600"
                        data-testid="login-back-home">
                        <ArrowLeft className="h-3.5 w-3.5" /> {a.backHome}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default Login;
