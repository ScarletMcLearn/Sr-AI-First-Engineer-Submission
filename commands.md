## 1. Before Recording

**Terminal 1 — Repository root**
```bash
docker compose up -d --wait db
```

**Terminal 2 — Start demo stack (leave running)**
```bash
cd frontend
pnpm demo:stack
```

**Terminal 3 — Start Playwright session (leave running)**
```bash
cd frontend
pnpm demo:session
```

## 2. During Recording

**Terminal 4 — Run each command individually when you're ready.**

```bash
cd frontend
```

**Scene 1 — Introduction**
```bash
pnpm demo:scene intro
```

**Scene 2 — Scorecard**
```bash
pnpm demo:scene scorecard
```

**Scene 3 — Issues and To-Dos**
```bash
pnpm demo:scene issues
```

**Scene 4 — Rocks and Milestones**
```bash
pnpm demo:scene rocks
```

**Scene 5 — Two-Browser Meeting**
```bash
pnpm demo:scene meeting
```

**Scene 6 — Real-Time Synchronization**
```bash
pnpm demo:scene sync
```

**Scene 7 — Reconnection**
```bash
pnpm demo:scene reconnect
```

**Scene 8 — Ratings and Summary**
```bash
pnpm demo:scene summary
```

**Scene 9 — Architecture and Testing**
```bash
pnpm demo:scene architecture
```

## 3. After Recording

**Stop the Playwright session**
```bash
pnpm demo:stop
```

**Stop the demo stack:** Press `Ctrl+C` in Terminal 2.

## 4. Additional Commands

| Purpose | Command |
|---|---|
| Check demo progress | `pnpm demo:status` |
| Reset all scenes and start over | `pnpm demo:reset` |
| Stop the session | `pnpm demo:stop` |
| Run all scenes automatically | `pnpm demo` |
| Validate all nine scenes headlessly | `pnpm demo:validate` |
| Run stack/controller unit tests | `pnpm test:stack` |
| Run backend tests | `pixi run test-backend` |
| Run regular Playwright tests | `pixi run test-e2e` |
| Run complete verification | `pixi run check` |
| Generate business rules report | `pixi run rules-report` |

**Note:** Run `pnpm` commands from the `frontend` directory and `pixi` commands from the repository root.

cd frontend
pnpm demo