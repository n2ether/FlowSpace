// Shared intake model for Free, Plus and Premium. One flow, four screens.
// Prices and photo caps mirror backend PACKAGES and must not drift from it.

export const PRODUCT_NAME = "FlowSpace Design Plan";
export const INTAKE_VERSION = "beta-4screen-v1";
export const PAYMENTS_DISABLED_NOTICE = "Payments are disabled in this preview. No charge will be made.";

export const PLANS = {
    free: { id: "free", name: "Free", price: 0, maxPhotos: 2 },
    plus: { id: "plus", name: "Plus", price: 10, maxPhotos: 3 },
    premium: { id: "premium", name: "Premium", price: 20, maxPhotos: 4 },
};

export function resolvePlan(planId) {
    return PLANS[String(planId || "").toLowerCase()] || PLANS.free;
}

export const PLAN_SCOPE = {
    free: [
        { title: "Design Plan", body: "A short starter plan: functional zones and first steps for the area your photos show." },
        { title: "Room Flow", body: "A simple map of the zones, at the level your photos support." },
        { title: "Companion Guide", body: "First practical steps, with few shopping details." },
    ],
    plus: [
        { title: "Design Plan", body: "A complete, selective plan that explains each change." },
        { title: "Room Flow", body: "A functional map at the level your photos and measurements support." },
        { title: "Companion Guide", body: "A lean guide to materials and practical execution." },
    ],
    premium: [
        { title: "Design Plan", body: "A complete plan that explains each change." },
        { title: "Room Flow", body: "A functional map at the level your photos and measurements support." },
        { title: "Companion Guide", body: "A fuller guide with detailed shopping and labels; routine and climate notes only when relevant." },
    ],
};

export const STEPS = [
    { id: "space", title: "Space & goal", heading: "Let's start with your space." },
    { id: "photos", title: "Photos", heading: "Show us the space as it is today." },
    { id: "needs", title: "Essentials", heading: "What should your plan work around?" },
    { id: "review", title: "Review", heading: "Review your project." },
];

export const SPACE_TYPES = [
    { id: "closet", label: "Closet" },
    { id: "garage", label: "Garage" },
    { id: "laundry_room", label: "Laundry room" },
    { id: "pantry", label: "Pantry" },
    { id: "mudroom", label: "Mudroom" },
    { id: "storage", label: "Storage area" },
    { id: "kids_room", label: "Kids' room" },
    { id: "home_office", label: "Home office" },
    { id: "living_room", label: "Living room" },
    { id: "bedroom", label: "Bedroom" },
    { id: "other", label: "Other" },
];

export const PRIORITIES = [
    { id: "everyday_use", label: "Easier everyday use" },
    { id: "storage", label: "More useful storage" },
    { id: "less_clutter", label: "Less visual clutter" },
    { id: "better_layout", label: "Better room layout" },
    { id: "calmer_look", label: "A calmer, more cohesive look" },
];

export const KEEP_OPTIONS = [
    { id: "keep_all", label: "Keep all current furniture" },
    { id: "keep_selected", label: "Keep selected items" },
    { id: "open", label: "Open to replacements" },
];

export const LIMIT_OPTIONS = [
    { id: "no_drilling", label: "No drilling" },
    { id: "no_painting", label: "No painting" },
    { id: "keep_layout", label: "Keep the layout" },
    { id: "easy_reach", label: "Easy-to-reach storage" },
    { id: "other", label: "Other" },
    { id: "none", label: "No specific limits" },
];

export const BUDGETS = [
    { id: "use_owned", label: "Use what I own" },
    { id: "under_100", label: "Under $100" },
    { id: "100_300", label: "$100–$300" },
    { id: "300_700", label: "$300–$700" },
    { id: "700_plus", label: "$700+" },
    { id: "not_sure", label: "Not sure yet" },
];

export const VISUAL_MODES = [
    { id: "match_current", label: "Match my current space" },
    { id: "choose_style", label: "Choose a style and palette" },
    { id: "suggest", label: "Let FlowSpace suggest" },
];

