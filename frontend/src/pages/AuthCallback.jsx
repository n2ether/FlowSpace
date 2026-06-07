import React, { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { authApi } from "../lib/api";
import { useAuth } from "../context/AuthContext";

const AuthCallback = () => {
    const hasProcessed = useRef(false);
    const navigate = useNavigate();
    const { setUser } = useAuth();

    useEffect(() => {
        if (hasProcessed.current) return;
        hasProcessed.current = true;

        const m = window.location.hash.match(/session_id=([^&]+)/);
        const sessionId = m ? decodeURIComponent(m[1]) : null;

        (async () => {
            if (!sessionId) {
                navigate("/login");
                return;
            }
            try {
                const r = await authApi.post("/auth/session", { session_id: sessionId });
                setUser(r.data);
                window.history.replaceState(null, "", window.location.pathname);
                navigate("/app", { state: { user: r.data } });
            } catch {
                navigate("/login");
            }
        })();
    }, [navigate, setUser]);

    return (
        <div className="flex min-h-screen items-center justify-center bg-slate-50">
            <div className="flex flex-col items-center gap-3 text-slate-600">
                <Loader2 className="h-8 w-8 animate-spin text-emerald-600" />
                <span className="text-sm">Signing you in…</span>
            </div>
        </div>
    );
};

export default AuthCallback;
