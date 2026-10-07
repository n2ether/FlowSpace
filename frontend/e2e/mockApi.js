// Network-level stand-in for the FlowSpace API: uploads, auth, leads, checkout.
// Records what the intake sends so tests can assert on the real payload.

function jpegFromMultipart(buf) {
    const start = buf.indexOf(Buffer.from([0xff, 0xd8, 0xff]));
    const end = buf.lastIndexOf(Buffer.from([0xff, 0xd9]));
    if (start < 0 || end < 0) return null;
    return buf.subarray(start, end + 2);
}

async function mockApi(page, { member = null } = {}) {
    const state = { uploads: new Map(), leads: [], checkouts: [], signups: [] };
    let n = 0;

    await page.route("**/api/**", async (route) => {
        const req = route.request();
        const url = new URL(req.url());
        const path = url.pathname;
        const method = req.method();
        const json = (status, body) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

        if (path === "/api/uploads/photo" && method === "POST") {
            n += 1;
            const id = String(n).padStart(24, "0");
            state.uploads.set(id, jpegFromMultipart(req.postDataBuffer() || Buffer.alloc(0)));
            return json(200, { id, url: `/api/uploads/photo/${id}` });
        }
        if (path.startsWith("/api/uploads/photo/") && method === "GET") {
            const body = state.uploads.get(path.split("/").pop());
            if (!body) return route.fulfill({ status: 404 });
            return route.fulfill({ status: 200, contentType: "image/jpeg", body });
        }
        if (path === "/api/auth/me") {
            return member ? json(200, member) : json(401, { detail: "Not signed in" });
        }
        if (path === "/api/auth/signup" && method === "POST") {
            const body = req.postDataJSON();
            state.signups.push(body);
            return json(200, {
                token: "test-token",
                member: { id: "m1", name: body.name, email: body.email, usage: { can_generate_free: true } },
            });
        }
        if (path === "/api/leads" && method === "POST") {
            const body = req.postDataJSON();
            state.leads.push(body);
            return json(200, { ...body, id: `lead-${state.leads.length}` });
        }
        if (path === "/api/checkout/session" && method === "POST") {
            state.checkouts.push(req.postDataJSON());
            return json(200, { url: `${url.origin}/?mock-checkout=1`, session_id: "cs_test" });
        }
        if (path.startsWith("/api/checkout/status/")) {
            return json(200, { payment_status: "paid", status: "complete", amount_total: 1000, currency: "usd" });
        }
        if (path === "/api/gallery") return json(200, []);
        return json(404, { detail: `unmocked ${method} ${path}` });
    });
    return state;
}

// Draws a room-like test photo in the browser so the real client-side checks run.
async function makePhoto(page, { seed = 1, width = 1200, height = 900, dark = false } = {}) {
    const base64 = await page.evaluate(
        ({ seed, width, height, dark }) => {
            let s = seed * 9973;
            const rnd = () => {
                s = (s * 16807) % 2147483647;
                return s / 2147483647;
            };
            const c = document.createElement("canvas");
            c.width = width;
            c.height = height;
            const g = c.getContext("2d");
            const shade = dark ? 0.12 : 1;
            const col = (r, gg, b) => `rgb(${Math.round(r * shade)},${Math.round(gg * shade)},${Math.round(b * shade)})`;
            g.fillStyle = col(230, 226, 214);
            g.fillRect(0, 0, width, height);
            g.fillStyle = col(196, 186, 168);
            g.fillRect(0, height * 0.7, width, height * 0.3);
            for (let i = 0; i < 40; i += 1) {
                g.fillStyle = col(60 + rnd() * 180, 60 + rnd() * 160, 50 + rnd() * 150);
                g.fillRect(rnd() * width, rnd() * height, 40 + rnd() * 240, 30 + rnd() * 200);
                g.strokeStyle = col(30, 30, 30);
                g.lineWidth = 3;
                g.strokeRect(rnd() * width, rnd() * height, 30 + rnd() * 200, 30 + rnd() * 160);
            }
            return c.toDataURL("image/jpeg", 0.85).split(",")[1];
        },
        { seed, width, height, dark },
    );
    return { name: `room-${seed}.jpg`, mimeType: "image/jpeg", buffer: Buffer.from(base64, "base64") };
}

module.exports = { mockApi, makePhoto };
