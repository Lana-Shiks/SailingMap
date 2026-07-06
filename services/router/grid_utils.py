import os
import json
import numpy as np

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')

class GridManager:
    def __init__(self):
        self.depths = None
        self.no_go_zones = None
        self.lane_costs = None
        self.metadata = None
        self.gazetteer = {}
        self.load_data()

    def load_data(self):
        grid_path = os.path.join(DATA_DIR, 'grid.npz')
        if os.path.exists(grid_path):
            data = np.load(grid_path)
            self.depths = data['depths']
            self.no_go_zones = data['no_go_zones']
            self.lane_costs = data['lane_costs']
            self.metadata = data['metadata'] # NORTH, SOUTH, WEST, EAST, RESOLUTION_DEG
            self.lat_steps, self.lon_steps = self.depths.shape
        else:
            print(f"Warning: {grid_path} not found.")

        gaz_path = os.path.join(DATA_DIR, 'gazetteer.json')
        if os.path.exists(gaz_path):
            with open(gaz_path, 'r') as f:
                gaz_list = json.load(f)
                for item in gaz_list:
                    self.gazetteer[item['id']] = item
        else:
            print(f"Warning: {gaz_path} not found.")

    def lat_lon_to_rc(self, lat: float, lon: float):
        if self.metadata is None: return 0, 0
        north, south, west, east, res = self.metadata
        r = int((north - lat) / res)
        c = int((lon - west) / res)
        return max(0, min(r, self.lat_steps - 1)), max(0, min(c, self.lon_steps - 1))

    def rc_to_lat_lon(self, r: int, c: int):
        if self.metadata is None: return 0.0, 0.0
        north, south, west, east, res = self.metadata
        lat = north - (r * res)
        lon = west + (c * res)
        return float(lat), float(lon)

    def is_navigable(self, r: int, c: int, min_tide_m: float, draft_m: float, safety_margin: float = 1.0):
        if not (0 <= r < self.lat_steps and 0 <= c < self.lon_steps):
            return False
        
        # no_go = True means impassable
        if self.no_go_zones[r, c]:
            return False
            
        charted_depth = self.depths[r, c]
        # Depth logic: positive depth means depth below datum? 
        # Wait, in generate_grid.py we used -15m for depth and +1m for land.
        # So "charted_depth" here is negative for underwater.
        # depth rule: charted_depth + tide_window.min_tide >= boat.draft_m + SAFETY_MARGIN (1.0m)
        # Wait, if charted is -15, -15 + (-0.3) = -15.3. We need actual depth magnitude.
        # Let's say depth value in our grid is elevation. Elevation = -Depth.
        # Or actual_depth = -charted_elevation.
        # Let's use elevation: water level = tide. 
        # actual depth = water level - seabed elevation.
        # tide - elevation >= draft + safety
        tide = min_tide_m
        elevation = charted_depth
        actual_depth = tide - elevation
        
        return actual_depth >= (draft_m + safety_margin)
