import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { Sparkles, LayoutGrid, CreditCard, LogOut } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useLang } from "../context/LanguageContext";
import { Button } from "./ui/button";

const Logo = () => (
    <Link to="/" className="flex items-center gap-2.5" data-testid="app-logo-link">
        <span className="flex h-9 w-9 items-center justify-center">
            <svg viewBox="0 0 64 64" className="h-9 w-9" fill="none" stroke="#5C7A65"
                strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10 32 L32 10 L54 32 L54 56 L10 56 Z" />
                <path d="M14 42 C24 34, 30 50, 40 42 C46 37, 50 42, 54 42" strokeWidth="2.4" />
            </svg>
        </span>
        <span className="font-heading text-lg font-semibold tracking-tight text-slate-900">FlowSpace</span>
    </Link>
);

const planMeta = {
    free: { label: "Free", cls: "bg-slate-100 text-slate-600" },
    pro: { label: "Pro", cls: "bg-emerald-50 text-emerald-700" },
    premium: { label: "Premium", cls: "bg-amber-50 text-amber-700" },
};

const AppHeader = ({ active }) => {
    const { user, logout } = useAuth();
    const { t } = useLang();
    const navigate = useNavigate();

    const plan = user?.subscription_plan || "free";
    const limit = user?.monthly_generation_limit ?? 1;
    const used = user?.monthly_generations_used ?? 0;
    const remaining = plan === "premium" ? t.app.unlimited : Math.max(0, limit - used);
    const meta = planMeta[plan] || planMeta.free;

    const doLogout = async () => {
        await logout();
        navigate("/");
    };

    return (
        <header className="sticky top-0 z-50 border-b border-slate-200/80 bg-white/80 backdrop-blur-xl">
            <div className="container-app flex h-16 items-center justify-between gap-4">
                <Logo />
                <div className="flex items-center gap-2">
                    <span className={`hidden rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-widest md:inline-flex ${meta.cls}`}
                        data-testid="app-plan-badge">
                        {meta.label}
                    </span>
                    <span className="hidden items-center gap-1 rounded-full border border-slate-200 px-3 py-1 text-xs font-medium text-slate-600 md:inline-flex"
                        data-testid="app-credits-badge">
                        <Sparkles className="h-3.5 w-3.5 text-emerald-500" />
                        {remaining} {t.app.credits}
                    </span>
                    <Button variant={active === "dashboard" ? "default" : "ghost"} size="sm"
                        onClick={() => navigate("/app")}
                        className={active === "dashboard" ? "rounded-full bg-emerald-500 text-white hover:bg-emerald-600" : "rounded-full text-slate-600"}
                        data-testid="nav-dashboard">
                        <LayoutGrid className="mr-1.5 h-4 w-4" />{t.app.dashboard}
                    </Button>
                    <Button variant={active === "billing" ? "default" : "ghost"} size="sm"
                        onClick={() => navigate("/app/billing")}
                        className={active === "billing" ? "rounded-full bg-emerald-500 text-white hover:bg-emerald-600" : "rounded-full text-slate-600"}
                        data-testid="nav-billing">
                        <CreditCard className="mr-1.5 h-4 w-4" />{t.app.manageBilling}
                    </Button>
                    <button onClick={doLogout}
                        className="inline-flex h-9 w-9 items-center justify-center rounded-full text-slate-500 hover:bg-slate-100 hover:text-red-600"
                        data-testid="nav-logout" title={t.app.logout}>
                        <LogOut className="h-4 w-4" />
                    </button>
                </div>
            </div>
        </header>
    );
};

export default AppHeader;
