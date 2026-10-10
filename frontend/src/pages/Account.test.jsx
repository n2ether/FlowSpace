import React from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Account, { customerStatus, spaceTitle } from "./Account";
import { api } from "../lib/api";

jest.mock("../components/Header", () => () => null);
jest.mock("../components/Footer", () => () => null);

const mockAuth = {
    member: { id: "m1", name: "Ada Lovelace", usage: { free_generations_used: 1, can_generate_free: false } },
    loading: false,
};
jest.mock("../context/AuthContext", () => ({ useAuth: () => mockAuth }));

jest.mock("../lib/api", () => ({
    api: { get: jest.fn() },
    apiErrorMessage: () => "error",
}));

function renderAccount(spaces) {
    api.get.mockResolvedValue({ data: { spaces, usage: mockAuth.member.usage } });
    return render(
        <MemoryRouter>
            <Account />
        </MemoryRouter>,
    );
}

describe("My Spaces", () => {
    it("titles a failed generation with its space name and a neutral In review status", async () => {
        renderAccount([
            {
                id: "s1",
                title: "Bedroom",
                space_type: "bedroom",
                status: "in_review",
                status_label: "In review",
                package_id: "plus",
                deliverable: { has_plan: false },
            },
        ]);
        expect(await screen.findByTestId("space-title-s1")).toHaveTextContent("Bedroom");
        expect(screen.getByTestId("space-status-s1")).toHaveTextContent("In review");
        expect(screen.getByText("Our beta team reviews every plan before it's sent.")).toBeInTheDocument();
        expect(screen.queryByText(/error/i)).not.toBeInTheDocument();
    });

    it("renders a legacy 'error' lead as In review, never the raw status", async () => {
        renderAccount([
            { id: "s2", space_type: "other", title: "Craft room", status: "error", package_id: "free" },
            { id: "s3", space_type: "garage", status: "error", package_id: "free" },
        ]);
        expect(await screen.findByTestId("space-title-s2")).toHaveTextContent("Craft room");
        expect(screen.getByTestId("space-title-s3")).toHaveTextContent("Garage");
        expect(screen.getByTestId("space-status-s2")).toHaveTextContent("In review");
        expect(screen.getByTestId("space-status-s3")).toHaveTextContent("In review");
        expect(screen.queryByText(/error/i)).not.toBeInTheDocument();
    });

    it("maps every raw status to a customer-safe label", () => {
        expect(customerStatus({ status: "processing" }).label).toBe("In progress");
        expect(customerStatus({ status: "incomplete" }).label).toBe("In review");
        expect(customerStatus({ status: "pdf_ready" }).label).toBe("In review");
        expect(customerStatus({ status: "something_new" }).label).toBe("In review");
        expect(customerStatus({ status: "delivered" }).label).toBe("Delivered");
        expect(spaceTitle({ space_type: "other" })).toBe("Other space");
        expect(spaceTitle({ space_type: "laundry_room" })).toBe("Laundry room");
    });
});
