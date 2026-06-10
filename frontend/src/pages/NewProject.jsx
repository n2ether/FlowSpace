import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Upload, X, Sparkles, Loader2, ArrowLeft, Plus } from "lucide-react";
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
const PLAN_MAX_PHOTOS = { free: 1, pro: 3, premium: 10 };

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
    const a = t.app;
    const [roomType, setRoomType] = useState("");
    const [style, setStyle] = useState("");
    const [photos, setPhotos] = useState([]); // array of data URLs
    const [submitting, setSubmitting] = useState(false);

    const plan = user?.subscription_plan || "free";
    const limit = user?.monthly_generation_limit ?? 1;
    const used = user?.monthly_generations_used ?? 0;
    const isPremium = plan === "premium";
    const remaining = isPremium ? Infinity : Math.max(0, limit - used);
    const planMaxPhotos = PLAN_MAX_PHOTOS[plan] ?? 1;
    const maxPhotos = isPremium ? planMaxPhotos : Math.min(planMaxPhotos, remaining);
    const noCredits = remaining <= 0;

    const handleFiles = async (fileList) => {
        const files = Array.from(fileList || []);
        if (!files.length) return;
        const room = maxPhotos - photos.length;
        if (room <= 0) {
            toast.error(`${a.photoLimitReached} (${maxPhotos})`);
            return;
        }
        const accepted = [];
        for (const file of files.slice(0, room)) {
            if (file.size > MAX_FILE_BYTES) {
                toast.error(`${file.name}: too large (max 5MB)`);
                continue;
            }
            const dataUrl = await new Promise((res, rej) => {
                const r = new FileReader();
                r.onload = () => res(r.result);
                r.onerror = rej;
                r.readAsDataURL(file);
            });
            accepted.push(dataUrl);
        }
        if (files.length > room) toast.info(`${a.onlyAdded} ${room}`);
        setPhotos((prev) => [...prev, ...accepted].slice(0, maxPhotos));
    };

    const removePhoto = (i) => setPhotos((prev) => prev.filter((_, idx) => idx !== i));

    const canSubmit = roomType && style && photos.length > 0 && !submitting && !noCredits;

    const submit = async () => {
        if (!canSubmit) return;
        setSubmitting(true);
        try {
            const r = await authApi.post("/projects", {
                room_type: roomType, style, photos, language: lang,
            });
            await checkAuth();
            navigate(`/app/project/${r.data.id}`);
        } catch (e) {
            const detail = e?.response?.data?.detail || "";
            if (e?.response?.status === 402) {
                toast.error(a.creditLimit);
                navigate("/app/billing");
            } else if (typeof detail === "string" && detail.startsWith("too_many_photos")) {
                toast.error(`${a.photoLimitReached} (${detail.split(":")[1]})`);
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
                    <ArrowLeft className="h-4 w-4" /> {a.dashboard}
                </button>

                <div className="mx-auto max-w-2xl">
                    <div className="mb-8 text-center">
                        <h1 className="font-heading text-3xl font-light tracking-tight text-slate-900 sm:text-4xl"
                            data-testid="new-title">
                            {a.newTitle}
                        </h1>
                        <p className="mt-3 text-slate-600">{a.newSub}</p>
                    </div>

                    {noCredits && (
                        <div className="mb-6 flex items-center justify-between gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-800"
                            data-testid="new-no-credits">
                            <span className="text-sm">{a.creditLimit}</span>
                            <Button onClick={() => navigate("/app/billing")}
                                className="rounded-full bg-amber-500 text-white hover:bg-amber-600" size="sm">
                                {a.upgrade}
                            </Button>
                        </div>
                    )}

                    <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm md:p-10">
                        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                            <div>
                                <Label>{a.roomType}</Label>
                                <Select value={roomType} onValueChange={setRoomType}>
                                    <SelectTrigger className="mt-1.5" data-testid="new-room-select">
                                        <SelectValue placeholder={a.roomType} />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {ROOM_OPTIONS.map(([k, v]) => (
                                            <SelectItem key={k} value={k} data-testid={`new-room-${k}`}>{v}</SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                            <div>
                                <Label>{a.style}</Label>
                                <Select value={style} onValueChange={setStyle}>
                                    <SelectTrigger className="mt-1.5" data-testid="new-style-select">
                                        <SelectValue placeholder={a.style} />
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
                            <div className="flex items-center justify-between">
                                <Label>{a.uploadPhotosTitle}</Label>
                                <span className="text-xs text-slate-400" data-testid="new-photo-counter">
                                    {photos.length}/{isPremium ? planMaxPhotos : maxPhotos} · {a.eachPhotoCredit}
                                </span>
                            </div>

                            <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-3">
                                {photos.map((src, i) => (
                                    <div key={i} className="relative overflow-hidden rounded-xl border border-slate-200" data-testid={`new-photo-${i}`}>
                                        <img src={src} alt={`room ${i + 1}`} className="h-28 w-full object-cover" />
                                        <button onClick={() => removePhoto(i)}
                                            className="absolute right-2 top-2 flex h-7 w-7 items-center justify-center rounded-full bg-slate-900/80 text-white hover:bg-red-600"
                                            data-testid={`new-photo-remove-${i}`}>
                                            <X className="h-3.5 w-3.5" />
                                        </button>
                                    </div>
                                ))}
                                {photos.length < maxPhotos && (
                                    <>
                                        <label htmlFor="room-photos"
                                            className="flex h-28 cursor-pointer flex-col items-center justify-center gap-1.5 rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 text-center transition-colors hover:border-emerald-400"
                                            data-testid="new-photo-drop">
                                            {photos.length === 0
                                                ? <Upload className="h-6 w-6 text-emerald-600" />
                                                : <Plus className="h-6 w-6 text-emerald-600" />}
                                            <span className="px-2 text-xs font-medium text-slate-600">
                                                {photos.length === 0 ? a.uploadPhoto : a.addPhoto}
                                            </span>
                                        </label>
                                        <input id="room-photos" type="file" accept="image/*" multiple={maxPhotos > 1}
                                            className="hidden" onChange={(e) => handleFiles(e.target.files)}
                                            data-testid="new-photo-input" />
                                    </>
                                )}
                            </div>
                            <p className="mt-2 text-xs text-slate-500">{a.uploadHelp}</p>
                        </div>

                        <Button onClick={submit} disabled={!canSubmit}
                            className="mt-8 w-full rounded-full bg-emerald-500 py-6 text-base text-white hover:bg-emerald-600 disabled:opacity-60"
                            data-testid="new-generate-btn">
                            {submitting ? (
                                <><Loader2 className="mr-2 h-5 w-5 animate-spin" /> {a.generating}</>
                            ) : (
                                <><Sparkles className="mr-2 h-5 w-5" /> {a.generate}
                                    {photos.length > 1 ? ` (${photos.length})` : ""}</>
                            )}
                        </Button>
                    </div>
                </div>
            </main>
        </div>
    );
};

export default NewProject;
