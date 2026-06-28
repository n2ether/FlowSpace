import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function AuthCallback() {
  const location = useLocation();
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const processed = useRef(false);

  useEffect(() => {
    // Run the session-id exchange exactly once, even under StrictMode.
    if (processed.current) return;
    processed.current = true;

    const hash = location.hash || window.location.hash || "";
    const m = hash.match(/session_id=([^&]+)/);
    if (!m) {
      navigate("/", { replace: true });
      return;
    }
    const sessionId = decodeURIComponent(m[1]);

    (async () => {
      try {
        await axios.post(`${API}/auth/session`, null, {
          headers: { "X-Session-ID": sessionId },
        });
        await refresh();
        // Clean the URL fragment and route to /projects (or wherever user came from)
        const dest = location.pathname && location.pathname !== "/" ? location.pathname : "/projects";
        window.history.replaceState({}, "", dest);
        navigate(dest, { replace: true });
      } catch {
        toast.error("Sign-in failed. Please try again.");
        navigate("/", { replace: true });
      }
    })();
  }, [location, navigate, refresh]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-white text-slate-500">
      Signing you in…
    </div>
  );
}
