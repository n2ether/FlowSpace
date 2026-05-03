import React, { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, ArrowRight, Check, Upload, X } from "lucide-react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Label } from "../components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "../components/ui/select";
import { Progress } from "../components/ui/progress";
import { useLang } from "../context/LanguageContext";
import { api } from "../lib/api";
import { toast } from "sonner";

const MAX_PHOTOS = 6;
const MAX_FILE_BYTES = 1.5 * 1024 * 1024; // 1.5MB per photo

const Intake = () => {
    const { t, lang } = useLang();
    const navigate = useNavigate();
    const [search] = useSearchParams();
    const presetPackage = search.get("package") || "";

    const [step, setStep] = useState(0);
    const [submitting, setSubmitting] = useState(false);
    const [done, setDone] = useState(false);

    const [form, setForm] = useState({
        name: "",
        email: "",
        phone: "",
        space_type: "",
        biggest_challenge: "",
        goals: "",
        timeline: "",
        package_id: presetPackage,
        photos: [],
    });

    const update = (k, v) => setForm((f) => ({ ...f, [k]: v }));

    const steps = [
        { title: t.intake.fields.spaceType, id: "space" },
        { title: t.intake.fields.challenge, id: "needs" },
        { title: t.intake.fields.photos, id: "photos" },
        { title: t.intake.fields.name, id: "contact" },
    ];

    const canNext = () => {
        if (step === 0) return !!form.space_type;
        if (step === 1) return (form.biggest_challenge || "").trim().length > 0;
        if (step === 2) return true;
        if (step === 3)
            return (
                form.name.trim().length > 1 &&
                /^\S+@\S+\.\S+$/.test(form.email)
            );
        return true;
    };

    const next = () => {
        if (!canNext()) {
            toast.error(lang === "es" ? "Completa este paso" : lang === "pt" ? "Complete esta etapa" : "Please complete this step");
            return;
        }
        if (step < steps.length - 1) setStep(step + 1);
        else submit();
    };

    const back = () => {
        if (step > 0) setStep(step - 1);
    };

    const handleFiles = async (files) => {
        const arr = Array.from(files || []);
        if (arr.length === 0) return;
        const remaining = MAX_PHOTOS - form.photos.length;
        const sliced = arr.slice(0, remaining);
        const encoded = [];
        for (const f of sliced) {
            if (f.size > MAX_FILE_BYTES) {
                toast.error(`${f.name}: too large (max 1.5MB)`);
                continue;
            }
            const dataUrl = await new Promise((res, rej) => {
                const r = new FileReader();
                r.onload = () => res(r.result);
                r.onerror = rej;
                r.readAsDataURL(f);
            });
            encoded.push(dataUrl);
        }
        update("photos", [...form.photos, ...encoded]);
    };

    const removePhoto = (idx) => {
        update(
            "photos",
            form.photos.filter((_, i) => i !== idx),
        );
    };

    const submit = async () => {
        setSubmitting(true);
        try {
            await api.post("/leads", {
                name: form.name,
                email: form.email,
                phone: form.phone || null,
                space_type: form.space_type,
                package_id: form.package_id || null,
                biggest_challenge: form.biggest_challenge,
                goals: form.goals,
                timeline: form.timeline,
                photos: form.photos,
                language: lang,
            });
            setDone(true);
        } catch (e) {
            console.error(e);
            toast.error("Submission failed. Please try again.");
        } finally {
            setSubmitting(false);
        }
    };

    const progress = ((step + 1) / steps.length) * 100;

    return (
        <div className="App min-h-screen bg-slate-50">
            <Header />
            <main className="container-app py-16 md:py-24">
                <div className="mx-auto max-w-2xl">
                    <div className="mb-10 text-center">
                        <h1 className="font-heading text-4xl font-light tracking-tight text-slate-900 sm:text-5xl">
                            {t.intake.title}
                        </h1>
                        <p className="mt-3 text-slate-600">{t.intake.sub}</p>
                    </div>

                    {!done && (
                        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm md:p-10">
                            <div className="mb-6 flex items-center justify-between text-xs font-medium uppercase tracking-widest text-slate-500">
                                <span data-testid="intake-step-label">
                                    {t.intake.step} {step + 1} {t.intake.of} {steps.length}
                                </span>
                                <span>{steps[step].title}</span>
                            </div>
                            <Progress value={progress} className="mb-8 h-1.5" data-testid="intake-progress" />

                            <AnimatePresence mode="wait">
                                <motion.div
                                    key={step}
                                    initial={{ opacity: 0, x: 12 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    exit={{ opacity: 0, x: -12 }}
                                    transition={{ duration: 0.25 }}
                                    className="flex flex-col gap-5"
                                >
                                    {step === 0 && (
                                        <>
                                            <Label>{t.intake.fields.spaceType}</Label>
                                            <Select
                                                value={form.space_type}
                                                onValueChange={(v) => update("space_type", v)}
                                            >
                                                <SelectTrigger data-testid="intake-space-select">
                                                    <SelectValue
                                                        placeholder={t.intake.fields.spaceType}
                                                    />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {Object.entries(t.intake.fields.spaceOptions).map(
                                                        ([k, v]) => (
                                                            <SelectItem
                                                                key={k}
                                                                value={k}
                                                                data-testid={`intake-space-opt-${k}`}
                                                            >
                                                                {v}
                                                            </SelectItem>
                                                        ),
                                                    )}
                                                </SelectContent>
                                            </Select>

                                            <Label className="mt-2">{t.intake.fields.package}</Label>
                                            <div className="grid grid-cols-3 gap-2">
                                                {[
                                                    { id: "basic", label: t.packages.basic.name },
                                                    { id: "standard", label: t.packages.standard.name },
                                                    { id: "premium", label: t.packages.premium.name },
                                                ].map((p) => (
                                                    <button
                                                        key={p.id}
                                                        type="button"
                                                        onClick={() => update("package_id", p.id)}
                                                        className={`rounded-xl border px-4 py-3 text-sm font-medium transition-all ${
                                                            form.package_id === p.id
                                                                ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                                                                : "border-slate-200 bg-white text-slate-600 hover:border-emerald-300"
                                                        }`}
                                                        data-testid={`intake-pkg-${p.id}`}
                                                    >
                                                        {p.label}
                                                    </button>
                                                ))}
                                            </div>
                                        </>
                                    )}

                                    {step === 1 && (
                                        <>
                                            <Label>{t.intake.fields.challenge}</Label>
                                            <Textarea
                                                value={form.biggest_challenge}
                                                onChange={(e) =>
                                                    update("biggest_challenge", e.target.value)
                                                }
                                                placeholder={t.intake.placeholders.challenge}
                                                rows={3}
                                                data-testid="intake-challenge-input"
                                            />
                                            <Label className="mt-2">{t.intake.fields.goals}</Label>
                                            <Textarea
                                                value={form.goals}
                                                onChange={(e) => update("goals", e.target.value)}
                                                placeholder={t.intake.placeholders.goals}
                                                rows={3}
                                                data-testid="intake-goals-input"
                                            />
                                            <Label className="mt-2">{t.intake.fields.timeline}</Label>
                                            <Input
                                                value={form.timeline}
                                                onChange={(e) => update("timeline", e.target.value)}
                                                placeholder="ASAP / 2 weeks / 1 month"
                                                data-testid="intake-timeline-input"
                                            />
                                        </>
                                    )}

                                    {step === 2 && (
                                        <>
                                            <Label>{t.intake.fields.photos}</Label>
                                            <label
                                                htmlFor="photo-input"
                                                className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 px-6 py-10 text-center transition-colors hover:border-emerald-400"
                                                data-testid="intake-photo-drop"
                                            >
                                                <Upload className="h-6 w-6 text-emerald-600" />
                                                <span className="text-sm font-medium text-slate-700">
                                                    {t.intake.fields.photos}
                                                </span>
                                                <span className="text-xs text-slate-500">
                                                    {t.intake.fields.photosHelp}
                                                </span>
                                            </label>
                                            <input
                                                id="photo-input"
                                                type="file"
                                                accept="image/*"
                                                multiple
                                                className="hidden"
                                                onChange={(e) => handleFiles(e.target.files)}
                                                data-testid="intake-photo-input"
                                            />
                                            {form.photos.length > 0 && (
                                                <div className="mt-2 grid grid-cols-3 gap-3">
                                                    {form.photos.map((src, i) => (
                                                        <div
                                                            key={i}
                                                            className="relative aspect-square overflow-hidden rounded-lg border border-slate-200"
                                                        >
                                                            <img
                                                                src={src}
                                                                alt={`photo-${i}`}
                                                                className="h-full w-full object-cover"
                                                            />
                                                            <button
                                                                type="button"
                                                                onClick={() => removePhoto(i)}
                                                                className="absolute right-1 top-1 flex h-6 w-6 items-center justify-center rounded-full bg-slate-900/80 text-white hover:bg-red-600"
                                                                data-testid={`intake-photo-remove-${i}`}
                                                            >
                                                                <X className="h-3.5 w-3.5" />
                                                            </button>
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                        </>
                                    )}

                                    {step === 3 && (
                                        <>
                                            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                                                <div>
                                                    <Label>{t.intake.fields.name}</Label>
                                                    <Input
                                                        value={form.name}
                                                        onChange={(e) => update("name", e.target.value)}
                                                        data-testid="intake-name-input"
                                                    />
                                                </div>
                                                <div>
                                                    <Label>{t.intake.fields.email}</Label>
                                                    <Input
                                                        type="email"
                                                        value={form.email}
                                                        onChange={(e) => update("email", e.target.value)}
                                                        data-testid="intake-email-input"
                                                    />
                                                </div>
                                            </div>
                                            <Label>{t.intake.fields.phone}</Label>
                                            <Input
                                                value={form.phone}
                                                onChange={(e) => update("phone", e.target.value)}
                                                data-testid="intake-phone-input"
                                            />
                                        </>
                                    )}
                                </motion.div>
                            </AnimatePresence>

                            <div className="mt-8 flex items-center justify-between">
                                <Button
                                    variant="outline"
                                    onClick={back}
                                    disabled={step === 0}
                                    className="rounded-full"
                                    data-testid="intake-back-btn"
                                >
                                    <ArrowLeft className="mr-2 h-4 w-4" />
                                    {t.intake.back}
                                </Button>
                                <Button
                                    onClick={next}
                                    disabled={submitting || !canNext()}
                                    className="rounded-full bg-emerald-500 px-6 text-white hover:bg-emerald-600 disabled:opacity-60"
                                    data-testid="intake-next-btn"
                                >
                                    {step === steps.length - 1
                                        ? submitting
                                            ? "..."
                                            : t.intake.submit
                                        : t.intake.next}
                                    <ArrowRight className="ml-2 h-4 w-4" />
                                </Button>
                            </div>
                        </div>
                    )}

                    {done && (
                        <motion.div
                            initial={{ opacity: 0, y: 12 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="rounded-3xl border border-emerald-200 bg-white p-10 text-center shadow-sm"
                            data-testid="intake-done"
                        >
                            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500 text-white">
                                <Check className="h-7 w-7" />
                            </div>
                            <h2 className="mt-5 font-heading text-3xl font-light text-slate-900">
                                {t.intake.thankYou}
                            </h2>
                            <p className="mt-3 text-slate-600">{t.intake.thankYouSub}</p>
                            <Button
                                onClick={() => navigate("/")}
                                className="mt-6 rounded-full bg-slate-900 text-white hover:bg-slate-700"
                                data-testid="intake-back-home"
                            >
                                {t.success.backHome}
                            </Button>
                        </motion.div>
                    )}
                </div>
            </main>
            <Footer />
        </div>
    );
};

export default Intake;
