import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { LanguageProvider } from "./context/LanguageContext";
import { Toaster } from "./components/ui/sonner";
import Landing from "./pages/Landing";
import Intake from "./pages/Intake";
import Success from "./pages/Success";
import AdminLogin from "./pages/AdminLogin";
import Admin from "./pages/Admin";
import AdminDeliverable from "./pages/AdminDeliverable";

function App() {
    return (
        <LanguageProvider>
            <BrowserRouter>
                <Routes>
                    <Route path="/" element={<Landing />} />
                    <Route path="/intake" element={<Intake />} />
                    <Route path="/success" element={<Success />} />
                    <Route path="/admin/login" element={<AdminLogin />} />
                    <Route path="/admin" element={<Admin />} />
                    <Route path="/admin/leads/:leadId/design" element={<AdminDeliverable />} />
                </Routes>
                <Toaster position="top-right" richColors />
            </BrowserRouter>
        </LanguageProvider>
    );
}

export default App;
