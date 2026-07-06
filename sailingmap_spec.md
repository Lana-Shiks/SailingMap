# SailingMap v1 — Specification & Build Plan

**Status:** Approved for implementation
**Date:** 2026-07-04
**Purpose:** This document is the durable asset. Coding agents implement *from this spec*; when behavior must change, change the spec first, then regenerate/patch code. Do not encode requirements only in prompts or code comments.

---

## 1. Product definition

SailingMap plans sailing routes on San Francisco Bay from a natural-language trip request and guarantees the boat is back at the dock before sunset.

**Core interaction:** the user types a request like *"I want a ~3-hour sail from Berkeley Marina this afternoon, my boat draws 1.8m, I'd like to see Alcatraz."* The system returns:

1. A route drawn on the map (dense coordinate path through navigable water)
2. Per-leg timing, point of sail, and hazard flags
3. A plain-English (or Russian) briefing: wind, tide strategy, tacking legs, shipping-lane crossings, sunset margin
4. Support for follow-up edits in the same conversation ("make it shorter", "leave an hour later")

---

## 2. Architecture

**One agent, many tools.** No orchestrator/sub-agent topology in v1.

```
Next.js frontend (dumb renderer)
      │  REST + SSE
      ▼
ADK api_server  ──►  Concierge Agent (single LLM agent)
                          │ MCP tools           │ HTTP tool
                          ▼                     ▼
                  Weather MCP server      Routing Service (FastAPI, deterministic)
                  (NOAA tides/currents,   - offline-built bathymetry grid
                   Open-Meteo wind/waves, - A* pathfinding
                   sunset API)            - duration-fitting search
                                          - time model & safety limits
```

### 2.1 Non-negotiable system invariants

These are architectural laws. Any PR violating them is wrong by definition.

- **INV-1 — Coordinates only from the router.** No LLM output, prompt, frontend constant, or config file may introduce route geometry. The frontend renders exactly and only `plan_route` output. Delete all hardcoded waypoint arrays in `frontend/src/app/page.tsx`.
- **INV-2 — The router is a pure function.** All environmental data (wind, currents, tide window, sunset) is passed *in* as parameters. The routing service makes no network calls at request time.
- **INV-3 — Safety limits live in deterministic code**, never in the agent prompt. The agent cannot override them; it can only narrate refusals.
- **INV-4 — The LLM expresses places as gazetteer names, never lat/lon.** Unknown place → the agent asks or omits; it must fail loudly, not guess coordinates.
- **INV-5 — Structured payloads are language-invariant.** Conversation may be English or Russian; every tool payload is English/ISO-8601/SI units.

---

## 3. Routing Service (`services/router/` — rename from `agents/routing_agent.py`; it is not an agent)

### 3.1 Offline data pipeline (`services/router/pipeline/`)

Run at build time, not request time. Outputs a versioned grid artifact.

1. **Bathymetry:** download NOAA NCEI San Francisco Bay DEM (real survey bathymetry; implementer must verify current dataset name/URL at build time). Replace `sf_bay_depth.json` mock.
2. **Grid:** resample to a regular grid of **50–100 m cells** covering the Bay (tune so Raccoon Strait is threadable and A* over the full Bay completes < 2 s).
3. **Static no-go polygons** (`data/no_go_zones.geojson`, hand-curated): Alcatraz restricted/standoff zone, permanent security zones, other CFR-designated restricted areas. Burned into the grid as impassable.
4. **Shipping lanes / VTS traffic scheme** (`data/shipping_lanes.geojson`): burned in as a **cost multiplier** (suggested 3×), not impassable. Cells tagged so legs crossing them can be flagged.
5. Output: `grid.npz` (or equivalent) with per-cell: charted depth (m, negative = below datum), no_go flag, lane flag/cost.

### 3.2 Passability rule (computed per request)

A cell is navigable iff:

```
charted_depth + tide_window.min_tide  ≥  boat.draft_m + SAFETY_MARGIN (1.0 m)
AND no_go == false
```

`tide_window.min_tide` = the lowest predicted tide across the entire trip window (conservative). Per-cell time-stepped tides are v2.

### 3.3 Pathfinding

- **A\*** over the navigable grid, 8-connected, Euclidean/haversine heuristic, lane-cost multiplier applied to edge weights.
- Output paths are simplified (e.g., Douglas-Peucker) but every retained vertex and every straight segment between vertices must remain within navigable cells (re-validate after simplification).