export const STYLES = [
    { id: "modern", label: "Modern" },
    { id: "minimal", label: "Minimal" },
    { id: "scandinavian", label: "Scandinavian" },
    { id: "farmhouse", label: "Farmhouse" },
    { id: "cozy_layered", label: "Cozy & layered" },
    { id: "natural", label: "Natural / organic" },
];

export const PALETTES = [
    { id: "warm_neutrals", label: "Warm neutrals" },
    { id: "white", label: "White & light" },
    { id: "sage", label: "Sage green" },
    { id: "earth", label: "Earth tones" },
    { id: "blue", label: "Soft blues" },
    { id: "wood", label: "Wood tones" },
];

export const SHOT_TYPES = [
    { id: "wide", label: "Wide view" },
    { id: "detail", label: "Close-up of an item" },
];

export const COVERAGE_OPTIONS = [
    { id: "whole", label: "Yes, they show the whole area" },
    { id: "partial", label: "Only part of it — plan the area shown" },
];

export const MEASURE_UNITS = [
    { id: "ft", label: "feet" },
    { id: "in", label: "inches" },
    { id: "m", label: "meters" },
    { id: "cm", label: "centimeters" },
];

export const MEASURE_MODES = [
    { id: "provided", label: "I'll add measurements" },
    { id: "not_to_scale", label: "I can't measure now — use a functional map, not to scale" },
];

export const CLIMATE_OPTIONS = [
    { id: "humidity", label: "Humidity or damp" },
    { id: "heat", label: "Heat" },
    { id: "cold", label: "Cold" },
    { id: "dust", label: "Dust" },
];

export const SHOP_COUNTRIES = [
    { id: "US", label: "United States" },
    { id: "CA", label: "Canada" },
    { id: "GB", label: "United Kingdom" },
    { id: "BR", label: "Brazil" },
    { id: "other", label: "Somewhere else" },
];

export const KIDS_ACTIVITIES = [
    { id: "sleep", label: "Sleep" },
    { id: "changing", label: "Changing" },
    { id: "play", label: "Play" },
    { id: "shared", label: "Shared use" },
];

export const KIDS_STAGES = [
    { id: "baby", label: "Baby" },
    { id: "toddler", label: "Toddler" },
    { id: "school_age", label: "School age" },
    { id: "teen", label: "Teen" },
];

const TEXT_QUESTIONS = {
    home_office: "Who uses this space, and what equipment needs a permanent place?",
    closet: "Which items need the most space or easier access?",
    storage: "Which items need the most space or easier access?",
    laundry_room: "Which daily task is hardest in this space?",
    pantry: "Which daily task is hardest in this space?",
    bedroom: "What needs to happen comfortably in this space?",
    living_room: "What needs to happen comfortably in this space?",
    mudroom: "What needs to happen comfortably in this space?",
    other: "What needs to happen comfortably in this space?",
};

// kind: "kids" | "garage" | "text"
export function spaceQuestion(spaceType) {
    if (spaceType === "kids_room") {
        return { kind: "kids", legend: "Which activities should this room support?" };
    }
    if (spaceType === "garage") {
        return { kind: "garage", legend: "Does a vehicle need to park here, and what large items must fit?" };
    }
    if (TEXT_QUESTIONS[spaceType]) {
        return { kind: "text", legend: TEXT_QUESTIONS[spaceType] };
    }
    return null;
}

export const OUT_OF_SCOPE_RE =
    /\b(whole (house|home|apartment|flat)|entire (house|home)|every room|yard|garden|lawn|patio|deck|pool|roof|exterior|outside|office building|store|shop floor|restaurant|warehouse|commercial|car interior|boat|rv|camper)\b/i;
const PAINT_RE = /\b(paint|repaint|painting|painted|accent wall|wall colou?r)\b/i;
const CLIMATE_RE = /\b(humid|humidity|damp|moist|moisture|mold|mould|condensation|heat|hot|cold|freez|dust|dusty)\w*/i;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export const SPECIFICS_MAX = 200;

