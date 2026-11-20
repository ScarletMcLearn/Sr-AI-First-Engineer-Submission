// Client for the manual demo session: `pnpm demo:scene <id>`, `demo:status`, `demo:reset`, `demo:stop`.
// Short-lived: it asks the running session (demo/assessment-demo-session.spec.ts) to do one thing,
// prints the streamed output, and exits. It never starts a browser itself.
import http from "node:http";

const port = Number(process.env.DEMO_CONTROL_PORT ?? 8199);
const [action, arg] = process.argv.slice(2);

const routes = {
  scene: { method: "POST", path: `/scene/${encodeURIComponent(arg ?? "")}` },
  status: { method: "GET", path: "/status" },
  reset: { method: "POST", path: "/reset" },
  stop: { method: "POST", path: "/stop" },
};
const route = routes[action];
if (!route || (action === "scene" && !arg)) {
  console.error(
    "Usage: pnpm demo:scene <intro|scorecard|issues|rocks|meeting|sync|reconnect|summary|architecture>",
  );
  process.exit(2);
}

const req = http.request(
  { host: "127.0.0.1", port, method: route.method, path: route.path },
  (res) => {
    let tail = "";
    res.setEncoding("utf8");
    res.on("data", (chunk) => {
      tail = (tail + chunk).slice(-64);
      process.stdout.write(chunk.replace(/\n?::exit \d+\n?/, "\n"));
    });
    res.on("end", () => {
      const code = /::exit (\d+)/.exec(tail);
      process.exit(code ? (Number(code[1]) === 200 ? 0 : 1) : res.statusCode === 200 ? 0 : 1);
    });
  },
);
req.on("error", () => {
  console.error(
    "No demo session is running.\nStart one in a separate terminal:  pnpm demo:session",
  );
  process.exit(3);
});
req.end();
