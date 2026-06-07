import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
    LogOut, Plus, Trash2, Users, Image as ImageIcon, CreditCard, LayoutGrid,
    BarChart3, Tag, FolderKanban, Check,
} from "lucide-react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Button } from "../components/ui/button";
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { adminClient } from "../lib/api";
import { useLang } from "../context/LanguageContext";
import { toast } from "sonner";

const StatCard = ({ label, value }) => (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <div className="text-xs uppercase tracking-widest text-slate-400">{label}</div>
        <div className="mt-1 font-heading text-3xl font-light text-slate-900">{value}</div>
    </div>
);

const Admin = () => {
    const { t } = useLang();
    const navigate = useNavigate();
    const token = localStorage.getItem("cs_admin_token");
    const client = adminClient(token);

    const [stats, setStats] = useState(null);
    const [users, setUsers] = useState([]);
    const [projects, setProjects] = useState([]);
    const [subs, setSubs] = useState([]);
    const [transactions, setTransactions] = useState([]);
    const [gallery, setGallery] = useState([]);
    const [affiliate, setAffiliate] = useState([]);
    const [newItem, setNewItem] = useState({ title: "", category: "garage", before_url: "", after_url: "" });
    const [newAff, setNewAff] = useState({ category: "", product_name: "", product_description: "", affiliate_url: "", image_url: "", price_range: "", room_type: "" });

    useEffect(() => {
        if (!token) {
            navigate("/admin/login");
            return;
        }
        loadAll();
    }, [token]);

    const loadAll = async () => {
        try {
            const [s, u, p, sub, x, g, a] = await Promise.all([
                client.get("/admin/stats"),
                client.get("/admin/users"),
                client.get("/admin/projects"),
                client.get("/admin/subscriptions"),
                client.get("/admin/transactions"),
                client.get("/gallery"),
                client.get("/admin/affiliate"),
            ]);
            setStats(s.data); setUsers(u.data || []); setProjects(p.data || []);
            setSubs(sub.data || []); setTransactions(x.data || []); setGallery(g.data || []);
            setAffiliate(a.data || []);
        } catch (e) {
            if (e?.response?.status === 401) {
                localStorage.removeItem("cs_admin_token");
                navigate("/admin/login");
            } else {
                toast.error("Failed to load admin data");
            }
        }
    };
    const adjustCredits = async (user_id, value) => {
        try {
            await client.post("/admin/credits", { user_id, monthly_generations_used: Number(value) });
            toast.success("Credits updated");
            loadAll();
        } catch {
            toast.error("Could not update credits");
        }
    };

    const addGalleryItem = async (e) => {
        e.preventDefault();
        try {
            await client.post("/admin/gallery", newItem);
            toast.success("Added");
            setNewItem({ title: "", category: "garage", before_url: "", after_url: "" });
            loadAll();
        } catch { toast.error("Could not save"); }
    };

    const deleteGallery = async (id) => {
        try { await client.delete(`/admin/gallery/${id}`); loadAll(); } catch { toast.error("Could not delete"); }
    };

    const addAffiliate = async (e) => {
        e.preventDefault();
        try {
            await client.post("/admin/affiliate", newAff);
            toast.success("Product added");
            setNewAff({ category: "", product_name: "", product_description: "", affiliate_url: "", image_url: "", price_range: "", room_type: "" });
            loadAll();
        } catch { toast.error("Could not save product"); }
    };

    const deleteAffiliate = async (id) => {
        try { await client.delete(`/admin/affiliate/${id}`); loadAll(); } catch { toast.error("Could not delete"); }
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
                    <h1 className="font-heading text-4xl font-light tracking-tight text-slate-900">{t.admin.dashboard}</h1>
                    <Button variant="outline" onClick={logout} className="rounded-full" data-testid="admin-logout">
                        <LogOut className="mr-2 h-4 w-4" /> {t.admin.logout}
                    </Button>
                </div>

                <Tabs defaultValue="overview" className="w-full">
                    <TabsList className="mb-6 flex-wrap">
                        <TabsTrigger value="overview" data-testid="tab-overview"><BarChart3 className="mr-2 h-4 w-4" />Overview</TabsTrigger>
                        <TabsTrigger value="users" data-testid="tab-users"><Users className="mr-2 h-4 w-4" />Users ({users.length})</TabsTrigger>
                        <TabsTrigger value="projects" data-testid="tab-projects"><FolderKanban className="mr-2 h-4 w-4" />Projects ({projects.length})</TabsTrigger>
                        <TabsTrigger value="subs" data-testid="tab-subs"><CreditCard className="mr-2 h-4 w-4" />Subscriptions ({subs.length})</TabsTrigger>
                        <TabsTrigger value="tx" data-testid="tab-tx"><CreditCard className="mr-2 h-4 w-4" />Transactions ({transactions.length})</TabsTrigger>
                        <TabsTrigger value="affiliate" data-testid="tab-affiliate"><Tag className="mr-2 h-4 w-4" />Affiliate ({affiliate.length})</TabsTrigger>
                        <TabsTrigger value="gallery" data-testid="tab-gallery"><ImageIcon className="mr-2 h-4 w-4" />Gallery ({gallery.length})</TabsTrigger>
                    </TabsList>

                    <TabsContent value="overview">
                        {stats && (
                            <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4" data-testid="admin-stats">
                                <StatCard label="Users" value={stats.users} />
                                <StatCard label="Paid users" value={stats.paid_users} />
                                <StatCard label="Revenue (paid)" value={`$${Number(stats.revenue).toLocaleString()}`} />
                                <StatCard label="Projects" value={stats.projects} />
                                <StatCard label="Completed" value={stats.completed} />
                                <StatCard label="Failed" value={stats.failed} />
                                <StatCard label="Free / Pro / Premium" value={`${stats.by_plan?.free || 0} / ${stats.by_plan?.pro || 0} / ${stats.by_plan?.premium || 0}`} />
                            </div>
                        )}
                    </TabsContent>

                    <TabsContent value="users">
                        <div className="space-y-3">
                            {users.map((u) => (
                                <div key={u.user_id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-5" data-testid={`user-row-${u.user_id}`}>
                                    <div>
                                        <div className="font-medium text-slate-900">{u.name} {u.is_admin && <span className="text-xs text-emerald-600">(admin)</span>}</div>
                                        <div className="text-sm text-slate-500">{u.email}</div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium uppercase tracking-widest text-emerald-700">{u.subscription_plan}</span>
                                        <span className="text-sm text-slate-500">{u.monthly_generations_used}/{u.monthly_generation_limit} used</span>
                                        <Input type="number" defaultValue={u.monthly_generations_used} className="w-20"
                                            onBlur={(e) => { if (Number(e.target.value) !== u.monthly_generations_used) adjustCredits(u.user_id, e.target.value); }}
                                            data-testid={`user-credits-${u.user_id}`} />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </TabsContent>

                    <TabsContent value="projects">
                        <div className="space-y-3">
                            {projects.map((p) => (
                                <div key={p.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-5" data-testid={`proj-row-${p.id}`}>
                                    <div>
                                        <div className="font-medium capitalize text-slate-900">{(p.room_type || "").replace("_", " ")} · {(p.style || "").replace("_", " ")}</div>
                                        <div className="text-xs text-slate-500">{p.user_id} · {(p.created_at || "").slice(0, 16).replace("T", " ")}</div>
                                    </div>
                                    <span className={`rounded-full px-3 py-1 text-xs font-medium uppercase tracking-widest ${p.status === "complete" ? "bg-emerald-50 text-emerald-700" : p.status === "failed" ? "bg-red-50 text-red-600" : "bg-blue-50 text-blue-700"}`}>{p.status}</span>
                                </div>
                            ))}
                        </div>
                    </TabsContent>

                    <TabsContent value="subs">
                        <div className="space-y-3">
                            {subs.length === 0 && <p className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-slate-500">No subscriptions yet.</p>}
                            {subs.map((s) => (
                                <div key={s.stripe_subscription_id || s.user_id} className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white p-5" data-testid={`sub-row-${s.user_id}`}>
                                    <div>
                                        <div className="font-medium capitalize text-slate-900">{s.plan_name}</div>
                                        <div className="text-xs text-slate-500">{s.user_id} · {s.stripe_subscription_id}</div>
                                    </div>
                                    <span className={`rounded-full px-3 py-1 text-xs font-medium uppercase tracking-widest ${s.status === "active" ? "bg-emerald-50 text-emerald-700" : "bg-slate-50 text-slate-600"}`}>{s.status}</span>
                                </div>
                            ))}
                        </div>
                    </TabsContent>

                    <TabsContent value="tx">
                        <div className="space-y-3">
                            {transactions.length === 0 && <p className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-slate-500">{t.admin.noTx}</p>}
                            {transactions.map((x) => (
                                <div key={x.session_id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-5" data-testid={`tx-row-${x.session_id}`}>
                                    <div>
                                        <div className="font-medium text-slate-900">{x.plan || x.package_id} · ${Number(x.amount).toFixed(2)} {(x.currency || "").toUpperCase()}</div>
                                        <div className="text-xs text-slate-500">{x.email || "—"}</div>
                                    </div>
                                    <span className={`rounded-full px-3 py-1 text-xs font-medium uppercase tracking-widest ${x.payment_status === "paid" ? "bg-emerald-50 text-emerald-700" : "bg-slate-50 text-slate-600"}`}>{x.payment_status}</span>
                                </div>
                            ))}
                        </div>
                    </TabsContent>

                    <TabsContent value="affiliate">
                        <form onSubmit={addAffiliate} className="mb-6 rounded-2xl border border-slate-200 bg-white p-6">
                            <div className="mb-4 flex items-center gap-2"><Plus className="h-4 w-4 text-emerald-600" /><span className="font-heading font-medium">Add affiliate product</span></div>
                            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                                <div><Label>Product name</Label><Input value={newAff.product_name} onChange={(e) => setNewAff((n) => ({ ...n, product_name: e.target.value }))} required data-testid="aff-name" /></div>
                                <div><Label>Affiliate URL</Label><Input type="url" value={newAff.affiliate_url} onChange={(e) => setNewAff((n) => ({ ...n, affiliate_url: e.target.value }))} required data-testid="aff-url" /></div>
                                <div><Label>Category</Label><Input value={newAff.category} onChange={(e) => setNewAff((n) => ({ ...n, category: e.target.value }))} data-testid="aff-category" /></div>
                                <div><Label>Room type (optional)</Label><Input value={newAff.room_type} onChange={(e) => setNewAff((n) => ({ ...n, room_type: e.target.value }))} placeholder="garage, closet…" data-testid="aff-room" /></div>
                                <div><Label>Price range</Label><Input value={newAff.price_range} onChange={(e) => setNewAff((n) => ({ ...n, price_range: e.target.value }))} placeholder="$40-$60" data-testid="aff-price" /></div>
                                <div><Label>Image URL</Label><Input type="url" value={newAff.image_url} onChange={(e) => setNewAff((n) => ({ ...n, image_url: e.target.value }))} data-testid="aff-image" /></div>
                            </div>
                            <Button type="submit" className="mt-5 rounded-full bg-emerald-500 text-white hover:bg-emerald-600" data-testid="aff-save"><Check className="mr-2 h-4 w-4" />Save</Button>
                        </form>
                        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                            {affiliate.map((a) => (
                                <div key={a.id} className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white p-4" data-testid={`aff-row-${a.id}`}>
                                    <div>
                                        <div className="font-medium text-slate-900">{a.product_name}</div>
                                        <div className="text-xs text-slate-500">{a.category} {a.room_type ? `· ${a.room_type}` : ""} · {a.price_range}</div>
                                    </div>
                                    <Button variant="ghost" onClick={() => deleteAffiliate(a.id)} className="text-red-600 hover:bg-red-50" data-testid={`aff-delete-${a.id}`}><Trash2 className="h-4 w-4" /></Button>
                                </div>
                            ))}
                        </div>
                    </TabsContent>

                    <TabsContent value="gallery">
                        <form onSubmit={addGalleryItem} className="mb-6 rounded-2xl border border-slate-200 bg-white p-6">
                            <div className="mb-4 flex items-center gap-2"><Plus className="h-4 w-4 text-emerald-600" /><span className="font-heading font-medium">{t.admin.addGallery}</span></div>
                            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                                <div><Label>{t.admin.title}</Label><Input value={newItem.title} onChange={(e) => setNewItem((n) => ({ ...n, title: e.target.value }))} required data-testid="admin-gallery-title" /></div>
                                <div><Label>{t.admin.category}</Label>
                                    <Select value={newItem.category} onValueChange={(v) => setNewItem((n) => ({ ...n, category: v }))}>
                                        <SelectTrigger data-testid="admin-gallery-category"><SelectValue /></SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="garage">Garage</SelectItem>
                                            <SelectItem value="closet">Closet</SelectItem>
                                            <SelectItem value="laundry">Laundry</SelectItem>
                                            <SelectItem value="storage">Storage</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div><Label>{t.admin.beforeUrl}</Label><Input type="url" value={newItem.before_url} onChange={(e) => setNewItem((n) => ({ ...n, before_url: e.target.value }))} required data-testid="admin-gallery-before" /></div>
                                <div><Label>{t.admin.afterUrl}</Label><Input type="url" value={newItem.after_url} onChange={(e) => setNewItem((n) => ({ ...n, after_url: e.target.value }))} required data-testid="admin-gallery-after" /></div>
                            </div>
                            <Button type="submit" className="mt-5 rounded-full bg-emerald-500 text-white hover:bg-emerald-600" data-testid="admin-gallery-save">{t.admin.save}</Button>
                        </form>
                        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                            {gallery.map((g) => (
                                <div key={g.id} className="flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-4" data-testid={`admin-gallery-row-${g.id}`}>
                                    <img src={g.after_url} alt={g.title} className="h-16 w-20 rounded-md object-cover" />
                                    <div className="flex-1">
                                        <div className="font-medium text-slate-900">{g.title}</div>
                                        <div className="text-xs uppercase tracking-widest text-slate-400">{g.category}</div>
                                    </div>
                                    <Button variant="ghost" onClick={() => deleteGallery(g.id)} className="text-red-600 hover:bg-red-50" data-testid={`admin-gallery-delete-${g.id}`}><Trash2 className="h-4 w-4" /></Button>
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
