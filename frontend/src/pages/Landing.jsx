import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
    ArrowRight,
    Check,
    Sparkles,
    ShoppingBag,
    LayoutGrid,
    Heart,
    Clock,
    Upload,
    Pencil,
    Target,
    Star,
    Users,
    Home,
    Compass,
    ArrowUpRight,
} from "lucide-react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import BeforeAfterSlider from "../components/BeforeAfterSlider";
import { Button } from "../components/ui/button";
import {
    Accordion,
    AccordionContent,
    AccordionItem,
    AccordionTrigger,
} from "../components/ui/accordion";
import { api } from "../lib/api";
import { useLang } from "../context/LanguageContext";

const fadeUp = {
    initial: { opacity: 0, y: 16 },
    whileInView: { opacity: 1, y: 0 },
    viewport: { once: true, margin: "-80px" },
    transition: { duration: 0.6, ease: "easeOut" },
};

const Eyebrow = ({ children, testId }) => (
    <span
        className="inline-flex items-center gap-2 text-xs font-medium uppercase tracking-[0.22em] text-emerald-700"
        data-testid={testId}
    >
        <span className="h-px w-6 bg-emerald-400" />
        {children}
    </span>
);

const Hero = () => {
    const { t } = useLang();
    const navigate = useNavigate();
    const scroll = (id) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });

    return (
        <section className="relative overflow-hidden bg-white pt-14 md:pt-20">
            <div className="pointer-events-none absolute inset-0 -z-10">
                <div className="absolute left-1/2 top-[-10%] h-[520px] w-[520px] -translate-x-1/2 rounded-full bg-emerald-100/60 blur-3xl" />
                <div className="absolute right-[-10%] top-[30%] h-[420px] w-[420px] rounded-full bg-blue-100/50 blur-3xl" />
            </div>

            <div className="container-app grid grid-cols-1 items-center gap-12 pb-16 md:gap-16 md:pb-24 lg:grid-cols-[1.05fr_1fr]">
                <motion.div {...fadeUp} className="flex flex-col gap-7">
                    <Eyebrow testId="hero-eyebrow">{t.hero.eyebrow}</Eyebrow>
                    <h1 className="font-heading text-[40px] font-light leading-[1.05] tracking-tight text-slate-900 sm:text-[56px] lg:text-[68px]">
                        {t.hero.h1_a}
                        <span className="block text-emerald-600">{t.hero.h1_b}</span>
                    </h1>
                    <p className="max-w-xl text-lg leading-relaxed text-slate-600">
                        {t.hero.sub}
                    </p>

                    <div className="flex flex-wrap items-center gap-3 pt-2">
                        <Button
                            onClick={() => navigate("/upload")}
                            className="group rounded-full bg-emerald-500 px-6 py-6 text-base font-medium text-white shadow-sm transition-all hover:-translate-y-0.5 hover:bg-emerald-600 hover:shadow-md"
                            data-testid="hero-cta-start"
                        >
                            {t.hero.cta_primary}
                            <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                        </Button>
                        <Button
                            variant="outline"
                            onClick={() => scroll("gallery")}
                            className="rounded-full border-slate-200 bg-white px-6 py-6 text-base font-medium text-slate-700 hover:border-emerald-300 hover:text-emerald-700"
                            data-testid="hero-cta-examples"
                        >
                            {t.hero.cta_secondary}
                        </Button>
                    </div>

                    <div className="flex flex-wrap items-center gap-5 pt-2 text-sm text-slate-500">
                        <div className="flex items-center gap-2">
                            <Clock className="h-4 w-4 text-emerald-600" />
                            <span>{t.hero.delivery}</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Star className="h-4 w-4 fill-amber-400 text-amber-400" />
                            <Star className="h-4 w-4 fill-amber-400 text-amber-400" />
                            <Star className="h-4 w-4 fill-amber-400 text-amber-400" />
                            <Star className="h-4 w-4 fill-amber-400 text-amber-400" />
                            <Star className="h-4 w-4 fill-amber-400 text-amber-400" />
                            <span className="ml-1">4.9 / 500+</span>
                        </div>
                    </div>
                </motion.div>

                <motion.div {...fadeUp} transition={{ duration: 0.7, delay: 0.1 }}>
                    <div className="relative">
                        <div className="absolute -top-6 -left-6 hidden h-28 w-28 rounded-2xl bg-blue-50 md:block" />
                        <div className="absolute -bottom-6 -right-6 hidden h-28 w-28 rounded-2xl bg-emerald-50 md:block" />
                        <BeforeAfterSlider
                            beforeUrl="https://images.unsplash.com/photo-1570129476815-ba368ac77013?auto=format&fit=crop&w=1600&q=80"
                            afterUrl="https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=1600&q=80"
                            beforeLabel={t.hero.beforeLabel}
                            afterLabel={t.hero.afterLabel}
                            className="relative aspect-[4/5] w-full shadow-xl"
                            testIdPrefix="hero-slider"
                        />
                    </div>
                </motion.div>
            </div>
        </section>
    );
};

