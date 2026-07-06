import math
from datetime import datetime, timedelta
import heapq
from typing import List, Dict, Any, Tuple
from .models import PlanRouteRequest, Leg
from .grid_utils import GridManager

def haversine(lat1, lon1, lat2, lon2):
    R = 3440.065 # radius of Earth in nautical miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def get_bearing(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)
    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    return (math.degrees(math.atan2(y, x)) + 360) % 360

def speed_curve(wind_speed: float, boat_id: str) -> float:
    # simple mock curve
    if wind_speed < 2: return 0.0
    if wind_speed < 5: return 2.0
    if wind_speed < 10: return 4.0
    if wind_speed < 15: return 5.5
    return 6.0 # hull speed

class Pathfinder:
    def __init__(self, grid_manager: GridManager):
        self.gm = grid_manager

    def a_star(self, start_rc, end_rc, req: PlanRouteRequest):
        min_tide = req.tide_window.min_tide_m
        draft = req.boat.draft_m
        
        if not self.gm.is_navigable(start_rc[0], start_rc[1], min_tide, draft):
            return None # Start is not navigable
        if not self.gm.is_navigable(end_rc[0], end_rc[1], min_tide, draft):
            return None # End is not navigable

        open_set = []
        heapq.heappush(open_set, (0.0, start_rc))
        came_from = {}
        g_score = {start_rc: 0.0}
        
        # We need euclidean distance in cells for heuristic
        def h(r, c):
            return math.sqrt((r - end_rc[0])**2 + (c - end_rc[1])**2)

        dirs = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]

        while open_set:
            _, curr = heapq.heappop(open_set)
            
            if curr == end_rc:
                # Reconstruct path
                path = []
                while curr in came_from:
                    path.append(curr)
                    curr = came_from[curr]
                path.append(start_rc)
                path.reverse()
                return path

            for dr, dc in dirs:
                nr, nc = curr[0] + dr, curr[1] + dc
                if not self.gm.is_navigable(nr, nc, min_tide, draft):
                    continue
                
                step_cost = math.sqrt(dr**2 + dc**2)
                lane_multiplier = self.gm.lane_costs[nr, nc]
                cost = step_cost * lane_multiplier

                tentative_g = g_score[curr] + cost
                neighbor = (nr, nc)
                
                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = curr
                    g_score[neighbor] = tentative_g
                    f_score = tentative_g + 3.0 * h(nr, nc)  # Weighted A*
                    heapq.heappush(open_set, (f_score, neighbor))
                    
        return None

    def simplify_path(self, path):
        # Douglas-Peucker simplification mock (just keeping 1 of every N for now if straight)
        # For an MVP, we return a downsampled path, ensuring points are within navigable
        if len(path) <= 2: return path
        simplified = [path[0]]
        for i in range(1, len(path)-1):
            if i % 5 == 0: # crude downsample
                simplified.append(path[i])
        simplified.append(path[-1])
        return simplified

    def evaluate_route(self, path, req: PlanRouteRequest):
        # path is list of (r, c)
        coords = [self.gm.rc_to_lat_lon(r, c) for r, c in path]
        
        # Check wind ceiling
        max_gust = max([wf.gust_kt for wf in req.wind_forecast] + [0])
        effective_cap = min(req.boat.max_wind_kt, 30.0)
        if max_gust > effective_cap:
            return {"status": "infeasible", "reason": "wind_exceeds_ceiling"}
            
        legs = []
        current_time = req.departure_time
        
        # Split into legs
        for i in range(len(coords) - 1):
            lat1, lon1 = coords[i]
            lat2, lon2 = coords[i+1]
            dist_nm = haversine(lat1, lon1, lat2, lon2)
            if dist_nm < 0.01: continue
            
            heading = get_bearing(lat1, lon1, lat2, lon2)
            
            # Find closest wind
            wind = min(req.wind_forecast, key=lambda w: abs((w.time - current_time).total_seconds()))
            
            # Point of sail
            flags = []
            heading_diff = abs((heading - wind.direction_deg + 180) % 360 - 180)
            
            if heading_diff <= 45:
                pos = "upwind"
                flags.append("tacking_required")
                dist_nm *= 1.4
            elif heading_diff >= 150:
                pos = "downwind"
            else:
                pos = "reaching"
                
            if wind.speed_kt < 3:
                flags.append("light_air")
                
            boat_spd = speed_curve(wind.speed_kt, req.boat.speed_curve_id)
            
            # Current (mock projection)
            curr_vec = min(req.current_vectors, key=lambda c: abs((c.time - current_time).total_seconds()))
            curr_diff = abs((heading - curr_vec.direction_deg + 180) % 360 - 180)
            curr_impact = curr_vec.speed_kt * math.cos(math.radians(curr_diff))
            
            sog = boat_spd + curr_impact
            if sog < 0.5:
                sog = 0.5
                flags.append("adverse_current")
                
            leg_duration_hrs = dist_nm / sog
            current_time += timedelta(hours=leg_duration_hrs)
            
            legs.append(Leg(
                from_idx=i,
                to_idx=i+1,
                heading_deg=heading,
                distance_nm=dist_nm,
                point_of_sail=pos,
                est_sog_kt=sog,
                eta=current_time,
                flags=flags
            ))

        sunset_margin = (req.sunset_time - current_time).total_seconds() / 60.0
        if sunset_margin < 30:
            return {"status": "infeasible", "reason": "sunset_violation"}
            
        if any("light_air" in lg.flags for lg in legs) and req.duration_target_min and (current_time - req.departure_time).total_seconds()/60 > req.duration_target_min * 1.5:
            return {"status": "infeasible", "reason": "light_air_duration"}

        return {
            "status": "ok",
            "coordinates": [[lat, lon] for lat, lon in coords],
            "legs": legs,
            "return_eta": current_time,
            "sunset_margin_min": int(sunset_margin)
        }
