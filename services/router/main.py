from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from .models import PlanRouteRequest, PlanRouteResponse
from .grid_utils import GridManager
from .pathfinder import Pathfinder
import itertools

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

gm = GridManager()
pf = Pathfinder(gm)

@app.post("/plan_route", response_model=PlanRouteResponse)
def plan_route(req: PlanRouteRequest):
    if req.start not in gm.gazetteer:
        raise HTTPException(status_code=400, detail=f"Unknown start: {req.start}")
    
    start_pt = gm.gazetteer[req.start]
    end_pt = gm.gazetteer.get(req.end, start_pt)
    
    start_rc = gm.lat_lon_to_rc(start_pt['lat'], start_pt['lon'])
    end_rc = gm.lat_lon_to_rc(end_pt['lat'], end_pt['lon'])
    
    # Very simple duration fitting if pinned_waypoints exist or end != start
    # Just route through the points
    waypoints = [start_rc]
    for wp_id in req.pinned_waypoints:
        if wp_id in gm.gazetteer:
            wp = gm.gazetteer[wp_id]
            waypoints.append(gm.lat_lon_to_rc(wp['lat'], wp['lon']))
    waypoints.append(end_rc)
    
    full_path = []
    for i in range(len(waypoints)-1):
        segment = pf.a_star(waypoints[i], waypoints[i+1], req)
        if not segment:
            return PlanRouteResponse(status="infeasible", reason="no_navigable_path")
        if i > 0:
            full_path.extend(segment[1:])
        else:
            full_path.extend(segment)
            
    simplified = pf.simplify_path(full_path)
    result = pf.evaluate_route(simplified, req)
    
    if result["status"] != "ok":
        return PlanRouteResponse(status=result["status"], reason=result["reason"])
        
    # Note: proper duration fitting loops would evaluate multiple candidates here
    
    return PlanRouteResponse(
        status=result["status"],
        coordinates=result["coordinates"],
        legs=result["legs"],
        return_eta=result["return_eta"],
        sunset_margin_min=result["sunset_margin_min"]
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
