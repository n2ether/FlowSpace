import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import {
    Loader2, AlertCircle, Download, ArrowLeft, Gauge, DollarSign, Clock,
    Wrench, ShoppingBag, ListChecks, ExternalLink, Lock,
} from "lucide-react";
import AppHeader from "../components/AppHeader";
import { ProjectCompare } from "../components/AuthImage";
import { Button } from "../components/ui/button";
import { authApi, API } from "../lib/api";
import { useLang } from "../context/LanguageContext";
import { toast } from "sonner";

const ROOM_LABELS = {
    garage: "Garage", closet: "Closet", pantry: "Pantry", laundry: "Laundry Room",
    bedroom: "Bedroom", office: "Office", bathroom: "Bathroom", playroom: "Playroom",
    kitchen: "Kitchen", living_room: "Living Room", storage: "Storage Room",
    balcony: "Balcony", other: "Other",
};

const Stat = ({ Icon, label, value }) => (
    <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
            <Icon className="h-5 w-5" />
        </span>
        <div>
            <div className="text-xs uppercase tracking-widest text-slate-400">{label}</div>
            <div className="font-heading text-lg font-medium text-slate-900">{value}</div>
        </div>
    </div>
);

const Results = () => {
    const { id } = useParams();
    const { t } = useLang();
    const navigate = useNavigate();
    const [project, setProject] = useState(null);
    const [notFound, setNotFound] = useState(false);
    const attempts = useRef(0);
    const [downloading, setDownloading] = useState(false);

    useEffect(() => {
        let active = true;
        const poll = async () => {
            try {
                const r = await authApi.get(`/projects/${id}`);
                if (!active) return;
                setProject(r.data);
                if (r.data.status === "processing" && attempts.current < 40) {
                    attempts.current += 1;
                    setTimeout(poll, 3000);
                }
            } catch (e) {
                if (e?.response?.status === 404) setNotFound(true);
            }
        };
        poll();
        return () => { active = false; };
    }, [id]);

    const downloadPdf = async () => {
        setDownloading(true);
        try {
            const res = await fetch(`${API}/projects/${id}/pdf`, { credentials: "include" });
            if (!res.ok) throw new Error();
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `FlowSpace_${id.slice(0, 8)}.pdf`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
        } catch {
            toast.error("PDF not available.");
        } finally {
            setDownloading(false);
        }
    };

    if (notFound) {
        return (
            <div className="min-h-screen bg-slate-50">
                <AppHeader />
                <main className="container-app flex min-h-[60vh] items-center justify-center">
                    <p className="text-slate-500">Project not found.</p>
                </main>
            </div>
        );
    }

    const plan = project?.organization_plan;
    const status = project?.status;

    return (
        <div className="min-h-screen bg-slate-50">
            <AppHeader />
            <main className="container-app py-10">
                <button onClick={() => navigate("/app")}
                    className="mb-6 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-emerald-600"
                    data-testid="results-back">
                    <ArrowLeft className="h-4 w-4" /> {t.app.dashboard}
                </button>

                {!project && (
                    <div className="flex min-h-[40vh] items-center justify-center">
                        <Loader2 className="h-8 w-8 animate-spin text-emerald-600" />
                    </div>
                )}

                {status === "processing" && (
                    <div className="rounded-3xl border border-slate-200 bg-white p-12 text-center" data-testid="results-processing">
                        <Loader2 className="mx-auto h-10 w-10 animate-spin text-emerald-600" />
                        <h1 className="mt-6 font-heading text-2xl font-light text-slate-900">{t.app.resultTitle}</h1>
                        <p className="mt-3 text-slate-600">{t.app.processingMsg}</p>
                    </div>
                )}

                {status === "failed" && (
                    <div className="rounded-3xl border border-red-200 bg-white p-12 text-center" data-testid="results-failed">
                        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-red-50 text-red-600">
                            <AlertCircle className="h-7 w-7" />
                        </div>
                        <h1 className="mt-5 font-heading text-2xl font-light text-slate-900">{t.app.failed}</h1>
                        <p className="mt-3 text-slate-600">{t.app.failedMsg}</p>
                        <Button onClick={() => navigate("/app/new")}
                            className="mt-6 rounded-full bg-emerald-500 px-6 text-white hover:bg-emerald-600"
                            data-testid="results-retry">
                            {t.app.tryAgain}
                        </Button>
                    </div>
                )}

                {status === "complete" && (
                    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
                        <div className="flex flex-col items-start justify-between gap-4 md:flex-row md:items-center">
                            <h1 className="font-heading text-3xl font-light tracking-tight text-slate-900 sm:text-4xl"
                                data-testid="results-title">
                                {ROOM_LABELS[project.room_type] || project.room_type} — {t.app.resultTitle}
                            </h1>
                            {project.pdf_storage_path ? (
                                <Button onClick={downloadPdf} disabled={downloading}
                                    className="rounded-full bg-emerald-500 px-6 text-white hover:bg-emerald-600"
                                    data-testid="results-download-pdf">
                                    {downloading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
                                    {t.app.downloadPdf}
                                </Button>
                            ) : (
                                <Button onClick={() => navigate("/app/billing")} variant="outline"
                                    className="rounded-full border-amber-300 text-amber-700 hover:bg-amber-50"
                                    data-testid="results-upgrade-pdf">
                                    <Lock className="mr-2 h-4 w-4" /> {t.app.upgrade}
                                </Button>
                            )}
                        </div>

                        <div className="mt-6">
                            <ProjectCompare projectId={project.id}
                                beforeLabel={t.hero.beforeLabel} afterLabel={t.hero.afterLabel}
                                className="aspect-[16/10] w-full shadow-md" testIdPrefix="results-compare" />
                        </div>

                        {project.watermarked && (
                            <p className="mt-3 rounded-xl bg-amber-50 p-3 text-center text-sm text-amber-800" data-testid="results-watermark-note">
                                {t.app.watermarkNote}
                            </p>
                        )}

                        {plan && (
                            <>
                                <div className="mt-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
                                    <Stat Icon={Gauge} label={t.app.score} value={`${plan.organization_score ?? "—"}/100`} />
                                    <Stat Icon={DollarSign} label={t.app.cost} value={`$${Number(plan.estimated_cost || 0).toLocaleString()}`} />
                                    <Stat Icon={Clock} label={t.app.time} value={plan.estimated_time || "—"} />
                                    <Stat Icon={Wrench} label={t.app.difficulty} value={plan.difficulty || "—"} />
                                </div>

                                <div className="mt-10 grid grid-cols-1 gap-8 lg:grid-cols-[1.1fr_1fr]">
                                    <div className="rounded-2xl border border-slate-200 bg-white p-7" data-testid="results-plan">
                                        <div className="flex items-center gap-2 text-emerald-700">
                                            <ListChecks className="h-5 w-5" />
                                            <h2 className="font-heading text-xl font-medium text-slate-900">{t.app.organizationPlan}</h2>
                                        </div>
                                        <p className="mt-3 text-slate-600">{plan.summary}</p>
                                        <ol className="mt-5 space-y-4">
                                            {(plan.steps || []).map((s, i) => (
                                                <li key={i} className="flex gap-3" data-testid={`results-step-${i}`}>
                                                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-sm font-semibold text-white">{i + 1}</span>
                                                    <div>
                                                        <div className="font-medium text-slate-900">{s.title}</div>
                                                        <div className="text-sm text-slate-600">{s.detail}</div>
                                                    </div>
                                                </li>
                                            ))}
                                        </ol>
                                    </div>

                                    <div className="rounded-2xl border border-slate-200 bg-white p-7" data-testid="results-shopping">
                                        <div className="flex items-center gap-2 text-emerald-700">
                                            <ShoppingBag className="h-5 w-5" />
                                            <h2 className="font-heading text-xl font-medium text-slate-900">{t.app.shoppingList}</h2>
                                        </div>
                                        <ul className="mt-4 space-y-4">
                                            {(plan.shopping_list || []).map((item, i) => (
                                                <li key={i} className="border-b border-slate-100 pb-4 last:border-0" data-testid={`results-item-${i}`}>
                                                    <div className="flex items-start justify-between gap-2">
                                                        <span className="font-medium text-slate-900">{item.name} <span className="text-slate-400">×{item.quantity || 1}</span></span>
                                                        <span className="shrink-0 text-sm font-medium text-emerald-700">{item.price_range || `$${item.est_price || 0}`}</span>
                                                    </div>
                                                    {item.reason && <p className="mt-1 text-sm text-slate-500">{item.reason}</p>}
                                                    {item.affiliate_links && (
                                                        <div className="mt-2 flex flex-wrap gap-2">
                                                            {item.affiliate_links.map((l, j) => (
                                                                <a key={j} href={l.url} target="_blank" rel="noreferrer"
                                                                    className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-emerald-50 hover:text-emerald-700"
                                                                    data-testid={`results-affiliate-${i}-${j}`}>
                                                                    {l.store} <ExternalLink className="h-3 w-3" />
                                                                </a>
                                                            ))}
                                                        </div>
                                                    )}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                </div>
                            </>
                        )}
                    </motion.div>
                )}
            </main>
        </div>
    );
};

export default Results;
