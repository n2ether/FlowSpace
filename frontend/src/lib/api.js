import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const MEMBER_TOKEN_KEY = "fs_member_token";

if (!BACKEND_URL) {
    // eslint-disable-next-line no-console
    console.error(
        "[FlowSpace] REACT_APP_BACKEND_URL is not set. " +
        "Set it in your hosting provider's environment variables and redeploy. " +
        "API calls will fail until this is fixed."
    );
}

export const API = `${BACKEND_URL || ""}/api`;

export const api = axios.create({
    baseURL: API,
    headers: { "Content-Type": "application/json" },
    withCredentials: true,
});

api.interceptors.request.use((config) => {
    try {
        const token = localStorage.getItem(MEMBER_TOKEN_KEY);
        if (token) {
            config.headers = config.headers || {};
            config.headers.Authorization = `Bearer ${token}`;
        }
    } catch {
        /* private mode / SSR */
    }
    return config;
});

export const adminClient = (token) =>
    axios.create({
        baseURL: API,
        headers: { "Content-Type": "application/json", "X-Admin-Token": token },
    });

export function apiErrorMessage(err, fallback = "Something went wrong. Please try again.") {
    const detail = err?.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (detail && typeof detail === "object" && detail.message) return detail.message;
    return err?.message || fallback;
}

export function apiErrorCode(err) {
    const detail = err?.response?.data?.detail;
    return (detail && typeof detail === "object" && detail.code) || null;
}
