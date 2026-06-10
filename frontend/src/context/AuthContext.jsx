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
        checkAuth();
    }, [checkAuth]);

    const login = async (email, password) => {
        const r = await authApi.post("/auth/login", { email, password });
        setUser(r.data);
        return r.data;
    };

    const register = async (email, password, name) => {
        const r = await authApi.post("/auth/register", { email, password, name });
        setUser(r.data);
        return r.data;
    };

    const logout = async () => {
        try {
            await authApi.post("/auth/logout");
        } catch (e) {
            console.error("Logout request failed", e);
        }
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, setUser, loading, checkAuth, login, register, logout }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error("useAuth must be inside AuthProvider");
    return ctx;
};
