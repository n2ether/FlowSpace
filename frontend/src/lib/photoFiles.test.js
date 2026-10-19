import { PHOTO_ACCEPT, isHeifFile, isSupportedPhotoFile } from "./photoFiles";

const file = (name, type) => ({ name, type });

describe("photo file acceptance", () => {
    test("the file input accepts HEIC and HEIF", () => {
        const accepted = PHOTO_ACCEPT.split(",");
        expect(accepted).toEqual(expect.arrayContaining(["image/*", "image/heic", "image/heif", ".heic", ".heif"]));
    });

    test("HEIC is recognized by MIME type or extension", () => {
        expect(isHeifFile(file("IMG_0001.HEIC", ""))).toBe(true);
        expect(isHeifFile(file("photo", "image/heic"))).toBe(true);
        expect(isHeifFile(file("photo", "image/heif"))).toBe(true);
        expect(isHeifFile(file("photo.jpg", "image/jpeg"))).toBe(false);
    });

    test("validation keeps images and HEIC with an empty type, and rejects other files", () => {
        expect(isSupportedPhotoFile(file("a.jpg", "image/jpeg"))).toBe(true);
        expect(isSupportedPhotoFile(file("IMG_0002.heic", ""))).toBe(true);
        expect(isSupportedPhotoFile(file("IMG_0003.heif", "application/octet-stream"))).toBe(true);
        expect(isSupportedPhotoFile(file("notes.pdf", "application/pdf"))).toBe(false);
        expect(isSupportedPhotoFile(null)).toBe(false);
    });
});
