import React, { useState } from "react";
import { Link } from "react-router-dom";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { api, apiErrorMessage } from "../lib/api";

const FALLBACK_SENT =
    "If an account exists for that email, we've sent a link to reset your password. The link expires in 60 minutes.";

export default function ForgotPassword() {
    const [email, setEmail] = useState("");
    const [loading, setLoading] = useState(false);
    const [sent, setSent] = useState("");
    const [error, setError] = useState("");

    const submit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError("");
        try {
            const { data } = await api.post("/auth/forgot-password", { email: email.trim() });
            setSent(data?.message || FALLBACK_SENT);
        } catch (err) {
            setError(apiErrorMessage(err, "Could not send a reset link. Please try again."));
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
                    data-testid="forgot-form"
                >
                    <span className="eyebrow">Members</span>
                    <h1 className="mt-4 font-display text-3xl font-light text-slate-900">Reset your password</h1>
                    {sent ? (
                        <p
                            role="status"
                            className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900"
                            data-testid="forgot-sent"
                        >
                            {sent}
                        </p>
                    ) : (
                        <>
                            <p className="mt-2 text-sm text-slate-600">
                                Enter the email you signed up with and we&apos;ll send you a link to choose a new password.
                            </p>
                            <label htmlFor="forgot-email" className="mt-8 mb-2 block text-sm font-medium text-slate-800">
                                Email
                            </label>
                            <input
                                id="forgot-email"
                                type="email"
                                required
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                className="input"
                                placeholder="you@example.com"
                                autoComplete="email"
                                data-testid="forgot-email"
                            />
                            {error && (
                                <p role="alert" className="mt-3 text-sm text-rose-700" data-testid="forgot-error">
                                    {error}
                                </p>
                            )}
                            <button
                                type="submit"
                                disabled={loading}
                                className="btn-primary mt-6 w-full justify-center"
                                data-testid="forgot-submit"
                            >
                                {loading ? "Sending…" : "Send reset link"}
                            </button>
                        </>
                    )}
                    <p className="mt-4 text-center text-sm text-slate-600">
                        <Link to="/login" className="font-medium text-emerald-700 hover:text-emerald-800" data-testid="forgot-to-login">
                            Back to log in
                        </Link>
                    </p>
                </form>
            </main>
            <Footer />
        </div>
    );
}
