import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LogOut, Plus, Trash2, Users, Image, CreditCard } from "lucide-react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Button } from "../components/ui/button";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "../components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { adminClient } from "../lib/api";
import { useLang } from "../context/LanguageContext";
import { toast } from "sonner";

const Admin = () => {
    const { t } = useLang();
    const navigate = useNavigate();
    const token = localStorage.getItem("cs_admin_token");
    const [leads, setLeads] = useState([]);
    const [gallery, setGallery] = useState([]);
    const [transactions, setTransactions] = useState([]);
    const [newItem, setNewItem] = useState({
        title: "",
        category: "garage",
        before_url: "",
        after_url: "",
    });

    useEffect(() => {
        if (!token) {
            navigate("/admin/login");
            return;
        }
        loadAll();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [token]);

    const client = adminClient(token);

    const loadAll = async () => {
        try {
            const [l, g, x] = await Promise.all([
                client.get("/admin/leads"),
                client.get("/gallery"),
                client.get("/admin/transactions"),
            ]);
            setLeads(l.data || []);
            setGallery(g.data || []);
            setTransactions(x.data || []);
        } catch (e) {
            if (e?.response?.status === 401) {
                localStorage.removeItem("cs_admin_token");
                navigate("/admin/login");
            } else {
                toast.error("Failed to load admin data");
            }
        }
    };

    const addGalleryItem = async (e) => {
        e.preventDefault();
        try {
            await client.post("/admin/gallery", newItem);
            toast.success("Added");
            setNewItem({ title: "", category: "garage", before_url: "", after_url: "" });
            loadAll();
        } catch {
            toast.error("Could not save");
        }
    };

    const deleteItem = async (id) => {
        try {
            await client.delete(`/admin/gallery/${id}`);
            loadAll();
        } catch {
            toast.error("Could not delete");
        }
    };

    const logout = () => {
        localStorage.removeItem("cs_admin_token");
        navigate("/admin/login");
    };

    return (
        <div className="App min-h-screen bg-slate-50">
            <Header />
            <main className="container-app py-12">
                <div className="mb-8 flex items-center justify-between">
                    <h1 className="font-heading text-4xl font-light tracking-tight text-slate-900">
                        {t.admin.dashboard}
                    </h1>
                    <Button
                        variant="outline"
                        onClick={logout}
                        className="rounded-full"
                        data-testid="admin-logout"
                    >
                        <LogOut className="mr-2 h-4 w-4" /> {t.admin.logout}
                    </Button>
                </div>

                <Tabs defaultValue="leads" className="w-full">
                    <TabsList className="mb-6">
                        <TabsTrigger value="leads" data-testid="tab-leads">
                            <Users className="mr-2 h-4 w-4" />
                            {t.admin.leads} ({leads.length})
                        </TabsTrigger>
                        <TabsTrigger value="gallery" data-testid="tab-gallery">
                            <Image className="mr-2 h-4 w-4" />
                            {t.admin.gallery} ({gallery.length})
                        </TabsTrigger>
                        <TabsTrigger value="tx" data-testid="tab-tx">
                            <CreditCard className="mr-2 h-4 w-4" />
                            {t.admin.transactions} ({transactions.length})
                        </TabsTrigger>
                    </TabsList>

                    <TabsContent value="leads">
                        {leads.length === 0 && (
                            <p className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-slate-500">
                                {t.admin.noLeads}
                            </p>
                        )}
                        <div className="space-y-3">
                            {leads.map((l) => (
                                <div
                                    key={l.id}
                                    className="rounded-2xl border border-slate-200 bg-white p-5"
                                    data-testid={`lead-row-${l.id}`}
                                >
                                    <div className="flex flex-wrap items-start justify-between gap-3">
                                        <div>
                                            <div className="font-heading text-lg font-medium text-slate-900">
                                                {l.name}
                                            </div>
                                            <div className="text-sm text-slate-500">
                                                {l.email} {l.phone ? `· ${l.phone}` : ""}
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium uppercase tracking-widest text-emerald-700">
                                                {l.space_type}
                                            </span>
                                            {l.package_id && (
                                                <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium uppercase tracking-widest text-blue-700">
                                                    {l.package_id}
                                                </span>
                                            )}
                                            <span className="rounded-full bg-slate-50 px-3 py-1 text-xs text-slate-500">
                                                {l.language?.toUpperCase()}
                                            </span>
                                        </div>
                                    </div>
                                    {l.biggest_challenge && (
                                        <p className="mt-3 text-sm text-slate-600">
                                            <strong>Challenge:</strong> {l.biggest_challenge}
                                        </p>
                                    )}
                                    {l.goals && (
                                        <p className="mt-1 text-sm text-slate-600">
                                            <strong>Goals:</strong> {l.goals}
                                        </p>
                                    )}
                                    {l.photos && l.photos.length > 0 && (
                                        <div className="mt-3 flex gap-2">
                                            {l.photos.slice(0, 6).map((p, i) => (
                                                <a
                                                    key={i}
                                                    href={p}
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className="block h-14 w-14 overflow-hidden rounded-md border border-slate-200"
                                                >
                                                    <img
                                                        src={p}
                                                        alt="photo"
                                                        className="h-full w-full object-cover"
                                                    />
                                                </a>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </TabsContent>

                    <TabsContent value="gallery">
                        <form
                            onSubmit={addGalleryItem}
                            className="mb-6 rounded-2xl border border-slate-200 bg-white p-6"
                        >
                            <div className="mb-4 flex items-center gap-2">
                                <Plus className="h-4 w-4 text-emerald-600" />
                                <span className="font-heading font-medium">
                                    {t.admin.addGallery}
                                </span>
                            </div>
                            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                                <div>
                                    <Label>{t.admin.title}</Label>
                                    <Input
                                        value={newItem.title}
                                        onChange={(e) =>
                                            setNewItem((n) => ({ ...n, title: e.target.value }))
                                        }
                                        required
                                        data-testid="admin-gallery-title"
                                    />
                                </div>
                                <div>
                                    <Label>{t.admin.category}</Label>
                                    <Select
                                        value={newItem.category}
                                        onValueChange={(v) =>
                                            setNewItem((n) => ({ ...n, category: v }))
                                        }
                                    >
                                        <SelectTrigger data-testid="admin-gallery-category">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="garage">Garage</SelectItem>
                                            <SelectItem value="closet">Closet</SelectItem>
                                            <SelectItem value="storage">Storage</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div>
                                    <Label>{t.admin.beforeUrl}</Label>
                                    <Input
                                        type="url"
                                        value={newItem.before_url}
                                        onChange={(e) =>
                                            setNewItem((n) => ({
                                                ...n,
                                                before_url: e.target.value,
                                            }))
                                        }
                                        required
                                        data-testid="admin-gallery-before"
                                    />
                                </div>
                                <div>
                                    <Label>{t.admin.afterUrl}</Label>
                                    <Input
                                        type="url"
                                        value={newItem.after_url}
                                        onChange={(e) =>
                                            setNewItem((n) => ({
                                                ...n,
                                                after_url: e.target.value,
                                            }))
                                        }
                                        required
                                        data-testid="admin-gallery-after"
                                    />
                                </div>
                            </div>
                            <Button
                                type="submit"
                                className="mt-5 rounded-full bg-emerald-500 text-white hover:bg-emerald-600"
                                data-testid="admin-gallery-save"
                            >
                                {t.admin.save}
                            </Button>
                        </form>

                        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                            {gallery.map((g) => (
                                <div
                                    key={g.id}
                                    className="flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-4"
                                    data-testid={`admin-gallery-row-${g.id}`}
                                >
                                    <img
                                        src={g.after_url}
                                        alt={g.title}
                                        className="h-16 w-20 rounded-md object-cover"
                                    />
                                    <div className="flex-1">
                                        <div className="font-medium text-slate-900">
                                            {g.title}
                                        </div>
                                        <div className="text-xs uppercase tracking-widest text-slate-400">
                                            {g.category}
                                        </div>
                                    </div>
                                    <Button
                                        variant="ghost"
                                        onClick={() => deleteItem(g.id)}
                                        className="text-red-600 hover:bg-red-50"
                                        data-testid={`admin-gallery-delete-${g.id}`}
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </div>
                            ))}
                        </div>
                    </TabsContent>

                    <TabsContent value="tx">
                        {transactions.length === 0 && (
                            <p className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-slate-500">
                                {t.admin.noTx}
                            </p>
                        )}
                        <div className="space-y-3">
                            {transactions.map((x) => (
                                <div
                                    key={x.session_id}
                                    className="rounded-2xl border border-slate-200 bg-white p-5"
                                    data-testid={`tx-row-${x.session_id}`}
                                >
                                    <div className="flex flex-wrap items-center justify-between gap-3">
                                        <div>
                                            <div className="font-medium text-slate-900">
                                                {x.package_id} · ${Number(x.amount).toFixed(2)}{" "}
                                                {(x.currency || "").toUpperCase()}
                                            </div>
                                            <div className="text-xs text-slate-500">
                                                {x.email || "—"} · {x.session_id}
                                            </div>
                                        </div>
                                        <span
                                            className={`rounded-full px-3 py-1 text-xs font-medium uppercase tracking-widest ${
                                                x.payment_status === "paid"
                                                    ? "bg-emerald-50 text-emerald-700"
                                                    : x.payment_status === "expired"
                                                      ? "bg-red-50 text-red-600"
                                                      : "bg-slate-50 text-slate-600"
                                            }`}
                                        >
                                            {x.payment_status}
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </TabsContent>
                </Tabs>
            </main>
            <Footer />
        </div>
    );
};

export default Admin;
