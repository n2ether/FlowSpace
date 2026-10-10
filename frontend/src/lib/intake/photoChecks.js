// Client-side photo checks: size, light, sharpness and near-duplicates.
// Heuristics only — they flag photos for the customer to replace or confirm;
// the backend and beta review still make the final call.

export const MIN_SHORT_SIDE = 480;
export const DARK_BRIGHTNESS = 40;
export const BLUR_SHARPNESS = 40;
export const DUPLICATE_DISTANCE = 5;
const SAMPLE_MAX = 256;

export function grayFromRGBA(rgba) {
    const n = rgba.length / 4;
    const gray = new Uint8ClampedArray(n);
    for (let i = 0; i < n; i += 1) {
        const o = i * 4;
        gray[i] = 0.299 * rgba[o] + 0.587 * rgba[o + 1] + 0.114 * rgba[o + 2];
    }
    return gray;
}

export function meanBrightness(gray) {
    if (!gray.length) return 0;
    let sum = 0;
    for (let i = 0; i < gray.length; i += 1) sum += gray[i];
    return sum / gray.length;
}

// Variance of the 4-neighbour Laplacian; low values mean few edges (blur).
export function laplacianVariance(gray, width, height) {
    if (width < 3 || height < 3) return 0;
    let sum = 0;
    let sumSq = 0;
    let n = 0;
    for (let y = 1; y < height - 1; y += 1) {
        for (let x = 1; x < width - 1; x += 1) {
            const i = y * width + x;
            const v = 4 * gray[i] - gray[i - 1] - gray[i + 1] - gray[i - width] - gray[i + width];
            sum += v;
            sumSq += v * v;
            n += 1;
        }
    }
    const mean = sum / n;
    return sumSq / n - mean * mean;
}

// Difference hash from a 9x8 grayscale sample → 16 hex chars.
export function dHash(gray9x8) {
    let bits = "";
    for (let y = 0; y < 8; y += 1) {
        for (let x = 0; x < 8; x += 1) {
            bits += gray9x8[y * 9 + x] > gray9x8[y * 9 + x + 1] ? "1" : "0";
        }
    }
    let hex = "";
    for (let i = 0; i < 64; i += 4) hex += parseInt(bits.slice(i, i + 4), 2).toString(16);
    return hex;
}

export function hammingHex(a, b) {
    if (!a || !b || a.length !== b.length) return Infinity;
    let d = 0;
    for (let i = 0; i < a.length; i += 1) {
        let x = parseInt(a[i], 16) ^ parseInt(b[i], 16);
        while (x) {
            d += x & 1;
            x >>= 1;
        }
    }
    return d;
}

// metrics: { width, height, brightness, sharpness, hash } or null when the
// browser could not decode the file (e.g. HEIC) — the server still checks it.
// others: [{ hash, index }] for photos already in the project.
export function assessPhoto(metrics, others = []) {
    const issues = [];
    if (!metrics) return issues;
    const shortSide = Math.min(metrics.width || 0, metrics.height || 0);
    if (shortSide && shortSide < MIN_SHORT_SIDE) {
        issues.push({
            code: "too_small",
            severity: "block",
            message: `This image is too small to show the space (at least ${MIN_SHORT_SIDE} px on the short side).`,
        });
    }
    const dup = others.find((o) => hammingHex(o.hash, metrics.hash) <= DUPLICATE_DISTANCE);
    if (dup) {
        issues.push({
            code: "duplicate",
            severity: "block",
            duplicateOf: dup.index,
            message: `This looks like the same view as Photo ${dup.index + 1}. Similar photos don't add coverage — use another angle.`,
        });
    }
    if (typeof metrics.brightness === "number" && metrics.brightness < DARK_BRIGHTNESS) {
        issues.push({ code: "dark", severity: "warn", message: "This photo looks very dark." });
    }
    if (typeof metrics.sharpness === "number" && metrics.sharpness < BLUR_SHARPNESS) {
        issues.push({ code: "blurry", severity: "warn", message: "This photo may be blurry." });
    }
    return issues;
}

// Issues are derived, never stored: removing Photo 1 clears a duplicate flag
// on Photo 2 without extra bookkeeping. Earlier photos win a duplicate pair.
export function withIssues(photos) {
    return (photos || []).map((photo, index) => {
        const others = photos
            .slice(0, index)
            .map((p, i) => ({ hash: p.metrics?.hash, index: i }))
            .filter((o) => o.hash);
        return { ...photo, issues: assessPhoto(photo.metrics, others) };
    });
}

function loadImage(file) {
    return new Promise((resolve, reject) => {
        const url = URL.createObjectURL(file);
        const img = new Image();
        img.onload = () => resolve({ img, url });
        img.onerror = () => {
            URL.revokeObjectURL(url);
            reject(new Error("decode failed"));
        };
        img.src = url;
    });
}

export async function measurePhoto(file) {
    try {
        const { img, url } = await loadImage(file);
        const width = img.naturalWidth;
        const height = img.naturalHeight;
        const scale = Math.min(1, SAMPLE_MAX / Math.max(width, height));
        const sw = Math.max(3, Math.round(width * scale));
        const sh = Math.max(3, Math.round(height * scale));
        const canvas = document.createElement("canvas");
        canvas.width = sw;
        canvas.height = sh;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0, sw, sh);
        const gray = grayFromRGBA(ctx.getImageData(0, 0, sw, sh).data);
        const tiny = document.createElement("canvas");
        tiny.width = 9;
        tiny.height = 8;
        const tctx = tiny.getContext("2d");
        tctx.drawImage(img, 0, 0, 9, 8);
        const hash = dHash(grayFromRGBA(tctx.getImageData(0, 0, 9, 8).data));
        URL.revokeObjectURL(url);
        return {
            width,
            height,
            brightness: meanBrightness(gray),
            sharpness: laplacianVariance(gray, sw, sh),
            hash,
        };
    } catch {
        return null;
    }
}
