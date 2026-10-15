import {
    PLANS,
    buildLeadPayload,
    contradictions,
    coverageLimitations,
    emptyForm,
    firstInvalidStep,
    measurementsNeeded,
    parseDraft,
    planLine,
    resolveContradiction,
    resolvePlan,
    roomFlowMode,
    serializeDraft,
    shoppingLocationNeeded,
    spaceQuestion,
    submitLabel,
    validateContact,
    validateNeeds,
    validatePhotos,
    validateSpace,
} from "./model";

const wide = (n, extra = {}) => ({ id: `id${n}`, url: `/api/uploads/photo/${n}`, shot: "wide", issues: [], ...extra });

function readyForm(over = {}) {
    return {
        ...emptyForm(),
        space_type: "bedroom",
        priority: "storage",
        coverage: "whole",
        keep: "keep_all",
        limits: ["none"],
        budget: "100_300",
        name: "Camila",
        email: "camila@example.com",
        password: "password12",
        ...over,
    };
}

describe("plans", () => {
    it("keeps the approved prices and photo caps", () => {
        expect(PLANS.free).toMatchObject({ price: 0, maxPhotos: 2 });
        expect(PLANS.plus).toMatchObject({ price: 10, maxPhotos: 3 });
        expect(PLANS.premium).toMatchObject({ price: 20, maxPhotos: 4 });
        expect(resolvePlan("PREMIUM").id).toBe("premium");
        expect(resolvePlan("bogus").id).toBe("free");
    });

    it("states the plan and one-time price explicitly", () => {
        expect(planLine(PLANS.plus)).toBe("Your plan: Plus — $10, one-time payment.");
        expect(submitLabel(PLANS.premium)).toBe("Continue to payment — $20");
        expect(submitLabel(PLANS.free)).toBe("Create my free Design Plan");
        expect(planLine(PLANS.plus)).not.toMatch(/free/i);
    });
});

describe("screen 1 — space & goal", () => {
    it("requires a space and one priority", () => {
        const e = validateSpace(emptyForm());
        expect(e.space_type).toBeTruthy();
        expect(e.priority).toBeTruthy();
    });

    it("asks which space for Other and flags out-of-scope spaces", () => {
        expect(validateSpace(readyForm({ space_type: "other" })).other_label).toMatch(/which space/i);
        expect(validateSpace(readyForm({ space_type: "other", other_label: "the whole house" })).other_label).toMatch(
            /one indoor room/i,
        );
        expect(validateSpace(readyForm({ space_type: "other", other_label: "playroom" }))).toEqual({});
    });
});

