import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "../components/ui/button";
import { useAuth } from "../context/AuthContext";
import { useLang } from "../context/LanguageContext";

const GoogleIcon = () => (
    <svg className="h-5 w-5" viewBox="0 0 24 24">
        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1z" />
        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z" />
        <path fill="#FBBC05" d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84z" />
        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1A11 11 0 0 0 2.18 7.06l3.66 2.84C6.71 7.3 9.14 5.38 12 5.38z" />
    </svg>
);

const Login = () => {
    const { user, login, loading } = useAuth();
    const { t } = useLang();
    const navigate = useNavigate();

    useEffect(() => {
        if (!loading && user) navigate("/app");
    }, [user, loading, navigate]);

    return (
        <div className="relative min-h-screen overflow-hidden bg-white">
            <div className="pointer-events-none absolute inset-0 -z-10">
                <div className="absolute left-1/2 top-[-10%] h-[520px] w-[520px] -translate-x-1/2 rounded-full bg-emerald-100/60 blur-3xl" />
                <div className="absolute right-[-10%] top-[40%] h-[420px] w-[420px] rounded-full bg-blue-100/50 blur-3xl" />
            </div>
            <div className="container-app flex min-h-screen items-center justify-center py-16">
                <div className="w-full max-w-md rounded-3xl border border-slate-200 bg-white/80 p-10 text-center shadow-xl backdrop-blur"
                    data-testid="login-card">
                    <span className="mx-auto flex h-12 w-12 items-center justify-center">
                        <svg viewBox="0 0 64 64" className="h-12 w-12" fill="none" stroke="#5C7A65"
                            strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M10 32 L32 10 L54 32 L54 56 L10 56 Z" />
                            <path d="M14 42 C24 34, 30 50, 40 42 C46 37, 50 42, 54 42" strokeWidth="2.4" />
                        </svg>
                    </span>
                    <h1 className="mt-5 font-heading text-3xl font-light tracking-tight text-slate-900">
                        {t.app.loginTitle}
                    </h1>
                    <p className="mt-3 text-slate-600">{t.app.loginSub}</p>

                    <Button onClick={login}
                        className="mt-8 w-full gap-3 rounded-full border border-slate-200 bg-white py-6 text-base font-medium text-slate-800 shadow-sm hover:bg-slate-50"
                        data-testid="google-login-btn">
                        <GoogleIcon />
                        {t.app.continueGoogle}
                    </Button>

                    <button onClick={() => navigate("/")}
                        className="mt-6 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-emerald-600"
                        data-testid="login-back-home">
                        <ArrowLeft className="h-4 w-4" />
                        {t.app.backHome}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default Login;