export function emptyForm() {
    return {
        space_type: "",
        other_label: "",
        priority: "",
        specifics: "",
        photo_mode: "photos",
        conceptual_ack: false,
        coverage: "",
        keep: "",
        keep_items: "",
        limits: [],
        limit_other: "",
        change_avoid: "",
        budget: "",
        visual_open: false,
        visual_mode: "match_current",
        style: "",
        palette: "",
        space_answers: { activities: [], stage: "", vehicle: "", large_items: "", text: "" },
        needs_exact_fit: false,
        layout_within_current: false,
        paint_confirmed: false,
        measure_mode: "",
        measurements: { unit: "ft", width: "", length: "", fixed: "", items: "" },
        climate: "",
        shop_country: "",
        shop_postal: "",
        name: "",
        email: "",
        password: "",
    };
}

export function labelFor(list, id) {
    const hit = list.find((o) => o.id === id);
    return hit ? hit.label : "";
}

export function spaceLabel(form) {
    if (form.space_type === "other") return form.other_label.trim() || "Other";
    return labelFor(SPACE_TYPES, form.space_type);
}

// ── Photos ──────────────────────────────────────────────

const ANGLE_TIPS = {
    closet: "Open the doors and shoot from the entrance. Add a second angle if one side is hidden.",
    garage: "Shoot from the main door, then from the opposite corner to show the back wall.",
    pantry: "Open the doors and shoot straight on, then add a closer view of the busiest shelves if needed.",
    laundry_room: "Shoot from the doorway, then from the side that shows the machines and counters.",
};

export function angleTip(spaceType) {
    return ANGLE_TIPS[spaceType] || "Start from a corner or the doorway, then add the opposite side if part of the room is out of frame.";
}

export function photoLabel(index) {
    return `Photo ${index + 1}`;
}

export function blockingIssues(photo) {
    return (photo.issues || []).filter((i) => i.severity === "block");
}

export function needsAcknowledgement(photo) {
    return (photo.issues || []).some((i) => i.severity === "warn") && !photo.acknowledged;
}

export function isAccepted(photo) {
    return Boolean(photo.url) && blockingIssues(photo).length === 0 && !needsAcknowledgement(photo);
}

export function acceptedPhotos(photos) {
    return (photos || []).filter(isAccepted);
}

export function hasUsableWideView(photos) {
    return acceptedPhotos(photos).some((p) => (p.shot || "wide") === "wide");
}

export function isConceptual(form, plan) {
    return plan.price === 0 && form.photo_mode === "conceptual";
}

// A personalized plan needs at least one accepted wide view. Free may instead
// take the clearly labelled conceptual path.
export function hasVisualEvidence(form, photos) {
    return form.photo_mode === "photos" && hasUsableWideView(photos);
}

// ── Conditional logic ───────────────────────────────────

export function wantsLayoutChange(form) {
    return (
        form.priority === "better_layout" &&
        !form.limits.includes("keep_layout") &&
        !form.layout_within_current
    );
}

export function measurementsNeeded(form) {
    const garageFit = form.space_type === "garage" && form.space_answers.vehicle === "yes";
    return wantsLayoutChange(form) || garageFit || Boolean(form.needs_exact_fit);
}

export function measurementReasons(form) {
    const reasons = [];
    if (wantsLayoutChange(form)) reasons.push("you want a better room layout");
    if (form.space_type === "garage" && form.space_answers.vehicle === "yes") {
        reasons.push("a vehicle needs to fit");
    }
    if (form.needs_exact_fit) reasons.push("something new must fit an exact spot");
    return reasons;
}

export function climateMentioned(form) {
    const text = `${form.limit_other} ${form.change_avoid} ${form.specifics}`;
    return CLIMATE_RE.test(text);
}

export function shoppingLocationNeeded(form, plan) {
    return plan.id === "premium" && Boolean(form.budget) && form.budget !== "use_owned";
}

export function roomFlowMode(form, plan) {
    if (isConceptual(form, plan)) return "conceptual";
    if (measurementsNeeded(form) && form.measure_mode === "provided") return "measured";
    return "not_to_scale";
}

