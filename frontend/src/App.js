import { useEffect } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import Landing from "@/pages/Landing";
import UploadFlow from "@/pages/UploadFlow";
import Success from "@/pages/Success";
import Result from "@/pages/Result";
import "@/App.css";

function App() {
  useEffect(() => {
    document.title = "FlowSpace.Solutions — Turn cluttered rooms into calm, organized spaces";
  }, []);

  return (
    <div className="App min-h-screen bg-white text-slate-900">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/upload/:planId" element={<UploadFlow />} />
          <Route path="/success" element={<Success />} />
          <Route path="/result/:submissionId" element={<Result />} />
        </Routes>
      </BrowserRouter>
      <Toaster richColors position="top-right" />
    </div>
  );
}

export default App;
