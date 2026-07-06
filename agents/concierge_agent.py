from dotenv import load_dotenv
load_dotenv()

from google.antigravity import Agent, LocalAgentConfig, types

import sys
import os
import json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

last_route_data = None

def plan_route(
    start: str,
    end: str,
    departure_time: str,
    pinned_waypoints: list[str],
    boat_draft_m: float,
    boat_speed_curve_id: str,
    boat_max_wind_kt: float,
    wind_forecast: list[dict],
    current_vectors: list[dict],
    tide_window_min_m: float,
    sunset_time: str
) -> dict:
    """Deterministic pathfinding and route evaluation. Use this to plan the sailing route."""
    global last_route_data
    import requests
    import os
    ROUTE_IPC_PATH = os.path.join(os.path.dirname(__file__), '..', 'latest_route.json')
    
    for wf in wind_forecast:
        if "gust_kt" not in wf or wf["gust_kt"] is None:
            wf["gust_kt"] = wf.get("speed_kt", 0.0) * 1.5
        if "direction_deg" not in wf or wf["direction_deg"] is None:
            wf["direction_deg"] = 0.0
            
    for cv in current_vectors:
        if "lat" not in cv or cv["lat"] is None: cv["lat"] = 37.8
        if "lon" not in cv or cv["lon"] is None: cv["lon"] = -122.4
        if "speed_kt" not in cv or cv["speed_kt"] is None: cv["speed_kt"] = 0.0
        if "direction_deg" not in cv or cv["direction_deg"] is None: cv["direction_deg"] = 0.0

    req = {
        "start": start,
        "end": end,
        "departure_time": departure_time,
        "pinned_waypoints": pinned_waypoints,
        "boat": {
            "draft_m": boat_draft_m,
            "speed_curve_id": boat_speed_curve_id,
            "max_wind_kt": boat_max_wind_kt
        },
        "wind_forecast": wind_forecast,
        "current_vectors": current_vectors,
        "tide_window": {
            "min_tide_m": tide_window_min_m
        },
        "sunset_time": sunset_time
    }
    
    router_url = os.environ.get("ROUTER_URL", "http://127.0.0.1:8000/plan_route")
    print("SENDING TO ROUTER:", json.dumps(req, indent=2))
    
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504], allowed_methods=["POST"])
    session.mount('http://', HTTPAdapter(max_retries=retries))

    try:
        res = session.post(router_url, json=req, timeout=15)
        if not res.ok:
            print(f"ROUTER ERROR ({res.status_code}): {res.text}")
            with open("last_422.txt", "w") as f:
                f.write(f"ROUTER ERROR ({res.status_code}): {res.text}\n")
                f.write(f"REQUEST: {json.dumps(req, indent=2)}\n")
        res.raise_for_status()
    except Exception as e:
        print(f"REQUESTS POST EXCEPTION: {e}")
        raise
    
    route_data = res.json()
    with open(ROUTE_IPC_PATH, "w") as f:
        json.dump(route_data, f)
        
    return route_data

weather_mcp = types.McpStdioServer(
    name="weather_server",
    command="python",
    args=["mcp/weather_server.py"]
)

gaz_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'gazetteer.json')
with open(gaz_path, 'r') as f:
    gaz_data = json.load(f)
    gaz_list_str = "\n".join([f"- ID: '{item['id']}' | Name: {item['display_name']} | Aliases: {', '.join(item.get('aliases', []))}" for item in gaz_data])

# --- Agent Configuration ---

config = LocalAgentConfig(
    model="gemini-3.1-flash-lite",
    system_instructions=f"""You are the Concierge Agent for the SailingMap system.
Your role is to plan sailing routes on San Francisco Bay from natural-language trip requests.

Available Gazetteer Waypoints:
{gaz_list_str}

Workflow:
1. Parse the user request to identify the start point, end point, and intermediate stops (pinned_waypoints). Use the exact 'ID' from the Available Gazetteer Waypoints above for any locations mentioned. If the user asks for a round trip (e.g., 'to Golden Gate and back'), set 'start' and 'end' to the same location, and add the destination to 'pinned_waypoints'.
2. If the user asks for a place not in the gazetteer, fail loudly and ask them to choose a known safe-water point. Do NOT invent coordinates or IDs.
3. Call the weather MCP tools (`get_marine_weather`, `get_tides_and_currents`, `get_sunset_time`) to get environmental constraints for the trip. Use boat configuration defaults (e.g. draft_m 1.5, max_wind 25.0) if unstated.
4. Call `plan_route` EXACTLY ONCE. Provide ALL required arguments. `wind_forecast` and `current_vectors` are lists of dictionaries. YOU MUST FORMAT `departure_time` and `sunset_time` strictly as ISO 8601 datetime strings (e.g. '2026-07-06T14:00:00-07:00').
5. Compose a briefing from the `legs[]`, flags, and `sunset_margin_min` returned by the router. Narrate the findings.
   - If the route is 'infeasible', explain the machine-readable reason (e.g. 'sunset_violation', 'wind_exceeds_ceiling') and propose concrete alternatives.
6. Return a response envelope matching this structure:
   ```json
   {{ "briefing_text": "<streamed narration>" }}
   ```
   Do not output the route data yourself, as it will be automatically attached by the backend.
7. Speak in the user's language (English or Russian), but keep all API tool payloads in English/ISO units.
""",
    tools=[plan_route],
    mcp_servers=[weather_mcp]
)

agent = Agent(config)

import asyncio
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

import os
ROUTE_IPC_PATH = os.path.join(os.path.dirname(__file__), '..', 'latest_route.json')

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with agent:
        yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    if os.path.exists(ROUTE_IPC_PATH):
        os.remove(ROUTE_IPC_PATH)
        
    response = await agent.chat(req.message)
    text = await response.text() if hasattr(response, 'text') and callable(getattr(response, 'text')) else str(response)
    
    route_data = None
    if os.path.exists(ROUTE_IPC_PATH):
        with open(ROUTE_IPC_PATH, "r") as f:
            route_data = json.load(f)
            
    return {"response": text, "route_data": route_data}

async def main():
    async with agent:
        print("Concierge Agent CLI is ready. Type 'exit' to quit.")
        while True:
            try:
                user_input = input("You: ")
                if user_input.lower() in ['exit', 'quit']:
                    break
                response = await agent.chat(user_input)
                text = await response.text() if hasattr(response, 'text') and callable(getattr(response, 'text')) else str(response)
                print(f"Agent: {text}")
            except (KeyboardInterrupt, EOFError):
                break
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        asyncio.run(main())
    else:
        import uvicorn
        uvicorn.run("concierge_agent:app", host="127.0.0.1", port=8001, reload=True)