export const ROOM_FLOW_COPY = {
    conceptual: "Conceptual zone diagram — not based on your room and not to scale.",
    measured: "Functional map using the measurements you confirmed. Furniture footprints and zones stay approximate.",
    not_to_scale: "Functional map, not to scale. Exact fits need checking before you buy or install.",
};

// ── Contradictions ──────────────────────────────────────
// Each needs one explicit answer before generating; never pick silently.

export function contradictions(form) {
    const out = [];
    const limits = form.limits || [];
    if (limits.includes("none") && limits.some((l) => l !== "none")) {
        out.push({
            id: "limits_none",
            field: "limits",
            message: "You chose “No specific limits” and also selected a limit. Which is right?",
            options: [
                { id: "keep_limits", label: "Keep my selected limits" },
                { id: "no_limits", label: "No specific limits" },
            ],
        });
    }
    if (form.priority === "better_layout" && limits.includes("keep_layout") && !form.layout_within_current) {
        out.push({
            id: "layout",
            field: "limits",
            message: "You asked for a better room layout and also to keep the layout. Which should we follow?",
            options: [
                { id: "layout_ok", label: "Layout changes are OK" },
                { id: "within_layout", label: "Keep the layout and improve within it" },
            ],
        });
    }
    if (limits.includes("no_painting") && PAINT_RE.test(form.change_avoid || "") && !form.paint_confirmed) {
        out.push({
            id: "paint",
            field: "change_avoid",
            message: "You mentioned paint, and you also selected “No painting”. Should the plan include painting?",
            options: [
                { id: "no_paint", label: "No painting" },
                { id: "paint_ok", label: "Painting is OK" },
            ],
        });
    }
    if (form.budget === "use_owned" && form.needs_exact_fit) {
        out.push({
            id: "budget_fit",
            field: "budget",
            message: "You chose “Use what I own” and also need something new to fit an exact spot. Which is right?",
            options: [
                { id: "owned_only", label: "Only use what I own" },
                { id: "open_to_buy", label: "I'm open to buying — let me pick a budget" },
            ],
        });
    }
    return out;
}

export function resolveContradiction(form, contradictionId, optionId) {
    const f = { ...form, limits: [...(form.limits || [])] };
    switch (`${contradictionId}:${optionId}`) {
        case "limits_none:keep_limits":
            f.limits = f.limits.filter((l) => l !== "none");
            break;
        case "limits_none:no_limits":
            f.limits = ["none"];
            f.limit_other = "";
            break;
        case "layout:layout_ok":
            f.limits = f.limits.filter((l) => l !== "keep_layout");
            break;
        case "layout:within_layout":
            f.layout_within_current = true;
            break;
        case "paint:no_paint":
            f.paint_confirmed = true;
            break;
        case "paint:paint_ok":
            f.limits = f.limits.filter((l) => l !== "no_painting");
            break;
        case "budget_fit:owned_only":
            f.needs_exact_fit = false;
            break;
        case "budget_fit:open_to_buy":
            f.budget = "";
            break;
        default:
            break;
    }
    return f;
}

// ── Validation ──────────────────────────────────────────
// Each validator returns { fieldId: message }. Field ids match DOM ids.

export function validateSpace(form) {
    const e = {};
    if (!form.space_type) e.space_type = "Choose the type of space.";
    if (form.space_type === "other") {
        const name = form.other_label.trim();
        if (name.length < 2) {
            e.other_label = "Tell us which space this is.";
        } else if (OUT_OF_SCOPE_RE.test(name)) {
            e.other_label =
                "The beta plans one indoor room or storage area at a time. Choose one room inside your home.";
        }
    }
    if (!form.priority) e.priority = "Choose what would make the biggest difference.";
    if (form.specifics.length > SPECIFICS_MAX) {
        e.specifics = `Keep this to ${SPECIFICS_MAX} characters or fewer.`;
    }
    return e;
}

