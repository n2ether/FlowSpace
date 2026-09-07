import React, { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { useAuth } from "../context/AuthContext";
import { apiErrorMessage } from "../lib/api";

export default function Login() {
    const { login } = useAuth();
    const navigate = useNavigate();
    const [params] = useSearchParams();
    const next = params.get("next") || "/account";
    const [form, setForm] = useState({ email: "", password: "" });
    const [loading, setLoading] = useState(false);

    const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

    const submit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            await login({ email: form.email.trim(), password: form.password });
            toast.success("Welcome back.");
            navigate(next.startsWith("/") ? next : "/account");
        } catch (err) {
            toast.error(apiErrorMessage(err, "Invalid email or password."));
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
                    data-testid="login-form"
                >
                    <span className="eyebrow">Members</span>
                    <h1 className="mt-4 font-display text-3xl font-light text-slate-900">
                        Log in to FlowSpace
                    </h1>
                    <p className="mt-2 text-sm text-slate-600">
                        Your Blueprints stay here — revisit every space you&apos;ve organized.
                    </p>
                    <label className="mt-8 mb-2 block text-sm font-medium text-slate-800">Email</label>
                    <input
                        type="email"
                        required
                        value={form.email}
                        onChange={set("email")}
                        className="input"
                        placeholder="you@example.com"
                        autoComplete="email"
                        data-testid="login-email"
                    />
                    <label className="mt-4 mb-2 block text-sm font-medium text-slate-800">Password</label>
                    <input
                        type="password"
                        required
                        value={form.password}
                        onChange={set("password")}
                        className="input"
                        placeholder="Your password"
                        autoComplete="current-password"
                        data-testid="login-password"
                    />
                    <button
                        type="submit"
                        disabled={loading}
                        className="btn-primary mt-6 w-full justify-center"
                        data-testid="login-submit"
                    >
                        {loading ? "Signing in…" : "Log in"}
                    </button>
                    <p className="mt-4 text-center text-sm text-slate-600">
                        New here?{" "}
                        <Link
                            to={`/signup${next !== "/account" ? `?next=${encodeURIComponent(next)}` : ""}`}
                            className="font-medium text-emerald-700 hover:text-emerald-800"
                            data-testid="login-to-signup"
                        >
                            Create a free account
                        </Link>
                    </p>
                </form>
            </main>
            <Footer />
        </div>
    );
}
