import React, { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, ArrowRight, Check, Upload, X, Loader2 } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import { Label } from "./ui/label";
import { Progress } from "./ui/progress";
import { useLang } from "../context/LanguageContext";
import { api, API } from "../lib/api";
import { toast } from "sonner";

const MAX_PHOTOS = 8;
const MAX_FILE_BYTES = 10 * 1024 * 1024;

const initialForm = {
    space_type: "",
    bothers_about: [],
    bothers_other: "",
    desired_feeling: [],
    feeling_other: "",
    must_stay: "",
    storage_needs: [],
    style_prefs: [],
    color_prefs: [],
    budget: "",
    diy_level: "",
    daily_improvement: "",
    photos: [], // {id, url}
    name: "",
    email: "",
    phone: "",
    package_id: "",
};

const Chip = ({ active, onClick, children, disabled, testId }) => (
    <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        data-testid={testId}
        className={`rounded-full border px-4 py-2.5 text-sm font-medium transition-all ${
            active
                ? "border-emerald-500 bg-emerald-500 text-white shadow-sm"
                : disabled
                  ? "cursor-not-allowed border-slate-200 bg-slate-50 text-slate-400"
                  : "border-slate-200 bg-white text-slate-700 hover:border-emerald-300 hover:bg-emerald-50"
        }`}
    >
        {active && <Check className="mr-1.5 inline h-3.5 w-3.5" strokeWidth={3} />}
        {children}
    </button>
);