export function validatePhotos(form, photos, plan, { pending = false } = {}) {
    const e = {};
    if (pending) {
        e.photos = "Confirm the orientation of your last photo before continuing.";
        return e;
    }
    if (photos.length > plan.maxPhotos) {
        e.photos = `The ${plan.name} plan includes up to ${plan.maxPhotos} photos. Remove ${photos.length - plan.maxPhotos} to continue.`;
        return e;
    }
    if (form.photo_mode === "conceptual") {
        if (plan.price > 0) {
            e.photos = "Paid plans need at least one clear, wide photo of your space.";
        } else if (!form.conceptual_ack) {
            e.conceptual_ack = "Confirm that you understand this is a conceptual plan.";
        }
        return e;
    }
    const broken = photos.find((p) => blockingIssues(p).length > 0);
    if (broken) {
        const i = photos.indexOf(broken);
        e.photos = `${photoLabel(i)}: ${blockingIssues(broken)[0].message} Replace or remove it to continue.`;
        return e;
    }
    const unconfirmed = photos.find(needsAcknowledgement);
    if (unconfirmed) {
        const i = photos.indexOf(unconfirmed);
        e.photos = `${photoLabel(i)} may not be clear enough. Replace it or choose “Keep this photo”.`;
        return e;
    }
    if (photos.length === 0) {
        e.photos =
            plan.price > 0
                ? "Add one clear, wide photo to continue. We don't charge for a personalized plan without a usable photo of your space."
                : "Add one clear, wide photo, or choose a conceptual plan below.";
        return e;
    }
    if (!hasUsableWideView(photos)) {
        e.photos = "A close-up helps explain an item, but we also need one wide view of the space. Mark or add a wide view.";
        return e;
    }
    if (!form.coverage) e.coverage = "Tell us whether your photos show the whole area.";
    return e;
}

export function validateNeeds(form, plan) {
    const e = {};
    if (!form.keep) e.keep = "Tell us what needs to stay.";
    if (form.keep === "keep_selected" && form.keep_items.trim().length < 2) {
        e.keep_items = "List the items that need to stay.";
    }
    if (!form.limits.length) e.limits = "Choose any limits, or “No specific limits”.";
    if (form.limits.includes("other") && form.limit_other.trim().length < 2) {
        e.limit_other = "Describe the other limit.";
    }
    if (!form.budget) e.budget = "Choose a budget for changes and purchases, or “Not sure yet”.";

    if (form.visual_mode === "choose_style") {
        if (!form.style) e.style = "Choose a style, or pick another visual preference.";
        if (!form.palette) e.palette = "Choose a palette, or pick another visual preference.";
    }

    const q = spaceQuestion(form.space_type);
    if (q?.kind === "kids" && !form.space_answers.activities.length) {
        e.space_activities = "Choose at least one activity.";
    }
    if (q?.kind === "garage" && !form.space_answers.vehicle) {
        e.space_vehicle = "Tell us whether a vehicle needs to park here.";
    }

    if (measurementsNeeded(form)) {
        if (!form.measure_mode) {
            e.measure_mode = "Add measurements, or choose a functional map that is not to scale.";
        } else if (form.measure_mode === "provided") {
            const m = form.measurements;
            const w = parseFloat(m.width);
            const l = parseFloat(m.length);
            if (!(w > 0)) e.measure_width = "Enter the width as a number greater than 0.";
            if (!(l > 0)) e.measure_length = "Enter the length as a number greater than 0.";
            if (wantsLayoutChange(form) && m.fixed.trim().length < 2) {
                e.measure_fixed = "Note where doors, windows or fixed items are — or write “none”.";
            }
            const fitNeeded =
                form.needs_exact_fit || (form.space_type === "garage" && form.space_answers.vehicle === "yes");
            if (fitNeeded && m.items.trim().length < 2) {
                e.measure_items = "Add the size of the items or spot that must fit.";
            }
        }
    }

    if (shoppingLocationNeeded(form, plan) && !form.shop_country) {
        e.shop_country = "Choose where you'll shop.";
    }

    const conflicts = contradictions(form);
    if (conflicts.length) e.contradictions = "Answer the question above so your plan follows one version.";
    return e;
}

