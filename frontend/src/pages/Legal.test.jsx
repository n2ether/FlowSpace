import React from "react";
import { render, screen } from "@testing-library/react";
import App from "../App";

jest.mock("../components/Header", () => () => null);
jest.mock("../components/ui/sonner", () => ({ Toaster: () => null }));
jest.mock("../context/AuthContext", () => ({
    AuthProvider: ({ children }) => children,
    useAuth: () => ({ member: null, loading: false, login: jest.fn(), applyAuth: jest.fn() }),
}));
jest.mock("./Landing", () => () => null);
jest.mock("./Intake", () => () => null);
jest.mock("./Success", () => () => null);
jest.mock("./Account", () => () => null);
jest.mock("./Admin", () => () => null);
jest.mock("./AdminLogin", () => () => null);
jest.mock("./AdminDeliverable", () => () => null);
jest.mock("./BlueprintPreview", () => () => null);
jest.mock("../lib/api", () => ({
    api: { get: jest.fn(() => Promise.reject(new Error("signed out"))), post: jest.fn() },
    apiErrorCode: () => null,
    apiErrorMessage: () => "error",
    MEMBER_TOKEN_KEY: "fs_member_token",
}));

function visit(path) {
    window.history.pushState({}, "", path);
    return render(<App />);
}

describe("Legal and support routes", () => {
    it.each([
        ["/privacy", "page-privacy", "Privacy Policy"],
        ["/photo-use", "page-photo-use", "Photo Use"],
        ["/terms", "page-terms", "Terms of Purchase"],
        ["/support", "page-support", "We're here to help"],
    ])("%s renders its page", (path, testId, heading) => {
        visit(path);
        const page = screen.getByTestId(testId);
        expect(page).toBeInTheDocument();
        expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(heading);
        expect(page).toHaveTextContent("help@flowspace.solutions");
        expect(screen.getByTestId("legal-last-updated")).toHaveTextContent(/^Last updated:/);
    });

    it("privacy names the processors and says Stripe handles cards", () => {
        visit("/privacy");
        const page = screen.getByTestId("page-privacy");
        for (const name of ["Stripe", "Resend", "Railway", "AI image and text processing providers"]) {
            expect(page).toHaveTextContent(name);
        }
        expect(page).toHaveTextContent("never sees or stores your full card number");
    });

    it("photo use rules out marketing without permission", () => {
        visit("/photo-use");
        expect(screen.getByTestId("page-photo-use")).toHaveTextContent("unless you give us explicit permission");
    });

    it("terms describe the three deliverables and a refund policy", () => {
        visit("/terms");
        const page = screen.getByTestId("page-terms");
        for (const part of ["Design Plan", "Room Flow", "Companion Guide", "Anchor tall or heavy furniture"]) {
            expect(page).toHaveTextContent(part);
        }
        expect(screen.getByTestId("terms-refund-policy")).toBeInTheDocument();
    });

    it("support links to password reset, privacy and terms", () => {
        visit("/support");
        expect(screen.getByTestId("support-link-reset")).toHaveAttribute("href", "/forgot-password");
        expect(screen.getByTestId("support-link-privacy")).toHaveAttribute("href", "/privacy");
        expect(screen.getByTestId("support-link-terms")).toHaveAttribute("href", "/terms");
    });

    it("legal copy carries no dates in the body", () => {
        for (const path of ["/privacy", "/photo-use", "/terms", "/support"]) {
            const { unmount } = visit(path);
            const text = document.querySelector("main").textContent;
            expect(text).not.toMatch(/\b(19|20)\d{2}\b/);
            unmount();
        }
    });

    it("the footer links to every legal page and the help inbox", () => {
        visit("/privacy");
        expect(screen.getByTestId("footer-link-privacy")).toHaveAttribute("href", "/privacy");
        expect(screen.getByTestId("footer-link-photo-use")).toHaveAttribute("href", "/photo-use");
        expect(screen.getByTestId("footer-link-terms")).toHaveAttribute("href", "/terms");
        expect(screen.getByTestId("footer-link-support")).toHaveAttribute("href", "/support");
        expect(screen.getByTestId("footer-link-contact")).toHaveAttribute("href", "mailto:help@flowspace.solutions");
        expect(screen.getByTestId("site-footer")).not.toHaveTextContent("contact@flowspace.solutions");
    });
});