### 3.4 Gazetteer (`data/gazetteer.json`)

~30 hand-curated named safe-water anchor points. Each: `{id, display_name, aliases[], lat, lon}` where (lat, lon) verifiably sits in deep water. Seed set must include: Berkeley Marina, Richmond (Marina Bay), Sausalito, South Beach Harbor (SF), Alameda/Oakland Estuary entrance, Angel Island (Ayala Cove approach), Raccoon Strait midpoint, Alcatraz viewing point (outside restricted zone), Golden Gate Bridge midspan approach, Treasure Island, McCovey Cove approach, Point Bonita approach (flag: outside-gate, exclude from default loops).

### 3.5 Time model

Per leg (a leg = path segment between direction changes above a threshold, or fixed ~1 nm chunks):

1. **Boat speed through water** = `speed_curve(wind_speed_at_leg_time)` — a lookup table per boat, e.g. `[(0kt→0.0), (2→1.5), (5→3.5), (8→5.0), (12→hull_speed), (20+→hull_speed)]`. Stored in boat config, linearly interpolated.
2. **Point of sail** from leg heading vs. forecast wind direction at the leg's ETA:
   - `upwind` if |heading − wind_source| ≤ 45° → flag `tacking_required`, multiply leg distance by **1.4** for time purposes (drawn line stays straight)
   - `downwind` if |heading − wind_from_reciprocal| ≤ 30° → flag `downwind`
   - else `reaching`
3. **Speed over ground** = boat speed ± projection of NOAA current vector onto leg heading (floor at 0.5 kt; if SOG floor is hit, flag `adverse_current`).
4. If wind < 3 kt on a leg → flag `light_air` (and the total-time consequence usually triggers infeasibility naturally).
5. ETAs accumulate; wind/current sampled at each leg's ETA from the passed-in forecast arrays.

### 3.6 Duration-fitting search (loops)

When `duration_target` is set: generate candidate routes = combinations of 1–3 gazetteer via-points (always including all `pinned_waypoints`), run A* + time model on each, return the candidate minimizing `|est_total_time − duration_target|` subject to all safety constraints. Beam/greedy search is fine; must evaluate ≤ ~200 candidates and respond < 10 s. Acceptance: returned estimate within **±20%** of target when feasible.

### 3.7 Safety limits (hard, in code)

| Limit | Value | Overridable? |
|---|---|---|
| Sunset buffer | `return_eta + 30 min ≤ sunset_time` | **No** |
| Wind ceiling | forecast gusts ≤ `boat.max_wind_kt` (default 20) | User-tunable, **absolute cap 30 kt** |
| Depth rule | §3.2 | No |
| No-go zones | never entered | No |

Violations → `status: "infeasible"` with machine-readable `reason` (`sunset_violation`, `wind_exceeds_ceiling`, `no_navigable_path`, `light_air_duration`). If shortening the route restores feasibility, the router may return `status: "shortened_to_fit"` with the shorter route.

### 3.8 API contract — `POST /plan_route`

**Request:**
```json
{
  "start": "berkeley_marina",
  "end": "berkeley_marina",
  "departure_time": "2026-07-04T13:00:00-07:00",
  "duration_target_min": 180,
  "pinned_waypoints": ["alcatraz_view"],
  "boat": { "draft_m": 1.8, "speed_curve_id": "default_30ft", "max_wind_kt": 22 },
  "wind_forecast": [ { "time": "...", "speed_kt": 12.0, "gust_kt": 16.0, "direction_deg": 280 } ],
  "current_vectors": [ { "time": "...", "lat": 0.0, "lon": 0.0, "speed_kt": 1.2, "direction_deg": 130 } ],
  "tide_window": { "min_tide_m": -0.3 },
  "sunset_time": "2026-07-04T20:32:00-07:00"
}
```

**Response:**
```json
{
  "status": "ok | shortened_to_fit | infeasible",
  "reason": null,
  "coordinates": [[37.87, -122.31], ...],
  "legs": [
    { "from_idx": 0, "to_idx": 41, "heading_deg": 245, "distance_nm": 2.1,
      "point_of_sail": "upwind | reaching | downwind",
      "est_sog_kt": 3.8, "eta": "2026-07-04T13:33:00-07:00",
      "flags": ["tacking_required", "lane_crossing", "light_air", "adverse_current"] }
  ],
  "return_eta": "2026-07-04T16:05:00-07:00",
  "sunset_margin_min": 267,
  "grid_version": "noaa-dem-2026-07"
}
```

