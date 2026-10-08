import React from "react";
import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import Intake from "./Intake";
import { api } from "../lib/api";
import { DRAFT_KEY, emptyForm, serializeDraft } from "../lib/intake/model";
import { measurePhoto } from "../lib/intake/photoChecks";
import { bakeRotation, inspectPhotoFile } from "../lib/photoOrientation";

jest.mock("../components/Header", () => () => null);
jest.mock("../components/Footer", () => () => null);

const mockAuth = { member: null, signup: jest.fn(), login: jest.fn(), refresh: jest.fn() };
jest.mock("../context/AuthContext", () => ({ useAuth: () => mockAuth }));

jest.mock("../lib/api", () => ({
    api: { post: jest.fn(), get: jest.fn() },
    apiErrorCode: (err) => err?.response?.data?.detail?.code || null,
    apiErrorMessage: (err) => err?.response?.data?.detail?.message || "error",
}));

jest.mock("../lib/photoOrientation", () => ({ inspectPhotoFile: jest.fn(), bakeRotation: jest.fn() }));

const mockMetrics = { width: 1600, height: 1200, brightness: 120, sharpness: 300, hash: "0f0f0f0f0f0f0f0f" };
jest.mock("../lib/intake/photoChecks", () => {
    const actual = jest.requireActual("../lib/intake/photoChecks");
    return { ...actual, measurePhoto: jest.fn() };
});

function renderIntake(plan = "plus") {
    return render(
        <MemoryRouter initialEntries={[`/intake?plan=${plan}`]}>
            <Routes>
                <Route path="/intake" element={<Intake />} />
                <Route path="/success" element={<p>success page</p>} />
            </Routes>
        </MemoryRouter>,
    );
}

let uploadCount = 0;
beforeEach(() => {
    localStorage.clear();
    uploadCount = 0;
    jest.clearAllMocks();
    measurePhoto.mockImplementation(async () => mockMetrics);
    inspectPhotoFile.mockImplementation(async (file) => ({ needsNudge: false, previewUrl: "blob:x", file }));
    bakeRotation.mockImplementation(async (file) => file);
    mockAuth.refresh = jest.fn();
    api.get.mockResolvedValue({ data: { enabled: true, mode: "test", message: null } });
    window.scrollTo = jest.fn();
    URL.revokeObjectURL = jest.fn();
    global.fetch = jest.fn(async () => {
        uploadCount += 1;
        const id = String(uploadCount).padStart(24, "a");
        return { ok: true, json: async () => ({ id, url: `/api/uploads/photo/${id}` }) };
    });
});

async function completeScreen1(user, { priority = "More useful storage", space = "Bedroom" } = {}) {
    await user.selectOptions(screen.getByLabelText("Which space are we planning?"), space);
    await user.click(screen.getByRole("radio", { name: priority }));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await screen.findByText("Step 2 of 4");
}

async function addPhoto(user, index = 0) {
    const file = new File(["img"], "room.jpg", { type: "image/jpeg" });
    await user.upload(screen.getByLabelText(/Add (a photo|another angle)/), file);
    await screen.findByTestId(`photo-card-${index}`);
}