export function validateContact(form, { signedIn }) {
    const e = {};
    if (form.name.trim().length < 2) e.name = "Enter your name.";
    if (!signedIn && !EMAIL_RE.test(form.email.trim())) e.email = "Enter a valid email address.";
    if (!signedIn && (form.password || "").length < 8) e.password = "Use at least 8 characters.";
    return e;
}

export function validateStep(stepIndex, ctx) {
    const { form, photos, plan, pending, signedIn } = ctx;
    if (stepIndex === 0) return validateSpace(form);
    if (stepIndex === 1) return validatePhotos(form, photos, plan, { pending });
    if (stepIndex === 2) return validateNeeds(form, plan);
    return validateContact(form, { signedIn });
}

export function firstInvalidStep(ctx) {
    for (let i = 0; i < 3; i += 1) {
        if (Object.keys(validateStep(i, ctx)).length) return i;
    }
    return -1;
}

// ── Summary & payload ───────────────────────────────────

export function coverageLimitations(form, photos, plan) {
    const notes = [];
    if (isConceptual(form, plan)) {
        notes.push("Conceptual plan: it is not based on photos of your room, and the images are ideas, not your space.");
        return notes;
    }
    const accepted = acceptedPhotos(photos);
    if (form.coverage === "partial") {
        notes.push("Your plan covers only the areas shown in your photos.");
    }
    if (accepted.length === 1 && form.coverage !== "partial") {
        notes.push("One photo: areas outside it can't be shown in the after-view.");
    }
    if (accepted.some((p) => p.shot === "detail")) {
        notes.push("Close-ups explain specific items; they don't add room coverage.");
    }
    notes.push(`You'll get one after-view for each accepted photo (${accepted.length}).`);
    if (roomFlowMode(form, plan) !== "measured") {
        notes.push("Exact fits and clearances need checking before you buy or install.");
    }
    if (form.budget === "not_sure") {
        notes.push("Budget not set yet: we'll focus on reorganizing what you have and mark purchases as optional.");
    }
    return notes;
}

export function limitsText(form) {
    return form.limits
        .map((l) => (l === "other" ? `Other: ${form.limit_other.trim()}` : labelFor(LIMIT_OPTIONS, l)))
        .join(", ");
}

export function buildIntake(form, photos, plan) {
    const accepted = acceptedPhotos(photos);
    const q = spaceQuestion(form.space_type);
    const space_answers = {};
    if (q?.kind === "kids") {
        space_answers.activities = form.space_answers.activities;
        if (form.space_answers.stage) space_answers.stage = form.space_answers.stage;
    } else if (q?.kind === "garage") {
        space_answers.vehicle = form.space_answers.vehicle;
        if (form.space_answers.large_items.trim()) space_answers.large_items = form.space_answers.large_items.trim();
    } else if (q?.kind === "text" && form.space_answers.text.trim()) {
        space_answers.text = form.space_answers.text.trim();
    }
    const needM = measurementsNeeded(form);
    return {
        version: INTAKE_VERSION,
        plan: plan.id,
        space_type: form.space_type,
        other_label: form.space_type === "other" ? form.other_label.trim() : "",
        priority: form.priority,
        specifics: form.specifics.trim(),
        photo_mode: isConceptual(form, plan) ? "conceptual" : "photos",
        coverage: isConceptual(form, plan) ? "" : form.coverage,
        photos: accepted.map((p, i) => ({
            ref: `P${i + 1}`,
            label: photoLabel(i),
            custom_label: (p.label || "").trim(),
            shot: p.shot || "wide",
            url: p.url,
            photo_id: p.id,
        })),
        keep: form.keep,
        keep_items: form.keep === "keep_selected" ? form.keep_items.trim() : "",
        limits: form.limits,
        limit_other: form.limits.includes("other") ? form.limit_other.trim() : "",
        layout_within_current: Boolean(form.layout_within_current),
        change_avoid: form.change_avoid.trim(),
        budget: form.budget,
        visual: {
            mode: form.visual_mode || "match_current",
            style: form.visual_mode === "choose_style" ? form.style : "",
            palette: form.visual_mode === "choose_style" ? form.palette : "",
        },
        space_answers,
        needs_exact_fit: Boolean(form.needs_exact_fit),
        measurements_needed: needM,
        measure_mode: needM ? form.measure_mode : "",
        measurements:
            needM && form.measure_mode === "provided"
                ? {
                      unit: form.measurements.unit,
                      width: parseFloat(form.measurements.width),
                      length: parseFloat(form.measurements.length),
                      fixed: form.measurements.fixed.trim(),
                      items: form.measurements.items.trim(),
                  }
                : null,
        climate: climateMentioned(form) ? form.climate : "",
        shop_country: shoppingLocationNeeded(form, plan) ? form.shop_country : "",
        shop_postal: shoppingLocationNeeded(form, plan) ? form.shop_postal.trim() : "",
        room_flow_mode: roomFlowMode(form, plan),
    };
}

