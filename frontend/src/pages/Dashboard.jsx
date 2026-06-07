import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Plus, Sparkles, Clock, AlertCircle, CheckCircle2, ArrowUpRight } from "lucide-react";
import AppHeader from "../components/AppHeader";
import { AuthImage } from "../components/AuthImage";
import { Button } from "../components/ui/button";
import { authApi } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useLang } from "../context/LanguageContext";

const ROOM_LABELS = {
    garage: "Garage", closet: "Closet", pantry: "Pantry", laundry: "Laundry Room",
    bedroom: "Bedroom", office: "Office", bathroom: "Bathroom", playroom: "Playroom",
    kitchen: "Kitchen", living_room: "Living Room", storage: "Storage Room",
    balcony: "Balcony", other: "Other",
};

const StatusBadge = ({ status }) => {
    const { t } = useLang();
    const map = {
        complete: { cls: "bg-emerald-50 text-emerald-700", Icon: CheckCircle2, label: t.app.complete },
        processing: { cls: "bg-blue-50 text-blue-700", Icon: Clock, label: t.app.processing },
        failed: { cls: "bg-red-50 text-red-600", Icon: AlertCircle, label: t.app.failed },
    };
    const m = map[status] || map.processing;
    return (
        <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${m.cls}`}>
            <m.Icon className="h-3.5 w-3.5" /> {m.label}
        </span>
    );
};

const Dashboard = () => {
    const { user } = useAuth();
    const { t } = useLang();
    const navigate = useNavigate();
    const [projects, setProjects] = useState([]);
    const [loaded, setLoaded] = useState(false);

    const load = async () => {
        try {
            const r = await authApi.get("/projects");
            setProjects(r.data || []);
            return r.data || [];
        } catch {
            return [];
        } finally {
            setLoaded(true);
        }
    };

    useEffect(() => {
        let timer;
        const tick = async () => {
            const data = await load();
            if (data.some((p) => p.status === "processing")) {
                timer = setTimeout(tick, 5000);
            }
        };
        tick();
        return () => clearTimeout(timer);
    }, []);

    const plan = user?.subscription_plan || "free";
    const limit = user?.monthly_generation_limit ?? 1;
    const used = user?.monthly_generations_used ?? 0;
    const remaining = plan === "premium" ? t.app.unlimited : Math.max(0, limit - used);

    return (
        <div className="min-h-screen bg-slate-50">
            <AppHeader active="dashboard" />
            <main className="container-app py-10">
                <div className="flex flex-col items-start justify-between gap-5 md:flex-row md:items-center">
                    <div>
                        <h1 className="font-heading text-3xl font-light tracking-tight text-slate-900 sm:text-4xl"
                            data-testid="dashboard-title">
                            {t.app.welcome}, {user?.name?.split(" ")[0] || ""}
                        </h1>
                        <p className="mt-2 flex items-center gap-2 text-slate-600">
                            <Sparkles className="h-4 w-4 text-emerald-500" />
                            {remaining} {t.app.credits} · {t.app.plan}: <span className="font-medium capitalize">{plan}</span>
                        </p>
                    </div>
                    <Button onClick={() => navigate("/app/new")}
                        className="rounded-full bg-emerald-500 px-6 py-6 text-base text-white hover:bg-emerald-600"
                        data-testid="dashboard-new-project">
                        <Plus className="mr-2 h-5 w-5" /> {t.app.newProject}
                    </Button>
                </div>

                {loaded && projects.length === 0 && (
                    <div className="mt-12 rounded-3xl border border-dashed border-slate-300 bg-white p-12 text-center"
                        data-testid="dashboard-empty">
                        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-50 text-emerald-600">
                            <Sparkles className="h-7 w-7" />
                        </div>
                        <p className="mt-5 text-slate-600">{t.app.noProjects}</p>
                        <Button onClick={() => navigate("/app/new")}
                            className="mt-6 rounded-full bg-emerald-500 px-6 text-white hover:bg-emerald-600"
                            data-testid="dashboard-empty-cta">
                            <Plus className="mr-2 h-4 w-4" /> {t.app.newProject}
                        </Button>
                    </div>
                )}

                <div className="mt-10 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
                    {projects.map((p, i) => (
                        <motion.button
                            key={p.id}
                            initial={{ opacity: 0, y: 12 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.4, delay: i * 0.04 }}
                            onClick={() => navigate(`/app/project/${p.id}`)}
                            className="group overflow-hidden rounded-2xl border border-slate-200 bg-white text-left transition-all hover:-translate-y-1 hover:shadow-lg"
                            data-testid={`project-card-${p.id}`}>
                            <div className="relative aspect-[4/3] w-full overflow-hidden bg-slate-100">
                                {p.status === "complete" && p.generated_storage_path ? (
                                    <AuthImage path={`/projects/${p.id}/image/generated`} alt={p.room_type}
                                        className="h-full w-full object-cover transition-transform group-hover:scale-105" />
                                ) : (
                                    <div className="flex h-full w-full items-center justify-center text-slate-400">
                                        {p.status === "failed"
                                            ? <AlertCircle className="h-8 w-8 text-red-400" />
                                            : <Clock className="h-8 w-8 animate-pulse" />}
                                    </div>
                                )}
                            </div>
                            <div className="flex items-center justify-between p-4">
                                <div>
                                    <div className="font-heading font-medium text-slate-900">
                                        {ROOM_LABELS[p.room_type] || p.room_type}
                                    </div>
                                    <div className="mt-1"><StatusBadge status={p.status} /></div>
                                </div>
                                <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-emerald-50 text-emerald-600">
                                    <ArrowUpRight className="h-4 w-4" />
                                </span>
                            </div>
                        </motion.button>
                    ))}
                </div>
            </main>
        </div>
    );
};

export default Dashboard;
