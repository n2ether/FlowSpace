import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Upload, X, Sparkles, Loader2, ArrowLeft } from "lucide-react";
import AppHeader from "../components/AppHeader";
import { Button } from "../components/ui/button";
import { Label } from "../components/ui/label";
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";
import { authApi } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useLang } from "../context/LanguageContext";
import { toast } from "sonner";

const MAX_FILE_BYTES = 5 * 1024 * 1024;

const ROOM_OPTIONS = [
    ["garage", "Garage"], ["closet", "Closet"], ["pantry", "Pantry"], ["laundry", "Laundry Room"],
    ["bedroom", "Bedroom"], ["office", "Office"], ["bathroom", "Bathroom"], ["playroom", "Playroom"],
    ["kitchen", "Kitchen"], ["living_room", "Living Room"], ["storage", "Storage Room"],
    ["balcony", "Apartment Balcony"], ["other", "Other"],
];

const STYLE_OPTIONS = [
    ["modern", "Modern"], ["minimalist", "Minimalist"], ["family_friendly", "Family-Friendly"],
    ["luxury", "Luxury"], ["budget_friendly", "Budget-Friendly"], ["neutral", "Neutral"],
    ["warm", "Warm"], ["scandinavian", "Scandinavian"], ["industrial", "Industrial"],
    ["farmhouse", "Farmhouse"], ["custom", "Custom"],
];

const NewProject = () => {
    const { lang, t } = useLang();
    const { user, checkAuth } = useAuth();
    const navigate = useNavigate();
    const [roomType, setRoomType] = useState("");
    const [style, setStyle] = useState("");
    const [photo, setPhoto] = useState(null);
    const [submitting, setSubmitting] = useState(false);

    const plan = user?.subscription_plan || "free";
    const limit = user?.monthly_generation_limit ?? 1;
    const used = user?.monthly_generations_used ?? 0;
    const noCredits = plan !== "premium" && used >= limit;

    const handleFile = async (file) => {
        if (!file) return;
        if (file.size > MAX_FILE_BYTES) {
            toast.error("Image too large (max 5MB)");
            return;
        }
        const dataUrl = await new Promise((res, rej) => {
            const r = new FileReader();
            r.onload = () => res(r.result);
            r.onerror = rej;
            r.readAsDataURL(file);
        });
        setPhoto(dataUrl);
    };

    const canSubmit = roomType && style && photo && !submitting && !noCredits;

    const submit = async () => {
        if (!canSubmit) return;
        setSubmitting(true);
        try {
            const r = await authApi.post("/projects", {
                room_type: roomType, style, photo, language: lang,
            });
            await checkAuth();
            navigate(`/app/project/${r.data.id}`);
        } catch (e) {
            if (e?.response?.status === 402) {
                toast.error(t.app.creditLimit);
                navigate("/app/billing");
            } else {
                toast.error("Could not start transformation. Please try again.");
            }
            setSubmitting(false);
        }
    };

    return (
        <div className="min-h-screen bg-slate-50">
            <AppHeader />
            <main className="container-app py-10">
                <button onClick={() => navigate("/app")}
                    className="mb-6 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-emerald-600"
                    data-testid="new-back">
                    <ArrowLeft className="h-4 w-4" /> {t.app.dashboard}
                </button>

                <div className="mx-auto max-w-2xl">
                    <div className="mb-8 text-center">
                        <h1 className="font-heading text-3xl font-light tracking-tight text-slate-900 sm:text-4xl"
                            data-testid="new-title">
                            {t.app.newTitle}
                        </h1>
                        <p className="mt-3 text-slate-600">{t.app.newSub}</p>
                    </div>

                    {noCredits && (
                        <div className="mb-6 flex items-center justify-between gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-800"
                            data-testid="new-no-credits">
                            <span className="text-sm">{t.app.creditLimit}</span>
                            <Button onClick={() => navigate("/app/billing")}
                                className="rounded-full bg-amber-500 text-white hover:bg-amber-600" size="sm">
                                {t.app.upgrade}
                            </Button>
                        </div>
                    )}

                    <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm md:p-10">
                        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                            <div>
                                <Label>{t.app.roomType}</Label>
                                <Select value={roomType} onValueChange={setRoomType}>
                                    <SelectTrigger className="mt-1.5" data-testid="new-room-select">
                                        <SelectValue placeholder={t.app.roomType} />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {ROOM_OPTIONS.map(([k, v]) => (
                                            <SelectItem key={k} value={k} data-testid={`new-room-${k}`}>{v}</SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                            <div>
                                <Label>{t.app.style}</Label>
                                <Select value={style} onValueChange={setStyle}>
                                    <SelectTrigger className="mt-1.5" data-testid="new-style-select">
                                        <SelectValue placeholder={t.app.style} />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {STYLE_OPTIONS.map(([k, v]) => (
                                            <SelectItem key={k} value={k} data-testid={`new-style-${k}`}>{v}</SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        <div className="mt-6">
                            <Label>{t.app.uploadPhoto}</Label>
                            {!photo ? (
                                <>
                                    <label htmlFor="room-photo"
                                        className="mt-1.5 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 px-6 py-12 text-center transition-colors hover:border-emerald-400"
                                        data-testid="new-photo-drop">
                                        <Upload className="h-7 w-7 text-emerald-600" />
                                        <span className="text-sm font-medium text-slate-700">{t.app.uploadPhoto}</span>
                                        <span className="text-xs text-slate-500">{t.app.uploadHelp}</span>
                                    </label>
                                    <input id="room-photo" type="file" accept="image/*" className="hidden"
                                        onChange={(e) => handleFile(e.target.files?.[0])}
                                        data-testid="new-photo-input" />
                                </>
                            ) : (
                                <div className="relative mt-1.5 overflow-hidden rounded-2xl border border-slate-200">
                                    <img src={photo} alt="room" className="max-h-80 w-full object-cover" />
                                    <button onClick={() => setPhoto(null)}
                                        className="absolute right-3 top-3 flex h-8 w-8 items-center justify-center rounded-full bg-slate-900/80 text-white hover:bg-red-600"
                                        data-testid="new-photo-remove">
                                        <X className="h-4 w-4" />
                                    </button>
                                </div>
                            )}
                        </div>

                        <Button onClick={submit} disabled={!canSubmit}
                            className="mt-8 w-full rounded-full bg-emerald-500 py-6 text-base text-white hover:bg-emerald-600 disabled:opacity-60"
                            data-testid="new-generate-btn">
                            {submitting ? (
                                <><Loader2 className="mr-2 h-5 w-5 animate-spin" /> {t.app.generating}</>
                            ) : (
                                <><Sparkles className="mr-2 h-5 w-5" /> {t.app.generate}</>
                            )}
                        </Button>
                    </div>
                </div>
            </main>
        </div>
    );
};

export default NewProject;
