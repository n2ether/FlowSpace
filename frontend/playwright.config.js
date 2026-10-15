// End-to-end intake checks against the production build. The API is mocked
// per test (see e2e/mockApi.js), so no backend, Stripe, or email is touched.
const { defineConfig, devices } = require("@playwright/test");

const PORT = Number(process.env.E2E_PORT || 3100);
const BASE = `http://localhost:${PORT}`;

module.exports = defineConfig({
    testDir: "./e2e",
    timeout: 60_000,
    fullyParallel: true,
    reporter: [["list"]],
    use: {
        baseURL: BASE,
        trace: "retain-on-failure",
    },
    projects: [
        { name: "mobile-iphone", use: { ...devices["iPhone 13"], browserName: "chromium" } },
        { name: "mobile-small", use: { browserName: "chromium", viewport: { width: 320, height: 640 }, isMobile: true, hasTouch: true } },
        { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    ],
    webServer: {
        command: `REACT_APP_BACKEND_URL=${BASE} npx craco build && npx serve -s build -l ${PORT}`,
        url: BASE,
        reuseExistingServer: true,
        timeout: 240_000,
    },
});
