import React, { useEffect, useState } from "react";
import BeforeAfterSlider from "./BeforeAfterSlider";
import { API } from "../lib/api";

// Fetches a backend-protected image as a blob (cookie auth) and renders it.
export const AuthImage = ({ path, alt = "", className = "", testId }) => {
    const [url, setUrl] = useState(null);
    useEffect(() => {
        let active = true;
        let obj;
        fetch(`${API}${path}`, { credentials: "include" })
            .then((r) => (r.ok ? r.blob() : Promise.reject()))
            .then((b) => {
                if (active) {
                    obj = URL.createObjectURL(b);
                    setUrl(obj);
                }
            })
            .catch((e) => console.error("AuthImage load failed", e));
        return () => {
            active = false;
            if (obj) URL.revokeObjectURL(obj);
        };
    }, [path]);

    if (!url) return <div className={`animate-pulse bg-slate-100 ${className}`} data-testid={testId} />;
    return <img src={url} alt={alt} className={className} data-testid={testId} />;
};

// Loads both project images as blobs then renders the comparison slider.
export const ProjectCompare = ({ projectId, beforeLabel, afterLabel, className = "", testIdPrefix }) => {
    const [before, setBefore] = useState(null);
    const [after, setAfter] = useState(null);

    useEffect(() => {
        let active = true;
        const urls = [];
        const load = async (which, setter) => {
            try {
                const r = await fetch(`${API}/projects/${projectId}/image/${which}`, { credentials: "include" });
                if (!r.ok) return;
                const b = await r.blob();
                const u = URL.createObjectURL(b);
                urls.push(u);
                if (active) setter(u);
            } catch (e) {
                console.error("ProjectCompare image load failed", e);
            }
        };
        load("original", setBefore);
        load("generated", setAfter);
        return () => {
            active = false;
            urls.forEach((u) => URL.revokeObjectURL(u));
        };
    }, [projectId]);

    if (!before || !after) {
        return <div className={`animate-pulse rounded-2xl bg-slate-100 ${className}`} data-testid={`${testIdPrefix}-loading`} />;
    }
    return (
        <BeforeAfterSlider
            beforeUrl={before}
            afterUrl={after}
            beforeLabel={beforeLabel}
            afterLabel={afterLabel}
            className={className}
            testIdPrefix={testIdPrefix}
        />
    );
};
