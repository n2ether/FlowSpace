import React from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Success from "./Success";
import { api } from "../lib/api";

jest.mock("../components/Header", () => () => null);
jest.mock("../components/Footer", () => () => null);
jest.mock("../lib/api", () => ({ api: { get: jest.fn() } }));

function renderSuccess(url) {
    return render(
        <MemoryRouter initialEntries={[url]}>
            <Success />
        </MemoryRouter>,
    );
}

describe("Success page", () => {
    it("reminds the customer about spam only once (free plan)", () => {
        renderSuccess("/success?plan=free");
        expect(screen.getByText("Your Design Plan is in progress")).toBeInTheDocument();
        expect(screen.getByTestId("success-card").textContent.match(/spam/gi)).toHaveLength(1);
    });

    it("reminds the customer about spam only once (paid plan)", async () => {
        api.get.mockResolvedValue({ data: { payment_status: "paid", amount_total: 1000, currency: "usd" } });
        renderSuccess("/success?session_id=cs_test_1");
        expect(await screen.findByText("You're all set!")).toBeInTheDocument();
        expect(screen.getByTestId("success-card").textContent.match(/spam/gi)).toHaveLength(1);
    });
});
