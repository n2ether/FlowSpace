import { useEffect, useState } from "react";

// Current time, refreshed every `intervalMs` so time-based status can change on screen.
export function useNow(intervalMs = 15000) {
    const [now, setNow] = useState(() => Date.now());
    useEffect(() => {
        const id = setInterval(() => setNow(Date.now()), intervalMs);
        return () => clearInterval(id);
    }, [intervalMs]);
    return now;
}
