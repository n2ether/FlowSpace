/**
 * Client-side orientation helpers for the upload path.
 *
 * Browsers apply EXIF when showing <img> / createImageBitmap; GridFS + FLUX
 * historically did not. We detect landscape / ambiguous / rotated-EXIF photos
 * and bake a gravity-correct JPEG before upload.
 */

export function readJpegExifOrientation(buffer) {
    const view = new DataView(buffer);
    if (view.byteLength < 4 || view.getUint16(0) !== 0xffd8) return 1;
    let offset = 2;
    while (offset + 4 <= view.byteLength) {
        const marker = view.getUint16(offset);
        offset += 2;
        if (marker === 0xffda) break;
        if (offset + 2 > view.byteLength) break;
        const size = view.getUint16(offset);
        if (size < 2) break;
        if (marker === 0xffe1 && size >= 8) {
            const body = offset + 2;
            if (body + 6 <= view.byteLength) {
                const header = String.fromCharCode(
                    view.getUint8(body),
                    view.getUint8(body + 1),
                    view.getUint8(body + 2),
                    view.getUint8(body + 3),
                );
                if (header === "Exif") {
                    const tiff = body + 6;
                    return _readTiffOrientation(view, tiff) || 1;
                }
            }
        }
        offset += size;
    }
    return 1;
}

function _readTiffOrientation(view, tiff) {
    if (tiff + 8 > view.byteLength) return 1;
    const endian = view.getUint16(tiff);
    const little = endian === 0x4949;
    const get16 = (o) => (little ? view.getUint16(o, true) : view.getUint16(o, false));
    const get32 = (o) => (little ? view.getUint32(o, true) : view.getUint32(o, false));
    if (get16(tiff + 2) !== 42) return 1;
    let dir = tiff + get32(tiff + 4);
    if (dir + 2 > view.byteLength) return 1;
    const count = get16(dir);
    dir += 2;
    for (let i = 0; i < count; i += 1) {
        const entry = dir + i * 12;
        if (entry + 12 > view.byteLength) break;
        if (get16(entry) === 0x0112) {
            return get16(entry + 8) || 1;
        }
    }
    return 1;
}

export function inspectNeedsNudge({ width, height, exifOrientation = 1 }) {
    const w = Number(width) || 0;
    const h = Number(height) || 0;
    const landscape = w > h;
    const nearSquare = Math.abs(w - h) / Math.max(w, h, 1) < 0.08;
    const rotatedExif = Number(exifOrientation) > 1;
    let reason = null;
    if (rotatedExif) reason = "exif";
    else if (landscape) reason = "landscape";
    else if (nearSquare) reason = "ambiguous";
    return {
        landscape,
        nearSquare,
        rotatedExif,
        needsNudge: Boolean(reason),
        reason,
    };
}

export async function inspectPhotoFile(file) {
    const buffer = await file.arrayBuffer();
    const exifOrientation = readJpegExifOrientation(buffer);
    let width = 0;
    let height = 0;
    if (typeof createImageBitmap === "function") {
        const bitmap = await createImageBitmap(file);
        width = bitmap.width;
        height = bitmap.height;
        if (typeof bitmap.close === "function") bitmap.close();
    } else {
        const decoded = await _loadHtmlImage(file);
        width = decoded.width;
        height = decoded.height;
    }
    const inspect = inspectNeedsNudge({ width, height, exifOrientation });
    return {
        file,
        exifOrientation,
        width,
        height,
        previewUrl: URL.createObjectURL(file),
        ...inspect,
    };
}

function _loadHtmlImage(file) {
    return new Promise((resolve, reject) => {
        const url = URL.createObjectURL(file);
        const img = new Image();
        img.onload = () => {
            URL.revokeObjectURL(url);
            resolve(img);
        };
        img.onerror = () => {
            URL.revokeObjectURL(url);
            reject(new Error("Could not read photo"));
        };
        img.src = url;
    });
}

/** Bake EXIF (via createImageBitmap) plus extra clockwise quarter-turns into a JPEG File. */
export async function bakeRotation(file, extraQuarterTurns = 0) {
    const bitmap = await createImageBitmap(file);
    const turns = ((Number(extraQuarterTurns) % 4) + 4) % 4;
    let width = bitmap.width;
    let height = bitmap.height;
    if (turns % 2 === 1) {
        const swap = width;
        width = height;
        height = swap;
    }
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    ctx.translate(width / 2, height / 2);
    ctx.rotate((turns * 90 * Math.PI) / 180);
    ctx.drawImage(bitmap, -bitmap.width / 2, -bitmap.height / 2);
    if (typeof bitmap.close === "function") bitmap.close();
    const blob = await new Promise((resolve, reject) => {
        canvas.toBlob(
            (b) => (b ? resolve(b) : reject(new Error("Could not encode photo"))),
            "image/jpeg",
            0.92,
        );
    });
    const name = String(file.name || "photo.jpg").replace(/\.\w+$/, ".jpg");
    return new File([blob], name, { type: "image/jpeg" });
}