Validate requests with a strict schema (Pydantic); reject unknown gazetteer IDs with a listing of valid ones.

---

## 4. Weather MCP Server (`mcp/weather_server.py` — largely as built)

Keep the three FastMCP tools; changes:

- `get_tides_and_currents` must also return `min_tide_m` over a requested window, and current vectors at the ~5 Bay NOAA current stations for the trip window.
- `get_marine_weather` must return an hourly wind array (speed, gust, direction) covering `departure_time … departure_time + duration + 2h`, not a single snapshot.
- `get_sunset_time` unchanged.

---

## 5. Concierge Agent (`agents/concierge_agent.py`)

**Responsibilities (only these):**
1. Parse the NL request into structured parameters (start, duration, departure time, pinned gazetteer waypoints, boat overrides). Ask a clarifying question if start or rough duration is missing; otherwise use defaults from boat config.
2. Call MCP tools to gather wind forecast, tide window + currents, sunset time.
3. Make **one** `plan_route` call (follow-ups = another single call with adjusted params).
4. Compose the briefing from `legs[]`, flags, and `sunset_margin_min` — narrate, never contradict, the router's numbers. On `infeasible`, explain the machine-readable reason and propose concrete alternatives (earlier departure, shorter duration, different start).
5. Respond in the user's language (EN/RU). Payloads stay English/ISO (INV-5).

**Required wiring fixes (from audit):** register the three weather MCP tools *and* a `plan_route` HTTP tool in `CapabilitiesConfig`; retire the stdin REPL as the primary interface in favor of `adk api_server`.

**Prohibited:** emitting coordinates; restating safety limits as if negotiable; inventing place names outside the gazetteer.

### 5.1 Response envelope (agent → frontend)

```json
{ "briefing_text": "<streamed narration>", "route": { …full plan_route response, untouched… } }
```

---

## 6. Frontend (`frontend/`)

- Talks to ADK api_server (REST + SSE). Chat pane streams `briefing_text`.
- Map renders **only** `route.coordinates` (INV-1). Delete all hardcoded route arrays.
- Leg styling from router data: `upwind/tacking_required` → dashed red; `downwind` → green; `reaching` → default; `lane_crossing` → warning icon at leg midpoint.
- Display `return_eta` and `sunset_margin_min` prominently; `infeasible` renders the reason, not a route.
- Follow-up messages go through the same chat session; each new envelope fully replaces the rendered route.

---

## 7. Gherkin acceptance specs (`specs/features/`)

These are the executable definition of done. Layer-1 scenarios run against the router with fixture data; layer-2 against the agent.

```gherkin
Feature: Routes never touch land or forbidden water
  Scenario Outline: any gazetteer pair yields a fully navigable path
    Given the production grid and a boat with draft 1.8m and min tide 0.0m
    When I request a route from <start> to <end>
    Then every returned coordinate lies in a navigable cell
    And every straight segment between consecutive coordinates stays in navigable cells
    # Implemented as a property test over randomized gazetteer pairs (≥200 pairs in CI)

  Scenario: no-go zones are never entered
    When I request a route pinned to "alcatraz_view"
    Then no coordinate falls inside data/no_go_zones.geojson polygons

Feature: Back before sunset
  Scenario: sunset margin is enforced
    Given sunset at 20:32 and a requested departure of 18:30 with duration 180 min
    When I request a loop from "berkeley_marina"
    Then status is "shortened_to_fit" or "infeasible"
    And any returned route has return_eta + 30 min ≤ sunset

  Scenario: becalmed day
    Given a wind forecast of 2 kt all afternoon
    When I request a 3-hour, 10 nm-class loop
    Then status is "infeasible" with reason "light_air_duration" or a drastically shortened route

Feature: Depth respects draft and tide
  Scenario: deep-draft boat is kept out of shallows a dinghy may cross
    Given boat A draft 0.3m and boat B draft 2.5m and min tide -0.5m
    When both request the same shallow-adjacent route
    Then boat B's path avoids all cells where depth + tide < 3.5m

Feature: Duration fitting
  Scenario: three-hour request returns roughly three hours
    Given 12 kt steady wind and neutral current
    When I request duration_target 180 min from "sausalito"
    Then status is "ok" and est total time is within ±20% of 180 min
    And pinned waypoints, if any, appear on the path

Feature: Wind ceiling
  Scenario: gusts above the boat ceiling are refused
    Given forecast gusts of 26 kt and boat max_wind_kt 22
    Then status is "infeasible" with reason "wind_exceeds_ceiling"
  Scenario: nobody exceeds the absolute cap
    Given a user-configured max_wind_kt of 35
    Then the effective ceiling used is 30 kt

Feature: Agent extraction (layer 2, golden set)
  Scenario: English request maps to exact payload
    Given "3 hour sail from Berkeley tomorrow at 1pm, we draw six feet, want to see Alcatraz"
    Then the plan_route payload has start "berkeley_marina", duration_target_min 180,
         draft_m 1.83, pinned_waypoints ["alcatraz_view"], departure_time tomorrow 13:00 local
  Scenario: Russian request maps to the same schema
    Given the same trip requested in Russian
    Then the payload is identical in structure, English IDs, and SI units
  Scenario: unknown place fails loudly
    Given a request to visit "Catalina Island"
    Then the agent does not invent a waypoint and asks/declines instead
```

