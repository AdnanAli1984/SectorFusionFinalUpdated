import numpy as np
from sklearn.cluster import DBSCAN
import pandas as pd
from scipy.spatial import ConvexHull
from typing import Tuple, List, Dict, Optional
from tilt import calculate_actual_coordinates

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points in meters"""
    R = 6371  # Earth's radius in kilometers
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    return R * c * 1000  # Convert to meters

def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the bearing (azimuth) between two points"""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    y = np.sin(dlon) * np.cos(lat2)
    x = np.cos(lat1) * np.sin(lat2) - np.sin(lat1) * np.cos(lat2) * np.cos(dlon)
    initial_bearing = np.arctan2(y, x)
    initial_bearing = np.degrees(initial_bearing)
    return (initial_bearing + 360) % 360

def validate_ep_coordinates(mr_data: pd.DataFrame, ep_lat: float, ep_lon: float, 
                          lat_col: str, lon_col: str, radius: int = 1000) -> bool:
    """Validate if EP coordinates have sufficient MR points within specified radius"""
    try:
        distances = np.array([
            calculate_distance(ep_lat, ep_lon, row[lat_col], row[lon_col])
            for _, row in mr_data.iterrows()
        ])
        points_within_radius = np.sum(distances <= radius)
        return points_within_radius >= 10
    except Exception as e:
        print(f"Error in validate_ep_coordinates: {str(e)}")
        return False

def calculate_grid_center(points: np.ndarray) -> Tuple[float, float]:
    """Calculate the center of a grid of points using convex hull centroid"""
    try:
        if len(points) < 3:
            return np.mean(points[:, 0]), np.mean(points[:, 1])
        hull = ConvexHull(points)
        hull_points = points[hull.vertices]
        return np.mean(hull_points[:, 0]), np.mean(hull_points[:, 1])
    except Exception as e:
        print(f"Error in calculate_grid_center: {str(e)}")
        return np.mean(points[:, 0]), np.mean(points[:, 1])

# Change this function name
def process_grid_based_site(mr_data: pd.DataFrame, mappings: Dict[str, str], 
                          ep_data: Optional[pd.DataFrame] = None) -> List[Dict]:
    """Process site using grid-based azimuth calculation method"""
    # Initialize variables at the start
    site_id = None
    cell_id = None
    lat_col = mappings['MR Latitude']
    lon_col = mappings['MR Longitude']
    cell_id_col = mappings['MR Cell ID']
    site_id_col = mappings['MR Site ID']

    try:
        site_id = mr_data[site_id_col].iloc[0]
        # Process coordinates and calculate azimuth
        results = []
        for cell_id in mr_data[cell_id_col].unique():
            cell_data = mr_data[mr_data[cell_id_col] == cell_id]
            
            # Get site coordinates
            if ep_data is not None:
                site_ep_data = ep_data[ep_data[mappings['EP Site ID']] == site_id]
                if not site_ep_data.empty:
                    site_lat = float(site_ep_data[mappings['EP Latitude']].iloc[0])
                    site_lon = float(site_ep_data[mappings['EP Longitude']].iloc[0])
                else:
                    site_lat, site_lon = calculate_actual_coordinates(
                        cell_data, lat_col, lon_col
                    )
            else:
                site_lat, site_lon = calculate_actual_coordinates(
                    cell_data, lat_col, lon_col
                )

            # Calculate grid-based azimuth
            points = []
            for _, row in cell_data.iterrows():
                dist = calculate_distance(site_lat, site_lon, row[lat_col], row[lon_col])
                if dist <= 1000:  # 1000m radius
                    points.append([row[lat_col], row[lon_col]])

            if len(points) >= 5:
                points = np.array(points)
                grid_center_lat, grid_center_lon = calculate_grid_center(points)
                actual_azimuth = calculate_bearing(site_lat, site_lon, 
                                                 grid_center_lat, grid_center_lon)
            else:
                actual_azimuth = 0.0

            results.append({
                'Site ID': site_id,
                'Cell ID': cell_id,
                'Actual Latitude': site_lat,
                'Actual Longitude': site_lon,
                'Actual Azimuth': round(actual_azimuth, 2)
            })

        return results

    except Exception as e:
        print(f"Error in process_grid_based_site: {str(e)}")
        return [{
            'Site ID': site_id,
            'Cell ID': cell_id,
            'Actual Latitude': mr_data[lat_col].mean(),
            'Actual Longitude': mr_data[lon_col].mean(),
            'Actual Azimuth': 0.0
        }]