# Sailing Maps: Richmond Navigator - Implementation Plan

Building a full-stack web application serving as an AI-driven sailing navigation guide for the San Francisco Bay Area using Google ADK 2.0.

## Proposed Changes

### 1. Project Initialization & Scaffold

- The API key has been provided via a `.env` file.
- Initialize a new Next.js project with React in the `SailingMapV2` directory.
- Scaffold the basic directory structure for the frontend UI, agents, and the local MCP server.

### 2. Multi-Agent Architecture (ADK 2.0)

- **Concierge Agent**: Create the supervisor agent definition to manage conversation state, collect boat specs, and route user intents.
- **Weather Agent (MCP Server)**:
  - Create a local MCP server that integrates with external APIs:
    - NOAA CO-OPS API (Tidal & Current Vectors)
    - Open-Meteo Marine API (Wind & Weather Forecasts)
    - SunriseSunset.io API (Dynamic Sunset Calculator)
- **Routing Agent**:
  - Implement Python scripts/tools (Agent Skills) for physics-bound pathfinding, evaluating wind-current intersections, tacking efficiency, and return margins.
- **Safety & Security Layer**:
  - Implement deterministic fallbacks to override AI responses if the sunset margin is breached or wind speeds exceed 25 knots at the Golden Gate.

### 3. Frontend & UI (Next.js)

- Implement a rich, dynamic, and responsive UI with modern aesthetics (glassmorphism, curated colors, micro-animations) using Next.js and React.
- Integrate **Leaflet.js** to dynamically plot AI-generated routes, safety zones, and waypoints.
- Implement localization (EN/RU) using a simple dictionary-based approach mapped to the Concierge Agent's output.

## Verification Plan

### Automated Tests
- Unit tests for the Routing Agent's Python pathfinding logic to ensure strict adherence to physics and safety constraints.
- Mock tests for the MCP Weather Server API endpoints to ensure resilient data parsing.

### Manual Verification
- Test all four benchmark scenarios (Richmond to Berkeley, Angel Island, Golden Gate Bridge, Bay Bridge).
- Verify the bilingual UI switching (English/Russian) works seamlessly.
- Trigger safety fallbacks manually (e.g., mock wind > 25 knots) to ensure deterministic overrides function correctly.
