// A running production server retains asset names from its original build.
import { spawn } from "node:child_process";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

export async function requireStoppedDashboard(port = 3000) {
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error("PORT must be a valid TCP port.");
  await new Promise((resolve, reject) => {
    const socket = net.createConnection({ host: "127.0.0.1", port });
    const fail = () => {
      socket.destroy();
      reject(new Error(`Stop the dashboard on port ${port} before building, then restart it after the build. A live server can retain missing CSS/JavaScript references.`));
    };
    socket.setTimeout(1000, fail);
    socket.once("connect", fail);
    socket.once("error", (error) => {
      socket.destroy();
      if (error.code === "ECONNREFUSED") resolve();
      else reject(new Error("Could not verify that the dashboard is stopped; build cancelled."));
    });
  });
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    for (const port of new Set([3000, Number(process.env.PORT ?? 3000)])) await requireStoppedDashboard(port);
    const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
    const child = spawn(process.execPath, [path.join(root, "node_modules/next/dist/bin/next"), "build", ...process.argv.slice(2)],
      { cwd: root, stdio: "inherit", shell: false });
    child.once("error", () => { console.error("Next.js build could not start."); process.exitCode = 1; });
    child.once("exit", (code) => { process.exitCode = code ?? 1; });
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
