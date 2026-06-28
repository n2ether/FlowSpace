import { useEffect } from "react";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider } from "@/contexts/AuthContext";
import Landing from "@/pages/Landing";
import UploadFlow from "@/pages/UploadFlow";
import Success from "@/pages/Success";
import Result from "@/pages/Result";
import Projects from "@/pages/Projects";
import AuthCallback from "@/pages/AuthCallback";
import DevLogin from "@/pages/DevLogin";
import "@/App.css";

function AppRouter() {
  const location = useLocation();
  // CRITICAL: detect session_id during render (NOT in useEffect) to handle
  // OAuth callback before any other route renders.
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/upload/:planId" element={<UploadFlow />} />
      <Route path="/success" element={<Success />} />
      <Route path="/result/:submissionId" element={<Result />} />
      <Route path="/projects" element={<Projects />} />
      <Route path="/dev/login" element={<DevLogin />} />
    </Routes>
  );
}

function App() {
  useEffect(() => {
    document.title = "FlowSpace.Solutions — Turn cluttered rooms into calm, organized spaces";
  }, []);

  return (
    <div className="App min-h-screen bg-white text-slate-900">
      <AuthProvider>
        <BrowserRouter>
          <AppRouter />
        </BrowserRouter>
      </AuthProvider>
      <Toaster richColors position="top-right" />
    </div>
  );
}

export default App;
