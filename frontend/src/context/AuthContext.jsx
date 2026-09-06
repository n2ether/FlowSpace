import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, apiErrorMessage, MEMBER_TOKEN_KEY } from "../lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [member, setMember] = useState(null);
    const [loading, setLoading] = useState(true);

    const applyAuth = useCallback((data) => {
        const next = data?.member || data || null;
        if (data?.token) {
            try {
                localStorage.setItem(MEMBER_TOKEN_KEY, data.token);
            } catch {
                /* ignore */
            }
        }
        setMember(next);
        return next;
    }, []);

    const refresh = useCallback(async () => {
        try {
            const { data } = await api.get("/auth/me");
            setMember(data);
            return data;
        } catch {
            setMember(null);
            try {
                localStorage.removeItem(MEMBER_TOKEN_KEY);
            } catch {
                /* ignore */
            }
            return null;
        }
    }, []);

    useEffect(() => {
        refresh().finally(() => setLoading(false));
    }, [refresh]);

    const signup = useCallback(
        async (payload) => {
            const { data } = await api.post("/auth/signup", payload);
            return applyAuth(data);
        },
        [applyAuth]
    );

    const login = useCallback(
        async (payload) => {
            const { data } = await api.post("/auth/login", payload);
            return applyAuth(data);
        },
        [applyAuth]
    );

    const logout = useCallback(async () => {
        try {
            await api.post("/auth/logout");
        } catch {
            /* still clear local session */
        }
        try {
            localStorage.removeItem(MEMBER_TOKEN_KEY);
        } catch {
            /* ignore */
        }
        setMember(null);
    }, []);

    const value = useMemo(
        () => ({ member, loading, signup, login, logout, refresh, applyAuth }),
        [member, loading, signup, login, logout, refresh, applyAuth]
    );

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error("useAuth must be inside AuthProvider");
    return ctx;
}

export { apiErrorMessage };
