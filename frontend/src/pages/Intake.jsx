import React from "react";
import { useSearchParams } from "react-router-dom";
import Header from "../components/Header";
import Footer from "../components/Footer";
import Questionnaire from "../components/Questionnaire";
import { useLang } from "../context/LanguageContext";

const Intake = () => {
    const { t } = useLang();
    const [search] = useSearchParams();
    const presetPackage = search.get("package") || "";

    return (
        <div className="App min-h-screen bg-slate-50">
            <Header />
            <main className="container-app py-12 md:py-20">
                <div className="mx-auto max-w-3xl">
                    <div className="mb-10 text-center">
                        <h1 className="font-heading text-4xl font-light tracking-tight text-slate-900 sm:text-5xl">
                            {t.questionnaire.title}
                        </h1>
                        <p className="mt-3 text-slate-600">{t.questionnaire.sub}</p>
                    </div>
                    <Questionnaire presetPackage={presetPackage} />
                </div>
            </main>
            <Footer />
        </div>
    );
};

export default Intake;
