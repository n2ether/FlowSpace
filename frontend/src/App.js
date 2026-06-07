import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { LanguageProvider } from "./context/LanguageContext";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { Toaster } from "./components/ui/sonner";
import { Loader2 } from "lucide-react";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import AuthCallback from "./pages/AuthCallback";
import Dashboard from "./pages/Dashboard";
import NewProject from "./pages/NewProject";
import Results from "./pages/Results";
import Billing from "./pages/Billing";
import AdminLogin from "./pages/AdminLogin";
import Admin from "./pages/Admin";

const Splash = () => (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <Loader2 className="h-8 w-8 animate-spin text-emerald-600" />
    </div>
);

const ProtectedRoute = ({ children }) => {
    const { user, loading } = useAuth();
    if (loading) return <Splash />;
    if (!user) return <Navigate to="/login" replace />;
    return children;
};

function AppRoutes() {
    const location = useLocation();
    // Process OAuth callback BEFORE any protected route runs (prevents race conditions).
    if (location.hash?.includes("session_id=")) {
        return <AuthCallback />;
    }
    return (
        <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/app" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
            <Route path="/app/new" element={<ProtectedRoute><NewProject /></ProtectedRoute>} />
            <Route path="/app/project/:id" element={<ProtectedRoute><Results /></ProtectedRoute>} />
            <Route path="/app/billing" element={<ProtectedRoute><Billing /></ProtectedRoute>} />
            <Route path="/admin/login" element={<AdminLogin />} />
            <Route path="/admin" element={<Admin />} />
            <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
    );
}

function App() {
    return (
        <LanguageProvider>
            <AuthProvider>
                <BrowserRouter>
                    <AppRoutes />
                    <Toaster position="top-right" richColors />
                </BrowserRouter>
            </AuthProvider>
        </LanguageProvider>
    );
}

export default App;
