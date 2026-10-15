import React from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Landing from "./Landing";

jest.mock("../components/Header", () => () => null);
jest.mock("../components/Footer", () => () => null);
jest.mock("../components/BeforeAfterSlider", () => () => null);

function renderLanding(url) {
    return render(
        <MemoryRouter initialEntries={[url]}>
            <Landing />
        </MemoryRouter>,
    );
}

let scrolledTo;
beforeEach(() => {
    scrolledTo = [];
    Element.prototype.scrollIntoView = jest.fn(function scrollIntoView() {
        scrolledTo.push(this.id);
    });
    jest.spyOn(window, "requestAnimationFrame").mockImplementation((cb) => {
        cb(0);
        return 1;
    });
    jest.spyOn(window, "cancelAnimationFrame").mockImplementation(() => {});
});

afterEach(() => jest.restoreAllMocks());

describe("Canceled checkout", () => {
    it("shows a neutral notice and scrolls to the plans", () => {
        renderLanding("/?canceled=1#packages");
        const notice = screen.getByTestId("checkout-canceled-notice");
        expect(notice).toHaveTextContent("Checkout canceled. No charge was made.");
        expect(notice).toHaveAttribute("role", "status");
        expect(notice.className).not.toMatch(/red|rose/);
        expect(document.getElementById("packages")).toContainElement(notice);
        expect(scrolledTo).toEqual(["packages"]);
    });

    it("shows nothing on a normal visit", () => {
        renderLanding("/");
        expect(screen.queryByTestId("checkout-canceled-notice")).not.toBeInTheDocument();
        expect(scrolledTo).toEqual([]);
    });
});
