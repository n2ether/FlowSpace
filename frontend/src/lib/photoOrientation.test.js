import { inspectNeedsNudge, readJpegExifOrientation } from "./photoOrientation";

function jpegWithOrientation(orientation = 6) {
    // Minimal APP1/Exif TIFF so the parser can find tag 0x0112.
    const parts = [];
    const push16 = (n) => parts.push((n >> 8) & 0xff, n & 0xff);
    // SOI
    parts.push(0xff, 0xd8);
    // APP1
    parts.push(0xff, 0xe1);
    const app1Start = parts.length;
    push16(0); // placeholder length
    parts.push(0x45, 0x78, 0x69, 0x66, 0x00, 0x00); // Exif\0\0
    const tiff = parts.length;
    parts.push(0x4d, 0x4d); // big endian
    push16(42);
    parts.push(0x00, 0x00, 0x00, 0x08); // IFD0 at +8
    push16(1); // one entry
    push16(0x0112); // Orientation
    push16(3); // SHORT
    parts.push(0x00, 0x00, 0x00, 0x01); // count
    push16(orientation);
    push16(0); // padding for the 4-byte value slot
    push16(0); // next IFD = 0
    const app1Len = parts.length - app1Start;
    parts[app1Start] = (app1Len >> 8) & 0xff;
    parts[app1Start + 1] = app1Len & 0xff;
    // SOS so the walker stops
    parts.push(0xff, 0xda, 0x00, 0x02);
    return new Uint8Array(parts).buffer;
}

describe("inspectNeedsNudge", () => {
    test("landscape photos need a ceiling-up confirm", () => {
        const r = inspectNeedsNudge({ width: 4032, height: 3024, exifOrientation: 1 });
        expect(r.needsNudge).toBe(true);
        expect(r.reason).toBe("landscape");
    });

    test("portrait with orientation 1 is left alone", () => {
        const r = inspectNeedsNudge({ width: 3024, height: 4032, exifOrientation: 1 });
        expect(r.needsNudge).toBe(false);
        expect(r.reason).toBe(null);
    });

    test("rotated EXIF is treated as ambiguous even if pixels are portrait", () => {
        const r = inspectNeedsNudge({ width: 3024, height: 4032, exifOrientation: 6 });
        expect(r.needsNudge).toBe(true);
        expect(r.reason).toBe("exif");
    });

    test("near-square is ambiguous", () => {
        const r = inspectNeedsNudge({ width: 1000, height: 1020, exifOrientation: 1 });
        expect(r.needsNudge).toBe(true);
        expect(r.reason).toBe("ambiguous");
    });
});

describe("readJpegExifOrientation", () => {
    test("reads Orientation=6 from a constructed JPEG header", () => {
        expect(readJpegExifOrientation(jpegWithOrientation(6))).toBe(6);
    });

    test("non-jpeg returns 1", () => {
        expect(readJpegExifOrientation(new Uint8Array([0, 1, 2, 3]).buffer)).toBe(1);
    });
});
