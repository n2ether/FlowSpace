import React, { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { useAuth } from "../context/AuthContext";
import { api, apiErrorCode, apiErrorMessage } from "../lib/api";

export const MIN_PASSWORD_LENGTH = 8;

export function passwordProblem(password, confirm) {
    if (!password || password.length < MIN_PASSWORD_LENGTH) {
        return `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`;
    }
    if (password !== confirm) return "Passwords don't match.";
    return "";
}

const linkClass = "font-medium text-emerald-700 hover:text-emerald-800";

export default function ResetPassword() {
    const { applyAuth } = useAuth();
    const navigate = useNavigate();
    const [params] = useSearchParams();
    const [token] = useState(() => params.get("token") || "");
    const [form, setForm] = useState({ password: "", confirm: "" });
    const [error, setError] = useState("");
    const [linkInvalid, setLinkInvalid] = useState(false);
    const [loading, setLoading] = useState(false);

    // Keep the token out of the address bar and browser history once it's in memory.
    useEffect(() => {
        if (params.get("token")) navigate("/reset-password", { replace: true });
    }, [params, navigate]);

    const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

    const submit = async (e) => {
        e.preventDefault();
        const problem = passwordProblem(form.password, form.confirm);
        if (problem) {
            setError(problem);
            return;
        }
        setError("");
        setLoading(true);
        try {
            const { data } = await api.post("/auth/reset-password", { token, password: form.password });
            applyAuth(data);
            toast.success("Password updated. You're signed in.");
            navigate("/account", { replace: true });
        } catch (err) {
            if (apiErrorCode(err) === "INVALID_RESET_TOKEN") {
                setLinkInvalid(true);
            } else {
                setError(apiErrorMessage(err, "Could not reset your password. Please try again."));
            }
        } finally {
            setLoading(false);
        }
    };

    const invalid = !token || linkInvalid;

    return (
        <div className="min-h-screen bg-slate-50">
            <Header />
            <main className="container-app flex min-h-[calc(100vh-10rem)] items-center justify-center py-16">
                <form
                    onSubmit={submit}
                    className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-8 shadow-sm"
                    data-testid="reset-form"
                >
                    <span className="eyebrow">Members</span>
                    <h1 className="mt-4 font-display text-3xl font-light text-slate-900">Choose a new password</h1>
                    {invalid ? (
                        <div className="mt-6 space-y-4" data-testid="reset-invalid">
                            <p role="alert" className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                                This reset link is invalid or has expired. Reset links work once and expire after 60 minutes.
                            </p>
                            <Link to="/forgot-password" className="btn-primary w-full justify-center" data-testid="reset-request-new">
                                Request a new link
                            </Link>
                        </div>
                    ) : (
                        <>
                            <p className="mt-2 text-sm text-slate-600">
                                Use at least {MIN_PASSWORD_LENGTH} characters. You&apos;ll be signed in once it&apos;s saved.
                            </p>
                            <label htmlFor="reset-password" className="mt-8 mb-2 block text-sm font-medium text-slate-800">
                                New password
                            </label>
                            <input
                                id="reset-password"
                                type="password"
                                required
                                minLength={MIN_PASSWORD_LENGTH}
                                value={form.password}
                                onChange={set("password")}
                                className="input"
                                placeholder={`At least ${MIN_PASSWORD_LENGTH} characters`}
                                autoComplete="new-password"
                                data-testid="reset-password"
                            />
                            <label htmlFor="reset-confirm" className="mt-4 mb-2 block text-sm font-medium text-slate-800">
                                Confirm new password
                            </label>
                            <input
                                id="reset-confirm"
                                type="password"
                                required
                                value={form.confirm}
                                onChange={set("confirm")}
                                className="input"
                                placeholder="Type it again"
                                autoComplete="new-password"
                                data-testid="reset-confirm"
                            />
                            {error && (
                                <p role="alert" className="mt-3 text-sm text-rose-700" data-testid="reset-error">
                                    {error}
                                </p>
                            )}
                            <button
                                type="submit"
                                disabled={loading}
                                className="btn-primary mt-6 w-full justify-center"
                                data-testid="reset-submit"
                            >
                                {loading ? "Saving…" : "Save new password"}
                            </button>
                        </>
                    )}
                    <p className="mt-4 text-center text-sm text-slate-600">
                        <Link to="/login" className={linkClass}>
                            Back to log in
                        </Link>
                    </p>
                </form>
            </main>
            <Footer />
        </div>
    );
}
