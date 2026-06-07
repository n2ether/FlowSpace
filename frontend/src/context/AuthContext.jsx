import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { authApi } from "../lib/api";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    const checkAuth = useCallback(async () => {
        try {
            const r = await authApi.get("/auth/me");
            setUser(r.data);
        } catch {
            setUser(null);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        // CRITICAL: If returning from OAuth callback, skip the /me check.
        // AuthCallback will exchange the session_id and establish the session first.
        if (window.location.hash?.includes("session_id=")) {
            setLoading(false);
            return;
        }
        checkAuth();
    }, [checkAuth]);

    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const login = () => {
        const redirectUrl = window.location.origin + "/app";
        window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
    };

    const logout = async () => {
        try {
            await authApi.post("/auth/logout");
        } catch {
            /* ignore */
        }
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, setUser, loading, checkAuth, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error("useAuth must be inside AuthProvider");
    return ctx;
};
