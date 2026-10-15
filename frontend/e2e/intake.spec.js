const { test, expect } = require("@playwright/test");
const { mockApi, makePhoto } = require("./mockApi");

async function expectNoHorizontalScroll(page) {
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, "page must not scroll horizontally").toBeLessThanOrEqual(0);
}

async function expectStep(page, n, heading) {
    await expect(page.getByTestId("intake-step-label")).toHaveText(`Step ${n} of 4`);
    await expect(page.getByRole("progressbar")).toHaveAttribute("aria-valuenow", String(n));
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(heading);
    await expectNoHorizontalScroll(page);
}

async function upload(page, photo) {
    await page.getByTestId("intake-photo-input").setInputFiles(photo);
}

test("Plus: full four-screen journey on a phone, payload and payment hand-off", async ({ page }) => {
    const api = await mockApi(page);
    await page.goto("/intake?plan=plus");

    await expectStep(page, 1, "Let's start with your space.");
    await expect(page.getByTestId("intake-plan-badge")).toContainText("FlowSpace Design Plan · Plus");
    await expect(page.getByTestId("intake-plan-badge")).toContainText("$10 one-time");
    await expect(page.locator("body")).not.toContainText(/minute/i);
    await expect(page.locator("body")).not.toContainText(/Blueprint/);

    await page.getByTestId("intake-next").click();
    await expect(page.getByTestId("intake-error-summary")).toBeFocused();
    await expect(page.getByLabel("Which space are we planning?")).toHaveAttribute("aria-invalid", "true");

    await page.getByLabel("Which space are we planning?").selectOption("home_office");
    await page.getByRole("radio", { name: "More useful storage" }).check();
    await page.getByLabel(/Anything specific you want to solve/).fill("Guitar and ukulele need a home");
    await page.getByTestId("intake-next").click();

    await expectStep(page, 2, "Show us the space as it is today.");
    await page.getByTestId("intake-next").click();
    await expect(page.getByTestId("intake-error-summary")).toContainText("don't charge for a personalized plan");

    await upload(page, await makePhoto(page, { seed: 1, width: 900, height: 1200 }));
    await expect(page.getByTestId("photo-card-0")).toBeVisible();
    await expect(page.getByTestId("photo-status-0")).toHaveText("Accepted");
    await page.getByLabel("Label for Photo 1").fill("Wall with hooks");

    await upload(page, await makePhoto(page, { seed: 7, width: 1200, height: 900 }));
    await expect(page.getByTestId("photo-orientation-nudge")).toBeVisible();
    await page.getByTestId("photo-orientation-confirm").click();
    await expect(page.getByTestId("photo-card-1")).toBeVisible();
    await page.getByTestId("photo-card-1").getByRole("radio", { name: "Close-up of an item" }).check();
    await expect(page.getByTestId("photo-count")).toContainText("2 of 3 added");
    await expectNoHorizontalScroll(page);

    await page.getByRole("radio", { name: "Only part of it — plan the area shown" }).check();
    await page.getByTestId("intake-next").click();

    await expectStep(page, 3, "What should your plan work around?");
    await expect(page.getByLabel("Who uses this space, and what equipment needs a permanent place?")).toBeVisible();
    await expect(page.getByTestId("visual-toggle")).toHaveAttribute("aria-expanded", "false");
    await page.getByRole("radio", { name: "Keep selected items" }).check();
    await page.getByLabel("Which items need to stay?").fill("existing wall hooks in Photo 1; desk");
    await page.getByRole("checkbox", { name: "No drilling" }).check();
    await page.getByRole("checkbox", { name: "No specific limits" }).check();
    await page.getByRole("radio", { name: "$100–$300" }).check();
    await expect(page.getByTestId("conflict-limits_none")).toBeVisible();
    await page.getByTestId("intake-next").click();
    await expect(page.getByTestId("intake-error-summary")).toContainText("one version");
    await page.getByTestId("resolve-limits_none-keep_limits").click();
    await expect(page.getByTestId("contradictions")).toHaveCount(0);
    await page.getByTestId("visual-toggle").click();
    await page.getByRole("radio", { name: "Choose a style and palette" }).check();
    await page.getByRole("radio", { name: "Scandinavian" }).check();
    await page.getByRole("radio", { name: "Sage green" }).check();
    await expectNoHorizontalScroll(page);
    await page.getByTestId("intake-next").click();

    await expectStep(page, 4, "Review your project.");
    await expect(page.getByTestId("review-photos")).toContainText("Photo 1 — Wall with hooks");
    await expect(page.getByTestId("review-photos")).toContainText("Only the areas shown in the photos");
    await expect(page.getByTestId("review-limitations")).toContainText("one after-view for each accepted photo (2)");
    await expect(page.getByTestId("review-limitations")).toContainText("Close-ups explain specific items");
    await expect(page.getByTestId("room-flow-mode")).toContainText("not to scale");
    await expect(page.getByTestId("review-plan-line")).toHaveText("Your plan: Plus — $10, one-time payment.");
    await expect(page.locator("body")).not.toContainText(/first .*free/i);

    await page.getByRole("button", { name: "Edit space and goal" }).click();
    await expectStep(page, 1, "Let's start with your space.");
    await expect(page.getByLabel("Which space are we planning?")).toHaveValue("home_office");
    await page.getByRole("button", { name: "Save and return to review" }).click();
    await expectStep(page, 4, "Review your project.");

    await page.getByTestId("intake-submit").click();
    await expect(page.getByTestId("intake-error-summary")).toContainText("Enter your name");
    await page.getByLabel("Your name").fill("Camila");
    await page.getByLabel("Email").fill("camila@example.com");
    await page.getByLabel("Create a password to keep this plan").fill("password12");
    const submit = page.getByTestId("intake-submit");
    await expect(submit).toHaveText("Continue to payment — $10");
    const box = await submit.boundingBox();
    expect(box.height).toBeGreaterThanOrEqual(44);
    await submit.click();

    await page.waitForURL(/mock-checkout=1/);
    expect(api.leads).toHaveLength(1);
    const lead = api.leads[0];
    expect(lead.package_id).toBe("plus");
    expect(lead.photos).toHaveLength(2);
    expect(lead.intake.photos.map((p) => [p.ref, p.shot])).toEqual([
        ["P1", "wide"],
        ["P2", "detail"],
    ]);
    expect(lead.intake).toMatchObject({
        space_type: "home_office",
        priority: "storage",
        coverage: "partial",
        keep: "keep_selected",
        limits: ["no_drilling"],
        budget: "100_300",
        visual: { mode: "choose_style", style: "scandinavian", palette: "sage" },
        room_flow_mode: "not_to_scale",
    });
    expect(api.checkouts[0]).toMatchObject({ package_id: "plus", metadata: { lead_id: "lead-1" } });
});

