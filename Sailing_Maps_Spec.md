# System Specification: Sailing Maps: Richmond Navigator

## 1. Project Context & Deployment
**Objective:** Build a full-stack web application serving as an AI-driven sailing navigation guide for the San Francisco Bay Area. 
**Environment:** Develop using **Google Agent Development Kit (ADK)** framework within the **Antigravity** developer platform (leveraging the `google-developer-knowledge` MCP).
**Milestone:** Day 1 deliverable for the Kaggle & Google 5-day AI Agents intensive course.

## 2. API Availability & Telemetry Sources
*API Verification Complete:* All external environmental telemetry APIs and mapping services specified for this project are freely available for public and non-commercial use.
* **Marine Maps:** **NOAA Nautical Charts** (Public domain, free via nauticalcharts.noaa.gov).
* **Tidal & Current Vectors:** **NOAA CO-OPS API** (Free, open public REST API, no authentication required).
* **Wind & Weather Forecasts:** **Open-Meteo Marine API / NOAA NWS API** (Free tiers available without API keys for non-commercial use).
* **Dynamic Sunset Calculator:** **SunriseSunset.io API** (Free, JSON-based REST API, no authentication required).

## 3. The Problem & Scenario Constraints
San Francisco Bay is notorious for its challenging navigation conditions. Sailors here face a chaotic intersection of strong thermal winds, especially near the Golden Gate, and powerful, shifting tidal currents. Miscalculations lead to dangerous drift, stall zones, and compromised vessel safety.

**Scenario:** A sailboat departing from Richmond Marina at 11:00 AM must return strictly before sunset. The agent must calculate exact travel times based on vessel capabilities and environmental vectors, adapting the route to guarantee the vessel returns safely before darkness falls. Seasonal variance must be mathematically accounted for in the travel window.

## 4. Multi-Agent Architecture
The system utilizes a decoupled, safety-first multi-agent orchestration pattern coordinated by a centralized supervisor.

### A. Concierge Agent (The Supervisor)
* **Role:** Natural language orchestration layer and user interface entry point.
* **Responsibilities:** Manage conversation state, collect initial boat specifications (e.g., draft, hull speed), and delegate sub-tasks to downstream agents based on intent routing.
* **Tools:** Utilizes the ADK Agents CLI for localized deployment testing, environment configuration, and scaffolding specialized tool declarations.

### B. Weather Agent (Data Acquisition via MCP)
* **Role:** Real-time environmental telemetry gatherer.
* **Responsibilities:** Operates natively over the Model Context Protocol (MCP). Connects to a custom MCP Weather Server that exposes tools for fetching live NOAA tidal stream vectors, wind speed forecasts for the Central San Francisco Bay, and dynamic sunset calculators, securely injecting them into the context window.

### C. Routing Agent (The Analytical Engine)
* **Role:** Executes physics-bound pathfinding calculations.
* **Responsibilities:** Uses computational Python tools (Agent Skills) to evaluate wind-current intersections. It takes telemetry from the MCP Server and models whether a sailboat departing from Richmond at 11:00 AM can safely tack against afternoon thermal gusts and return prior to the dynamically calculated sunset margin. Utilizes NOAA Nautical Charts for spatial marine boundaries.

### D. Safety & Security Layer (Built-in Guardrails)
* **Role:** Enforcement of absolute operational safety boundaries.
* **Responsibilities:** * **Input/Output Sandboxing:** Prevents prompt injection attacks trying to override vessel constraints or bypass environmental safety warnings.
    * **Deterministic Fallbacks:** Automatically overrides the LLM response if the sunset margin is breached or if wind speeds exceed 25 knots at the Golden Gate, forcing a safe short-route alternative to Richmond.

## 5. Spec-Driven Development (SDD) Guidelines for Antigravity Agents
The system logic must be built entirely by defining rigorous behavioral specifications in the Antigravity environment. 
* **Actionable Rule:** Feed explicit constraints to the autonomous code synthesizer (e.g., "If headway tidal current exceeds 2 knots, redirect route closer to the shoreline counter-currents" and "Flag any route exceeding the dynamic sunset safety margin").
* **Goal:** Allow the environment to synthesize stable Python code, ensuring development focus remains on pure mathematical logic and system safety.

## 6. Value Proposition
Sailing Map acts as a safety-first economic optimizer. By merging mathematical precision with an intuitive conversational interface, it significantly mitigates navigation risks, prevents emergency equipment wear from sudden thermal gusts, and reduces the captain's prep time from hours to seconds.

## 7. Localization
The user interface and all autonomous agent outputs must be fully localized. The system must seamlessly support a bilingual toggle between:
* **English**
* **Russian**

## 8. Verified Benchmark Routes (Test Data)
The system offers a built-in database of pre-verified benchmark scenarios starting from Richmond:
* **Richmond to Angel Island:** Easy (Ideal for verifying the agent's basic handling of tidal stream shifts).
* **Richmond to Golden Gate Bridge:** Medium (Requires the algorithms to calculate precise tacks against heavy thermal gusts).
* **Richmond to Bay Bridge past SF:** Medium (Involves navigating complex hydrodynamic conditions in the central bay around the Oakland span, bypassing San Francisco harbors).
