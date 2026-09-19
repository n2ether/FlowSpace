import { useCallback, useState } from "react";
import { bakeRotation, inspectPhotoFile } from "./photoOrientation";

export function usePhotoUploadQueue({ uploadFile, remainingSlots }) {
    const [uploading, setUploading] = useState(false);
    const [pending, setPending] = useState(null);
    const [queue, setQueue] = useState([]);

    const uploadBaked = useCallback(
        async (file, quarterTurns) => {
            const baked = await bakeRotation(file, quarterTurns);
            return uploadFile(baked);
        },
        [uploadFile],
    );

    const processQueue = useCallback(
        async (files) => {
            if (!files.length) {
                setPending(null);
                setQueue([]);
                setUploading(false);
                return;
            }
            const [file, ...rest] = files;
            try {
                const inspection = await inspectPhotoFile(file);
                if (!inspection.needsNudge) {
                    await uploadBaked(file, 0);
                    URL.revokeObjectURL(inspection.previewUrl);
                    await processQueue(rest);
                    return;
                }
                setPending({ inspection, quarterTurns: 0, previewUrl: inspection.previewUrl });
                setQueue(rest);
                setUploading(false);
            } catch (err) {
                // If we cannot inspect (HEIC, etc.), upload raw — backend still EXIF-corrects.
                await uploadFile(file);
                await processQueue(rest);
            }
        },
        [uploadBaked, uploadFile],
    );

    const handleFiles = useCallback(
        async (fileList) => {
            const max = typeof remainingSlots === "number" ? remainingSlots : 99;
            const files = Array.from(fileList || []).slice(0, Math.max(0, max));
            if (!files.length) return;
            setUploading(true);
            await processQueue(files);
        },
        [processQueue, remainingSlots],
    );

    const rotatePending = useCallback(async () => {
        if (!pending) return;
        const nextTurns = pending.quarterTurns + 1;
        const baked = await bakeRotation(pending.inspection.file, nextTurns);
        const previewUrl = URL.createObjectURL(baked);
        URL.revokeObjectURL(pending.previewUrl);
        setPending({ ...pending, quarterTurns: nextTurns, previewUrl });
    }, [pending]);

    const confirmPending = useCallback(async () => {
        if (!pending) return;
        setUploading(true);
        try {
            await uploadBaked(pending.inspection.file, pending.quarterTurns);
        } finally {
            URL.revokeObjectURL(pending.previewUrl);
            const rest = queue;
            setPending(null);
            setQueue([]);
            await processQueue(rest);
        }
    }, [pending, queue, processQueue, uploadBaked]);

    return {
        uploading,
        pending,
        handleFiles,
        rotatePending,
        confirmPending,
    };
}