// Maps onto the existing Lead schema so the current pipeline keeps working;
// `intake` carries the structured answers the fact sheet is built from.
export function buildLeadPayload(form, photos, plan, member) {
    const intake = buildIntake(form, photos, plan);
    const priority = labelFor(PRIORITIES, form.priority);
    const challenge = [priority, form.specifics.trim()].filter(Boolean).join(" — ");
    const keepLabel = labelFor(KEEP_OPTIONS, form.keep);
    const mustStay = form.keep === "keep_selected" ? `${keepLabel}: ${form.keep_items.trim()}` : keepLabel;
    const choose = form.visual_mode === "choose_style";
    return {
        name: form.name.trim(),
        email: (member?.email || form.email).trim(),
        space_type: form.space_type,
        package_id: plan.id,
        biggest_challenge: challenge,
        goals: form.specifics.trim() || null,
        photos: intake.photos.map((p) => p.url),
        must_stay: mustStay || null,
        style_prefs: choose && form.style ? [form.style] : [],
        color_prefs: choose && form.palette ? [form.palette] : [],
        budget: form.budget || null,
        daily_improvement: form.change_avoid.trim() || null,
        language: "en",
        intake,
    };
}

// ── Draft persistence ───────────────────────────────────

export const DRAFT_KEY = "fs_intake_draft_v1";

export function serializeDraft({ form, photos, step }) {
    const { password, ...safeForm } = form;
    return JSON.stringify({
        version: INTAKE_VERSION,
        savedAt: new Date().toISOString(),
        step,
        form: safeForm,
        photos: photos
            .filter((p) => p.url)
            .map(({ id, url, label, shot, metrics, acknowledged }) => ({
                id,
                url,
                label,
                shot,
                metrics,
                acknowledged,
            })),
    });
}

export function parseDraft(raw) {
    if (!raw) return null;
    try {
        const data = JSON.parse(raw);
        if (!data || data.version !== INTAKE_VERSION) return null;
        const base = emptyForm();
        const form = {
            ...base,
            ...data.form,
            space_answers: { ...base.space_answers, ...(data.form?.space_answers || {}) },
            measurements: { ...base.measurements, ...(data.form?.measurements || {}) },
        };
        const step = Math.min(Math.max(Number(data.step) || 0, 0), STEPS.length - 1);
        return { form, photos: Array.isArray(data.photos) ? data.photos : [], step, savedAt: data.savedAt };
    } catch {
        return null;
    }
}

export function priceLabel(plan) {
    return plan.price === 0 ? "Free" : `$${plan.price}`;
}

export function submitLabel(plan) {
    return plan.price === 0 ? "Create my free Design Plan" : `Continue to payment — $${plan.price}`;
}

export function planLine(plan) {
    return plan.price === 0
        ? "Your plan: Free — $0. One free Design Plan per account."
        : `Your plan: ${plan.name} — $${plan.price}, one-time payment.`;
}
