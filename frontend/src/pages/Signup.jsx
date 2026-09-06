import React, { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { useAuth } from "../context/AuthContext";
import { apiErrorCode, apiErrorMessage } from "../lib/api";

export default function Signup() {
    const { signup, login } = useAuth();
    const navigate = useNavigate();
    const [params] = useSearchParams();
    const next = params.get("next") || "/account";
    const [form, setForm] = useState({ name: "", email: "", password: "" });
    const [loading, setLoading] = useState(false);

    const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

    const submit = async (e) => {
        e.preventDefault();
        if (form.password.length < 8) {
            toast.error("Password must be at least 8 characters.");
            return;
        }
        setLoading(true);
        try {
            await signup({
                name: form.name.trim(),
                email: form.email.trim(),
                password: form.password,
            });
            toast.success("Account created. Your first Blueprint is free.");
            navigate(next.startsWith("/") ? next : "/account");
        } catch (err) {
            if (apiErrorCode(err) === "EMAIL_IN_USE") {
                try {
                    await login({ email: form.email.trim(), password: form.password });
                    toast.success("Welcome back — we signed you in.");
                    navigate(next.startsWith("/") ? next : "/account");
                    return;
                } catch {
                    toast.error("An account with this email already exists. Log in to continue.");
                    return;
                } finally {
                    setLoading(false);
                }
            }
            toast.error(apiErrorMessage(err, "Could not create your account."));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-slate-50">
            <Header />
            <main className="container-app flex min-h-[calc(100vh-10rem)] items-center justify-center py-16">
                <form
                    onSubmit={submit}
                    className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-8 shadow-sm"
                    data-testid="signup-form"
                >
                    <span className="eyebrow">Members</span>
                    <h1 className="mt-4 font-display text-3xl font-light text-slate-900">
                        Create your free account
                    </h1>
                    <p className="mt-2 text-sm text-slate-600">
                        Keep every space you organize. First Blueprint is free — upgrade when you
                        want another.
                    </p>
                    <label className="mt-8 mb-2 block text-sm font-medium text-slate-800">Name</label>
                    <input
                        required
                        value={form.name}
                        onChange={set("name")}
                        className="input"
                        placeholder="Jane Doe"
                        autoComplete="name"
                        data-testid="signup-name"
                    />
                    <label className="mt-4 mb-2 block text-sm font-medium text-slate-800">Email</label>
                    <input
                        type="email"
                        required
                        value={form.email}
                        onChange={set("email")}
                        className="input"
                        placeholder="you@example.com"
                        autoComplete="email"
                        data-testid="signup-email"
                    />
                    <label className="mt-4 mb-2 block text-sm font-medium text-slate-800">Password</label>
                    <input
                        type="password"
                        required
                        minLength={8}
                        value={form.password}
                        onChange={set("password")}
                        className="input"
                        placeholder="At least 8 characters"
                        autoComplete="new-password"
                        data-testid="signup-password"
                    />
                    <button
                        type="submit"
                        disabled={loading}
                        className="btn-primary mt-6 w-full justify-center"
                        data-testid="signup-submit"
                    >
                        {loading ? "Creating account…" : "Create free account"}
                    </button>
                    <p className="mt-4 text-center text-sm text-slate-600">
                        Already a member?{" "}
                        <Link
                            to={`/login${next !== "/account" ? `?next=${encodeURIComponent(next)}` : ""}`}
                            className="font-medium text-emerald-700 hover:text-emerald-800"
                            data-testid="signup-to-login"
                        >
                            Log in
                        </Link>
                    </p>
                </form>
            </main>
            <Footer />
        </div>
    );
}
