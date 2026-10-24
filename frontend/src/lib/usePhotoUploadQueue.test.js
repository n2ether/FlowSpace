import { act, renderHook } from "@testing-library/react";
import { bakeRotation, inspectPhotoFile } from "./photoOrientation";
import { usePhotoUploadQueue } from "./usePhotoUploadQueue";

jest.mock("./photoOrientation", () => ({ inspectPhotoFile: jest.fn(), bakeRotation: jest.fn() }));

beforeEach(() => {
    inspectPhotoFile.mockImplementation(async (file) => ({ file, needsNudge: true, reason: "landscape", previewUrl: "blob:preview" }));
    bakeRotation.mockImplementation(async (file) => file);
    global.URL.revokeObjectURL = jest.fn();
});

function deferred() {
    let resolve;
    const promise = new Promise((r) => {
        resolve = r;
    });
    return { promise, resolve };
}

test("a double tap on Ceiling is up uploads the photo once", async () => {
    const upload = deferred();
    const uploadFile = jest.fn(() => upload.promise);
    const { result } = renderHook(() => usePhotoUploadQueue({ uploadFile, remainingSlots: 3 }));
    const file = new File(["x"], "closet.jpg", { type: "image/jpeg" });

    await act(async () => {
        await result.current.handleFiles([file]);
    });
    expect(result.current.pending).not.toBeNull();

    let first;
    let second;
    await act(async () => {
        first = result.current.confirmPending();
        second = result.current.confirmPending();
        upload.resolve();
        await Promise.all([first, second]);
    });

    expect(uploadFile).toHaveBeenCalledTimes(1);
    expect(result.current.pending).toBeNull();
    expect(result.current.uploading).toBe(false);
});