const Questionnaire = ({ presetPackage = "", onDone, embedded = false }) => {
    const { t, lang } = useLang();
    const q = t.questionnaire;
    const [step, setStep] = useState(0);
    const [submitting, setSubmitting] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [done, setDone] = useState(false);
    const [form, setForm] = useState({ ...initialForm, package_id: presetPackage });

    const update = useCallback((k, v) => setForm((f) => ({ ...f, [k]: v })), []);

    const toggleInList = (key, value, max = null) => {
        setForm((f) => {
            const list = f[key] || [];
            if (list.includes(value)) {
                return { ...f, [key]: list.filter((x) => x !== value) };
            }
            if (max && list.length >= max) {
                toast.message(q.limitReached);
                return f;
            }
            return { ...f, [key]: [...list, value] };
        });
    };

    const steps = [
        { id: "space", required: true },
        { id: "bothers", required: false },
        { id: "feeling", required: false },
        { id: "must_stay", required: false },
        { id: "storage", required: false },
        { id: "style", required: false },
        { id: "budget", required: false },
        { id: "diy", required: false },
        { id: "photos", required: false },
        { id: "final", required: false },
        { id: "contact", required: true },
    ];

    const canNext = () => {
        const id = steps[step].id;
        if (id === "space") return !!form.space_type;
        if (id === "contact")
            return (
                form.name.trim().length > 1 && /^\S+@\S+\.\S+$/.test(form.email)
            );
        return true;
    };

    const next = () => {
        if (!canNext()) {
            toast.error(q.required);
            return;
        }
        if (step < steps.length - 1) setStep(step + 1);
        else submit();
    };

    const back = () => step > 0 && setStep(step - 1);

    const handleFiles = async (files) => {
        const arr = Array.from(files || []);
        if (arr.length === 0) return;
        const remaining = MAX_PHOTOS - form.photos.length;
        const sliced = arr.slice(0, remaining);
        setUploading(true);
        const uploaded = [];
        for (const f of sliced) {
            if (f.size > MAX_FILE_BYTES) {
                toast.error(`${f.name}: ${q.tooLarge}`);
                continue;
            }
            try {
                const fd = new FormData();
                fd.append("file", f);
                const res = await api.post("/uploads/photo", fd, {
                    headers: { "Content-Type": "multipart/form-data" },
                });
                if (res.data?.url) uploaded.push({ id: res.data.id, url: res.data.url });
            } catch (e) {
                console.error(e);
                toast.error(q.uploadFailed);
            }
        }
        if (uploaded.length) update("photos", [...form.photos, ...uploaded]);
        setUploading(false);
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
                biggest_challenge: null,
                goals: null,
                timeline: null,
                photos: form.photos.map((p) => p.url),
                bothers_about: form.bothers_about,
                bothers_other: form.bothers_other || null,
                desired_feeling: form.desired_feeling,
                feeling_other: form.feeling_other || null,
                must_stay: form.must_stay || null,
                storage_needs: form.storage_needs,
                style_prefs: form.style_prefs,
                color_prefs: form.color_prefs,
                budget: form.budget || null,
                diy_level: form.diy_level || null,
                daily_improvement: form.daily_improvement || null,
                language: lang,
            });
            setDone(true);
            onDone?.();
        } catch (e) {
            console.error(e);
            toast.error("Submission failed. Please try again.");
        } finally {
            setSubmitting(false);
        }
    };

    const progress = ((step + 1) / steps.length) * 100;
    const currentId = steps[step].id;

    if (done) {
        return (
            <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-3xl border border-emerald-200 bg-white p-10 text-center shadow-sm"
                data-testid="questionnaire-done"
            >
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500 text-white">
                    <Check className="h-7 w-7" />
                </div>
                <h2 className="mt-5 font-heading text-3xl font-light text-slate-900">
                    {q.thankYou}
                </h2>
                <p className="mt-3 text-slate-600">{q.thankYouSub}</p>
            </motion.div>
        );
    }

    return (
        <div className={embedded ? "" : "rounded-3xl border border-slate-200 bg-white p-6 shadow-sm md:p-10"}>
            <div className="mb-5 flex items-center justify-between text-xs font-medium uppercase tracking-widest text-slate-500">
                <span data-testid="questionnaire-step-label">
                    {q.step} {step + 1} {q.of} {steps.length}
                </span>
                <span className="text-emerald-600">
                    {Math.round(progress)}%
                </span>
            </div>
            <Progress value={progress} className="mb-7 h-1.5" data-testid="questionnaire-progress" />

            <AnimatePresence mode="wait">
                <motion.div
                    key={currentId}
                    initial={{ opacity: 0, x: 16 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -16 }}
                    transition={{ duration: 0.25 }}
                    className="flex flex-col gap-5"
                >
                    {/* Space type */}
                    {currentId === "space" && (
                        <>
                            <h3 className="font-heading text-2xl font-light text-slate-900">{q.spaceTitle}</h3>
                            <p className="text-sm text-slate-500">{q.spaceSub}</p>
                            <div className="flex flex-wrap gap-2 pt-2">
                                {Object.entries(q.spaceOptions).map(([k, v]) => (
                                    <Chip
                                        key={k}
                                        active={form.space_type === k}
                                        onClick={() => update("space_type", k)}
                                        testId={`q-space-${k}`}
                                    >
                                        {v}
                                    </Chip>
                                ))}
                            </div>
                        </>
                    )}

                    {/* Bothers */}
                    {currentId === "bothers" && (
                        <>
                            <h3 className="font-heading text-2xl font-light text-slate-900">{q.bothersTitle}</h3>
                            <p className="text-sm text-emerald-600">{q.maxThree}</p>
                            <div className="flex flex-wrap gap-2 pt-2">
                                {Object.entries(q.bothersOptions).map(([k, v]) => (
                                    <Chip
                                        key={k}
                                        active={form.bothers_about.includes(k)}
                                        disabled={
                                            !form.bothers_about.includes(k) && form.bothers_about.length >= 3
                                        }
                                        onClick={() => toggleInList("bothers_about", k, 3)}
                                        testId={`q-bothers-${k}`}
                                    >
                                        {v}
                                    </Chip>
                                ))}
                            </div>
                            <Label className="mt-3 text-slate-700">{q.other}</Label>
                            <Input
                                value={form.bothers_other}
                                onChange={(e) => update("bothers_other", e.target.value)}
                                placeholder={q.otherPlaceholder}
                                data-testid="q-bothers-other"
                            />
                        </>
                    )}

                    {/* Feeling */}
                    {currentId === "feeling" && (
                        <>
                            <h3 className="font-heading text-2xl font-light text-slate-900">{q.feelingTitle}</h3>
                            <p className="text-sm text-emerald-600">{q.maxThree}</p>
                            <div className="flex flex-wrap gap-2 pt-2">
                                {Object.entries(q.feelingOptions).map(([k, v]) => (
                                    <Chip
                                        key={k}
                                        active={form.desired_feeling.includes(k)}
                                        disabled={
                                            !form.desired_feeling.includes(k) && form.desired_feeling.length >= 3
                                        }
                                        onClick={() => toggleInList("desired_feeling", k, 3)}
                                        testId={`q-feeling-${k}`}
                                    >
                                        {v}
                                    </Chip>
                                ))}
                            </div>
                            <Label className="mt-3 text-slate-700">{q.other}</Label>
                            <Input
                                value={form.feeling_other}
                                onChange={(e) => update("feeling_other", e.target.value)}
                                placeholder={q.otherPlaceholder}
                                data-testid="q-feeling-other"
                            />
                        </>
                    )}

                    {/* Must stay */}
                    {currentId === "must_stay" && (
                        <>
                            <h3 className="font-heading text-2xl font-light text-slate-900">{q.mustStayTitle}</h3>
                            <p className="text-sm text-slate-500">{q.mustStaySub}</p>
                            <Textarea
                                rows={4}
                                value={form.must_stay}
                                onChange={(e) => update("must_stay", e.target.value)}
                                placeholder={q.mustStayPlaceholder}
                                data-testid="q-must-stay"
                            />
                        </>
                    )}

                    {/* Storage */}
                    {currentId === "storage" && (
                        <>
                            <h3 className="font-heading text-2xl font-light text-slate-900">{q.storageTitle}</h3>
                            <p className="text-sm text-emerald-600">{q.chooseAll}</p>
                            <div className="flex flex-wrap gap-2 pt-2">
                                {Object.entries(q.storageOptions).map(([k, v]) => (
                                    <Chip
                                        key={k}
                                        active={form.storage_needs.includes(k)}
                                        onClick={() => toggleInList("storage_needs", k)}
                                        testId={`q-storage-${k}`}
                                    >
                                        {v}
                                    </Chip>
                                ))}
                            </div>
                        </>
                    )}

                    {/* Style preferences */}
                    {currentId === "style" && (
                        <>
                            <h3 className="font-heading text-2xl font-light text-slate-900">{q.styleTitle}</h3>
                            <p className="text-sm text-slate-500">{q.styleSub}</p>

                            <div className="mt-3">
                                <Label className="text-xs font-medium uppercase tracking-widest text-emerald-700">
                                    {q.styleHeading}
                                </Label>
                                <div className="mt-3 flex flex-wrap gap-2">
                                    {Object.entries(q.styleOptions).map(([k, v]) => (
                                        <Chip
                                            key={k}
                                            active={form.style_prefs.includes(k)}
                                            onClick={() => toggleInList("style_prefs", k)}
                                            testId={`q-style-${k}`}
                                        >
                                            {v}
                                        </Chip>
                                    ))}
                                </div>
                            </div>

                            <div className="mt-5">
                                <Label className="text-xs font-medium uppercase tracking-widest text-emerald-700">
                                    {q.colorsHeading}
                                </Label>
                                <div className="mt-3 flex flex-wrap gap-2">
                                    {Object.entries(q.colorOptions).map(([k, v]) => (
                                        <Chip
                                            key={k}
                                            active={form.color_prefs.includes(k)}
                                            onClick={() => toggleInList("color_prefs", k)}
                                            testId={`q-color-${k}`}
                                        >
                                            {v}
                                        </Chip>
                                    ))}
                                </div>
                            </div>
                        </>
                    )}

                    {/* Budget */}
                    {currentId === "budget" && (
                        <>
                            <h3 className="font-heading text-2xl font-light text-slate-900">{q.budgetTitle}</h3>
                            <div className="flex flex-wrap gap-2 pt-2">
                                {Object.entries(q.budgetOptions).map(([k, v]) => (
                                    <Chip
                                        key={k}
                                        active={form.budget === k}
                                        onClick={() => update("budget", k)}
                                        testId={`q-budget-${k}`}
                                    >
                                        {v}
                                    </Chip>
                                ))}
                            </div>
                        </>
                    )}

                    {/* DIY */}
                    {currentId === "diy" && (
                        <>
                            <h3 className="font-heading text-2xl font-light text-slate-900">{q.diyTitle}</h3>
                            <div className="flex flex-wrap gap-2 pt-2">
                                {Object.entries(q.diyOptions).map(([k, v]) => (
                                    <Chip
                                        key={k}
                                        active={form.diy_level === k}
                                        onClick={() => update("diy_level", k)}
                                        testId={`q-diy-${k}`}
                                    >
                                        {v}
                                    </Chip>
                                ))}
                            </div>
                        </>
                    )}

                    {/* Photos */}
                    {currentId === "photos" && (
                        <>
                            <h3 className="font-heading text-2xl font-light text-slate-900">{q.uploadTitle}</h3>
                            <p className="text-sm text-slate-500">{q.uploadSub}</p>
                            <label
                                htmlFor="q-photo-input"
                                className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 px-6 py-10 text-center transition-colors hover:border-emerald-400"
                                data-testid="q-photo-drop"
                            >
                                {uploading ? (
                                    <Loader2 className="h-6 w-6 animate-spin text-emerald-600" />
                                ) : (
                                    <Upload className="h-6 w-6 text-emerald-600" />
                                )}
                                <span className="text-sm font-medium text-slate-700">
                                    {uploading ? q.uploading : q.uploadCta}
                                </span>
                                <span className="text-xs text-slate-500">{q.uploadHelp}</span>
                            </label>
                            <input
                                id="q-photo-input"
                                type="file"
                                accept="image/*"
                                multiple
                                className="hidden"
                                onChange={(e) => handleFiles(e.target.files)}
                                data-testid="q-photo-input"
                            />
                            {form.photos.length > 0 && (
                                <div className="mt-2 grid grid-cols-3 gap-3 sm:grid-cols-4">
                                    {form.photos.map((p, i) => (
                                        <div
                                            key={p.id || i}
                                            className="relative aspect-square overflow-hidden rounded-lg border border-slate-200"
                                            data-testid={`q-photo-thumb-${i}`}
                                        >
                                            <img
                                                src={`${API.replace("/api", "")}${p.url}`}
                                                alt={`upload-${i}`}
                                                className="h-full w-full object-cover"
                                            />
                                            <button
                                                type="button"
                                                onClick={() => removePhoto(i)}
                                                className="absolute right-1 top-1 flex h-6 w-6 items-center justify-center rounded-full bg-slate-900/80 text-white hover:bg-red-600"
                                                data-testid={`q-photo-remove-${i}`}
                                            >
                                                <X className="h-3.5 w-3.5" />
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </>
                    )}

                    {/* Final */}
                    {currentId === "final" && (
                        <>
                            <h3 className="font-heading text-2xl font-light text-slate-900">{q.finalTitle}</h3>
                            <Textarea
                                rows={4}
                                value={form.daily_improvement}
                                onChange={(e) => update("daily_improvement", e.target.value)}
                                placeholder={q.finalPlaceholder}
                                data-testid="q-daily-improvement"
                            />
                        </>
                    )}

                    {/* Contact */}
                    {currentId === "contact" && (
                        <>
                            <h3 className="font-heading text-2xl font-light text-slate-900">{q.contactTitle}</h3>
                            <p className="text-sm text-slate-500">{q.contactSub}</p>
                            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                                <div>
                                    <Label>{q.name}</Label>
                                    <Input
                                        value={form.name}
                                        onChange={(e) => update("name", e.target.value)}
                                        data-testid="q-name"
                                    />
                                </div>
                                <div>
                                    <Label>{q.email}</Label>
                                    <Input
                                        type="email"
                                        value={form.email}
                                        onChange={(e) => update("email", e.target.value)}
                                        data-testid="q-email"
                                    />
                                </div>
                            </div>
                            <Label>{q.phone}</Label>
                            <Input
                                value={form.phone}
                                onChange={(e) => update("phone", e.target.value)}
                                data-testid="q-phone"
                            />

                            <Label className="mt-2">{q.packageTitle}</Label>
                            <div className="grid grid-cols-3 gap-2">
                                {[
                                    { id: "basic", label: t.packages.basic.name },
                                    { id: "standard", label: t.packages.standard.name },
                                    { id: "premium", label: t.packages.premium.name },
                                ].map((p) => (
                                    <button
                                        key={p.id}
                                        type="button"
                                        onClick={() =>
                                            update("package_id", form.package_id === p.id ? "" : p.id)
                                        }
                                        className={`rounded-xl border px-4 py-3 text-sm font-medium transition-all ${
                                            form.package_id === p.id
                                                ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                                                : "border-slate-200 bg-white text-slate-600 hover:border-emerald-300"
                                        }`}
                                        data-testid={`q-pkg-${p.id}`}
                                    >
                                        {p.label}
                                    </button>
                                ))}
                            </div>
                        </>
                    )}
                </motion.div>
            </AnimatePresence>

            <div className="mt-8 flex items-center justify-between gap-3">
                <Button
                    variant="outline"
                    onClick={back}
                    disabled={step === 0}
                    className="rounded-full"
                    data-testid="questionnaire-back-btn"
                >
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    {q.back}
                </Button>
                <Button
                    onClick={next}
                    disabled={submitting || !canNext()}
                    className="rounded-full bg-emerald-500 px-6 text-white hover:bg-emerald-600 disabled:opacity-60"
                    data-testid="questionnaire-next-btn"
                >
                    {step === steps.length - 1
                        ? submitting
                            ? "..."
                            : q.submit
                        : q.next}
                    <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
            </div>
        </div>
    );
};

export default Questionnaire;