test("Premium: duplicate and tiny photos are flagged before payment", async ({ page }) => {
    await mockApi(page);
    await page.goto("/intake?plan=premium");
    await page.getByLabel("Which space are we planning?").selectOption("garage");
    await page.getByRole("radio", { name: "Better room layout" }).check();
    await page.getByTestId("intake-next").click();

    const same = await makePhoto(page, { seed: 3, width: 900, height: 1200 });
    await upload(page, same);
    await expect(page.getByTestId("photo-card-0")).toBeVisible();
    await upload(page, { ...same, name: "again.jpg" });
    await expect(page.getByTestId("photo-status-1")).toHaveText("Needs replacing");
    await expect(page.getByTestId("photo-issues-1")).toContainText("same view as Photo 1");
    await upload(page, await makePhoto(page, { seed: 4, width: 240, height: 320 }));
    await expect(page.getByTestId("photo-issues-2")).toContainText("too small");

    await page.getByRole("radio", { name: "Yes, they show the whole area" }).check();
    await page.getByTestId("intake-next").click();
    await expect(page.getByTestId("intake-error-summary")).toContainText("Photo 2");

    await page.getByTestId("photo-replace-input-1").setInputFiles(await makePhoto(page, { seed: 11, width: 900, height: 1200 }));
    await expect(page.getByTestId("photo-status-1")).toHaveText("Accepted");
    await page.getByRole("button", { name: "Remove Photo 3" }).click();
    await page.getByTestId("intake-next").click();
    await expectStep(page, 3, "What should your plan work around?");

    await page.getByRole("radio", { name: "Yes" }).check();
    await expect(page.getByTestId("measurements")).toContainText("a vehicle needs to fit");
    await page.getByRole("radio", { name: "Keep all current furniture" }).check();
    await page.getByRole("checkbox", { name: "No specific limits" }).check();
    await page.getByRole("radio", { name: "$300–$700" }).check();
    await page.getByRole("radio", { name: "I'll add measurements" }).check();
    await page.getByTestId("intake-next").click();
    const summary = page.getByTestId("intake-error-summary");
    await expect(summary).toContainText("width");
    await expect(summary).toContainText("Choose where you'll shop");
    await page.getByLabel("Width").fill("20");
    await page.getByLabel("Length", { exact: true }).fill("22");
    await page.getByLabel("Doors, windows and fixed items").fill("Garage door on the front wall; water heater back left");
    await page.getByLabel("Sizes of the items or spot that must fit").fill("SUV 16 ft long, 6.5 ft wide");
    await page.getByLabel("Where will you shop?").selectOption("US");
    await page.getByTestId("intake-next").click();
    await expectStep(page, 4, "Review your project.");
    await expect(page.getByTestId("room-flow-mode")).toContainText("measurements you confirmed");
    await expect(page.getByTestId("review-plan-line")).toHaveText("Your plan: Premium — $20, one-time payment.");
    await expect(page.getByTestId("intake-submit")).toHaveText("Continue to payment — $20");
});

