import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

def calculate_distance(lat1, lon1, lat2, lon2):
    import math
    R = 6371
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance = R * c
    return distance * 1000

def calculate_azimuth(lat1, lon1, lat2, lon2):
    import math
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    azimuth = math.atan2(y, x)
    azimuth = math.degrees(azimuth)
    azimuth = (azimuth + 360) % 360
    return azimuth

def calculate_actual_azimuth_with_centroid(mr_data, ep_data, mappings, site_id, cell_id, carrier, min_points=30, max_distance=2000):
    """
    Robust centroid-based actual azimuth calculation for a single cell:
    - Filter MR points within max_distance of site
    - Optionally cluster with DBSCAN to find main lobe
    - Use centroid (unweighted)
    - Calculate azimuth from EP site coordinates to centroid using Google/compass convention
    Returns: float (azimuth in degrees) or None if not enough MR points
    """
    try:
        # Generate EP_key and MR_key if not present in mappings
        if 'EP_key' not in mappings:
            ep_data['EP_key'] = ep_data[mappings['EP Site ID']].astype(str) + '_' + ep_data[mappings['EP Cell ID']].astype(str)
            mappings['EP_key'] = 'EP_key'
        if 'MR_key' not in mappings:
            mr_data['MR_key'] = mr_data[mappings['MR Site ID']].astype(str) + '_' + mr_data[mappings['MR Cell ID']].astype(str)
            mappings['MR_key'] = 'MR_key'

        # Always use 'Carrier_Lookup' for MR filtering, create if missing
        if 'Carrier_Lookup' not in mr_data.columns:
            ep_key_to_carrier = dict(zip(ep_data[mappings['EP_key']], ep_data[mappings['Carrier']]))
            mr_data['Carrier_Lookup'] = mr_data[mappings['MR_key']].map(ep_key_to_carrier)

        # Filter EP row using mappings['Carrier']
        ep_row = ep_data[(ep_data[mappings['EP Site ID']] == site_id) & 
                        (ep_data[mappings['EP Cell ID']] == cell_id) & 
                        (ep_data[mappings['Carrier']] == carrier)]
        if ep_row.empty:
            return None
        ep_row = ep_row.iloc[0]
        ep_lat = float(ep_row[mappings['EP Latitude']])
        ep_lon = float(ep_row[mappings['EP Longitude']])

        # Get all MR points for this cell and carrier at this site using Carrier_Lookup
        mr_points = mr_data[(mr_data[mappings['MR Site ID']] == site_id) & 
                          (mr_data[mappings['MR Cell ID']] == cell_id) & 
                          (mr_data['Carrier_Lookup'] == carrier)]

        if len(mr_points) < min_points:
            return None

        coords = mr_points[[mappings['MR Latitude'], mappings['MR Longitude']]].values.astype(float)
        
        # Filter by distance from site
        dists = np.array([calculate_distance(ep_lat, ep_lon, lat, lon) for lat, lon in coords])
        in_range = dists < max_distance
        coords = coords[in_range]
        
        if len(coords) < min_points:
            return None

        # Optionally cluster with DBSCAN to find main lobe
        if len(coords) > 100:
            clustering = DBSCAN(eps=0.0015, min_samples=10).fit(coords)
            labels = clustering.labels_
            valid = labels != -1
            if np.any(valid):
                main_label = pd.Series(labels[valid]).mode()[0]
                cluster_coords = coords[labels == main_label]
                if len(cluster_coords) >= min_points:
                    coords = cluster_coords

        # Centroid (unweighted)
        centroid_lat = np.mean(coords[:, 0])
        centroid_lon = np.mean(coords[:, 1])
        
        # Calculate azimuth from EP site coordinates to centroid
        actual_azimuth = calculate_azimuth(ep_lat, ep_lon, centroid_lat, centroid_lon)
        return actual_azimuth
        
    except Exception as e:
        print(f"Error in calculate_actual_azimuth_with_centroid: {str(e)}")
        return None 