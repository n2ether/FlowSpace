import React, { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { AlertCircle, CheckCircle2, Download, Loader2, PlayCircle } from "lucide-react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Progress } from "../components/ui/progress";
import { api, API } from "../lib/api";

const stages = [
    "pending",
    "uploaded",
    "image_processing",
    "image_complete",
    "plan_generating",
    "pdf_generating",
    "video_generating",
    "complete",
];

const statusLabel = {
    pending: "Queued",
    uploaded: "Photos uploaded",
    image_processing: "Creating organized room images",
    image_complete: "Images complete",
    plan_generating: "Writing your organization plan",
    pdf_generating: "Building your PDF",
    video_generating: "Creating walkthrough video",
    complete: "Complete",
    failed: "Failed",
};

const Results = () => {
    const { jobId } = useParams();
    const [job, setJob] = useState(null);
    const [error, setError] = useState("");

    const assetUrl = (url) => (url?.startsWith("http") ? url : `${API.replace("/api", "")}${url}`);
    const progress = useMemo(() => {
        if (!job) return 0;
        if (job.status === "failed") return 100;
        const index = Math.max(0, stages.indexOf(job.status));
        return Math.round(((index + 1) / stages.length) * 100);
    }, [job]);

    useEffect(() => {
        let stopped = false;
        const load = async () => {
            try {
                const res = await api.get(`/jobs/${jobId}`);
                if (stopped) return;
                setJob(res.data);
                setError("");
                if (!["complete", "failed"].includes(res.data.status)) {
                    setTimeout(load, 2500);
                }
            } catch (e) {
                console.error(e);
                if (!stopped) setError("We could not load this job yet. Please refresh in a moment.");
            }
        };
        load();
        return () => {
            stopped = true;
        };
    }, [jobId]);

    return (
        <div className="App min-h-screen bg-slate-50">
            <Header />
            <main className="container-app py-12 md:py-16">
                <div className="mx-auto max-w-5xl">
                    <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
                        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                            <div>
                                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-emerald-700">
                                    Customer results
                                </p>
                                <h1 className="mt-3 font-heading text-4xl font-light tracking-tight text-slate-900">
                                    {job ? `${job.room_type} transformation` : "Loading transformation"}
                                </h1>
                                <p className="mt-3 max-w-2xl text-slate-600">
                                    Your original room structure is used as the source. The organized concepts focus on storage, labels, shelves, bins, hooks, and other practical organization systems.
                                </p>
                            </div>
                            {job && (
                                <Badge className={job.status === "complete" ? "bg-emerald-500" : job.status === "failed" ? "bg-red-500" : "bg-blue-500"}>
                                    {statusLabel[job.status] || job.status}
                                </Badge>
                            )}
                        </div>

                        {error && (
                            <div className="mt-6 flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                                <AlertCircle className="h-4 w-4" /> {error}
                            </div>
                        )}

                        <div className="mt-8">
                            <div className="mb-2 flex items-center justify-between text-sm text-slate-500">
                                <span>{job ? statusLabel[job.status] || job.status : "Checking status"}</span>
                                <span>{progress}%</span>
                            </div>
                            <Progress value={progress} className="h-2" />
                        </div>

                        {job && job.status !== "complete" && job.status !== "failed" && (
                            <div className="mt-6 flex items-center gap-3 rounded-2xl bg-blue-50 p-4 text-sm text-blue-700">
                                <Loader2 className="h-5 w-5 animate-spin" />
                                Processing happens in the background. You can leave this page and come back later.
                            </div>
                        )}

                        {job?.stage_errors?.length > 0 && (
                            <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-4">
                                <div className="font-medium text-amber-900">Processing notes</div>
                                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-amber-800">
                                    {job.stage_errors.map((err, index) => (
                                        <li key={`${err.stage}-${index}`}>{err.stage}: {err.message}</li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>

                    {job?.modified_images?.length > 0 && (
                        <section className="mt-8 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm md:p-8">
                            <h2 className="font-heading text-2xl font-medium text-slate-900">Organized image concepts</h2>
                            <div className="mt-5 grid grid-cols-1 gap-5 md:grid-cols-2">
                                {job.modified_images.map((image) => (
                                    <div key={image.index} className="rounded-2xl border border-slate-200 p-3">
                                        <div className="grid grid-cols-2 gap-3">
                                            <img src={assetUrl(image.original_url)} alt="Original room" className="h-56 w-full rounded-xl object-cover" />
                                            {image.status === "complete" ? (
                                                <img src={assetUrl(image.modified_url)} alt="Organized room" className="h-56 w-full rounded-xl object-cover" />
                                            ) : (
                                                <div className="flex h-56 items-center justify-center rounded-xl bg-red-50 p-4 text-center text-sm text-red-700">
                                                    Image failed: {image.error}
                                                </div>
                                            )}
                                        </div>
                                        <div className="mt-3 flex items-center justify-between text-xs uppercase tracking-widest text-slate-500">
                                            <span>Photo {image.index}</span>
                                            <span>{image.provider || image.status}</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </section>
                    )}

                    {job?.plan && (
                        <section className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-[1.2fr_0.8fr]">
                            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm md:p-8">
                                <h2 className="font-heading text-2xl font-medium text-slate-900">Organization plan</h2>
                                <p className="mt-3 text-slate-600">{job.plan.room_summary}</p>
                                <h3 className="mt-6 font-heading text-lg font-medium text-slate-900">DIY steps</h3>
                                <ol className="mt-3 list-decimal space-y-2 pl-5 text-slate-700">
                                    {(job.plan.diy_steps || []).map((step, index) => <li key={index}>{step}</li>)}
                                </ol>
                            </div>
                            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm md:p-8">
                                <h2 className="font-heading text-2xl font-medium text-slate-900">Downloads</h2>
                                <div className="mt-5 space-y-3">
                                    {job.pdf_url ? (
                                        <Button asChild className="w-full rounded-full bg-emerald-500 text-white hover:bg-emerald-600">
                                            <a href={assetUrl(job.pdf_url)} target="_blank" rel="noreferrer">
                                                <Download className="mr-2 h-4 w-4" /> Download PDF
                                            </a>
                                        </Button>
                                    ) : (
                                        <div className="rounded-xl bg-slate-50 p-4 text-sm text-slate-500">PDF is still being generated.</div>
                                    )}
                                    {job.video_url ? (
                                        <Button asChild variant="outline" className="w-full rounded-full">
                                            <a href={assetUrl(job.video_url)} target="_blank" rel="noreferrer">
                                                <PlayCircle className="mr-2 h-4 w-4" /> View walkthrough video
                                            </a>
                                        </Button>
                                    ) : job.video_status === "failed" ? (
                                        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                                            Video generation failed, but your PDF deliverable is available.
                                        </div>
                                    ) : (
                                        <div className="rounded-xl bg-slate-50 p-4 text-sm text-slate-500">Video is pending.</div>
                                    )}
                                </div>
                            </div>
                        </section>
                    )}

                    {job?.status === "complete" && (
                        <div className="mt-8 flex items-center gap-3 rounded-3xl border border-emerald-100 bg-emerald-50 p-6 text-emerald-800">
                            <CheckCircle2 className="h-6 w-6" />
                            Your FlowSpace deliverable is ready. A completion email is sent when email settings are configured.
                        </div>
                    )}
                </div>
            </main>
            <Footer />
        </div>
    );
};

export default Results;
