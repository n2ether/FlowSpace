import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { LanguageProvider } from "./context/LanguageContext";
import { AuthProvider } from "./context/AuthContext";
import { Toaster } from "./components/ui/sonner";
import Landing from "./pages/Landing";
import Intake from "./pages/Intake";
import Success from "./pages/Success";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Account from "./pages/Account";
import AdminLogin from "./pages/AdminLogin";
import Admin from "./pages/Admin";
import AdminDeliverable from "./pages/AdminDeliverable";
import BlueprintPreview from "./pages/BlueprintPreview";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import Privacy from "./pages/Privacy";
import PhotoUse from "./pages/PhotoUse";
import Terms from "./pages/Terms";
import Support from "./pages/Support";

function App() {
    return (
        <LanguageProvider>
            <BrowserRouter>
                <AuthProvider>
                    <Routes>
                        <Route path="/" element={<Landing />} />
                        <Route path="/intake" element={<Intake />} />
                        <Route path="/success" element={<Success />} />
                        <Route path="/login" element={<Login />} />
                        <Route path="/signup" element={<Signup />} />
                        <Route path="/account" element={<Account />} />
                        <Route path="/forgot-password" element={<ForgotPassword />} />
                        <Route path="/reset-password" element={<ResetPassword />} />
                        <Route path="/privacy" element={<Privacy />} />
                        <Route path="/photo-use" element={<PhotoUse />} />
                        <Route path="/terms" element={<Terms />} />
                        <Route path="/support" element={<Support />} />
                        <Route path="/admin/login" element={<AdminLogin />} />
                        <Route path="/admin" element={<Admin />} />
                        <Route path="/admin/leads/:leadId/design" element={<AdminDeliverable />} />
                        <Route path="/admin/leads/:leadId/blueprint" element={<BlueprintPreview />} />
                    </Routes>
                    <Toaster position="top-right" richColors />
                </AuthProvider>
            </BrowserRouter>
        </LanguageProvider>
    );
}

export default App;
