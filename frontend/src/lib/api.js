import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({
    baseURL: API,
    headers: { "Content-Type": "application/json" },
});

// Authenticated client — sends the httpOnly session cookie.
export const authApi = axios.create({
    baseURL: API,
    headers: { "Content-Type": "application/json" },
    withCredentials: true,
});

// FastAPI 422 returns detail as an array of {msg} objects — normalize to a string.
export function formatApiError(detail) {
    if (detail == null) return "Something went wrong. Please try again.";
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail))
        return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).filter(Boolean).join(" ");
    if (detail && typeof detail.msg === "string") return detail.msg;
    return String(detail);
}

export const adminClient = (token) =>
    axios.create({
        baseURL: API,
        headers: { "Content-Type": "application/json", "X-Admin-Token": token },
    });
