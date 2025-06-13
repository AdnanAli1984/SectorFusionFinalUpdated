import numpy as np
from scipy.optimize import minimize, curve_fit
from sklearn.cluster import DBSCAN
import pandas as pd
import time

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate the great circle distance between two points"""
    R = 6371  # Earth's radius in kilometers
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    return R * c * 1000  # Convert to meters

def calculate_bearing(lat1, lon1, lat2, lon2):
    """Calculate the bearing (azimuth) between two points"""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    y = np.sin(dlon) * np.cos(lat2)
    x = np.cos(lat1) * np.sin(lat2) - np.sin(lat1) * np.cos(lat2) * np.cos(dlon)
    initial_bearing = np.arctan2(y, x)
    initial_bearing = np.degrees(initial_bearing)
    return (initial_bearing + 360) % 360

def calculate_actual_coordinates(group, lat_col, lon_col, rsrp_col):
    """
    Calculate actual site coordinates using only MR data points
    """
    try:
        # Get all measurement points
        points = group[[lat_col, lon_col]].values
        
        # Calculate centroid as initial reference
        init_lat = np.mean(points[:, 0])
        init_lon = np.mean(points[:, 1])
        
        # Find points forming the densest cluster
        distances = np.array([
            calculate_distance(init_lat, init_lon, p[0], p[1])
            for p in points
        ])
        
        # Focus on points within 200m
        close_mask = distances <= 200
        if np.sum(close_mask) >= 5:
            close_points = points[close_mask]
            
            # Use DBSCAN to find the core cluster
            clustering = DBSCAN(
                eps=0.0002,  # ~20m
                min_samples=3
            ).fit(close_points)
            
            # Find largest cluster
            if len(np.unique(clustering.labels_[clustering.labels_ != -1])) > 0:
                labels = pd.Series(clustering.labels_)
                largest_cluster = labels[labels != -1].mode()[0]
                cluster_points = close_points[clustering.labels_ == largest_cluster]
                
                if len(cluster_points) >= 3:
                    # Use median of cluster points
                    final_lat = np.median(cluster_points[:, 0])
                    final_lon = np.median(cluster_points[:, 1])
                    return final_lat, final_lon
        
        return init_lat, init_lon
        
    except Exception as e:
        print(f"Error in calculate_actual_coordinates: {str(e)}")
        return group[lat_col].mean(), group[lon_col].mean()

def calculate_sector_azimuth(cell_data, site_lat, site_lon, lat_col, lon_col, ep_lat=None, ep_lon=None, site_id=None, cell_id=None, carrier=None, planned_azimuth=None):
    """
    Calculate actual azimuth using EP coordinates first, then fall back to actual coordinates
    Added debugging for azimuth calculations
    """
    try:
        # Get measurement points for this cell
        points = cell_data[[lat_col, lon_col]].values
        
        print(f"\n{'='*80}")
        print(f"Azimuth Calculation Debug for Site: {site_id}, Cell: {cell_id}, Carrier: {carrier}")
        print(f"Planned Azimuth: {planned_azimuth}°")
        print(f"{'='*80}")
        
        # Try EP coordinates first if available
        if ep_lat is not None and ep_lon is not None:
            print(f"\nAttempting azimuth calculation with EP coordinates:")
            print(f"EP Latitude: {ep_lat}, EP Longitude: {ep_lon}")
            
            # Calculate angles and distances using EP coordinates
            ep_angles = []
            ep_distances = []
            
            for point in points:
                dist = calculate_distance(ep_lat, ep_lon, point[0], point[1])
                angle = calculate_bearing(ep_lat, ep_lon, point[0], point[1])
                if dist <= 500:  # Consider points within 500m
                    ep_angles.append(angle)
                    ep_distances.append(dist)
            
            print(f"Found {len(ep_angles)} valid measurement points using EP coordinates")
            
            # If we have enough points with EP coordinates
            if len(ep_angles) >= 5:
                print("\nUSING EP COORDINATES for azimuth calculation")
                angles = np.array(ep_angles)
                distances = np.array(ep_distances)
                used_lat = ep_lat
                used_lon = ep_lon
                coord_type = "EP"
            else:
                print(f"\nInsufficient points with EP coordinates ({len(ep_angles)} < 5)")
                print("FALLING BACK to actual coordinates:")
                print(f"Actual Latitude: {site_lat}, Actual Longitude: {site_lon}")
                
                # Fall back to actual coordinates
                angles = []
                distances = []
                for point in points:
                    dist = calculate_distance(site_lat, site_lon, point[0], point[1])
                    angle = calculate_bearing(site_lat, site_lon, point[0], point[1])
                    if dist <= 500:
                        angles.append(angle)
                        distances.append(dist)
                angles = np.array(angles)
                distances = np.array(distances)
                used_lat = site_lat
                used_lon = site_lon
                coord_type = "Actual"
                print(f"Found {len(angles)} valid measurement points using actual coordinates")
        else:
            print("\nNo EP coordinates available, using actual coordinates")
            angles = []
            distances = []
            for point in points:
                dist = calculate_distance(site_lat, site_lon, point[0], point[1])
                angle = calculate_bearing(site_lat, site_lon, point[0], point[1])
                if dist <= 500:
                    angles.append(angle)
                    distances.append(dist)
            angles = np.array(angles)
            distances = np.array(distances)
            used_lat = site_lat
            used_lon = site_lon
            coord_type = "Actual"
            print(f"Found {len(angles)} valid measurement points using actual coordinates")

        # If we don't have enough points with either method
        if len(angles) < 5:
            print("\nINSUFFICIENT POINTS for azimuth calculation with both methods")
            print(f"Final Result: Azimuth = 0.0° (using {coord_type} coordinates)")
            if planned_azimuth is not None:
                print(f"Azimuth Difference: N/A (insufficient data)")
            print(f"{'-'*80}")
            return 0.0

        # Divide into distance bands to analyze pattern
        distance_bands = [(0, 100), (100, 200), (200, 300), (300, 400), (400, 500)]
        band_directions = []
        
        print("\nDistance Band Analysis:")
        for dist_min, dist_max in distance_bands:
            band_mask = (distances >= dist_min) & (distances < dist_max)
            band_angles = angles[band_mask]
            
            if len(band_angles) >= 5:
                # Use rolling 20° windows to find densest direction
                angle_bins = np.arange(0, 360, 20)
                counts = []
                
                for center in angle_bins:
                    window_angles = ((band_angles - center + 180) % 360) - 180
                    count = np.sum(np.abs(window_angles) <= 10)
                    counts.append((center, count))
                
                if counts:
                    max_direction = max(counts, key=lambda x: x[1])
                    band_directions.append((max_direction[0], max_direction[1], dist_min))
                    print(f"Band {dist_min}-{dist_max}m: {len(band_angles)} points, " 
                          f"Peak direction: {max_direction[0]}°")
        
        if not band_directions:
            print(f"\nNo valid direction bands found with {coord_type} coordinates")
            print(f"Final Result: Azimuth = 0.0° (using {coord_type} coordinates)")
            if planned_azimuth is not None:
                print(f"Azimuth Difference: N/A (no valid bands)")
            print(f"{'-'*80}")
            return 0.0
            
        # Weight directions by point count and inverse distance
        total_weight = 0
        weighted_sum = 0
        
        print("\nBand Weighting:")
        for angle, count, dist in band_directions:
            weight = count * (1 / (dist + 100))
            weighted_sum += angle * weight
            total_weight += weight
            print(f"Band starting at {dist}m: Angle = {angle}°, Points = {count}, "
                  f"Weight = {weight:.2f}")
            
        if total_weight > 0:
            final_azimuth = weighted_sum / total_weight
            print(f"\nFINAL RESULT:")
            print(f"Calculated Azimuth: {final_azimuth:.2f}° (using {coord_type} coordinates)")
            if planned_azimuth is not None:
                azimuth_diff = abs(final_azimuth - planned_azimuth)
                print(f"Planned Azimuth: {planned_azimuth}°")
                print(f"Azimuth Difference: {azimuth_diff:.2f}°")
            print(f"{'-'*80}")
            return round(final_azimuth, 2)
        
        print(f"\nNo valid weighted sum calculated")
        print(f"Final Result: Azimuth = 0.0° (using {coord_type} coordinates)")
        if planned_azimuth is not None:
            print(f"Azimuth Difference: N/A (no valid calculation)")
        print(f"{'-'*80}")
        return 0.0
        
    except Exception as e:
        print(f"\nError in calculate_sector_azimuth: {str(e)}")
        print(f"Final Result: Azimuth = 0.0° (error occurred)")
        if planned_azimuth is not None:
            print(f"Azimuth Difference: N/A (error)")
        print(f"{'-'*80}")
        return 0.0

    
def calculate_tilt(distances, rsrp_values):
    """Calculate the antenna tilt based on distance and RSRP measurements"""
    def rsrp_model(d, tilt):
        return -10 * 3.5 * np.log10(d) - 20 * np.log10(4 * np.pi * 2100 / 3e8) - tilt * d

    try:
        popt, _ = curve_fit(rsrp_model, distances, rsrp_values, p0=[0])
        tilt = popt[0]
        tilt_degrees = np.arctan(tilt) * 180 / np.pi
        return tilt_degrees
    except:
        return 0.0

def process_site(group, mappings, ep_data=None):
    """Process each site using EP coordinates first for azimuth calculation"""
    try:
        # Get column names from mappings
        lat_col = mappings['MR Latitude']
        lon_col = mappings['MR Longitude']
        rsrp_col = mappings['MR RSRP']
        cell_id_col = mappings['MR Cell ID']
        site_id_col = mappings['MR Site ID']

        # Calculate actual coordinates
        actual_lat, actual_lon = calculate_actual_coordinates(
            group, lat_col, lon_col, rsrp_col
        )

        # Get EP coordinates and planned azimuth
        ep_lat = None
        ep_lon = None
        site_id = group[site_id_col].iloc[0]
        
        if ep_data is not None:
            site_ep_data = ep_data[ep_data[mappings['EP Site ID']] == site_id]
            if not site_ep_data.empty:
                ep_lat = float(site_ep_data[mappings['EP Latitude']].iloc[0])
                ep_lon = float(site_ep_data[mappings['EP Longitude']].iloc[0])

        results = []
        # Process each cell
        for cell_id in group[cell_id_col].unique():
            cell_mask = group[cell_id_col] == cell_id
            cell_data = group[cell_mask]
            
            # Get carrier and planned azimuth for this cell
            if ep_data is not None:
                cell_ep_data = ep_data[
                    (ep_data[mappings['EP Site ID']] == site_id) & 
                    (ep_data[mappings['EP Cell ID']] == cell_id)
                ]
                if not cell_ep_data.empty:
                    carrier = cell_ep_data[mappings['Carrier']].iloc[0]
                    planned_azimuth = float(cell_ep_data[mappings['EP Azimuth']].iloc[0])
                else:
                    carrier = "Unknown"
                    planned_azimuth = None
            else:
                carrier = "Unknown"
                planned_azimuth = None
            
            # Calculate azimuth using EP coordinates first
            azimuth = calculate_sector_azimuth(
                cell_data, actual_lat, actual_lon,
                lat_col, lon_col, ep_lat, ep_lon,
                site_id, cell_id, carrier, planned_azimuth
            )
            
            # Calculate other parameters
            cell_lats = cell_data[lat_col].values
            cell_lons = cell_data[lon_col].values
            cell_rsrp = cell_data[rsrp_col].values
            
            distances = np.array([
                calculate_distance(actual_lat, actual_lon, clat, clon)
                for clat, clon in zip(cell_lats, cell_lons)
            ])
            
            tilt = calculate_tilt(distances[distances > 0], cell_rsrp[distances > 0])
            
            results.append({
                'Site ID': site_id,
                'Cell ID': cell_id,
                'Actual Latitude': actual_lat,
                'Actual Longitude': actual_lon,
                'Actual Azimuth': azimuth,
                'Actual Tilt': tilt
            })
        
        return results
        
    except Exception as e:
        print(f"Error in process_site: {str(e)}")
        return [{
            'Site ID': site_id,
            'Cell ID': group[cell_id_col].iloc[0],
            'Actual Latitude': group[lat_col].mean(),
            'Actual Longitude': group[lon_col].mean(),
            'Actual Azimuth': 0.0,
            'Actual Tilt': 0.0
        }]