// `pnpm demo:session`: checks prerequisites, then starts the persistent manual demo session.
// The session keeps both browsers and the seeded database until `pnpm demo:stop` (or Ctrl+C).
import { spawn } from "node:child_process";
import net from "node:net";

const port = Number(process.env.DEMO_CONTROL_PORT ?? 8199);

function portOpen(p) {
  return new Promise((resolve) => {
    const socket = net.connect({ port: p, host: "127.0.0.1" }, () => {
      socket.destroy();
      resolve(true);
    });
    socket.on("error", () => resolve(false));
    socket.setTimeout(1500, () => {
      socket.destroy();
      resolve(false);
    });
  });
}

if (await portOpen(port)) {
  console.error(
    `A demo session is already running (control port ${port}).\nUse pnpm demo:status, demo:reset or demo:stop.`,
  );
  process.exit(2);
}
if (!(await portOpen(5432))) {
  console.error(
    "PostgreSQL is not reachable on localhost:5432.\nStart it first:  docker compose up -d --wait db   (or: pixi run db-up)",
  );
  process.exit(2);
}

const child = spawn(
  "pnpm",
  ["exec", "playwright", "test", "-c", "playwright.demo.config.ts", "--project=session"],
  { stdio: "inherit", shell: true, env: process.env },
);
child.on("exit", (code) => process.exit(code ?? 1));
