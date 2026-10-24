import {
    DELAYED_NOTE,
    ESTIMATE_MINUTES,
    displayStatus,
    isDelayed,
    recordProgressStart,
    serverClockOffset,
    spaceThumbnail,
} from "./projectStatus";

const NOW = Date.parse("2026-10-14T12:00:00Z");
const minutesAgo = (m) => new Date(NOW - m * 60 * 1000).toISOString();

beforeEach(() => localStorage.clear());

describe("delay notice", () => {
    it("stays In progress within the estimate", () => {
        const space = { id: "a", status: "in_progress", processing_started_at: minutesAgo(ESTIMATE_MINUTES - 1) };
        expect(isDelayed(space, NOW)).toBe(false);
        expect(displayStatus(space, NOW).label).toBe("In progress");
    });

    it("says it is taking longer once past the estimate, and promises an email", () => {
        const space = { id: "a", status: "in_progress", processing_started_at: minutesAgo(ESTIMATE_MINUTES + 1) };
        const status = displayStatus(space, NOW);
        expect(status.delayed).toBe(true);
        expect(status.label).toBe("Taking a little longer");
        expect(status.note).toBe(DELAYED_NOTE);
        expect(status.note).toMatch(/email you when it's ready/);
    });

    it("trusts the backend's delayed flag", () => {
        expect(isDelayed({ id: "a", status: "in_progress", delayed: true }, NOW)).toBe(true);
    });

    it("falls back to when this browser first saw the project", () => {
        recordProgressStart("b", NOW - (ESTIMATE_MINUTES + 2) * 60 * 1000);
        recordProgressStart("b", NOW);
        expect(isDelayed({ id: "b", status: "in_progress" }, NOW)).toBe(true);
        expect(isDelayed({ id: "c", status: "in_progress" }, NOW)).toBe(false);
    });

    it.each(["in_review", "delivered", "awaiting_payment"])("never marks %s as delayed", (status) => {
        expect(isDelayed({ id: "a", status, processing_started_at: minutesAgo(600) }, NOW)).toBe(false);
    });

    it("corrects for a device clock that differs from the server", () => {
        expect(serverClockOffset("2026-10-14T12:05:00Z", NOW)).toBe(5 * 60 * 1000);
        expect(serverClockOffset(undefined, NOW)).toBe(0);
    });
});

describe("thumbnails", () => {
    const space = {
        status: "in_review",
        photos: [{ url: "https://cdn.example/own.jpg" }],
        deliverable: { front_view_url: "https://cdn.example/generated.jpg" },
    };

    it("shows the customer's own photo until the package is delivered", () => {
        expect(spaceThumbnail(space)).toBe("https://cdn.example/own.jpg");
        expect(spaceThumbnail({ ...space, status: "delivered" })).toBe("https://cdn.example/generated.jpg");
    });
});
