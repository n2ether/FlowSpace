// Which files the photo inputs accept. iPhones save HEIC; several browsers report
// an empty MIME type for it, so the extension counts too. The backend converts
// HEIC/HEIF to JPEG on upload.

export const PHOTO_ACCEPT = "image/*,image/heic,image/heif,.heic,.heif";

const HEIF_TYPES = new Set(["image/heic", "image/heif", "image/heic-sequence", "image/heif-sequence"]);
const HEIF_EXT = /\.(heic|heif)$/i;

export const UNSUPPORTED_PHOTO_MESSAGE = "Use a JPEG, PNG, WebP or HEIC photo.";

export function isHeifFile(file) {
    if (!file) return false;
    const type = String(file.type || "").toLowerCase();
    return HEIF_TYPES.has(type) || HEIF_EXT.test(String(file.name || ""));
}

export function isSupportedPhotoFile(file) {
    if (!file) return false;
    const type = String(file.type || "").toLowerCase();
    return type.startsWith("image/") || isHeifFile(file);
}
