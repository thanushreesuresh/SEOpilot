import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

const root = path.resolve(__dirname, "..");
const python = process.env.CI ? "python" : path.join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const safeEnvironment = { PYTHON_DOTENV_DISABLED: "1", OPENAI_API_KEY: "", GITHUB_APP_ID: "", GITHUB_APP_PRIVATE_KEY_PATH: "", GITHUB_APP_OWNERS: "", SEOPILOT_AI_ENABLED: "false", SEOPILOT_PROXY_TOKEN_FILE: path.join(root, ".tmp", "e2e-proxy-token") };

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 45_000,
  use: { baseURL: "http://localhost:3000", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `"${python}" -m uvicorn seopilot.app:app --app-dir backend --host 127.0.0.1 --port 8000 --no-proxy-headers`,
      cwd: root,
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: !process.env.CI,
      env: { ...safeEnvironment, SEOPILOT_DB: path.join(root, ".tmp", "e2e.db") },
    },
    {
      command: "npm run dev",
      env: safeEnvironment,
      url: "http://localhost:3000",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
