import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import AccountSpace, { filenameFrom } from "./AccountSpace";
import { api } from "../lib/api";

jest.mock("../components/Header", () => () => null);
jest.mock("../components/Footer", () => () => null);

let mockAuth = { member: { id: "m1", name: "Ada" }, loading: false };
jest.mock("../context/AuthContext", () => ({ useAuth: () => mockAuth }));

jest.mock("../lib/api", () => ({
    api: { get: jest.fn() },
    apiErrorMessage: (_err, fallback) => fallback,
}));

const PLAN = {
    lead_id: "lead-1",
    title: "Closet",
    status: "in_review",
    approved: false,
    summary: "A calm closet with a clear landing zone.",
    strategy: ["Hang daily wear at eye level"],
    zones: [{ title: "Daily wear", desc: "Front rail" }],
    shopping_list: [{ name: "Slim hangers", qty: 30, price: 24 }],
    afters: [{ after_url: "/api/uploads/photo/after1" }],
};

function mockApi({ plan = PLAN, planError = null } = {}) {
    api.get.mockImplementation((url) => {
        if (url.endsWith("/plan")) return planError ? Promise.reject(planError) : Promise.resolve({ data: plan });
        if (url.endsWith("/board")) return Promise.resolve({ data: new Blob(["png"], { type: "image/png" }) });
        if (url.endsWith("/pdf"))
            return Promise.resolve({
                data: new Blob(["%PDF"], { type: "application/pdf" }),
                headers: { "content-disposition": 'attachment; filename="FlowSpace_Closet_Companion_Guide_Ada.pdf"' },
            });
        return Promise.reject(new Error(`unexpected ${url}`));
    });
}

function renderPage(path = "/account/spaces/lead-1") {
    return render(
        <MemoryRouter initialEntries={[path]}>
            <Routes>
                <Route path="/account/spaces/:leadId" element={<AccountSpace />} />
                <Route path="/login" element={<p>login page</p>} />
            </Routes>
        </MemoryRouter>,
    );
}

beforeEach(() => {
    mockAuth = { member: { id: "m1", name: "Ada" }, loading: false };
    api.get.mockReset();
    global.URL.createObjectURL = jest.fn(() => "blob:board");
    global.URL.revokeObjectURL = jest.fn();
    window.scrollTo = jest.fn();
});

describe("My Spaces plan page", () => {
    it("shows the draft banner, board, afters, and plan in English", async () => {
        mockApi();
        renderPage();
        expect(await screen.findByTestId("space-plan-draft-banner")).toHaveTextContent("In review – draft");
        expect(screen.getByTestId("space-plan-title")).toHaveTextContent("Closet");
        expect(await screen.findByTestId("space-plan-board")).toHaveAttribute("src", "blob:board");
        const afters = screen.getByTestId("space-plan-afters").querySelectorAll("img");
        expect(afters).toHaveLength(1);
        expect(afters[0].getAttribute("src")).toMatch(/\/api\/uploads\/photo\/after1$/);
        expect(screen.getByText("Daily wear")).toBeInTheDocument();
        expect(screen.getByText("Slim hangers")).toBeInTheDocument();
        expect(screen.getByTestId("space-plan-download")).toHaveTextContent("Download PDF");
        expect(api.get).toHaveBeenCalledWith("/me/spaces/lead-1/plan");
        expect(api.get).toHaveBeenCalledWith("/me/spaces/lead-1/board", { responseType: "blob" });
    });

    it("downloads the PDF through the authenticated client", async () => {
        mockApi();
        renderPage();
        const button = await screen.findByTestId("space-plan-download");
        const click = jest.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
        fireEvent.click(button);
        await waitFor(() => expect(click).toHaveBeenCalled());
        expect(api.get).toHaveBeenCalledWith("/me/spaces/lead-1/pdf", { responseType: "blob" });
        click.mockRestore();
    });

    it("hides the draft banner once the plan is approved and delivered", async () => {
        mockApi({ plan: { ...PLAN, approved: true, status: "delivered" } });
        renderPage();
        await screen.findByTestId("space-plan-title");
        expect(screen.queryByTestId("space-plan-draft-banner")).not.toBeInTheDocument();
    });

    it("shows a calm not-found state for someone else's plan", async () => {
        mockApi({ planError: { response: { status: 404 } } });
        renderPage();
        expect(await screen.findByTestId("space-plan-missing")).toHaveTextContent("We couldn't find this plan");
        expect(api.get).not.toHaveBeenCalledWith("/me/spaces/lead-1/board", expect.anything());
    });

    it("sends a signed-out visitor to log in and back", async () => {
        mockAuth = { member: null, loading: false };
        mockApi();
        renderPage();
        expect(await screen.findByText("login page")).toBeInTheDocument();
        expect(api.get).not.toHaveBeenCalled();
    });

    it("reads the PDF filename from Content-Disposition", () => {
        expect(filenameFrom('attachment; filename="A_B.pdf"', "x.pdf")).toBe("A_B.pdf");
        expect(filenameFrom("", "x.pdf")).toBe("x.pdf");
    });
});
