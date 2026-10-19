import React from "react";
import Header from "./Header";
import Footer from "./Footer";

export const SUPPORT_EMAIL = "help@flowspace.solutions";

// Filled in at launch. Keep the body free of dates so the copy stays evergreen.
export const LAST_UPDATED = "";

export function SupportLink({ className = "" }) {
    return (
        <a href={`mailto:${SUPPORT_EMAIL}`} className={`font-medium text-emerald-700 hover:text-emerald-800 ${className}`}>
            {SUPPORT_EMAIL}
        </a>
    );
}

export function LegalSection({ title, children }) {
    return (
        <section className="mt-10">
            <h2 className="font-display text-2xl font-light text-slate-900">{title}</h2>
            <div className="mt-3 space-y-3 leading-relaxed text-slate-600">{children}</div>
        </section>
    );
}

export function BulletList({ items }) {
    return (
        <ul className="list-disc space-y-2 pl-5">
            {items.map((item, i) => (
                <li key={i}>{item}</li>
            ))}
        </ul>
    );
}

export default function LegalLayout({ eyebrow, title, intro, testId, children }) {
    return (
        <div className="min-h-screen bg-slate-50">
            <Header />
            <main className="container-app py-16" data-testid={testId}>
                <article className="mx-auto max-w-3xl rounded-3xl border border-slate-200 bg-white p-8 shadow-sm md:p-12">
                    <span className="eyebrow">{eyebrow}</span>
                    <h1 className="mt-4 font-display text-4xl font-light tracking-tight text-slate-900">{title}</h1>
                    <p className="mt-2 text-sm text-slate-500" data-testid="legal-last-updated">
                        Last updated: {LAST_UPDATED || "—"}
                    </p>
                    {intro && <p className="mt-6 text-lg leading-relaxed text-slate-600">{intro}</p>}
                    {children}
                </article>
            </main>
            <Footer />
        </div>
    );
}
