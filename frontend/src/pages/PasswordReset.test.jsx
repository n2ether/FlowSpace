import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import Login from "./Login";
import ForgotPassword from "./ForgotPassword";
import ResetPassword, { passwordProblem } from "./ResetPassword";
import { api } from "../lib/api";

jest.mock("../components/Header", () => () => null);
jest.mock("../components/Footer", () => () => null);
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

const mockAuth = { login: jest.fn(), applyAuth: jest.fn() };
jest.mock("../context/AuthContext", () => ({ useAuth: () => mockAuth }));

jest.mock("../lib/api", () => ({
    api: { post: jest.fn() },
    apiErrorCode: (err) => err?.response?.data?.detail?.code || null,
    apiErrorMessage: (err, fallback) => err?.response?.data?.detail?.message || fallback,
}));

function Where() {
    const location = useLocation();
    return <p data-testid="where">{location.pathname + location.search}</p>;
}

function renderAt(url) {
    return render(
        <MemoryRouter initialEntries={[url]}>
            <Routes>
                <Route path="/login" element={<Login />} />
                <Route path="/forgot-password" element={<ForgotPassword />} />
                <Route path="/reset-password" element={<ResetPassword />} />
                <Route path="/account" element={<p>account page</p>} />
            </Routes>
            <Where />
        </MemoryRouter>,
    );
}

beforeEach(() => jest.clearAllMocks());

describe("Login", () => {
    it("links to forgot password", async () => {
        renderAt("/login");
        const link = screen.getByTestId("login-forgot-password");
        expect(link).toHaveTextContent("Forgot password?");
        await userEvent.click(link);
        expect(screen.getByTestId("forgot-form")).toBeInTheDocument();
    });
});

describe("Forgot password", () => {
    it("submits the email and shows the generic message", async () => {
        api.post.mockResolvedValue({ data: { ok: true, message: "If an account exists for that email, we've sent a link." } });
        renderAt("/forgot-password");
        await userEvent.type(screen.getByTestId("forgot-email"), "ada@example.com");
        await userEvent.click(screen.getByTestId("forgot-submit"));
        expect(api.post).toHaveBeenCalledWith("/auth/forgot-password", { email: "ada@example.com" });
        expect(await screen.findByTestId("forgot-sent")).toHaveTextContent("If an account exists");
    });

    it("shows the rate limit message", async () => {
        api.post.mockRejectedValue({ response: { status: 429, data: { detail: { code: "RATE_LIMITED", message: "Too many reset requests." } } } });
        renderAt("/forgot-password");
        await userEvent.type(screen.getByTestId("forgot-email"), "ada@example.com");
        await userEvent.click(screen.getByTestId("forgot-submit"));
        expect(await screen.findByTestId("forgot-error")).toHaveTextContent("Too many reset requests.");
    });
});

describe("Reset password", () => {
    it("uses the signup password rules", () => {
        expect(passwordProblem("short", "short")).toMatch(/at least 8/);
        expect(passwordProblem("long-enough", "different")).toMatch(/don't match/);
        expect(passwordProblem("long-enough", "long-enough")).toBe("");
    });

    it("removes the token from the URL", async () => {
        renderAt("/reset-password?token=abc123");
        await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent(/^\/reset-password$/));
        expect(screen.getByTestId("reset-password")).toBeInTheDocument();
    });

    it("rejects mismatched passwords without calling the API", async () => {
        renderAt("/reset-password?token=abc123");
        await userEvent.type(screen.getByTestId("reset-password"), "long-enough");
        await userEvent.type(screen.getByTestId("reset-confirm"), "long-enougX");
        await userEvent.click(screen.getByTestId("reset-submit"));
        expect(screen.getByTestId("reset-error")).toHaveTextContent("Passwords don't match.");
        expect(api.post).not.toHaveBeenCalled();
    });

    it("saves the new password, signs in and goes to the account", async () => {
        const data = { token: "jwt", member: { id: "m1", email: "ada@example.com" } };
        api.post.mockResolvedValue({ data });
        renderAt("/reset-password?token=abc123");
        await userEvent.type(screen.getByTestId("reset-password"), "brand-new-pass");
        await userEvent.type(screen.getByTestId("reset-confirm"), "brand-new-pass");
        await userEvent.click(screen.getByTestId("reset-submit"));
        expect(api.post).toHaveBeenCalledWith("/auth/reset-password", { token: "abc123", password: "brand-new-pass" });
        expect(mockAuth.applyAuth).toHaveBeenCalledWith(data);
        expect(await screen.findByText("account page")).toBeInTheDocument();
    });

    it("offers a new link when the token is expired or used", async () => {
        api.post.mockRejectedValue({ response: { status: 400, data: { detail: { code: "INVALID_RESET_TOKEN", message: "x" } } } });
        renderAt("/reset-password?token=used");
        await userEvent.type(screen.getByTestId("reset-password"), "brand-new-pass");
        await userEvent.type(screen.getByTestId("reset-confirm"), "brand-new-pass");
        await userEvent.click(screen.getByTestId("reset-submit"));
        expect(await screen.findByTestId("reset-invalid")).toBeInTheDocument();
        expect(screen.getByTestId("reset-request-new")).toHaveAttribute("href", "/forgot-password");
    });

    it("explains a link with no token", () => {
        renderAt("/reset-password");
        expect(screen.getByTestId("reset-invalid")).toBeInTheDocument();
    });
});
