// Customer-facing project status shared by My spaces and the project page.
// Raw lead statuses (and legacy "error") never reach the customer.

// Matches backend members.GENERATION_ESTIMATE_MINUTES. Preview runs measured
// about 3.5 to 7.5 minutes, so the estimate is the ceiling, not the average.
export const ESTIMATE_MINUTES = 10;
const PROGRESS_SEEN_PREFIX = "fs_progress_seen_";
export const CHECKOUT_LEAD_KEY = "fs_checkout_lead";

const SPACE_LABELS = {
    closet: "Closet",
    garage: "Garage",
    laundry_room: "Laundry room",
    pantry: "Pantry",
    mudroom: "Mudroom",
    storage: "Storage area",
    kids_room: "Kids' room",
    nursery: "Nursery",
    home_office: "Home office",
    living_room: "Living room",
    bedroom: "Bedroom",
    other: "Other space",
};

const IN_PROGRESS = { key: "in_progress", label: "In progress", note: "We're preparing your Design Plan." };
const IN_REVIEW = { key: "in_review", label: "In review", note: "Our beta team reviews every plan before it's sent." };
const DELIVERED = { key: "delivered", label: "Delivered", note: "Design Plan emailed to you." };
const AWAITING_PAYMENT = {
    key: "awaiting_payment",
    label: "Awaiting payment",
    note: "Finish checkout to start your Design Plan.",
};
const PAYMENT_NOT_COMPLETED = {
    key: "payment_not_completed",
    label: "Payment not completed",
    note: "Your payment didn't go through. Start checkout again to continue.",
};
const CHECKOUT_EXPIRED = {
    key: "checkout_expired",
    label: "Checkout expired",
    note: "Your checkout timed out before payment. Start checkout again to continue.",
};

export const DELIVERED_NOTE = DELIVERED.note;
export const DELAYED_NOTE =
    "This is taking a little longer than usual. Your Design Plan is still being prepared, " +
    "and we'll email you when it's ready. There's no need to keep this page open.";

const CUSTOMER_STATUS = {
    new: IN_PROGRESS,
    paid: IN_PROGRESS,
    processing: IN_PROGRESS,
    in_progress: IN_PROGRESS,
    review: IN_REVIEW,
    incomplete: IN_REVIEW,
    pdf_ready: IN_REVIEW,
    error: IN_REVIEW,
    in_review: IN_REVIEW,
    delivered: DELIVERED,
    awaiting_payment: AWAITING_PAYMENT,
    payment_not_completed: PAYMENT_NOT_COMPLETED,
    checkout_expired: CHECKOUT_EXPIRED,
};

export const STATUS_STYLES = {
    in_progress: "bg-sky-50 text-sky-800",
    delayed: "bg-amber-50 text-amber-800",
    in_review: "bg-emerald-50 text-emerald-800",
    delivered: "bg-emerald-500 text-white",
    awaiting_payment: "bg-amber-50 text-amber-800",
    payment_not_completed: "bg-red-50 text-red-800",
    checkout_expired: "bg-amber-50 text-amber-800",
};

export const PAYMENT_KEYS = new Set(["awaiting_payment", "payment_not_completed", "checkout_expired"]);

export function spaceTitle(space) {
    const title = (space.title || "").trim();
    if (title) return title;
    if (space.space_type === "other") return SPACE_LABELS.other;
    return SPACE_LABELS[space.space_type] || "Your space";
}

export function customerStatus(space) {
    const known = CUSTOMER_STATUS[(space.status || "new").toLowerCase()] || IN_REVIEW;
    // The backend owns the label (it knows the payment state); the table is a fallback.
    if (space.status_label) {
        return { key: known.key, label: space.status_label, note: space.status_note || known.note };
    }
    return known;
}

export function photoSrc(url) {
    if (!url) return null;
    if (url.startsWith("http")) return url;
    return `${process.env.REACT_APP_BACKEND_URL || ""}${url}`;
}

// The generated views are part of the package, so they only show once it is delivered.
export function spaceThumbnail(space, status = customerStatus(space)) {
    const own = typeof space.photos?.[0] === "string" ? space.photos[0] : space.photos?.[0]?.url;
    if (status.key === "delivered") return photoSrc(space.deliverable?.front_view_url) || photoSrc(own);
    return photoSrc(own);
}

export function recordProgressStart(leadId, at = Date.now()) {
    if (!leadId) return;
    try {
        const key = PROGRESS_SEEN_PREFIX + leadId;
        if (!localStorage.getItem(key)) localStorage.setItem(key, String(at));
    } catch {
        /* private mode */
    }
}

export function progressSeenAt(leadId) {
    try {
        const value = Number(localStorage.getItem(PROGRESS_SEEN_PREFIX + leadId));
        return Number.isFinite(value) && value > 0 ? value : null;
    } catch {
        return null;
    }
}

// When the customer's wait started: the backend's claim time, else the first
// time this browser saw the project in progress (older backends send neither).
export function progressStartedAt(space) {
    const fromServer = Date.parse(space.processing_started_at || "");
    if (Number.isFinite(fromServer)) return fromServer;
    return progressSeenAt(space.id);
}

// Milliseconds to add to this device's clock to match the backend's.
export function serverClockOffset(serverTime, deviceNow = Date.now()) {
    const parsed = Date.parse(serverTime || "");
    return Number.isFinite(parsed) ? parsed - deviceNow : 0;
}

export function estimateMinutes(space) {
    const value = Number(space.estimate_minutes);
    return Number.isFinite(value) && value > 0 ? value : ESTIMATE_MINUTES;
}

export function isDelayed(space, now = Date.now()) {
    if (customerStatus(space).key !== "in_progress") return false;
    if (space.delayed === true) return true;
    const started = progressStartedAt(space);
    if (!started) return false;
    return now - started > estimateMinutes(space) * 60 * 1000;
}

// Status shown on a card or the project page, including the delay state.
export function displayStatus(space, now = Date.now()) {
    const status = customerStatus(space);
    if (isDelayed(space, now)) {
        return { ...status, key: "in_progress", delayed: true, label: "Taking a little longer", note: DELAYED_NOTE };
    }
    return { ...status, delayed: false };
}
