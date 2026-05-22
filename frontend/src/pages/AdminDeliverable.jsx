import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
    ArrowLeft,
    FileDown,
    Save,
    Plus,
    Trash2,
    Image as ImageIcon,
    Loader2,
    Sparkles,
} from "lucide-react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Label } from "../components/ui/label";
import { adminClient, API } from "../lib/api";
import { toast } from "sonner";

const blankDeliverable = {
    intro: "",
    needs: [""],
    zones: [{ title: "", desc: "" }],
    wall_color_name: "",
    wall_color_code: "",
    wall_color_hex: "#cfd7d3",
    wall_color_note: "",
    shopping_list: [{ name: "", qty: 1, price: 0 }],
    budget_note: "",
    strategy: [""],
    action_plan: [""],
    benefits: [""],
    notes: "",
    summary: "",
    attachment_note: "",
    shopping_links: [{ name: "", url: "" }],
    front_view_url: "",
    floor_plan_url: "",
    view_1_url: "",
    view_2_url: "",
    view_3_url: "",
    include_customer_photos: true,
};

const SectionTitle = ({ children }) => (
    <h3 className="mt-8 font-heading text-lg font-medium text-slate-900">
        {children}
    </h3>
);

const ListEditor = ({ label, items, onChange, placeholder, testIdPrefix }) => (
    <div>
        <Label>{label}</Label>
        <div className="mt-2 space-y-2">
            {(items || []).map((v, i) => (
                <div key={i} className="flex gap-2">
                    <Input
                        value={v}
                        onChange={(e) => {
                            const next = [...items];
                            next[i] = e.target.value;
                            onChange(next);
                        }}
                        placeholder={placeholder}
                        data-testid={`${testIdPrefix}-${i}`}
                    />
                    <Button
                        type="button"
                        variant="ghost"
                        onClick={() => onChange(items.filter((_, j) => j !== i))}
                        className="text-red-600 hover:bg-red-50"
                        data-testid={`${testIdPrefix}-remove-${i}`}
                    >
                        <Trash2 className="h-4 w-4" />
                    </Button>
                </div>
            ))}
            <Button
                type="button"
                variant="outline"
                onClick={() => onChange([...(items || []), ""])}
                className="rounded-full"
                data-testid={`${testIdPrefix}-add`}
            >
                <Plus className="mr-1 h-4 w-4" /> Add
            </Button>
        </div>
    </div>
);

const ImageUrlField = ({ label, value, onChange, token, testId, onAiGenerate, aiBusy }) => {
    const [busy, setBusy] = useState(false);
    const handleUpload = async (file) => {
        if (!file) return;
        setBusy(true);
        try {
            const fd = new FormData();
            fd.append("file", file);
            const client = adminClient(token);
            const res = await client.post("/uploads/photo", fd, {
                headers: { "Content-Type": "multipart/form-data" },
            });
            if (res.data?.url) {
                onChange(res.data.url);
                toast.success("Uploaded");
            }
        } catch (e) {
            console.error(e);
            toast.error("Upload failed");
        } finally {
            setBusy(false);
        }
    };
    const previewSrc = value
        ? value.startsWith("http")
            ? value
            : `${API.replace("/api", "")}${value}`
        : null;
    return (
        <div>
            <Label>{label}</Label>
            <div className="mt-2 flex items-center gap-3">
                <div className="flex h-16 w-24 items-center justify-center overflow-hidden rounded-md border border-slate-200 bg-slate-50">
                    {previewSrc ? (
                        <img
                            src={previewSrc}
                            alt={label}
                            className="h-full w-full object-cover"
                        />
                    ) : (
                        <ImageIcon className="h-5 w-5 text-slate-300" />
                    )}
                </div>
                <div className="flex flex-1 flex-col gap-2">
                    <Input
                        value={value || ""}
                        onChange={(e) => onChange(e.target.value)}
                        placeholder="https://… or /api/uploads/photo/…"
                        data-testid={testId}
                    />
                    <div className="flex flex-wrap gap-2">
                        <label className="inline-flex w-fit cursor-pointer items-center gap-1 rounded-full border border-emerald-300 px-3 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-50">
                            {busy ? (
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                                <ImageIcon className="h-3.5 w-3.5" />
                            )}
                            Upload image
                            <input
                                type="file"
                                accept="image/*"
                                className="hidden"
                                onChange={(e) => handleUpload(e.target.files?.[0])}
                                data-testid={`${testId}-file`}
                            />
                        </label>
                        {onAiGenerate ? (
                            <button
                                type="button"
                                onClick={onAiGenerate}
                                disabled={aiBusy}
                                className="inline-flex w-fit items-center gap-1 rounded-full border border-violet-300 bg-violet-50 px-3 py-1 text-xs font-medium text-violet-700 hover:bg-violet-100 disabled:opacity-60"
                                data-testid={`${testId}-ai`}
                            >
                                {aiBusy ? (
                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                ) : (
                                    <Sparkles className="h-3.5 w-3.5" />
                                )}
                                {aiBusy ? "Generating…" : "Generate with AI"}
                            </button>
                        ) : null}
                    </div>
                </div>
            </div>
        </div>
    );
};

