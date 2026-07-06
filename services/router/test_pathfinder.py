import unittest
from datetime import datetime, timedelta
from services.router.pathfinder import haversine, get_bearing, speed_curve, Pathfinder
from services.router.models import PlanRouteRequest, BoatConfig, WindForecast, CurrentVector, TideWindow
from services.router.grid_utils import GridManager
import numpy as np

class MockGridManager(GridManager):
    def __init__(self):
        # Override init to not load real files
        self.grid_bounds = {"min_lat": 37.8, "max_lat": 37.9, "min_lon": -122.5, "max_lon": -122.3}
        self.lat_steps = 10
        self.lon_steps = 10
        self.metadata = (37.9, 37.8, -122.5, -122.3, 0.01)
        
        # All depths are 10m (navigable) -> elevation -10.0
        self.depths = np.full((10, 10), -10.0)
        self.no_go_zones = np.zeros((10, 10), dtype=bool)
        
        # Block a wall in the middle (elevation -0.5, with tide +1.0 = depth 1.5m. Boat draft is 1.5m + safety 1.0m = 2.5m required. So -0.5 is blocked)
        self.depths[2:8, 5] = -0.5
        
        # Lane costs neutral
        self.lane_costs = np.ones((10, 10))
        self.gazetteer = {}
        
    def load_grid(self):
        pass

class TestPathfinder(unittest.TestCase):
    def test_haversine(self):
        # 1 degree of latitude is ~60 nautical miles
        dist = haversine(0, 0, 1, 0)
        self.assertAlmostEqual(dist, 60.0, places=1)
        
    def test_get_bearing(self):
        # North
        self.assertAlmostEqual(get_bearing(0, 0, 1, 0), 0.0)
        # East
        self.assertAlmostEqual(get_bearing(0, 0, 0, 1), 90.0)
        # South
        self.assertAlmostEqual(get_bearing(1, 0, 0, 0), 180.0)
        # West
        self.assertAlmostEqual(get_bearing(0, 1, 0, 0), 270.0)

    def test_speed_curve(self):
        self.assertEqual(speed_curve(1, "std"), 0.0)
        self.assertEqual(speed_curve(3, "std"), 2.0)
        self.assertEqual(speed_curve(8, "std"), 4.0)
        self.assertEqual(speed_curve(12, "std"), 5.5)
        self.assertEqual(speed_curve(20, "std"), 6.0)

    def test_a_star_navigable(self):
        gm = MockGridManager()
        pf = Pathfinder(gm)
        
        boat = BoatConfig(draft_m=1.5, speed_curve_id="std_keel", max_wind_kt=25.0)
        req = PlanRouteRequest(
            start="A", end="B",
            departure_time=datetime.now(),
            boat=boat,
            wind_forecast=[], current_vectors=[],
            tide_window=TideWindow(min_tide_m=1.0),
            sunset_time=datetime.now()
        )
        
        start_rc = (1, 1)
        end_rc = (1, 8)
        
        path = pf.a_star(start_rc, end_rc, req)
        self.assertIsNotNone(path)
        self.assertEqual(path[0], start_rc)
        self.assertEqual(path[-1], end_rc)
        
    def test_a_star_unnavigable_start(self):
        gm = MockGridManager()
        pf = Pathfinder(gm)
        
        boat = BoatConfig(draft_m=1.5, speed_curve_id="std_keel", max_wind_kt=25.0)
        req = PlanRouteRequest(
            start="A", end="B",
            departure_time=datetime.now(),
            boat=boat,
            wind_forecast=[], current_vectors=[],
            tide_window=TideWindow(min_tide_m=1.0),
            sunset_time=datetime.now()
        )
        
        start_rc = (5, 5) # Blocked (0.5m depth + 1m tide = 1.5m water, draft 1.5m -> not navigable)
        end_rc = (1, 8)
        
        path = pf.a_star(start_rc, end_rc, req)
        self.assertIsNone(path)

    def test_evaluate_route_wind_exceeds_ceiling(self):
        gm = MockGridManager()
        pf = Pathfinder(gm)
        
        boat = BoatConfig(draft_m=1.5, speed_curve_id="std_keel", max_wind_kt=15.0)
        wind = [WindForecast(time=datetime.now(), speed_kt=20.0, gust_kt=35.0, direction_deg=270.0)]
        req = PlanRouteRequest(
            start="A", end="B",
            departure_time=datetime.now(),
            boat=boat,
            wind_forecast=wind, current_vectors=[],
            tide_window=TideWindow(min_tide_m=1.0),
            sunset_time=datetime.now() + timedelta(hours=5)
        )
        
        path = [(1, 1), (1, 2)]
        res = pf.evaluate_route(path, req)
        self.assertEqual(res["status"], "infeasible")
        self.assertEqual(res["reason"], "wind_exceeds_ceiling")

    def test_evaluate_route_sunset_violation(self):
        gm = MockGridManager()
        pf = Pathfinder(gm)
        
        boat = BoatConfig(draft_m=1.5, speed_curve_id="std_keel", max_wind_kt=25.0)
        wind = [WindForecast(time=datetime.now(), speed_kt=10.0, gust_kt=15.0, direction_deg=270.0)]
        current = [CurrentVector(time=datetime.now(), lat=0, lon=0, speed_kt=0.0, direction_deg=0.0)]
        
        req = PlanRouteRequest(
            start="A", end="B",
            departure_time=datetime.now(),
            boat=boat,
            wind_forecast=wind, current_vectors=current,
            tide_window=TideWindow(min_tide_m=1.0),
            # Sunset is in 20 minutes (too close)
            sunset_time=datetime.now() + timedelta(minutes=20)
        )
        
        # A long path to guarantee duration > 20 min or just evaluating sunset margin
        path = [(1, 1), (9, 9)]
        res = pf.evaluate_route(path, req)
        self.assertEqual(res["status"], "infeasible")
        self.assertEqual(res["reason"], "sunset_violation")

if __name__ == '__main__':
    unittest.main()