test("Free: conceptual path is labelled and the draft survives a reload", async ({ page }) => {
    const api = await mockApi(page);
    await page.goto("/intake?plan=free");
    await page.getByLabel("Which space are we planning?").selectOption("kids_room");
    await page.getByRole("radio", { name: "Less visual clutter" }).check();
    await page.getByTestId("intake-next").click();
    await expectStep(page, 2, "Show us the space as it is today.");

    await page.reload();
    await expect(page.getByTestId("intake-draft-restored")).toBeVisible();
    await expectStep(page, 2, "Show us the space as it is today.");

    await page.getByTestId("photo-mode-conceptual").check();
    await expect(page.getByText("Conceptual plan — not your room")).toBeVisible();
    await page.getByTestId("conceptual-ack").check();
    await page.getByTestId("intake-next").click();

    await page.getByRole("radio", { name: "Open to replacements" }).check();
    await page.getByRole("checkbox", { name: "Easy-to-reach storage" }).check();
    await page.getByRole("radio", { name: "Use what I own" }).check();
    await page.getByRole("checkbox", { name: "Sleep" }).check();
    await page.getByRole("checkbox", { name: "Play" }).check();
    await page.getByTestId("intake-next").click();

    await expectStep(page, 4, "Review your project.");
    await expect(page.getByTestId("review-photos")).toContainText("None — conceptual plan");
    await expect(page.getByTestId("review-limitations")).toContainText("Conceptual plan");
    await expect(page.getByTestId("room-flow-mode")).toContainText("Conceptual zone diagram");
    await expect(page.getByTestId("review-plan-line")).toContainText("Your plan: Free — $0");
    await page.getByLabel("Your name").fill("Ana");
    await page.getByLabel("Email").fill("ana@example.com");
    await page.getByLabel("Create a password to keep this plan").fill("password12");
    await expect(page.getByTestId("intake-submit")).toHaveText("Create my free Design Plan");
    await page.getByTestId("intake-submit").click();
    await page.waitForURL(/\/success\?plan=free/);
    expect(api.leads[0].intake).toMatchObject({ photo_mode: "conceptual", room_flow_mode: "conceptual" });
    expect(api.leads[0].photos).toEqual([]);
    expect(api.checkouts).toHaveLength(0);
    expect(await page.evaluate(() => localStorage.getItem("fs_intake_draft_v1"))).toBeNull();
});

test("keyboard: each screen can be completed without a pointer", async ({ page, isMobile }) => {
    test.skip(isMobile, "keyboard check runs on desktop");
    await mockApi(page);
    await page.goto("/intake?plan=plus");
    await page.getByLabel("Which space are we planning?").focus();
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Tab");
    await expect(page.getByRole("radio", { name: "Easier everyday use" })).toBeFocused();
    await page.keyboard.press("Space");
    await expect(page.getByRole("radio", { name: "Easier everyday use" })).toBeChecked();
    await page.keyboard.press("Enter");
    await expectStep(page, 2, "Show us the space as it is today.");
    await expect(page.getByRole("heading", { level: 1 })).toBeFocused();
});
