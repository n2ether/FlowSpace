import React, { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowRight, Loader2, Upload as UploadIcon, X } from "lucide-react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { api, API } from "../lib/api";
import { toast } from "sonner";

const MAX_FILE_BYTES = 10 * 1024 * 1024;
const storeOptions = ["Walmart", "Target", "IKEA", "Amazon", "The Container Store", "Wayfair"];

const initialForm = {
    customer_name: "",
    email: "",
    phone: "",
    room_type: "",
    pain_point: "",
    budget: "",
    preferred_stores: ["Walmart", "Target", "IKEA"],
    style_preference: "",
    rent_or_own: "",
    mounting_allowed: false,
};

const Upload = () => {
    const [params] = useSearchParams();
    const navigate = useNavigate();
    const [form, setForm] = useState(initialForm);
    const [photos, setPhotos] = useState([]);
    const [uploading, setUploading] = useState(false);
    const [submitting, setSubmitting] = useState(false);

    const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));
    const packageId = params.get("package") || "standard";

    const assetUrl = (url) => (url?.startsWith("http") ? url : `${API.replace("/api", "")}${url}`);

    const handleFiles = async (files) => {
        const selected = Array.from(files || []);
        if (!selected.length) return;
        const remaining = 4 - photos.length;
        if (remaining <= 0) {
            toast.error("You can upload up to 4 photos.");
            return;
        }
        setUploading(true);
        const uploaded = [];
        for (const file of selected.slice(0, remaining)) {
            if (!file.type.startsWith("image/")) {
                toast.error(`${file.name} is not an image.`);
                continue;
            }
            if (file.size > MAX_FILE_BYTES) {
                toast.error(`${file.name} is larger than 10MB.`);
                continue;
            }
            try {
                const data = new FormData();
                data.append("file", file);
                const res = await api.post("/uploads/photo", data, {
                    headers: { "Content-Type": "multipart/form-data" },
                });
                uploaded.push({ id: res.data.id, url: res.data.url, name: file.name });
            } catch (error) {
                console.error(error);
                toast.error(`Could not upload ${file.name}.`);
            }
        }
        setPhotos((current) => [...current, ...uploaded]);
        setUploading(false);
    };

    const removePhoto = (index) => setPhotos((current) => current.filter((_, i) => i !== index));

    const toggleStore = (store) => {
        setForm((current) => {
            const stores = current.preferred_stores || [];
            return {
                ...current,
                preferred_stores: stores.includes(store)
                    ? stores.filter((item) => item !== store)
                    : [...stores, store],
            };
        });
    };

    const submit = async (event) => {
        event.preventDefault();
        if (photos.length < 2 || photos.length > 4) {
            toast.error("Please upload 2 to 4 photos of the room.");
            return;
        }
        setSubmitting(true);
        try {
            const res = await api.post("/process-room", {
                ...form,
                package_id: packageId,
                photos: photos.map((photo) => photo.url),
            });
            navigate(`/results/${res.data.id}`);
        } catch (error) {
            console.error(error);
            toast.error(error?.response?.data?.detail || "Could not start your room transformation.");
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="App min-h-screen bg-slate-50">
            <Header />
            <main className="container-app py-12 md:py-16">
                <div className="mx-auto max-w-3xl">
                    <div className="mb-8 rounded-3xl border border-emerald-100 bg-white p-8 shadow-sm">
                        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-emerald-700">
                            FlowSpace upload
                        </p>
                        <h1 className="mt-3 font-heading text-4xl font-light tracking-tight text-slate-900 md:text-5xl">
                            Show us the room. We will preserve the structure and organize the chaos.
                        </h1>
                        <p className="mt-4 text-slate-600">
                            Upload 2-4 photos. The AI prompt is constrained to keep your layout, walls, floors,
                            doors, windows, fixtures, camera angle, and architectural features intact.
                        </p>
                    </div>

                    <form onSubmit={submit} className="space-y-6">
                        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm md:p-8">
                            <div className="flex items-center justify-between gap-4">
                                <div>
                                    <h2 className="font-heading text-2xl font-medium text-slate-900">Room photos</h2>
                                    <p className="mt-1 text-sm text-slate-500">Upload 2 to 4 clear angles of the same space.</p>
                                </div>
                                <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                                    {photos.length}/4
                                </span>
                            </div>
                            <label className="mt-5 flex cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-emerald-300 bg-emerald-50/60 p-8 text-center transition hover:bg-emerald-50">
                                {uploading ? <Loader2 className="h-8 w-8 animate-spin text-emerald-600" /> : <UploadIcon className="h-8 w-8 text-emerald-600" />}
                                <span className="mt-3 font-medium text-slate-800">Click to upload room photos</span>
                                <span className="mt-1 text-sm text-slate-500">JPG, PNG, or HEIC exports under 10MB each</span>
                                <input
                                    type="file"
                                    accept="image/*"
                                    multiple
                                    className="sr-only"
                                    onChange={(event) => handleFiles(event.target.files)}
                                    data-testid="upload-room-photos"
                                />
                            </label>
                            {photos.length > 0 && (
                                <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
                                    {photos.map((photo, index) => (
                                        <div key={photo.id} className="relative overflow-hidden rounded-xl border border-slate-200">
                                            <img src={assetUrl(photo.url)} alt={photo.name || "Room upload"} className="h-32 w-full object-cover" />
                                            <button
                                                type="button"
                                                onClick={() => removePhoto(index)}
                                                className="absolute right-2 top-2 rounded-full bg-white/90 p-1 text-slate-700 shadow"
                                                aria-label="Remove photo"
                                            >
                                                <X className="h-4 w-4" />
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </section>

                        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm md:p-8">
                            <h2 className="font-heading text-2xl font-medium text-slate-900">Intake details</h2>
                            <div className="mt-5 grid grid-cols-1 gap-5 md:grid-cols-2">
                                <div>
                                    <Label>Name</Label>
                                    <Input required value={form.customer_name} onChange={(e) => update("customer_name", e.target.value)} data-testid="upload-name" />
                                </div>
                                <div>
                                    <Label>Email</Label>
                                    <Input required type="email" value={form.email} onChange={(e) => update("email", e.target.value)} data-testid="upload-email" />
                                </div>
                                <div>
                                    <Label>Phone (optional)</Label>
                                    <Input value={form.phone} onChange={(e) => update("phone", e.target.value)} data-testid="upload-phone" />
                                </div>
                                <div>
                                    <Label>Room type</Label>
                                    <Select value={form.room_type} onValueChange={(value) => update("room_type", value)} required>
                                        <SelectTrigger data-testid="upload-room-type"><SelectValue placeholder="Choose a room" /></SelectTrigger>
                                        <SelectContent>
                                            {["garage", "closet", "pantry", "laundry", "bedroom", "office", "playroom", "kitchen", "mudroom", "other"].map((room) => (
                                                <SelectItem key={room} value={room}>{room.replace(/^\w/, (c) => c.toUpperCase())}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="md:col-span-2">
                                    <Label>Pain point</Label>
                                    <Textarea required value={form.pain_point} onChange={(e) => update("pain_point", e.target.value)} placeholder="What feels stressful, cluttered, or hard to maintain?" data-testid="upload-pain-point" />
                                </div>
                                <div>
                                    <Label>Budget</Label>
                                    <Select value={form.budget} onValueChange={(value) => update("budget", value)} required>
                                        <SelectTrigger data-testid="upload-budget"><SelectValue placeholder="Choose a budget" /></SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="under_100">Under $100</SelectItem>
                                            <SelectItem value="100_300">$100-$300</SelectItem>
                                            <SelectItem value="300_700">$300-$700</SelectItem>
                                            <SelectItem value="700_plus">$700+</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div>
                                    <Label>Style preference</Label>
                                    <Input required value={form.style_preference} onChange={(e) => update("style_preference", e.target.value)} placeholder="Minimal, warm, modern, natural..." data-testid="upload-style" />
                                </div>
                                <div>
                                    <Label>Rent or own?</Label>
                                    <Select value={form.rent_or_own} onValueChange={(value) => update("rent_or_own", value)} required>
                                        <SelectTrigger data-testid="upload-rent-own"><SelectValue placeholder="Select one" /></SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="rent">Rent</SelectItem>
                                            <SelectItem value="own">Own</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <label className="flex items-center gap-3 rounded-xl border border-slate-200 p-4 text-sm text-slate-700">
                                    <input
                                        type="checkbox"
                                        checked={form.mounting_allowed}
                                        onChange={(e) => update("mounting_allowed", e.target.checked)}
                                        className="h-4 w-4 accent-emerald-600"
                                        data-testid="upload-mounting"
                                    />
                                    Drilling or wall mounting is allowed
                                </label>
                            </div>

                            <div className="mt-5">
                                <Label>Preferred stores</Label>
                                <div className="mt-2 flex flex-wrap gap-2">
                                    {storeOptions.map((store) => (
                                        <button
                                            key={store}
                                            type="button"
                                            onClick={() => toggleStore(store)}
                                            className={`rounded-full border px-4 py-2 text-sm font-medium ${
                                                form.preferred_stores.includes(store)
                                                    ? "border-emerald-500 bg-emerald-500 text-white"
                                                    : "border-slate-200 bg-white text-slate-700"
                                            }`}
                                        >
                                            {store}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </section>

                        <div className="flex flex-col gap-3 rounded-3xl border border-emerald-100 bg-white p-5 shadow-sm md:flex-row md:items-center md:justify-between">
                            <p className="text-sm text-slate-600">
                                Your job will process in the background. If video generation fails, the PDF is still delivered.
                            </p>
                            <Button
                                type="submit"
                                disabled={submitting || uploading}
                                className="rounded-full bg-emerald-500 px-7 py-6 text-white hover:bg-emerald-600"
                                data-testid="upload-submit"
                            >
                                {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                                Start transformation
                                <ArrowRight className="ml-2 h-4 w-4" />
                            </Button>
                        </div>
                    </form>
                </div>
            </main>
            <Footer />
        </div>
    );
};

export default Upload;