const ValueProp = () => {
    const { t } = useLang();
    const icons = [LayoutGrid, ShoppingBag, Compass, Heart];
    return (
        <section id="value" className="relative bg-slate-50 section-pad">
            <div className="container-app">
                <motion.div {...fadeUp} className="max-w-2xl">
                    <Eyebrow>{t.value.eyebrow}</Eyebrow>
                    <h2 className="mt-4 font-heading text-4xl font-light tracking-tight text-slate-900 sm:text-5xl">
                        {t.value.title}
                    </h2>
                </motion.div>
                <div className="mt-14 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
                    {t.value.bullets.map((b, i) => {
                        const Icon = icons[i] || Sparkles;
                        return (
                            <motion.div
                                key={i}
                                {...fadeUp}
                                transition={{ duration: 0.5, delay: i * 0.05 }}
                                className="group flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-7 transition-all hover:-translate-y-1 hover:border-emerald-200 hover:shadow-md"
                                data-testid={`value-card-${i}`}
                            >
                                <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 transition-colors group-hover:bg-emerald-100">
                                    <Icon className="h-5 w-5" strokeWidth={1.6} />
                                </span>
                                <h3 className="font-heading text-xl font-medium text-slate-900">
                                    {b.t}
                                </h3>
                                <p className="text-slate-600">{b.d}</p>
                            </motion.div>
                        );
                    })}
                </div>
            </div>
        </section>
    );
};

const HowItWorks = () => {
    const { t } = useLang();
    const icons = [Upload, Pencil, Target];
    return (
        <section id="how" className="relative bg-white section-pad">
            <div className="container-app">
                <motion.div {...fadeUp} className="flex flex-col items-start gap-4">
                    <Eyebrow>{t.how.eyebrow}</Eyebrow>
                    <h2 className="font-heading text-4xl font-light tracking-tight text-slate-900 sm:text-5xl">
                        {t.how.title}
                    </h2>
                </motion.div>

                <div className="mt-16 grid grid-cols-1 gap-8 md:grid-cols-3">
                    {t.how.steps.map((step, i) => {
                        const Icon = icons[i];
                        return (
                            <motion.div
                                key={i}
                                {...fadeUp}
                                transition={{ duration: 0.6, delay: i * 0.08 }}
                                className="relative rounded-2xl border border-slate-200 bg-white p-8"
                                data-testid={`how-step-${i + 1}`}
                            >
                                <div className="absolute -top-5 left-8 flex h-10 w-10 items-center justify-center rounded-full bg-emerald-500 font-heading text-sm font-semibold text-white shadow-md">
                                    {i + 1}
                                </div>
                                <Icon className="h-8 w-8 text-emerald-600" strokeWidth={1.5} />
                                <h3 className="mt-5 font-heading text-xl font-medium text-slate-900">
                                    {step.t}
                                </h3>
                                <p className="mt-2 text-slate-600">{step.d}</p>
                            </motion.div>
                        );
                    })}
                </div>

                <div className="mt-10 inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700">
                    <Clock className="h-4 w-4" /> {t.how.delivery}
                </div>
            </div>
        </section>
    );
};

