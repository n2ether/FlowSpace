import React, { createContext, useContext, useEffect, useState } from "react";
import { translations } from "../i18n/translations";

const LanguageContext = createContext(null);

export const LanguageProvider = ({ children }) => {
    const [lang, setLang] = useState(() => {
        const stored = localStorage.getItem("cs_lang");
        if (stored && translations[stored]) return stored;
        const nav = (navigator.language || "en").toLowerCase();
        if (nav.startsWith("es")) return "es";
        if (nav.startsWith("pt")) return "pt";
        return "en";
    });

    useEffect(() => {
        localStorage.setItem("cs_lang", lang);
        document.documentElement.lang = lang;
    }, [lang]);

    const t = translations[lang];
    return (
        <LanguageContext.Provider value={{ lang, setLang, t }}>
            {children}
        </LanguageContext.Provider>
    );
};

export const useLang = () => {
    const ctx = useContext(LanguageContext);
    if (!ctx) throw new Error("useLang must be inside LanguageProvider");
    return ctx;
};
