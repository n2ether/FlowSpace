import React from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import ProjectStatus from "./ProjectStatus";
import { api } from "../lib/api";

jest.mock("../components/Header", () => () => null);
jest.mock("../components/Footer", () => () => null);

const mockAuth = { member: { id: "m1", name: "Camila", email: "camila@example.com" }, loading: false };
jest.mock("../context/AuthContext", () => ({ useAuth: () => mockAuth }));
jest.mock("../lib/api", () => ({ api: { get: jest.fn() }, apiErrorMessage: () => "error" }));

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

    it("handles a project that isn't in this account", async () => {
        renderProject(null);
        expect(await screen.findByTestId("project-missing")).toBeInTheDocument();
    });
});