const WhatYouGet = () => {
    const { t } = useLang();
    return (
        <section className="relative bg-slate-50 section-pad">
            <div className="container-app grid grid-cols-1 gap-12 lg:grid-cols-[1fr_1.1fr] lg:gap-20">
                <motion.div {...fadeUp} className="flex flex-col gap-6">
                    <Eyebrow>{t.what.eyebrow}</Eyebrow>
                    <h2 className="font-heading text-4xl font-light tracking-tight text-slate-900 sm:text-5xl">
                        {t.what.title}
                    </h2>
                    <ul className="mt-2 flex flex-col gap-4">
                        {t.what.items.map((item, i) => (
                            <li
                                key={i}
                                className="flex items-start gap-3 text-lg text-slate-700"
                                data-testid={`what-item-${i}`}
                            >
                                <span className="mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-white">
                                    <Check className="h-3.5 w-3.5" strokeWidth={3} />
                                </span>
                                {item}
                            </li>
                        ))}
                    </ul>
                </motion.div>

                <motion.div {...fadeUp} transition={{ duration: 0.7, delay: 0.1 }}>
                    <div className="grid grid-cols-2 grid-rows-2 gap-4">
                        <img
                            src="https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=900&q=80"
                            alt="Layout"
                            className="col-span-2 aspect-[16/9] w-full rounded-2xl object-cover"
                        />
                        <img
                            src="https://images.unsplash.com/photo-1551298370-9d3d53740c72?auto=format&fit=crop&w=700&q=80"
                            alt="Categories"
                            className="aspect-square w-full rounded-2xl object-cover"
                        />
                        <img
                            src="https://images.unsplash.com/photo-1604014237800-1c9102c219da?auto=format&fit=crop&w=700&q=80"
                            alt="Shopping list"
                            className="aspect-square w-full rounded-2xl object-cover"
                        />
                    </div>
                </motion.div>
            </div>
        </section>
    );
};

