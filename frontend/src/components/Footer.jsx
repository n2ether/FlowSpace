import React from "react";
import { Link } from "react-router-dom";
import { useLang } from "../context/LanguageContext";

const Footer = () => {
    const { t } = useLang();
    return (
        <footer className="border-t border-slate-200 bg-white">
            <div className="container-app flex flex-col items-start justify-between gap-6 py-10 md:flex-row md:items-center">
                <div className="flex items-center gap-3">
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
                    <div>
                        <div className="font-heading text-base font-semibold text-slate-900">
                            FlowSpace
                        </div>
                        <div className="text-xs text-slate-500">{t.footer.tagline}</div>
                    </div>
                </div>
                <div className="flex items-center gap-6 text-xs text-slate-500">
                    <span>
                        © {new Date().getFullYear()} FlowSpace · {t.footer.rights}
                    </span>
                    <Link
                        to="/admin/login"
                        className="text-slate-400 transition-colors hover:text-emerald-600"
                        data-testid="footer-admin-link"
                    >
                        {t.footer.admin}
                    </Link>
                </div>
            </div>
        </footer>
    );
};

export default Footer;
