import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ArrowRight, Check, CreditCard, Loader2 } from "lucide-react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { Button } from "../components/ui/button";
import { api } from "../lib/api";
import { toast } from "sonner";

const packageCopy = {
    basic: {
        name: "Essential Reset",
        price: 79,
        features: ["AI-organized room concepts", "Storage strategy", "Shopping search links", "PDF deliverable"],
    },
    standard: {
        name: "Calm Room Plan",
        price: 149,
        features: ["Everything in Essential", "DIY step-by-step guide", "Mental-health benefit notes", "Walkthrough video attempt"],
    },
    premium: {
        name: "Premium Transformation",
        price: 299,
        features: ["Priority-style deliverable", "More detailed product strategy", "Owner review-ready admin record", "PDF and video links"],
    },
};

const Checkout = () => {
    const [params] = useSearchParams();
    const [packages, setPackages] = useState(packageCopy);
    const [selected, setSelected] = useState(params.get("package") || "standard");
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        api.get("/packages")
            .then((res) => {
                const fromApi = {};
                (res.data.packages || []).forEach((pkg) => {
                    fromApi[pkg.id] = { ...(packageCopy[pkg.id] || {}), ...pkg };
                });
                if (Object.keys(fromApi).length) setPackages((current) => ({ ...current, ...fromApi }));
            })
            .catch(() => {});
    }, []);

    const startCheckout = async () => {
        setLoading(true);
        try {
            const res = await api.post("/checkout/session", {
                package_id: selected,
                origin_url: window.location.origin,
            });
            if (res.data?.url) {
                window.location.href = res.data.url;
            } else {
                toast.error("Checkout did not return a payment link. Please try again.");
            }
        } catch (error) {
            console.error(error);
            toast.error("Checkout is not available yet. Please try again shortly.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="App min-h-screen bg-slate-50">
            <Header />
            <main className="container-app py-12 md:py-16">
                <div className="mx-auto max-w-5xl">
                    <div className="mb-8 rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
                        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-emerald-700">
                            Checkout
                        </p>
                        <h1 className="mt-3 font-heading text-4xl font-light tracking-tight text-slate-900">
                            Choose your FlowSpace deliverable
                        </h1>
                        <p className="mt-3 max-w-2xl text-slate-600">
                            Stripe handles payment. After checkout, continue to the upload intake to create your room transformation job.
                        </p>
                    </div>

                    <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
                        {Object.entries(packages).map(([id, pkg]) => (
                            <button
                                key={id}
                                type="button"
                                onClick={() => setSelected(id)}
                                className={`rounded-3xl border bg-white p-6 text-left shadow-sm transition ${
                                    selected === id ? "border-emerald-500 ring-4 ring-emerald-50" : "border-slate-200 hover:border-emerald-200"
                                }`}
                                data-testid={`checkout-package-${id}`}
                            >
                                <div className="flex items-center justify-between">
                                    <h2 className="font-heading text-2xl font-medium text-slate-900">{pkg.name}</h2>
                                    {selected === id && <Check className="h-5 w-5 text-emerald-600" />}
                                </div>
                                <div className="mt-4 font-heading text-4xl font-light text-slate-900">${pkg.price}</div>
                                <ul className="mt-5 space-y-2 text-sm text-slate-600">
                                    {(pkg.features || []).map((feature) => (
                                        <li key={feature} className="flex gap-2">
                                            <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                                            {feature}
                                        </li>
                                    ))}
                                </ul>
                            </button>
                        ))}
                    </div>

                    <div className="mt-8 flex flex-col gap-3 rounded-3xl border border-emerald-100 bg-white p-6 shadow-sm md:flex-row md:items-center md:justify-between">
                        <div className="flex items-center gap-3 text-slate-700">
                            <CreditCard className="h-5 w-5 text-emerald-600" />
                            Payment uses the existing Stripe checkout session API.
                        </div>
                        <Button
                            onClick={startCheckout}
                            disabled={loading}
                            className="rounded-full bg-emerald-500 px-7 py-6 text-white hover:bg-emerald-600"
                            data-testid="checkout-start"
                        >
                            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                            Continue to checkout
                            <ArrowRight className="ml-2 h-4 w-4" />
                        </Button>
                    </div>
                </div>
            </main>
            <Footer />
        </div>
    );
};

export default Checkout;