const Packages = () => {
    const { t } = useLang();
    const navigate = useNavigate();
    const [loadingId, setLoadingId] = useState(null);

    const PACKAGE_PRICES = { basic: 79, standard: 149, premium: 299 };

    const startPlan = async (pkgId) => {
        setLoadingId(pkgId);
        navigate(`/checkout?package=${pkgId}`);
        setLoadingId(null);
    };

    const plans = [
        { id: "basic", data: t.packages.basic, featured: false },
        { id: "standard", data: t.packages.standard, featured: true },
        { id: "premium", data: t.packages.premium, featured: false },
    ];

    return (
        <section id="packages" className="relative bg-white section-pad">
            <div className="container-app">
                <motion.div {...fadeUp} className="mx-auto max-w-2xl text-center">
                    <Eyebrow>{t.packages.eyebrow}</Eyebrow>
                    <h2 className="mt-4 font-heading text-4xl font-light tracking-tight text-slate-900 sm:text-5xl">
                        {t.packages.title}
                    </h2>
                    <p className="mt-4 text-slate-600">{t.packages.sub}</p>
                </motion.div>

                <div className="mt-14 grid grid-cols-1 gap-6 lg:grid-cols-3">
                    {plans.map((p, i) => (
                        <motion.div
                            key={p.id}
                            {...fadeUp}
                            transition={{ duration: 0.5, delay: i * 0.07 }}
                            className={`relative flex flex-col rounded-2xl border bg-white p-8 transition-all hover:-translate-y-1 hover:shadow-lg ${
                                p.featured
                                    ? "border-emerald-500 shadow-lg ring-4 ring-emerald-50"
                                    : "border-slate-200"
                            }`}
                            data-testid={`package-${p.id}`}
                        >
                            {p.featured && (
                                <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-emerald-500 px-3 py-1 text-xs font-medium uppercase tracking-widest text-white shadow-sm">
                                    ★ {t.packages.recommended}
                                </span>
                            )}
                            <h3 className="font-heading text-2xl font-medium text-slate-900">
                                {p.data.name}
                            </h3>
                            <p className="mt-1 text-sm text-slate-500">{p.data.tagline}</p>
                            <div className="mt-6 flex items-baseline gap-2">
                                <span className="font-heading text-5xl font-light text-slate-900">
                                    ${PACKAGE_PRICES[p.id]}
                                </span>
                                <span className="text-sm text-slate-500">USD</span>
                            </div>

                            <ul className="mt-6 flex flex-col gap-3">
                                {p.data.features.map((f, j) => (
                                    <li key={j} className="flex items-start gap-2 text-slate-700">
                                        <Check
                                            className={`mt-0.5 h-5 w-5 shrink-0 ${
                                                p.featured ? "text-emerald-500" : "text-blue-600"
                                            }`}
                                            strokeWidth={2.2}
                                        />
                                        {f}
                                    </li>
                                ))}
                            </ul>

                            <Button
                                onClick={() => startPlan(p.id)}
                                disabled={loadingId === p.id}
                                className={`mt-8 w-full rounded-full py-6 text-base ${
                                    p.featured
                                        ? "bg-emerald-500 text-white hover:bg-emerald-600"
                                        : "bg-slate-900 text-white hover:bg-slate-700"
                                }`}
                                data-testid={`package-cta-${p.id}`}
                            >
                                {loadingId === p.id ? "..." : t.packages.cta}
                                <ArrowUpRight className="ml-2 h-4 w-4" />
                            </Button>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    );
};

const Gallery = () => {
    const { t } = useLang();
    const [items, setItems] = useState([]);
    const [filter, setFilter] = useState("all");

    useEffect(() => {
        api.get("/gallery")
            .then((r) => setItems(r.data || []))
            .catch(() => setItems([]));
    }, []);

    const filtered = filter === "all" ? items : items.filter((i) => i.category === filter);
    const cats = ["all", "garage", "closet", "storage"];

    return (
        <section id="gallery" className="relative bg-slate-50 section-pad">
            <div className="container-app">
                <motion.div {...fadeUp} className="flex flex-col items-start gap-4">
                    <Eyebrow>{t.gallery.eyebrow}</Eyebrow>
                    <h2 className="font-heading text-4xl font-light tracking-tight text-slate-900 sm:text-5xl">
                        {t.gallery.title}
                    </h2>
                    <p className="max-w-2xl text-slate-600">{t.gallery.sub}</p>
                </motion.div>

                <div className="mt-8 flex flex-wrap gap-2">
                    {cats.map((c) => (
                        <button
                            key={c}
                            onClick={() => setFilter(c)}
                            className={`rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
                                filter === c
                                    ? "border-emerald-500 bg-emerald-500 text-white"
                                    : "border-slate-200 bg-white text-slate-600 hover:border-emerald-300"
                            }`}
                            data-testid={`gallery-filter-${c}`}
                        >
                            {t.gallery.filters[c]}
                        </button>
                    ))}
                </div>

                <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-2">
                    {filtered.map((it, i) => (
                        <motion.div
                            key={it.id}
                            {...fadeUp}
                            transition={{ duration: 0.5, delay: i * 0.06 }}
                            className="group overflow-hidden rounded-2xl border border-slate-200 bg-white"
                            data-testid={`gallery-item-${it.id}`}
                        >
                            <BeforeAfterSlider
                                beforeUrl={it.before_url}
                                afterUrl={it.after_url}
                                beforeLabel={t.hero.beforeLabel}
                                afterLabel={t.hero.afterLabel}
                                className="aspect-[4/3] w-full"
                                testIdPrefix={`ba-${it.id}`}
                            />
                            <div className="flex items-center justify-between p-5">
                                <div>
                                    <div className="font-heading text-lg font-medium text-slate-900">
                                        {it.title}
                                    </div>
                                    <div className="mt-1 text-xs uppercase tracking-widest text-slate-400">
                                        {it.category}
                                    </div>
                                </div>
                                <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-emerald-50 text-emerald-600">
                                    <ArrowUpRight className="h-4 w-4" />
                                </span>
                            </div>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    );
};

const WhoItsFor = () => {
    const { t } = useLang();
    const icons = [Users, Home, Compass, Heart];
    return (
        <section className="relative bg-white section-pad">
            <div className="container-app">
                <motion.div {...fadeUp} className="max-w-2xl">
                    <Eyebrow>{t.who.eyebrow}</Eyebrow>
                    <h2 className="mt-4 font-heading text-4xl font-light tracking-tight text-slate-900 sm:text-5xl">
                        {t.who.title}
                    </h2>
                </motion.div>
                <div className="mt-12 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    {t.who.items.map((item, i) => {
                        const Icon = icons[i] || Users;
                        return (
                            <motion.div
                                key={i}
                                {...fadeUp}
                                transition={{ duration: 0.5, delay: i * 0.05 }}
                                className="flex items-start gap-4 rounded-2xl border border-slate-200 bg-white p-6 hover:border-blue-200"
                                data-testid={`who-item-${i}`}
                            >
                                <Icon className="h-6 w-6 shrink-0 text-blue-600" strokeWidth={1.6} />
                                <p className="font-medium text-slate-800">{item}</p>
                            </motion.div>
                        );
                    })}
                </div>
            </div>
        </section>
    );
};

const FAQ = () => {
    const { t } = useLang();
    return (
        <section id="faq" className="relative bg-slate-50 section-pad">
            <div className="container-app grid grid-cols-1 gap-12 lg:grid-cols-[1fr_1.2fr]">
                <motion.div {...fadeUp} className="flex flex-col gap-4">
                    <Eyebrow>{t.faq.eyebrow}</Eyebrow>
                    <h2 className="font-heading text-4xl font-light tracking-tight text-slate-900 sm:text-5xl">
                        {t.faq.title}
                    </h2>
                </motion.div>
                <motion.div {...fadeUp} transition={{ delay: 0.1 }}>
                    <Accordion type="single" collapsible className="w-full">
                        {t.faq.items.map((item, i) => (
                            <AccordionItem
                                key={i}
                                value={`q${i}`}
                                className="border-b border-slate-200"
                                data-testid={`faq-item-${i}`}
                            >
                                <AccordionTrigger className="text-left text-lg font-medium text-slate-900 hover:no-underline">
                                    {item.q}
                                </AccordionTrigger>
                                <AccordionContent className="text-base leading-relaxed text-slate-600">
                                    {item.a}
                                </AccordionContent>
                            </AccordionItem>
                        ))}
                    </Accordion>
                </motion.div>
            </div>
        </section>
    );
};

const FinalCTA = () => {
    const { t } = useLang();
    const navigate = useNavigate();
    return (
        <section className="relative bg-white section-pad">
            <div className="container-app">
                <motion.div
                    {...fadeUp}
                    className="relative overflow-hidden rounded-3xl border border-slate-200 bg-gradient-to-br from-emerald-500 to-emerald-600 p-10 text-white shadow-lg md:p-16"
                >
                    <div className="absolute -right-16 -top-16 h-72 w-72 rounded-full bg-white/10 blur-3xl" />
                    <div className="absolute -bottom-20 -left-16 h-72 w-72 rounded-full bg-blue-400/30 blur-3xl" />
                    <div className="relative grid grid-cols-1 items-center gap-10 md:grid-cols-[1.4fr_1fr]">
                        <div>
                            <h2 className="font-heading text-4xl font-light tracking-tight sm:text-5xl">
                                {t.finalCta.title}
                            </h2>
                            <p className="mt-4 max-w-xl text-lg text-emerald-50">
                                {t.finalCta.sub}
                            </p>
                        </div>
                        <div className="flex md:justify-end">
                            <Button
                                onClick={() => navigate("/upload")}
                                className="group rounded-full bg-white px-7 py-7 text-base font-medium text-emerald-700 shadow-sm hover:bg-emerald-50"
                                data-testid="final-cta-start"
                            >
                                {t.finalCta.btn}
                                <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                            </Button>
                        </div>
                    </div>
                </motion.div>
            </div>
        </section>
    );
};

const Landing = () => {
    useEffect(() => {
        // Handle hash scroll on arrival
        const hash = window.location.hash;
        if (hash) {
            setTimeout(() => {
                const el = document.getElementById(hash.replace("#", ""));
                if (el) el.scrollIntoView({ behavior: "smooth" });
            }, 200);
        }
    }, []);

    return (
        <div className="App">
            <Header />
            <main data-testid="landing-main">
                <Hero />
                <ValueProp />
                <HowItWorks />
                <WhatYouGet />
                <Packages />
                <Gallery />
                <WhoItsFor />
                <FAQ />
                <FinalCTA />
            </main>
            <Footer />
        </div>
    );
};

export default Landing;
