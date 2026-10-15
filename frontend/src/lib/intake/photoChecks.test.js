import {
    BLUR_SHARPNESS,
    assessPhoto,
    dHash,
    hammingHex,
    laplacianVariance,
    meanBrightness,
    withIssues,
} from "./photoChecks";

function gradient9x8(reverse = false) {
    const g = [];
    for (let y = 0; y < 8; y += 1) {
        for (let x = 0; x < 9; x += 1) g.push(reverse ? 255 - x * 20 - y : x * 20 + y);
    }
    return g;
}

const good = { width: 1600, height: 1200, brightness: 120, sharpness: 300 };

describe("photo metrics", () => {
    it("computes brightness and sharpness", () => {
        expect(meanBrightness(Uint8ClampedArray.from([0, 255]))).toBe(127.5);
        const flat = new Uint8ClampedArray(100).fill(128);
        expect(laplacianVariance(flat, 10, 10)).toBe(0);
        const checker = Uint8ClampedArray.from({ length: 100 }, (_, i) => ((i % 10) + Math.floor(i / 10)) % 2 ? 255 : 0);
        expect(laplacianVariance(checker, 10, 10)).toBeGreaterThan(BLUR_SHARPNESS);
    });

    it("hashes similar images close together and different images far apart", () => {
        const a = dHash(gradient9x8());
        const b = dHash(gradient9x8(true));
        expect(a).toHaveLength(16);
        expect(hammingHex(a, a)).toBe(0);
        expect(hammingHex(a, b)).toBeGreaterThan(20);
        expect(hammingHex(a, undefined)).toBe(Infinity);
    });
});

describe("assessPhoto", () => {
    it("accepts a clear photo", () => {
        expect(assessPhoto({ ...good, hash: "0f0f0f0f0f0f0f0f" })).toEqual([]);
    });

    it("blocks tiny images and near-duplicates", () => {
        expect(assessPhoto({ ...good, width: 300, height: 200 }).map((i) => i.code)).toEqual(["too_small"]);
        const issues = assessPhoto({ ...good, hash: "0f0f0f0f0f0f0f0e" }, [{ hash: "0f0f0f0f0f0f0f0f", index: 0 }]);
        expect(issues[0]).toMatchObject({ code: "duplicate", severity: "block", duplicateOf: 0 });
        expect(issues[0].message).toMatch(/Photo 1/);
    });

    it("warns on dark or blurry photos", () => {
        const codes = assessPhoto({ ...good, brightness: 10, sharpness: 5 }).map((i) => `${i.code}:${i.severity}`);
        expect(codes).toEqual(["dark:warn", "blurry:warn"]);
    });

    it("skips checks the browser could not run", () => {
        expect(assessPhoto(null)).toEqual([]);
    });

    it("derives duplicate flags from current order so removal clears them", () => {
        const p1 = { url: "a", metrics: { ...good, hash: "ffff0000ffff0000" } };
        const p2 = { url: "b", metrics: { ...good, hash: "ffff0000ffff0000" } };
        const both = withIssues([p1, p2]);
        expect(both[0].issues).toEqual([]);
        expect(both[1].issues[0].code).toBe("duplicate");
        expect(withIssues([p2])[0].issues).toEqual([]);
    });
});
