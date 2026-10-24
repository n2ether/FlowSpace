import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import ProjectStatus from "./ProjectStatus";
import { api } from "../lib/api";

jest.mock("../components/Header", () => () => null);
jest.mock("../components/Footer", () => () => null);

const mockAuth = { member: { id: "m1", name: "Camila", email: "camila@example.com" }, loading: false };
jest.mock("../context/AuthContext", () => ({ useAuth: () => mockAuth }));
jest.mock("../lib/api", () => ({ api: { get: jest.fn(), post: jest.fn() }, apiErrorMessage: () => "error" }));

function renderProject(space, extra = {}) {
    api.get.mockResolvedValue({ data: { spaces: space ? [space] : [], ...extra } });
    return render(
        <MemoryRouter initialEntries={["/account/spaces/l1"]}>
            <Routes>
                <Route path="/account/spaces/:leadId" element={<ProjectStatus />} />
            </Routes>
        </MemoryRouter>,
    );
}

const base = {
    id: "l1",
    title: "Nursery",
    space_type: "nursery",
    package_id: "plus",
    email: "camila@example.com",
    photos: [{ url: "https://cdn.example/own.jpg" }],
    deliverable: { has_plan: true, front_view_url: "https://cdn.example/generated.jpg" },
};

beforeEach(() => localStorage.clear());

describe("Project page", () => {
    it("opens an in-review project with a clear status and no package", async () => {
        renderProject({ ...base, status: "in_review", status_label: "In review" });
        expect(await screen.findByTestId("project-title")).toHaveTextContent("Nursery");
        expect(screen.getByTestId("project-status")).toHaveTextContent("In review");
        expect(screen.getByTestId("project-in-review")).toHaveTextContent(/email it to camila@example.com/);
        expect(screen.getByTestId("project-step-review")).toHaveAttribute("aria-current", "step");
        const images = screen.getAllByRole("img").map((img) => img.getAttribute("src"));
        expect(images).not.toContain("https://cdn.example/generated.jpg");
        expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
        expect(document.body).not.toHaveTextContent(/approve|blueprint|draft/i);
    });

    it("shows the estimate while preparing", async () => {
        renderProject({
            ...base,
            status: "in_progress",
            status_label: "In progress",
            processing_started_at: new Date().toISOString(),
            estimate_minutes: 10,
        });
        expect(await screen.findByTestId("project-in-progress")).toHaveTextContent("usually takes up to 10 minutes");
    });

    it("tells the customer when it runs past the estimate", async () => {
        renderProject({
            ...base,
            status: "in_progress",
            status_label: "In progress",
            processing_started_at: new Date(Date.now() - 25 * 60 * 1000).toISOString(),
        });
        const notice = await screen.findByTestId("project-delayed");
        expect(notice).toHaveTextContent("Taking a little longer than usual");
        expect(notice).toHaveTextContent(/email it to camila@example.com when it's ready/);
        expect(screen.getByTestId("project-status")).toHaveTextContent("Taking a little longer");
    });

    it("says delivered plans are in the inbox", async () => {
        renderProject({ ...base, status: "delivered", status_label: "Delivered", email_sent: true });
        expect(await screen.findByTestId("project-delivered")).toHaveTextContent("in your inbox");
    });

    it("finishes checkout for the same project instead of starting a new one", async () => {
        api.post.mockResolvedValue({ data: { url: "https://checkout.stripe.test/cs_new" } });
        const assign = jest.fn();
        const original = window.location;
        delete window.location;
        window.location = { origin: "https://preview.test", set href(url) { assign(url); } };
        try {
            renderProject({
                ...base,
                status: "awaiting_payment",
                status_label: "Awaiting payment",
                status_note: "Finish checkout to start your Design Plan.",
            });
            const resume = await screen.findByTestId("project-resume-checkout");
            expect(resume).toHaveTextContent("Finish checkout — $10");
            fireEvent.click(resume);
            await waitFor(() => expect(assign).toHaveBeenCalledWith("https://checkout.stripe.test/cs_new"));
            expect(api.post).toHaveBeenCalledWith("/checkout/session", {
                package_id: "plus",
                origin_url: "https://preview.test",
                email: "camila@example.com",
                metadata: { lead_id: "l1" },
            });
            expect(screen.getByTestId("project-choose-plan")).toHaveTextContent("Choose a different plan");
        } finally {
            window.location = original;
        }
    });

    it("keeps the customer on the page when checkout can't reopen", async () => {
        api.post.mockRejectedValue(new Error("nope"));
        renderProject({ ...base, status: "payment_not_completed", status_label: "Payment not completed" });
        fireEvent.click(await screen.findByTestId("project-resume-checkout"));
        expect(await screen.findByTestId("project-resume-error")).toHaveTextContent("error");
        expect(screen.getByTestId("project-resume-checkout")).not.toBeDisabled();
    });

    it("handles a project that isn't in this account", async () => {
        renderProject(null);
        expect(await screen.findByTestId("project-missing")).toBeInTheDocument();
    });
});