---

## 8. Test & eval plan

| Layer | Target | Tooling | Gate |
|---|---|---|---|
| 1. Router unit + property tests | all §7 router features, time model math, schema validation | pytest + hypothesis, fixture env data | CI-blocking |
| 2. Agent golden-set evals | ~30 NL→payload cases (EN + RU + missing-info + unknown-place), field-level scoring; tool-call trajectory checks (weather fetched before plan_route) | ADK eval tooling (`adk eval`) | CI-blocking |
| 3. E2E smoke | 3–5 scripted conversations via api_server; envelope schema; rendered route re-checked against layer-1 invariants | pytest + httpx | CI-blocking, small |
| (deferred) briefing quality | LLM-judge rubric on narration | — | v1.1 |

---

## 9. Repository layout

```
specs/
  features/*.feature          # §7 — the source of truth
  contracts/plan_route.md     # §3.8 schema, versioned
  contracts/envelope.md       # §5.1
  decisions.md                # this interview's decision log
services/router/              # FastAPI app + pipeline/ + tests/
mcp/weather_server.py
agents/concierge_agent.py     # + prompts/ + evals/golden_set.jsonl
frontend/
data/                         # gazetteer.json, no_go_zones.geojson, shipping_lanes.geojson, grid artifact
AGENTS.md                     # thin: stack, commands, pointer into specs/
```

---

## 10. Build order (each phase gated by its tests)

1. **P1 — Grid pipeline + data.** NOAA DEM → grid artifact; no-go & lane GeoJSONs; gazetteer with verified-in-water points. *Gate:* pipeline reproducible; every gazetteer point navigable at draft 2.5 m.
2. **P2 — Router core.** Passability rule, A*, simplification+revalidation, `/plan_route` for explicit start/end. *Gate:* land-crossing property test green over ≥200 random pairs.
3. **P3 — Time model + safety limits.** Speed curve, point-of-sail, 1.4× upwind, current projection, sunset/wind/infeasibility statuses. *Gate:* §7 sunset/depth/wind/becalmed scenarios green.
4. **P4 — Duration fitting.** Candidate search over gazetteer via-points. *Gate:* ±20% scenario green; p95 latency < 10 s.
5. **P5 — MCP upgrades + agent wiring.** Forecast-array tool outputs; register MCP + plan_route tools; system prompt; envelope. *Gate:* golden-set evals green.
6. **P6 — Bridge + frontend.** adk api_server; delete hardcoded waypoints; leg styling; follow-up edits. *Gate:* E2E smoke green; visual check shows zero land intersections.

---

## 11. Out of scope (v1) — do not build

Polar/isochrone wind routing and tack geometry · live AIS traffic · per-cell time-stepped tides · saved boat profiles/accounts (single boat config file only) · GPX export · routes outside the Golden Gate by default · offline/mobile.

## 12. Open items for implementers (verify, don't assume)

- Exact NOAA NCEI SF Bay DEM dataset ID/URL and license; NOAA current-station coverage inside the Bay.
- Current ADK api_server capabilities (SSE streaming shape, session semantics) against up-to-date docs.
- Authoritative boundaries for the Alcatraz restricted zone and Bay security zones (33 CFR) for `no_go_zones.geojson`.
- Grid resolution tuning (start 75 m; adjust per P2 latency and Raccoon Strait threadability).
