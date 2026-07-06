import os
import glob
import numpy as np
from scipy.ndimage import distance_transform_edt

# Central Bay Bounding Box (focusing on benchmark routes)
NORTH = 37.92
SOUTH = 37.77
WEST = -122.49
EAST = -122.30
RESOLUTION_DEG = 0.0001  # ~11m resolution

LAT_STEPS = int(np.ceil((NORTH - SOUTH) / RESOLUTION_DEG))
LON_STEPS = int(np.ceil((EAST - WEST) / RESOLUTION_DEG))

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data')

def load_local_nos():
    print("Parsing NOS bathymetry from local XYZ files...")
    import glob
    import gzip
    import csv
    
    nos_dir = os.path.join(DATA_DIR, 'nos-item-606320')
    xyz_files = glob.glob(os.path.join(nos_dir, '**', '*.xyz.gz'), recursive=True)
    
    points = []
    values = []
    
    for fp in xyz_files:
        try:
            with gzip.open(fp, 'rt') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'lat' in row and 'long' in row and 'depth' in row:
                        try:
                            lat = float(row['lat'])
                            lon = float(row['long'])
                            depth = float(row['depth'])
                            
                            # Filter points within our target area with a small buffer for better interpolation
                            if (WEST - 0.05 <= lon <= EAST + 0.05) and (SOUTH - 0.05 <= lat <= NORTH + 0.05):
                                points.append((lat, lon))
                                # Convert downward depth to negative elevation
                                values.append(-depth)
                        except ValueError:
                            continue
        except Exception as e:
            print(f"Error reading {fp}: {e}")
            
    if not points:
        raise ValueError("No data points found within the bounding box.")
        
    print(f"Loaded {len(points)} points from NOS dataset.")
    return np.array(points), np.array(values)

def generate_grid():
    print(f"Generating high-res grid: {LAT_STEPS}x{LON_STEPS} cells at {RESOLUTION_DEG} deg resolution.")
    from scipy.interpolate import griddata
    
    # 1. Generate target grid coordinates
    lat_grid = np.linspace(NORTH, SOUTH, LAT_STEPS)
    lon_grid = np.linspace(WEST, EAST, LON_STEPS)
    lon_mesh, lat_mesh = np.meshgrid(lon_grid, lat_grid)
    
    # 2. Get real NOAA Data
    try:
        points, values = load_local_nos()
        print("Interpolating NOS bathymetry to high-resolution grid...")
        depths = griddata(points, values, (lat_mesh, lon_mesh), method='linear', fill_value=1.0)
        depths = np.nan_to_num(depths, nan=1.0)
    except Exception as e:
        print(f"Failed to load local bathymetry: {e}")
        print("Falling back to flat deep water (-15m) for testing.")
        depths = np.full((LAT_STEPS, LON_STEPS), -15.0, dtype=np.float32)

    # Note: Depth is elevation in ETOPO. Negative is underwater.
    # Determine land (elevation >= 0)
    land_mask = depths >= 0
    
    print("Computing 10m safety buffer...")
    # Buffer 1 cell (~11m) from land
    # distance_transform_edt computes distance from background (0).
    dist_from_land = distance_transform_edt(~land_mask)
    
    # no_go_zones includes land AND cells within 1.0 cell distance from land (~11m safety buffer)
    no_go_zones = (dist_from_land <= 1.0) & (~land_mask)
    no_go_zones = no_go_zones | land_mask

    # Add shipping lane costs (simple static for now)
    lane_costs = np.ones_like(depths, dtype=np.float32)
    lane_c = int(((-122.470) - WEST) / RESOLUTION_DEG)
    if 0 <= lane_c < LON_STEPS:
        # 400m lane width (approx 36 cells at 11m res)
        lane_costs[:, max(0, lane_c-18):min(LON_STEPS, lane_c+18)] = 3.0

    os.makedirs(DATA_DIR, exist_ok=True)
    out_path = os.path.join(DATA_DIR, 'grid.npz')
    
    np.savez_compressed(
        out_path,
        depths=depths.astype(np.float32),
        no_go_zones=no_go_zones,
        lane_costs=lane_costs,
        metadata=np.array([NORTH, SOUTH, WEST, EAST, RESOLUTION_DEG])
    )
    print(f"Saved grid artifact to {out_path}")

if __name__ == "__main__":
    generate_grid()
