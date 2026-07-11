import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, ExternalLink, LogOut, RefreshCw } from "lucide-react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { adminClient, API } from "../lib/api";
import { toast } from "sonner";

const statusClass = {
    complete: "bg-emerald-500",
    failed: "bg-red-500",
    video_generating: "bg-blue-500",
    pdf_generating: "bg-blue-500",
    plan_generating: "bg-blue-500",
    image_processing: "bg-blue-500",
};

const AdminJobs = () => {
    const navigate = useNavigate();
    const token = localStorage.getItem("cs_admin_token");
    const [jobs, setJobs] = useState([]);
    const [loading, setLoading] = useState(true);
    const client = adminClient(token);

    const assetUrl = (url) => (url?.startsWith("http") ? url : `${API.replace("/api", "")}${url}`);

    const loadJobs = async () => {
        if (!token) {
            navigate("/admin/login");
            return;
        }
        setLoading(true);
        try {
            const res = await client.get("/admin/jobs");
            setJobs(res.data || []);
        } catch (error) {
            if (error?.response?.status === 401) {
                localStorage.removeItem("cs_admin_token");
                navigate("/admin/login");
            } else {
                toast.error("Failed to load jobs");
            }
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadJobs();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [token]);

    const requeue = async (jobId) => {
        try {
            await client.post("/generate-images", { job_id: jobId });
            toast.success("Job queued");
            loadJobs();
        } catch (error) {
            console.error(error);
            toast.error("Could not queue job");
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
                <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                    <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-emerald-700">
                            Owner dashboard
                        </p>
                        <h1 className="mt-2 font-heading text-4xl font-light tracking-tight text-slate-900">
                            FlowSpace automation jobs
                        </h1>
                    </div>
                    <div className="flex gap-2">
                        <Button variant="outline" className="rounded-full" onClick={loadJobs} disabled={loading}>
                            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh
                        </Button>
                        <Button variant="outline" className="rounded-full" onClick={logout}>
                            <LogOut className="mr-2 h-4 w-4" /> Logout
                        </Button>
                    </div>
                </div>

                <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm md:p-6">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Customer</TableHead>
                                <TableHead>Room</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead>Artifacts</TableHead>
                                <TableHead>Errors</TableHead>
                                <TableHead>Cost</TableHead>
                                <TableHead>Actions</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {jobs.map((job) => (
                                <TableRow key={job.id} data-testid={`admin-job-${job.id}`}>
                                    <TableCell>
                                        <div className="font-medium text-slate-900">{job.customer_name}</div>
                                        <div className="text-xs text-slate-500">{job.email}</div>
                                        <div className="text-xs text-slate-400">{new Date(job.created_at).toLocaleString()}</div>
                                    </TableCell>
                                    <TableCell>
                                        <div className="capitalize">{job.room_type}</div>
                                        <div className="max-w-[14rem] truncate text-xs text-slate-500">{job.pain_point}</div>
                                    </TableCell>
                                    <TableCell>
                                        <Badge className={statusClass[job.status] || "bg-slate-500"}>{job.status}</Badge>
                                        {job.video_status && <div className="mt-1 text-xs text-slate-500">Video: {job.video_status}</div>}
                                    </TableCell>
                                    <TableCell>
                                        <div className="flex flex-col gap-1 text-sm">
                                            <a className="inline-flex items-center gap-1 text-emerald-700 hover:underline" href={`/results/${job.id}`} target="_blank" rel="noreferrer">
                                                Results <ExternalLink className="h-3 w-3" />
                                            </a>
                                            {job.pdf_url && (
                                                <a className="inline-flex items-center gap-1 text-blue-700 hover:underline" href={assetUrl(job.pdf_url)} target="_blank" rel="noreferrer">
                                                    PDF <ExternalLink className="h-3 w-3" />
                                                </a>
                                            )}
                                            {job.video_url && (
                                                <a className="inline-flex items-center gap-1 text-blue-700 hover:underline" href={assetUrl(job.video_url)} target="_blank" rel="noreferrer">
                                                    Video <ExternalLink className="h-3 w-3" />
                                                </a>
                                            )}
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        {job.stage_errors?.length ? (
                                            <details className="max-w-xs">
                                                <summary className="flex cursor-pointer items-center gap-1 text-amber-700">
                                                    <AlertTriangle className="h-4 w-4" /> {job.stage_errors.length}
                                                </summary>
                                                <ul className="mt-2 space-y-1 text-xs text-slate-600">
                                                    {job.stage_errors.map((err, index) => (
                                                        <li key={index}>{err.stage}: {err.message}</li>
                                                    ))}
                                                </ul>
                                            </details>
                                        ) : (
                                            <span className="text-xs text-slate-400">None</span>
                                        )}
                                    </TableCell>
                                    <TableCell>${Number(job.cost_estimate || 0).toFixed(2)}</TableCell>
                                    <TableCell>
                                        <Button size="sm" variant="outline" onClick={() => requeue(job.id)}>
                                            Requeue
                                        </Button>
                                    </TableCell>
                                </TableRow>
                            ))}
                            {!jobs.length && (
                                <TableRow>
                                    <TableCell colSpan={7} className="py-10 text-center text-slate-500">
                                        {loading ? "Loading jobs..." : "No room jobs yet."}
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </div>
            </main>
            <Footer />
        </div>
    );
};

export default AdminJobs;