test("shows real progress and linked, labelled errors on screen 1", async () => {
    const user = userEvent.setup();
    renderIntake();
    expect(screen.getByText("Step 1 of 4")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "1");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Let's start with your space.");
    expect(screen.queryByText(/minute/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Continue" }));
    const summary = await screen.findByRole("alert");
    expect(summary).toHaveTextContent("Choose the type of space.");
    const select = screen.getByLabelText("Which space are we planning?");
    expect(select).toHaveAttribute("aria-invalid", "true");
    expect(select).toHaveAttribute("aria-describedby", expect.stringContaining("space_type-error"));
    expect(screen.getByRole("group", { name: "What would make the biggest difference?" })).toBeInTheDocument();
});

test("paid plan cannot continue without a usable photo", async () => {
    const user = userEvent.setup();
    renderIntake("plus");
    await completeScreen1(user);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Show us the space as it is today.");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/don't charge for a personalized plan/);
    expect(screen.queryByTestId("photo-mode-conceptual")).not.toBeInTheDocument();
});

test("free plan can take a clearly labelled conceptual path", async () => {
    const user = userEvent.setup();
    renderIntake("free");
    await completeScreen1(user);
    await user.click(screen.getByLabelText(/conceptual plan$/));
    expect(screen.getByText("Conceptual plan — not your room")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/understand this is a conceptual plan/);
    await user.click(screen.getByLabelText(/I understand this is a conceptual plan/));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await screen.findByText("Step 3 of 4");
});

test("labels photos automatically and supports label, replace and remove", async () => {
    const user = userEvent.setup();
    renderIntake("plus");
    await completeScreen1(user);
    await addPhoto(user);
    const card = screen.getByTestId("photo-card-0");
    expect(within(card).getByRole("heading", { name: "Photo 1" })).toBeInTheDocument();
    await user.type(within(card).getByLabelText(/Label for Photo 1/), "Left wall");
    expect(within(card).getByRole("img")).toHaveAttribute("alt", "Photo 1 — Left wall");
    expect(within(card).getByRole("button", { name: "Replace Photo 1" })).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Remove Photo 1" }));
    expect(screen.queryByTestId("photo-card-0")).not.toBeInTheDocument();
    expect(screen.getByText("0 of 3 added — the Plus plan includes up to 3")).toBeInTheDocument();
});

test("flags a duplicate view and blocks until it is removed", async () => {
    const user = userEvent.setup();
    renderIntake("premium");
    await completeScreen1(user);
    await addPhoto(user, 0);
    await addPhoto(user, 1);
    expect(screen.getByTestId("photo-status-1")).toHaveTextContent("Needs replacing");
    expect(screen.getByTestId("photo-issues-1")).toHaveTextContent(/same view as Photo 1/);
    await user.click(screen.getByRole("radio", { name: "Yes, they show the whole area" }));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/Photo 2/);
    await user.click(screen.getByRole("button", { name: "Remove Photo 2" }));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await screen.findByText("Step 3 of 4");
});

test("full paid journey: conditional questions, contradiction, review, payment", async () => {
    const user = userEvent.setup();
    api.post.mockImplementation(async (url) => {
        if (url === "/leads") return { data: { id: "lead-123" } };
        if (url === "/checkout/session") return { data: { url: "https://checkout.example/session" } };
        throw new Error(url);
    });
    mockAuth.signup.mockResolvedValue({ usage: { can_generate_free: true } });
    renderIntake("plus");
    await completeScreen1(user, { space: "Kids' room", priority: "Better room layout" });
    await addPhoto(user);
    await user.click(screen.getByRole("radio", { name: "Only part of it — plan the area shown" }));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await screen.findByText("Step 3 of 4");

    expect(screen.getByRole("group", { name: "Which activities should this room support?" })).toBeInTheDocument();
    expect(screen.getByTestId("visual-toggle")).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("group", { name: "Style" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "Keep selected items" }));
    await user.type(screen.getByLabelText("Which items need to stay?"), "six-drawer dresser in Photo 1");
    await user.click(screen.getByRole("checkbox", { name: "Keep the layout" }));
    await user.click(screen.getByRole("checkbox", { name: "No specific limits" }));
    await user.click(screen.getByRole("checkbox", { name: "No drilling" }));
    await user.click(screen.getByRole("radio", { name: "Not sure yet" }));
    await user.click(screen.getByRole("checkbox", { name: "Sleep" }));

    expect(screen.getByTestId("conflict-limits_none")).toBeInTheDocument();
    expect(screen.getByTestId("conflict-layout")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/one version/);

    await user.click(screen.getByRole("button", { name: "Keep my selected limits" }));
    await user.click(screen.getByRole("button", { name: "Layout changes are OK" }));
    expect(screen.queryByTestId("contradictions")).not.toBeInTheDocument();
    expect(screen.getByTestId("measurements")).toHaveTextContent(/you want a better room layout/);
    await user.click(screen.getByRole("radio", { name: /use a functional map, not to scale/ }));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await screen.findByText("Step 4 of 4");

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Review your project.");
    expect(screen.getByTestId("review-plan-line")).toHaveTextContent("Your plan: Plus — $10, one-time payment.");
    expect(screen.getByTestId("room-flow-mode")).toHaveTextContent(/not to scale/);
    expect(screen.getByTestId("review-limitations")).toHaveTextContent(/only the areas shown/);
    expect(screen.getByRole("region", { name: "Account" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Payment" })).toBeInTheDocument();
    expect(screen.queryByText(/first .*free/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Edit essentials" }));
    await screen.findByText("Step 3 of 4");
    await user.click(screen.getByRole("button", { name: "Save and return to review" }));
    await screen.findByText("Step 4 of 4");

    await user.type(screen.getByLabelText("Your name"), "Camila");
    await user.type(screen.getByLabelText("Email"), "camila@example.com");
    await user.type(screen.getByLabelText("Create a password to keep this plan"), "password12");
    await user.click(screen.getByRole("button", { name: "Continue to payment — $10" }));

    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/checkout/session", expect.anything()));
    const leadCall = api.post.mock.calls.find(([url]) => url === "/leads");
    const payload = leadCall[1];
    expect(payload.package_id).toBe("plus");
    expect(payload.photos).toHaveLength(1);
    expect(payload.intake).toMatchObject({
        priority: "better_layout",
        coverage: "partial",
        keep: "keep_selected",
        limits: ["no_drilling"],
        budget: "not_sure",
        measure_mode: "not_to_scale",
        room_flow_mode: "not_to_scale",
        space_answers: { activities: ["sleep"] },
    });
    expect(payload.intake.photos[0]).toMatchObject({ ref: "P1", label: "Photo 1" });
    expect(localStorage.getItem(DRAFT_KEY)).toBeNull();
});

test("preserves the draft across a reload or login round-trip", async () => {
    const user = userEvent.setup();
    const first = renderIntake("plus");
    await completeScreen1(user);
    first.unmount();
    renderIntake("plus");
    expect(screen.getByTestId("intake-draft-restored")).toBeInTheDocument();
    expect(screen.getByText("Step 2 of 4")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByLabelText("Which space are we planning?")).toHaveValue("bedroom");
    expect(screen.getByRole("radio", { name: "More useful storage" })).toBeChecked();
});

const PAYMENTS_OFF = "Payments are disabled in this preview. No charge will be made.";

function seedReviewDraft() {
    const form = {
        ...emptyForm(),
        space_type: "bedroom",
        priority: "storage",
        coverage: "whole",
        keep: "keep_all",
        limits: ["none"],
        budget: "100_300",
        name: "Camila",
        email: "camila@example.com",
        shop_country: "US",
    };
    const photos = [{ id: "p1", url: "/api/uploads/photo/aaaaaaaaaaaaaaaaaaaaaaaa", label: "", shot: "wide", metrics: mockMetrics }];
    localStorage.setItem(DRAFT_KEY, serializeDraft({ form, photos, step: 3 }));
}

function expectNeutralPaymentsOff(button) {
    const notice = screen.getByTestId("payments-disabled-notice");
    expect(notice).toHaveTextContent(PAYMENTS_OFF);
    expect(notice).toHaveAttribute("role", "status");
    expect(notice.className).not.toMatch(/red|rose/);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText(/stripe not configured/i)).not.toBeInTheDocument();
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-describedby", "payments-disabled-notice");
}

test("review shows a neutral payments-off notice up front when checkout is not configured", async () => {
    const user = userEvent.setup();
    api.get.mockResolvedValue({ data: { enabled: false, mode: null, message: PAYMENTS_OFF } });
    seedReviewDraft();
    renderIntake("plus");
    expect(await screen.findByTestId("payments-disabled-notice")).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith("/checkout/config");
    const pay = screen.getByRole("button", { name: "Continue to payment — $10" });
    expectNeutralPaymentsOff(pay);
    await user.click(pay);
    expect(api.post).not.toHaveBeenCalled();
});

test("review falls back to the neutral notice when checkout answers payments disabled", async () => {
    const user = userEvent.setup();
    api.get.mockRejectedValue(new Error("config probe unavailable"));
    api.post.mockImplementation(async (url) => {
        if (url === "/leads") return { data: { id: "lead-9" } };
        const err = new Error("503");
        err.response = { status: 503, data: { detail: "Stripe not configured" } };
        throw err;
    });
    mockAuth.signup.mockResolvedValue({ usage: { can_generate_free: true } });
    seedReviewDraft();
    renderIntake("premium");
    await screen.findByText("Step 4 of 4");
    expect(screen.queryByTestId("payments-disabled-notice")).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Create a password to keep this plan"), "password12");
    await user.click(screen.getByRole("button", { name: "Continue to payment — $20" }));
    await screen.findByTestId("payments-disabled-notice");
    expectNeutralPaymentsOff(screen.getByRole("button", { name: "Continue to payment — $20" }));
});
