# Requirement → test matrix

Verification kinds: **F** functional · **B** business rule · **S** security · **A** API · **C** concurrency ·
**R** real-time · **U** UI (Playwright). Result column = result of the final verification run (see
`TEST_RESULTS.md`); every automated test listed passed in that run. "—" means no automated coverage (called out below).

| Requirement | F | B | S | A | C | R | U | Tests (see `TEST_CASES.md`) | Result |
|---|---|---|---|---|---|---|---|---|---|
| R-RULE-00 time / weeks / quarters / DST | | ✔ | | | | | | TC-RULE-01..04 | Pass |
| R-RULE-01 measurable status | | ✔ | | ✔ | | | ✔ | TC-RULE-05..09, TC-API-01, TC-E2E-02 | Pass |
| R-RULE-02 overdue | | ✔ | | ✔ | | | ✔ | TC-RULE-10, TC-API-16, TC-E2E-02 | Pass |
| R-RULE-03 to-do completion rate | | ✔ | | ✔ | | | ✔ | TC-RULE-11..16, TC-REP-02, TC-API-16 | Pass |
| R-RULE-04/05 rock status & progress | | ✔ | | ✔ | | | ✔ | TC-RULE-17/18, TC-API-12, TC-E2E-02 | Pass |
| R-RULE-06 issue order | | ✔ | | ✔ | | | ✔ | TC-RULE-19, TC-API-07, TC-E2E-02 | Pass |
| R-RULE-07 meeting rating | | ✔ | | ✔ | | | ✔ | TC-RULE-20, TC-MTG-13, TC-E2E-01 | Pass |
| R-CONC-01 no duplicate Issues | | | | ✔ | ✔ | | ✔ | TC-API-05, TC-CONC-01/02, TC-E2E-02 | Pass |
| R-TEAM-01 team switcher / access | ✔ | | ✔ | ✔ | | | ✔ | TC-SEC-03/04, TC-E2E-03 | Pass |
| R-TEAM-02..04 scorecard, edit, make issue | ✔ | | | ✔ | | | ✔ | TC-API-01..05, TC-E2E-02 | Pass |
| R-TEAM-05..09 issues, solve, to-do from issue | ✔ | | | ✔ | | | ✔ | TC-API-07..15, TC-E2E-02 | Pass |
| R-TEAM-10/11 to-dos | ✔ | | | ✔ | | | ✔ | TC-API-16/17, TC-E2E-02 | Pass |
| R-TEAM-12 rocks | ✔ | | | ✔ | | | ✔ | TC-API-12, TC-E2E-02 | Pass |
| R-TEAM-13 reuse of Scorecard/Issues | ✔ | | | | | | ✔ | TC-E2E-01 | Pass |
| R-MTG-01 start / facilitator | ✔ | | | ✔ | | | ✔ | TC-MTG-01, TC-E2E-01 | Pass |
| R-MTG-02 one active meeting | | | | ✔ | ✔ | | | TC-MTG-02, TC-CONC-03, TC-DB-02 | Pass |
| R-MTG-03 join (observers) | ✔ | | ✔ | ✔ | | | ✔ | TC-MTG-04, TC-SEC-09, TC-E2E-04 | Pass |
| R-MTG-04 facilitator-only | | | ✔ | ✔ | | | ✔ | TC-MTG-05..07, TC-E2E-01 | Pass |
| R-MTG-05 server timer / overtime | | ✔ | | ✔ | | | ✔ | TC-MTG-08, TC-E2E-01 (UI overtime text: manual) | Pass (UI overtime: manual) |
| R-MTG-06 sync < 1 s | | | | | | ✔ | ✔ | TC-RT-01, TC-E2E-01 | Pass |
| R-MTG-07 late join / refresh / reconnect | | | | ✔ | | ✔ | ✔ | TC-MTG-09, TC-RT-04, TC-E2E-01 | Pass |
| R-MTG-08 ratings | | | ✔ | ✔ | | | ✔ | TC-MTG-10..12, TC-MTG-15, TC-DB-03, TC-E2E-01 | Pass |
| R-MTG-09 summaries (incl. seeded) | | ✔ | | ✔ | | | ✔ | TC-MTG-13, TC-REP-03/05, TC-E2E-01 | Pass |
| R-MTG-09 summary consistency under races | | | | ✔ | ✔ | | ✔ | TC-CONC-05..08 | Pass |
| R-MTG-11 stale update protection | | | | ✔ | ✔ | | | TC-MTG-06, TC-CONC-04 | Pass |
| R-SEC-01..06 server-side authorization & validation | | | ✔ | ✔ | | | ✔ | TC-SEC-01..09, TC-API-10 | Pass |
| R-DATA-01 DB constraints | | | | ✔ | | | | TC-DB-01..03 | Pass |
| R-DATA-02 UTC / APP_NOW | | ✔ | | ✔ | | | | TC-RULE-*, TC-REP-04, TC-API-14 | Pass |
| R-OPS-01 compose / seed | ✔ | | | | | | | TC-SEED-01..03, TC-OPS-01 (manual) | Pass |
| R-REP-01..03 rules report | | ✔ | | | | | | TC-REP-01..06, TC-OPS-02 (manual) | Pass |
| R-E2E-01 two-browser test | | | | | | ✔ | ✔ | TC-E2E-01 | Pass |
| R-BONUS-01 lost-update protection | | | | ✔ | | | | TC-API-03, TC-API-11 | Pass |
| R-BONUS-02 audit trail (meetings only) | | | | ✔ | | | | TC-MTG-15 | Pass (partial scope) |

## Requirements without (complete) automated coverage

* **R-DOC-02 video** — not recorded; script only (`DEMO_SCRIPT.md`).
* **Overtime display in the UI** — covered by the API timer test; the visual state was reviewed manually, not by a
  (>5 minute) end-to-end wait.
* **`docker compose up` startup** — verified manually (TC-OPS-01/02); CI builds the images and runs the stack smoke
  test but the check is a script, not part of `pixi run test`.
* **R-BONUS-03** (Issue from Rock / overdue To-Do) — not implemented.