describe("screen 2 — photos", () => {
    it("blocks paid plans without a usable photo", () => {
        expect(validatePhotos(readyForm(), [], PLANS.plus).photos).toMatch(/don't charge/);
        expect(validatePhotos(readyForm({ photo_mode: "conceptual" }), [], PLANS.plus).photos).toMatch(/Paid plans/);
    });

    it("lets Free continue conceptually only after explicit acknowledgement", () => {
        const f = readyForm({ photo_mode: "conceptual" });
        expect(validatePhotos(f, [], PLANS.free).conceptual_ack).toBeTruthy();
        expect(validatePhotos({ ...f, conceptual_ack: true }, [], PLANS.free)).toEqual({});
    });

    it("needs a wide view, not only close-ups", () => {
        const e = validatePhotos(readyForm(), [wide(1, { shot: "detail" })], PLANS.plus);
        expect(e.photos).toMatch(/wide view/);
    });

    it("blocks duplicates and unconfirmed warnings, accepts acknowledged ones", () => {
        const dup = wide(2, { issues: [{ code: "duplicate", severity: "block", message: "Same view." }] });
        expect(validatePhotos(readyForm(), [wide(1), dup], PLANS.plus).photos).toMatch(/Photo 2/);
        const blurry = wide(2, { issues: [{ code: "blurry", severity: "warn", message: "Blurry." }] });
        expect(validatePhotos(readyForm(), [wide(1), blurry], PLANS.plus).photos).toMatch(/Keep this photo/);
        expect(validatePhotos(readyForm(), [wide(1), { ...blurry, acknowledged: true }], PLANS.plus)).toEqual({});
    });

    it("enforces the plan's photo cap and requires a coverage answer", () => {
        expect(validatePhotos(readyForm(), [wide(1), wide(2), wide(3)], PLANS.free).photos).toMatch(/up to 2/);
        expect(validatePhotos(readyForm({ coverage: "" }), [wide(1)], PLANS.plus).coverage).toBeTruthy();
    });

    it("waits for a pending orientation check", () => {
        expect(validatePhotos(readyForm(), [wide(1)], PLANS.plus, { pending: true }).photos).toMatch(/orientation/);
    });
});

describe("screen 3 — essentials", () => {
    it("requires explicit keep, limits and budget answers", () => {
        const e = validateNeeds({ ...emptyForm(), space_type: "closet" }, PLANS.plus);
        expect(Object.keys(e)).toEqual(expect.arrayContaining(["keep", "limits", "budget"]));
    });

    it("asks space-specific questions only for the matching room", () => {
        expect(spaceQuestion("kids_room").kind).toBe("kids");
        expect(spaceQuestion("garage").kind).toBe("garage");
        expect(spaceQuestion("home_office").legend).toMatch(/equipment/);
        expect(validateNeeds(readyForm({ space_type: "kids_room" }), PLANS.free).space_activities).toBeTruthy();
        expect(validateNeeds(readyForm({ space_type: "garage" }), PLANS.free).space_vehicle).toBeTruthy();
    });

    it("asks for measurements only when layout or fit depends on them", () => {
        expect(measurementsNeeded(readyForm())).toBe(false);
        expect(measurementsNeeded(readyForm({ priority: "better_layout" }))).toBe(true);
        expect(measurementsNeeded(readyForm({ needs_exact_fit: true }))).toBe(true);
        const garage = readyForm({ space_type: "garage" });
        garage.space_answers = { ...garage.space_answers, vehicle: "yes" };
        expect(measurementsNeeded(garage)).toBe(true);
        const f = readyForm({ priority: "better_layout" });
        expect(validateNeeds(f, PLANS.plus).measure_mode).toBeTruthy();
        expect(validateNeeds({ ...f, measure_mode: "not_to_scale" }, PLANS.plus)).toEqual({});
        const provided = validateNeeds({ ...f, measure_mode: "provided" }, PLANS.plus);
        expect(Object.keys(provided)).toEqual(expect.arrayContaining(["measure_width", "measure_length", "measure_fixed"]));
    });

    it("labels the Room Flow by evidence level", () => {
        expect(roomFlowMode(readyForm(), PLANS.plus)).toBe("not_to_scale");
        expect(roomFlowMode(readyForm({ photo_mode: "conceptual" }), PLANS.free)).toBe("conceptual");
        expect(roomFlowMode(readyForm({ priority: "better_layout", measure_mode: "provided" }), PLANS.plus)).toBe("measured");
    });

    it("requires a shopping country only for Premium purchases", () => {
        expect(shoppingLocationNeeded(readyForm(), PLANS.premium)).toBe(true);
        expect(shoppingLocationNeeded(readyForm({ budget: "use_owned" }), PLANS.premium)).toBe(false);
        expect(shoppingLocationNeeded(readyForm(), PLANS.plus)).toBe(false);
    });

    it("detects and resolves contradictions instead of choosing silently", () => {
        const f = readyForm({ limits: ["none", "no_drilling"] });
        expect(contradictions(f).map((c) => c.id)).toEqual(["limits_none"]);
        expect(validateNeeds(f, PLANS.plus).contradictions).toBeTruthy();
        expect(resolveContradiction(f, "limits_none", "keep_limits").limits).toEqual(["no_drilling"]);
        expect(resolveContradiction(f, "limits_none", "no_limits").limits).toEqual(["none"]);

        const layout = readyForm({ priority: "better_layout", limits: ["keep_layout"] });
        expect(contradictions(layout).map((c) => c.id)).toEqual(["layout"]);
        const within = resolveContradiction(layout, "layout", "within_layout");
        expect(contradictions(within)).toEqual([]);
        expect(measurementsNeeded(within)).toBe(false);

        const paint = readyForm({ limits: ["no_painting"], change_avoid: "paint the walls sage" });
        expect(contradictions(paint).map((c) => c.id)).toEqual(["paint"]);
        expect(contradictions(resolveContradiction(paint, "paint", "no_paint"))).toEqual([]);

        const fit = readyForm({ budget: "use_owned", needs_exact_fit: true });
        expect(contradictions(fit).map((c) => c.id)).toEqual(["budget_fit"]);
        expect(resolveContradiction(fit, "budget_fit", "open_to_buy").budget).toBe("");
    });
});

describe("screen 4 — review & payload", () => {
    it("requires contact details and a password only when signed out", () => {
        const e = validateContact({ ...emptyForm() }, { signedIn: false });
        expect(Object.keys(e)).toEqual(["name", "email", "password"]);
        expect(validateContact(readyForm({ email: "", password: "" }), { signedIn: true })).toEqual({});
    });

    it("finds the first screen that still needs answers", () => {
        const ctx = { form: readyForm(), photos: [wide(1)], plan: PLANS.plus, pending: false, signedIn: true };
        expect(firstInvalidStep(ctx)).toBe(-1);
        expect(firstInvalidStep({ ...ctx, photos: [] })).toBe(1);
        expect(firstInvalidStep({ ...ctx, form: readyForm({ budget: "" }) })).toBe(2);
    });

    it("shows coverage limitations before payment", () => {
        const notes = coverageLimitations(readyForm({ coverage: "partial", budget: "not_sure" }), [wide(1)], PLANS.premium);
        expect(notes.join(" ")).toMatch(/only the areas shown/);
        expect(notes.join(" ")).toMatch(/one after-view for each accepted photo \(1\)/);
        expect(notes.join(" ")).toMatch(/purchases as optional/);
        expect(coverageLimitations(readyForm({ photo_mode: "conceptual" }), [], PLANS.free)[0]).toMatch(/Conceptual/);
    });

    it("builds a lead payload with only accepted photos and structured intake", () => {
        const dup = wide(2, { issues: [{ code: "duplicate", severity: "block", message: "x" }] });
        const form = readyForm({ keep: "keep_selected", keep_items: "dresser in Photo 1", specifics: "Toys" });
        const payload = buildLeadPayload(form, [wide(1, { label: "Crib wall" }), dup], PLANS.plus, null);
        expect(payload.package_id).toBe("plus");
        expect(payload.photos).toEqual(["/api/uploads/photo/1"]);
        expect(payload.intake.photos[0]).toMatchObject({ ref: "P1", label: "Photo 1", custom_label: "Crib wall" });
        expect(payload.must_stay).toBe("Keep selected items: dresser in Photo 1");
        expect(payload.biggest_challenge).toBe("More useful storage — Toys");
        expect(payload.style_prefs).toEqual([]);
        expect(payload.intake.room_flow_mode).toBe("not_to_scale");
        expect(payload).not.toHaveProperty("password");
    });
});

describe("draft persistence", () => {
    it("round-trips answers and photos but never the password", () => {
        const raw = serializeDraft({ form: readyForm(), photos: [wide(1, { label: "Left" })], step: 2 });
        expect(raw).not.toMatch(/password12/);
        const draft = parseDraft(raw);
        expect(draft.step).toBe(2);
        expect(draft.form.space_type).toBe("bedroom");
        expect(draft.form.password).toBe("");
        expect(draft.photos[0]).toMatchObject({ url: "/api/uploads/photo/1", label: "Left" });
    });

    it("ignores corrupt or old drafts", () => {
        expect(parseDraft("{nope")).toBeNull();
        expect(parseDraft(JSON.stringify({ version: "old", form: {} }))).toBeNull();
    });
});
