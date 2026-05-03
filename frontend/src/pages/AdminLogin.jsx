import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { LogIn } from "lucide-react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Button } from "../components/ui/button";
import { api } from "../lib/api";
import { useLang } from "../context/LanguageContext";
import { toast } from "sonner";

const AdminLogin = () => {
    const { t } = useLang();
    const [password, setPassword] = useState("");
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();

    const submit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const res = await api.post("/admin/login", { password });
            localStorage.setItem("cs_admin_token", res.data.token);
            navigate("/admin");
        } catch {
            toast.error("Invalid password");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="App min-h-screen bg-slate-50">
            <Header />
            <main className="container-app flex min-h-[calc(100vh-10rem)] items-center justify-center py-16">
                <form
                    onSubmit={submit}
                    className="w-full max-w-sm rounded-3xl border border-slate-200 bg-white p-8 shadow-sm"
                >
                    <div className="mb-6 flex items-center gap-2">
                        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500 text-white">
                            <LogIn className="h-4 w-4" />
                        </span>
                        <h1 className="font-heading text-2xl font-medium text-slate-900">
                            {t.admin.login}
                        </h1>
                    </div>
                    <Label>{t.admin.password}</Label>
                    <Input
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        data-testid="admin-password-input"
                        className="mt-1"
                        autoFocus
                    />
                    <Button
                        type="submit"
                        disabled={loading}
                        className="mt-6 w-full rounded-full bg-emerald-500 text-white hover:bg-emerald-600"
                        data-testid="admin-login-submit"
                    >
                        {loading ? "..." : t.admin.signIn}
                    </Button>
                </form>
            </main>
            <Footer />
        </div>
    );
};

export default AdminLogin;
