import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

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
});

export const adminClient = (token) =>
    axios.create({
        baseURL: API,
        headers: { "Content-Type": "application/json", "X-Admin-Token": token },
    });