const AdminDeliverable = () => {
    const navigate = useNavigate();
    const { leadId } = useParams();
    const token = localStorage.getItem("cs_admin_token");
    const [lead, setLead] = useState(null);
    const [form, setForm] = useState(blankDeliverable);
    const [saving, setSaving] = useState(false);
    const [downloading, setDownloading] = useState(false);
    const [drafting, setDrafting] = useState(false);
    const [aiImgBusy, setAiImgBusy] = useState(null); // slot key while generating

    const generateImage = async (slot) => {
        setAiImgBusy(slot);
        try {
            // Save current form first so prompt uses latest wall color / zones
            const client = adminClient(token);
            try {
                await client.put(`/admin/leads/${leadId}/deliverable`, cleanPayload());
            } catch (saveErr) {
                console.warn("pre-generate save failed", saveErr);
            }
            const res = await client.post(
                `/admin/leads/${leadId}/deliverable/generate-image`,
                {},
                { params: { slot }, timeout: 180000 },
            );
            const url = res.data?.url;
            if (url) {
                update(`${slot}_url`, url);
                toast.success("AI rendering generated");
            } else {
                toast.error("No image returned");
            }
        } catch (e) {
            console.error(e);
            const detail = e?.response?.data?.detail || "Generation failed";
            toast.error(detail);
        } finally {
            setAiImgBusy(null);
        }
    };

    const isEmptyText = (v) => !v || (typeof v === "string" && v.trim() === "");
    const isEmptyList = (l) =>
        !l || l.length === 0 || l.every((x) => isEmptyText(x));
    const isEmptyObjList = (l, keys) =>
        !l ||
        l.length === 0 ||
        l.every((it) => keys.every((k) => isEmptyText(it?.[k])));

    const applyDraft = (draft) => {
        setForm((f) => {
            const out = { ...f };
            // Text fields — fill only if currently empty
            for (const k of [
                "intro",
                "wall_color_name",
                "wall_color_code",
                "wall_color_note",
                "budget_note",
                "notes",
                "summary",
                "attachment_note",
            ]) {
                if (isEmptyText(f[k]) && draft[k]) out[k] = draft[k];
            }
            // Hex — only replace if default/empty
            if ((!f.wall_color_hex || f.wall_color_hex === "#cfd7d3") && draft.wall_color_hex) {
                out.wall_color_hex = draft.wall_color_hex;
            }
            // String list fields
            for (const k of ["needs", "strategy", "action_plan", "benefits"]) {
                if (isEmptyList(f[k]) && draft[k]?.length) out[k] = draft[k];
            }
            // Zones
            if (isEmptyObjList(f.zones, ["title", "desc"]) && draft.zones?.length) {
                out.zones = draft.zones;
            }
            // Shopping list
            if (
                isEmptyObjList(f.shopping_list, ["name"]) &&
                draft.shopping_list?.length
            ) {
                out.shopping_list = draft.shopping_list;
            }
            return out;
        });
    };

    const aiDraft = async () => {
        setDrafting(true);
        try {
            const client = adminClient(token);
            const res = await client.post(
                `/admin/leads/${leadId}/deliverable/draft`,
                {},
                { timeout: 90000 },
            );
            if (res.data?.draft) {
                applyDraft(res.data.draft);
                toast.success("AI draft applied to empty fields");
            }
        } catch (e) {
            console.error(e);
            toast.error("AI draft failed. Try again.");
        } finally {
            setDrafting(false);
        }
    };

    useEffect(() => {
        if (!token) {
            navigate("/admin/login");
            return;
        }
        const client = adminClient(token);
        client
            .get(`/admin/leads/${leadId}/deliverable`)
            .then((r) => {
                setLead(r.data.lead);
                if (r.data.deliverable) {
                    setForm({
                        ...blankDeliverable,
                        ...r.data.deliverable,
                        needs: r.data.deliverable.needs?.length
                            ? r.data.deliverable.needs
                            : [""],
                        strategy: r.data.deliverable.strategy?.length
                            ? r.data.deliverable.strategy
                            : [""],
                        action_plan: r.data.deliverable.action_plan?.length
                            ? r.data.deliverable.action_plan
                            : [""],
                        benefits: r.data.deliverable.benefits?.length
                            ? r.data.deliverable.benefits
                            : [""],
                        zones: r.data.deliverable.zones?.length
                            ? r.data.deliverable.zones
                            : [{ title: "", desc: "" }],
                        shopping_list: r.data.deliverable.shopping_list?.length
                            ? r.data.deliverable.shopping_list
                            : [{ name: "", qty: 1, price: 0 }],
                        shopping_links: r.data.deliverable.shopping_links?.length
                            ? r.data.deliverable.shopping_links
                            : [{ name: "", url: "" }],
                    });
                }
            })
            .catch((e) => {
                if (e?.response?.status === 401) {
                    localStorage.removeItem("cs_admin_token");
                    navigate("/admin/login");
                } else {
                    toast.error("Could not load lead");
                }
            });
    }, [leadId, token, navigate]);

    const update = (k, v) => setForm((f) => ({ ...f, [k]: v }));

    const cleanPayload = () => ({
        ...form,
        lead_id: leadId,
        needs: (form.needs || []).filter((x) => x && x.trim()),
        strategy: (form.strategy || []).filter((x) => x && x.trim()),
        action_plan: (form.action_plan || []).filter((x) => x && x.trim()),
        benefits: (form.benefits || []).filter((x) => x && x.trim()),
        zones: (form.zones || []).filter((z) => z.title || z.desc),
        shopping_list: (form.shopping_list || []).filter((s) => s.name && s.name.trim()),
        shopping_links: (form.shopping_links || []).filter((s) => s.name || s.url),
    });

    const save = async () => {
        setSaving(true);
        try {
            const client = adminClient(token);
            await client.put(`/admin/leads/${leadId}/deliverable`, cleanPayload());
            toast.success("Saved");
        } catch (e) {
            console.error(e);
            toast.error("Save failed");
        } finally {
            setSaving(false);
        }
    };

    const downloadPdf = async () => {
        setDownloading(true);
        try {
            // Save first so the latest data is in the PDF
            const client = adminClient(token);
            await client.put(`/admin/leads/${leadId}/deliverable`, cleanPayload());
            const res = await client.get(
                `/admin/leads/${leadId}/deliverable/pdf`,
                { responseType: "blob" },
            );
            const blob = new Blob([res.data], { type: "application/pdf" });
            const url = window.URL.createObjectURL(blob);
            const safeName = (lead?.name || "client").replace(/\s+/g, "_");
            const space = (lead?.space_type || "space");
            const space_cap = space.charAt(0).toUpperCase() + space.slice(1);
            const a = document.createElement("a");
            a.href = url;
            a.download = `FlowSpace_${space_cap}_Plan_${safeName}.pdf`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
            toast.success("PDF generated");
        } catch (e) {
            console.error(e);
            toast.error("Could not generate PDF");
        } finally {
            setDownloading(false);
        }
    };

    if (!lead) {
        return (
            <div className="App min-h-screen bg-slate-50">
                <Header />
                <main className="container-app py-20 text-center text-slate-500">
                    <Loader2 className="mx-auto h-6 w-6 animate-spin" /> Loading…
                </main>
                <Footer />
            </div>
        );
    }

    const space_cap =
        (lead.space_type || "Space").charAt(0).toUpperCase() +
        (lead.space_type || "Space").slice(1);

    return (
        <div className="App min-h-screen bg-slate-50">
            <Header />
            <main className="container-app py-10">
                <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
                    <div>
                        <Button
                            variant="ghost"
                            onClick={() => navigate("/admin")}
                            className="-ml-3 text-slate-600"
                            data-testid="deliverable-back"
                        >
                            <ArrowLeft className="mr-2 h-4 w-4" /> Back to leads
                        </Button>
                        <h1 className="mt-1 font-heading text-3xl font-light tracking-tight text-slate-900">
                            {space_cap} Design Plan
                        </h1>
                        <p className="text-sm text-slate-500">
                            for <strong>{lead.name}</strong> · {lead.email}
                        </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <Button
                            onClick={aiDraft}
                            disabled={drafting}
                            className="rounded-full border border-violet-200 bg-violet-50 text-violet-700 hover:bg-violet-100"
                            data-testid="deliverable-ai-draft"
                        >
                            <Sparkles className="mr-2 h-4 w-4" />
                            {drafting ? "Drafting…" : "Draft with AI"}
                        </Button>
                        <Button
                            onClick={save}
                            disabled={saving}
                            variant="outline"
                            className="rounded-full"
                            data-testid="deliverable-save"
                        >
                            <Save className="mr-2 h-4 w-4" />
                            {saving ? "Saving…" : "Save"}
                        </Button>
                        <Button
                            onClick={downloadPdf}
                            disabled={downloading}
                            className="rounded-full bg-emerald-500 text-white hover:bg-emerald-600"
                            data-testid="deliverable-pdf"
                        >
                            <FileDown className="mr-2 h-4 w-4" />
                            {downloading ? "Generating…" : "Generate PDF"}
                        </Button>
                    </div>
                </div>

                <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.4fr_1fr]">
                    <div className="rounded-2xl border border-slate-200 bg-white p-6 md:p-8">
                        <SectionTitle>Intro</SectionTitle>
                        <Textarea
                            rows={2}
                            value={form.intro}
                            onChange={(e) => update("intro", e.target.value)}
                            placeholder="Personalized opening line…"
                            data-testid="d-intro"
                        />

                        <SectionTitle>{space_cap} Needs</SectionTitle>
                        <ListEditor
                            label=""
                            items={form.needs}
                            onChange={(v) => update("needs", v)}
                            placeholder="e.g. Reading nook"
                            testIdPrefix="d-need"
                        />

                        <SectionTitle>Room Layout & Zones</SectionTitle>
                        <div className="space-y-3">
                            {form.zones.map((z, i) => (
                                <div
                                    key={i}
                                    className="grid grid-cols-1 gap-2 rounded-xl border border-slate-200 p-3 md:grid-cols-[1fr_2fr_auto]"
                                >
                                    <Input
                                        value={z.title}
                                        onChange={(e) => {
                                            const next = [...form.zones];
                                            next[i] = { ...z, title: e.target.value };
                                            update("zones", next);
                                        }}
                                        placeholder="Zone title"
                                        data-testid={`d-zone-title-${i}`}
                                    />
                                    <Input
                                        value={z.desc}
                                        onChange={(e) => {
                                            const next = [...form.zones];
                                            next[i] = { ...z, desc: e.target.value };
                                            update("zones", next);
                                        }}
                                        placeholder="Description"
                                        data-testid={`d-zone-desc-${i}`}
                                    />
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        onClick={() =>
                                            update(
                                                "zones",
                                                form.zones.filter((_, j) => j !== i),
                                            )
                                        }
                                        className="text-red-600"
                                        data-testid={`d-zone-remove-${i}`}
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </div>
                            ))}
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() =>
                                    update("zones", [...form.zones, { title: "", desc: "" }])
                                }
                                className="rounded-full"
                                data-testid="d-zone-add"
                            >
                                <Plus className="mr-1 h-4 w-4" /> Add zone
                            </Button>
                        </div>

                        <SectionTitle>Wall Color</SectionTitle>
                        <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_1fr_auto]">
                            <Input
                                value={form.wall_color_name}
                                onChange={(e) => update("wall_color_name", e.target.value)}
                                placeholder="Name (e.g. Sea Salt)"
                                data-testid="d-wall-name"
                            />
                            <Input
                                value={form.wall_color_code}
                                onChange={(e) => update("wall_color_code", e.target.value)}
                                placeholder="Code (e.g. SW 6204)"
                                data-testid="d-wall-code"
                            />
                            <div className="flex items-center gap-2">
                                <input
                                    type="color"
                                    value={form.wall_color_hex || "#cfd7d3"}
                                    onChange={(e) => update("wall_color_hex", e.target.value)}
                                    className="h-10 w-14 cursor-pointer rounded-md border border-slate-200"
                                    data-testid="d-wall-hex"
                                />
                                <span className="text-xs uppercase tracking-widest text-slate-500">
                                    {form.wall_color_hex}
                                </span>
                            </div>
                        </div>
                        <Textarea
                            rows={2}
                            value={form.wall_color_note}
                            onChange={(e) => update("wall_color_note", e.target.value)}
                            placeholder="Why this color works…"
                            className="mt-3"
                            data-testid="d-wall-note"
                        />

                        <SectionTitle>Shopping List & Budget</SectionTitle>
                        <div className="space-y-2">
                            <div className="hidden grid-cols-[1fr_70px_90px_auto] gap-2 px-1 text-xs font-medium uppercase tracking-widest text-slate-500 md:grid">
                                <span>Item</span>
                                <span>Qty</span>
                                <span>Price</span>
                                <span></span>
                            </div>
                            {form.shopping_list.map((it, i) => (
                                <div
                                    key={i}
                                    className="grid grid-cols-1 gap-2 md:grid-cols-[1fr_70px_90px_auto]"
                                >
                                    <Input
                                        value={it.name}
                                        onChange={(e) => {
                                            const next = [...form.shopping_list];
                                            next[i] = { ...it, name: e.target.value };
                                            update("shopping_list", next);
                                        }}
                                        placeholder="Item"
                                        data-testid={`d-item-name-${i}`}
                                    />
                                    <Input
                                        type="number"
                                        min="0"
                                        step="1"
                                        value={it.qty}
                                        onChange={(e) => {
                                            const next = [...form.shopping_list];
                                            next[i] = { ...it, qty: Number(e.target.value) || 0 };
                                            update("shopping_list", next);
                                        }}
                                        data-testid={`d-item-qty-${i}`}
                                    />
                                    <Input
                                        type="number"
                                        min="0"
                                        step="0.01"
                                        value={it.price}
                                        onChange={(e) => {
                                            const next = [...form.shopping_list];
                                            next[i] = { ...it, price: Number(e.target.value) || 0 };
                                            update("shopping_list", next);
                                        }}
                                        data-testid={`d-item-price-${i}`}
                                    />
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        onClick={() =>
                                            update(
                                                "shopping_list",
                                                form.shopping_list.filter((_, j) => j !== i),
                                            )
                                        }
                                        className="text-red-600"
                                        data-testid={`d-item-remove-${i}`}
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </div>
                            ))}
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() =>
                                    update("shopping_list", [
                                        ...form.shopping_list,
                                        { name: "", qty: 1, price: 0 },
                                    ])
                                }
                                className="rounded-full"
                                data-testid="d-item-add"
                            >
                                <Plus className="mr-1 h-4 w-4" /> Add item
                            </Button>
                        </div>
                        <Textarea
                            rows={2}
                            value={form.budget_note}
                            onChange={(e) => update("budget_note", e.target.value)}
                            placeholder="Budget note (optional)"
                            className="mt-3"
                            data-testid="d-budget-note"
                        />

                        <SectionTitle>Design Strategy</SectionTitle>
                        <ListEditor
                            label=""
                            items={form.strategy}
                            onChange={(v) => update("strategy", v)}
                            placeholder="e.g. Lead with neutrals"
                            testIdPrefix="d-strategy"
                        />

                        <SectionTitle>Simple Action Plan</SectionTitle>
                        <ListEditor
                            label=""
                            items={form.action_plan}
                            onChange={(v) => update("action_plan", v)}
                            placeholder="e.g. Paint walls"
                            testIdPrefix="d-action"
                        />

                        <SectionTitle>Benefits</SectionTitle>
                        <ListEditor
                            label=""
                            items={form.benefits}
                            onChange={(v) => update("benefits", v)}
                            placeholder="e.g. Easier to clean"
                            testIdPrefix="d-benefit"
                        />

                        <SectionTitle>Notes</SectionTitle>
                        <Textarea
                            rows={2}
                            value={form.notes}
                            onChange={(e) => update("notes", e.target.value)}
                            placeholder="e.g. All measurements are approximate."
                            data-testid="d-notes"
                        />

                        <SectionTitle>Design Summary</SectionTitle>
                        <Textarea
                            rows={3}
                            value={form.summary}
                            onChange={(e) => update("summary", e.target.value)}
                            placeholder="Short recap of the design's intent."
                            data-testid="d-summary"
                        />

                        <SectionTitle>Attachment Note</SectionTitle>
                        <Input
                            value={form.attachment_note}
                            onChange={(e) => update("attachment_note", e.target.value)}
                            placeholder="e.g. Quick video included separately."
                            data-testid="d-attach"
                        />

                        <SectionTitle>Shopping Links</SectionTitle>
                        <div className="space-y-2">
                            {form.shopping_links.map((l, i) => (
                                <div
                                    key={i}
                                    className="grid grid-cols-1 gap-2 md:grid-cols-[1fr_2fr_auto]"
                                >
                                    <Input
                                        value={l.name}
                                        onChange={(e) => {
                                            const next = [...form.shopping_links];
                                            next[i] = { ...l, name: e.target.value };
                                            update("shopping_links", next);
                                        }}
                                        placeholder="Item name"
                                        data-testid={`d-link-name-${i}`}
                                    />
                                    <Input
                                        value={l.url}
                                        onChange={(e) => {
                                            const next = [...form.shopping_links];
                                            next[i] = { ...l, url: e.target.value };
                                            update("shopping_links", next);
                                        }}
                                        placeholder="https://…"
                                        data-testid={`d-link-url-${i}`}
                                    />
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        onClick={() =>
                                            update(
                                                "shopping_links",
                                                form.shopping_links.filter((_, j) => j !== i),
                                            )
                                        }
                                        className="text-red-600"
                                        data-testid={`d-link-remove-${i}`}
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </div>
                            ))}
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() =>
                                    update("shopping_links", [
                                        ...form.shopping_links,
                                        { name: "", url: "" },
                                    ])
                                }
                                className="rounded-full"
                                data-testid="d-link-add"
                            >
                                <Plus className="mr-1 h-4 w-4" /> Add link
                            </Button>
                        </div>
                    </div>

                    {/* Sidebar: images */}
                    <aside className="space-y-4">
                        <div className="rounded-2xl border border-slate-200 bg-white p-6">
                            <h3 className="font-heading text-lg font-medium text-slate-900">
                                Renderings & layout
                            </h3>
                            <p className="text-xs text-slate-500">
                                Upload your renderings or paste URLs.
                            </p>
                            <div className="mt-4 space-y-4">
                                <ImageUrlField
                                    label="3D Front View"
                                    value={form.front_view_url}
                                    onChange={(v) => update("front_view_url", v)}
                                    token={token}
                                    testId="d-img-front"
                                    onAiGenerate={() => generateImage("front_view")}
                                    aiBusy={aiImgBusy === "front_view"}
                                />
                                <ImageUrlField
                                    label="Floor Plan (Top View)"
                                    value={form.floor_plan_url}
                                    onChange={(v) => update("floor_plan_url", v)}
                                    token={token}
                                    testId="d-img-floor"
                                />
                                <ImageUrlField
                                    label="View 1"
                                    value={form.view_1_url}
                                    onChange={(v) => update("view_1_url", v)}
                                    token={token}
                                    testId="d-img-v1"
                                />
                                <ImageUrlField
                                    label="View 2"
                                    value={form.view_2_url}
                                    onChange={(v) => update("view_2_url", v)}
                                    token={token}
                                    testId="d-img-v2"
                                />
                                <ImageUrlField
                                    label="View 3"
                                    value={form.view_3_url}
                                    onChange={(v) => update("view_3_url", v)}
                                    token={token}
                                    testId="d-img-v3"
                                />
                            </div>
                        </div>

                        <div className="rounded-2xl border border-slate-200 bg-white p-6">
                            <h3 className="font-heading text-lg font-medium text-slate-900">
                                Customer photos
                            </h3>
                            <label className="mt-3 flex items-center gap-2 text-sm text-slate-700">
                                <input
                                    type="checkbox"
                                    checked={form.include_customer_photos}
                                    onChange={(e) =>
                                        update("include_customer_photos", e.target.checked)
                                    }
                                    data-testid="d-include-photos"
                                />
                                Include uploaded reference photos in PDF
                            </label>
                            {lead.photos && lead.photos.length > 0 ? (
                                <div className="mt-3 grid grid-cols-3 gap-2">
                                    {lead.photos.map((p, i) => {
                                        const src = p.startsWith("http")
                                            ? p
                                            : `${API.replace("/api", "")}${p}`;
                                        return (
                                            <a
                                                key={i}
                                                href={src}
                                                target="_blank"
                                                rel="noreferrer"
                                                className="block aspect-square overflow-hidden rounded-md border border-slate-200"
                                            >
                                                <img
                                                    src={src}
                                                    alt={`ref-${i}`}
                                                    className="h-full w-full object-cover"
                                                />
                                            </a>
                                        );
                                    })}
                                </div>
                            ) : (
                                <p className="mt-3 text-sm text-slate-500">
                                    No customer photos uploaded.
                                </p>
                            )}
                        </div>
                    </aside>
                </div>
            </main>
            <Footer />
        </div>
    );
};

export default AdminDeliverable;
