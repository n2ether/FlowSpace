import React from "react";
import { Link } from "react-router-dom";
import { useLang } from "../context/LanguageContext";

const Footer = () => {
    const { t } = useLang();
    return (
        <footer className="border-t border-slate-200 bg-white">
            <div className="container-app flex flex-col items-start justify-between gap-6 py-10 md:flex-row md:items-center">
                <div className="flex items-center gap-3">
                    <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500 text-white">
                        <svg
                            width="16"
                            height="16"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2.4"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                        >
                            <path d="M3 21V8l9-5 9 5v13" />
                            <path d="M9 21V12h6v9" />
                        </svg>
                    </span>
                    <div>
                        <div className="font-heading text-base font-semibold text-slate-900">
                            ClearSpace
                        </div>
                        <div className="text-xs text-slate-500">{t.footer.tagline}</div>
                    </div>
                </div>
                <div className="flex items-center gap-6 text-xs text-slate-500">
                    <span>
                        © {new Date().getFullYear()} ClearSpace · {t.footer.rights}
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
