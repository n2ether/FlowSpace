import React, { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useLang } from "../context/LanguageContext";
import { LANGS } from "../i18n/translations";
import { Menu, X, ChevronDown } from "lucide-react";
import { Button } from "./ui/button";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "./ui/dropdown-menu";

const Header = () => {
    const { t, lang, setLang } = useLang();
    const [open, setOpen] = useState(false);
    const location = useLocation();
    const navigate = useNavigate();

    const isLanding = location.pathname === "/";

    const scrollTo = (id) => {
        setOpen(false);
        if (!isLanding) {
            navigate(`/#${id}`);
            return;
        }
        const el = document.getElementById(id);
        if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    };

    const navItems = [
        { id: "how", label: t.nav.how },
        { id: "packages", label: t.nav.packages },
        { id: "gallery", label: t.nav.gallery },
        { id: "faq", label: t.nav.faq },
    ];

    return (
        <header className="sticky top-0 z-50 border-b border-slate-200/80 bg-white/80 backdrop-blur-xl">
            <div className="container-app flex h-16 items-center justify-between">
                <Link
                    to="/"
                    className="flex items-center gap-2.5"
                    data-testid="logo-home-link"
                >
                    <span className="flex h-9 w-9 items-center justify-center">
                        <svg
                            viewBox="0 0 64 64"
                            className="h-9 w-9"
                            fill="none"
                            stroke="#5C7A65"
                            strokeWidth="2.6"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                        >
                            <path d="M10 32 L32 10 L54 32 L54 56 L10 56 Z" />
                            <path d="M14 42 C24 34, 30 50, 40 42 C46 37, 50 42, 54 42" strokeWidth="2.4" />
                        </svg>
                    </span>
                    <span className="font-heading text-lg font-semibold tracking-tight text-slate-900">
                        FlowSpace
                    </span>
                </Link>

                <nav className="hidden items-center gap-8 md:flex">
                    {navItems.map((n) => (
                        <button
                            key={n.id}
                            onClick={() => scrollTo(n.id)}
                            className="text-sm font-medium text-slate-600 transition-colors hover:text-emerald-600"
                            data-testid={`nav-${n.id}`}
                        >
                            {n.label}
                        </button>
                    ))}
                </nav>

                <div className="flex items-center gap-2">
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <button
                                className="hidden items-center gap-1 rounded-full border border-slate-200 px-3 py-1.5 text-xs font-medium uppercase tracking-widest text-slate-700 transition-colors hover:border-emerald-300 hover:text-emerald-700 md:inline-flex"
                                data-testid="lang-switcher-trigger"
                            >
                                {lang.toUpperCase()}
                                <ChevronDown className="h-3.5 w-3.5" />
                            </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="min-w-[7rem]">
                            {LANGS.map((l) => (
                                <DropdownMenuItem
                                    key={l.code}
                                    onClick={() => setLang(l.code)}
                                    className={
                                        lang === l.code
                                            ? "font-semibold text-emerald-700"
                                            : ""
                                    }
                                    data-testid={`lang-opt-${l.code}`}
                                >
                                    {l.label}
                                </DropdownMenuItem>
                            ))}
                        </DropdownMenuContent>
                    </DropdownMenu>

                    <Button
                        onClick={() => navigate("/intake")}
                        className="hidden rounded-full bg-emerald-500 px-5 text-white shadow-sm hover:bg-emerald-600 md:inline-flex"
                        data-testid="header-cta-start"
                    >
                        {t.nav.cta}
                    </Button>

                    <button
                        onClick={() => setOpen((v) => !v)}
                        className="inline-flex h-10 w-10 items-center justify-center rounded-lg text-slate-700 md:hidden"
                        data-testid="mobile-menu-toggle"
                    >
                        {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
                    </button>
                </div>
            </div>

            {open && (
                <div className="border-t border-slate-200 bg-white md:hidden">
                    <div className="container-app flex flex-col gap-1 py-4">
                        {navItems.map((n) => (
                            <button
                                key={n.id}
                                onClick={() => scrollTo(n.id)}
                                className="rounded-lg px-3 py-2 text-left text-sm font-medium text-slate-700 hover:bg-slate-50"
                                data-testid={`mobile-nav-${n.id}`}
                            >
                                {n.label}
                            </button>
                        ))}
                        <div className="mt-2 flex items-center gap-2 px-3">
                            {LANGS.map((l) => (
                                <button
                                    key={l.code}
                                    onClick={() => setLang(l.code)}
                                    className={`rounded-full border px-3 py-1 text-xs font-medium ${
                                        lang === l.code
                                            ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                                            : "border-slate-200 text-slate-600"
                                    }`}
                                    data-testid={`mobile-lang-${l.code}`}
                                >
                                    {l.label}
                                </button>
                            ))}
                        </div>
                        <Button
                            onClick={() => {
                                setOpen(false);
                                navigate("/intake");
                            }}
                            className="mt-3 rounded-full bg-emerald-500 text-white hover:bg-emerald-600"
                            data-testid="mobile-cta-start"
                        >
                            {t.nav.cta}
                        </Button>
                    </div>
                </div>
            )}
        </header>
    );
};

export default Header;
