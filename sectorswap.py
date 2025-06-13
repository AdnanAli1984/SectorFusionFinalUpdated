import pandas as pd 
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import math
import json
import os
from tilt import calculate_sector_azimuth
from sklearn.cluster import DBSCAN
from azimuth_utils import calculate_actual_azimuth_with_centroid

class SectorSwapCalculator:
    def __init__(self):
        self.FIXED_BEAMWIDTH = 65
        self.FIXED_DISTANCE = 1500
        self.param_settings = self.load_parameter_settings()

    def load_parameter_settings(self):
        try:
            if os.path.exists('Parameter_Settings.json'):
                with open('Parameter_Settings.json', 'r') as f:
                    return json.load(f)
            return {'sector_split': [], 'massive_mimo': []}
        except Exception as e:
            print(f"Error loading parameter settings: {str(e)}")
            return {'sector_split': [], 'massive_mimo': []}

    def check_sector_split_pair(self, site_name, cell_id, carrier, ep_data, mappings):
        """
        Check if the cell is part of a sector split pair by looking for its matching parent/child
        """
        try:
            for split in self.param_settings.get('sector_split', []):
                if split['Layer'] == carrier:
                    # Check if current cell is parent
                    if str(cell_id) == str(split['Parrent ID']):
                        # Look for child in same site
                        child_exists = ep_data[
                            (ep_data[mappings['EP Site ID']] == site_name) & 
                            (ep_data[mappings['EP Cell ID']].astype(str) == str(split['Child ID']))
                        ].shape[0] > 0
                        if child_exists:
                            return True, str(split['Child ID'])
                    # Check if current cell is child
                    elif str(cell_id) == str(split['Child ID']):
                        # Look for parent in same site
                        parent_exists = ep_data[
                            (ep_data[mappings['EP Site ID']] == site_name) & 
                            (ep_data[mappings['EP Cell ID']].astype(str) == str(split['Parrent ID']))
                        ].shape[0] > 0
                        if parent_exists:
                            return True, str(split['Parrent ID'])
            return False, None
        except Exception as e:
            print(f"Error checking sector split pair: {str(e)}")
            return False, None

    def check_massive_mimo_group(self, site_name, cell_id, carrier, ep_data, mappings):
        """
        Check if the cell is part of a massive MIMO group by checking all beam cells exist
        """
        try:
            for mimo in self.param_settings.get('massive_mimo', []):
                if mimo['Layer'] == carrier:
                    beam_ids = [str(mimo[f'Beam{i}']) for i in range(4)]
                    # If current cell is one of the beams
                    if str(cell_id) in beam_ids:
                        # Check if all other beams exist for this site
                        all_beams_exist = True
                        for beam_id in beam_ids:
                            beam_exists = ep_data[
                                (ep_data[mappings['EP Site ID']] == site_name) & 
                                (ep_data[mappings['EP Cell ID']].astype(str) == beam_id)
                            ].shape[0] > 0
                            if not beam_exists:
                                all_beams_exist = False
                                break
                        if all_beams_exist:
                            return True, beam_ids
            return False, None
        except Exception as e:
            print(f"Error checking massive MIMO group: {str(e)}")
            return False, None

    def build_azimuth_result_table(self, mr_data, ep_data, mappings, min_points=30, max_distance=2000):
        """
        Build the azimuth result table using the same logic as ActualAzimuthWindow.calculate_actual_azimuth_with_centroid.
        Returns a DataFrame with columns:
        ['eNodeb Name', 'Cell ID', 'Carrier', 'Planned Azimuth', 'Actual Azimuth', 'Azimuth Difference', 'Actual Latitude', 'Actual Longitude', 'Result']
        """
        results = []
        # Collect all split cells by site and carrier
        split_cells = set()
        for split in self.param_settings.get('sector_split', []):
            split_cells.add((split['Layer'], str(split['Parrent ID'])))
            split_cells.add((split['Layer'], str(split['Child ID'])))
        for _, ep_row in ep_data.iterrows():
            cell_id = str(ep_row[mappings['EP Cell ID']])
            carrier = ep_row[mappings['Carrier']]
            site_id = ep_row[mappings['EP Site ID']]
            ep_lat = float(ep_row[mappings['EP Latitude']])
            ep_lon = float(ep_row[mappings['EP Longitude']])
            planned_azimuth = float(ep_row[mappings['EP Azimuth']])
            is_split = (carrier, cell_id) in split_cells
            if is_split:
                print(f"[AZIMUTH DEBUG] Calculating actual azimuth for split cell: Site {site_id}, Cell {cell_id}, Carrier {carrier}")
            actual_azimuth = calculate_actual_azimuth_with_centroid(
                mr_data, ep_data, mappings, site_id, cell_id, carrier, min_points, max_distance
            )
            if actual_azimuth is None:
                results.append({
                    'eNodeb Name': site_id,
                    'Cell ID': cell_id,
                    'Carrier': carrier,
                    'Planned Azimuth': planned_azimuth,
                    'Actual Azimuth': 'Less Number of MR',
                    'Azimuth Difference': 'Less Number of MR',
                    'Actual Latitude': ep_lat,
                    'Actual Longitude': ep_lon,
                    'Result': 'Less Number of MR'
                })
                continue
            azimuth_diff = abs(planned_azimuth - actual_azimuth)
            azimuth_diff = min(azimuth_diff, 360 - azimuth_diff)
            results.append({
                'eNodeb Name': site_id,
                'Cell ID': cell_id,
                'Carrier': carrier,
                'Planned Azimuth': planned_azimuth,
                'Actual Azimuth': round(actual_azimuth, 2),
                'Azimuth Difference': round(azimuth_diff, 2),
                'Actual Latitude': ep_lat,
                'Actual Longitude': ep_lon,
                'Result': 'OK'
            })
        return pd.DataFrame(results)

    def sector_swap_analysis(self, mr_data, ep_data, mappings, executor=None, progress_callback=None):
        results = []
        mr_lat_col = mappings["MR Latitude"]
        mr_lon_col = mappings["MR Longitude"]
        ep_lat_col = mappings["EP Latitude"]
        ep_lon_col = mappings["EP Longitude"]
        ep_azimuth_col = mappings["EP Azimuth"]
        ep_carrier_col = mappings["Carrier"]

        total_cells = ep_data.shape[0]
        processed_cells = 0

        futures = []
        for enodeb in ep_data[mappings["EP Site ID"]].unique():
            ep_enodeb_data = ep_data[ep_data[mappings["EP Site ID"]] == enodeb]
            mr_enodeb_data = mr_data[mr_data[mappings["MR Site ID"]] == enodeb]
            
            future = executor.submit(
                self.process_enodeb,
                enodeb, ep_enodeb_data, mr_enodeb_data, mappings,
                mr_lat_col, mr_lon_col, ep_lat_col, ep_lon_col,
                ep_azimuth_col, ep_carrier_col
            )
            futures.append(future)

        for future in as_completed(futures):
            results.extend(future.result())
            processed_cells += len(future.result())
            if progress_callback:
                progress = int((processed_cells / total_cells) * 100)
                progress_callback(progress)

        result_columns = ['eNodeb Name', 'Cell ID', 'Result', 'Cell Type']
        result_df = pd.DataFrame(results, columns=result_columns)

        # Remove any extra columns and sort by Site ID (eNodeb Name)
        result_df = result_df[result_columns]
        result_df = result_df.sort_values(by='eNodeb Name', ascending=True)

        # DEBUG: Print all sector swap found rows before deduplication
        print("[DEBUG] Rows with 'Sector Swap Found' before deduplication:")
        print(result_df[result_df['Result'].str.contains('Sector Swap Found', na=False)])

        # Deduplicate: prioritize sector swap results over generic 'No Sector Swap Found - Sector Split'
        def split_priority(result):
            if isinstance(result, str) and "Sector Swap Found" in result:
                return 2
            if isinstance(result, str) and "No Sector Swap Found (Split, Valid MR)" in result:
                return 1
            return 0
        result_df['split_priority'] = result_df['Result'].apply(split_priority)
        result_df = result_df.sort_values(by='split_priority', ascending=False)
        result_df = result_df.drop_duplicates(subset=['eNodeb Name', 'Cell ID'], keep='first')
        result_df = result_df.drop(columns=['split_priority'])

        # FINAL DEBUG: Show split sector swaps in the final result table
        print("[FINAL DEBUG] Split sector swaps in final result table:")
        print(result_df[(result_df['Cell Type'] == 'Sector Split') & (result_df['Result'].str.contains('Sector Swap Found', na=False))])

        return result_df

    def process_enodeb(self, enodeb, ep_enodeb_data, mr_enodeb_data, mappings,
                       mr_lat_col, mr_lon_col, ep_lat_col, ep_lon_col,
                       ep_azimuth_col, ep_carrier_col):
        results = []
        
        # Pre-analyze all cells for special configurations
        cell_configurations = {}
        
        # First, check each cell for both massive MIMO and sector split configurations
        for _, ep_row in ep_enodeb_data.iterrows():
            cell_id = ep_row[mappings["EP Cell ID"]]
            carrier = ep_row[ep_carrier_col]
            
            # Create a key for this cell
            cell_key = f"{cell_id}_{carrier}"
            
            # Check massive MIMO first (takes priority)
            is_mimo, mimo_group = self.check_massive_mimo_group(
                enodeb, cell_id, carrier, ep_enodeb_data, mappings
            )
            
            # Check sector split
            is_split, split_partner = self.check_sector_split_pair(
                enodeb, cell_id, carrier, ep_enodeb_data, mappings
            )
            
            # Store configuration information
            cell_configurations[cell_key] = {
                'is_mimo': is_mimo,
                'mimo_group': mimo_group,
                'is_split': is_split,
                'split_partner': split_partner
            }
        
        # First, validate MIMO configurations
        # For each possible MIMO group, check if all 4 beams exist at the site
        valid_mimo_groups = {}
        for cell_key, config in cell_configurations.items():
            if config['is_mimo'] and config['mimo_group']:
                carrier = cell_key.split('_')[1]  # Extract carrier from cell_key
                mimo_group_key = f"{tuple(sorted(config['mimo_group']))}_{carrier}"
                
                if mimo_group_key not in valid_mimo_groups:
                    # Check if all beams in the group exist
                    all_beams_exist = True
                    for beam_id in config['mimo_group']:
                        beam_key = f"{beam_id}_{carrier}"
                        if beam_key not in cell_configurations:
                            all_beams_exist = False
                            break
                    
                    valid_mimo_groups[mimo_group_key] = all_beams_exist
        
        # Next, identify special cases where sector split pairs might be part of MIMO groups
        # For each sector split pair, check if both are in the same MIMO group
        split_mimo_overlap = {}
        for cell_key, config in cell_configurations.items():
            if config['is_split'] and config['split_partner']:
                carrier = cell_key.split('_')[1]
                cell_id = cell_key.split('_')[0]
                partner_id = config['split_partner']
                
                # Check if both cell and partner are part of the same MIMO group
                for other_key, other_config in cell_configurations.items():
                    if (other_config['is_mimo'] and other_config['mimo_group'] and 
                        cell_id in other_config['mimo_group'] and 
                        partner_id in other_config['mimo_group']):
                        
                        # Found a case where split pair is also part of MIMO group
                        mimo_group_key = f"{tuple(sorted(other_config['mimo_group']))}_{carrier}"
                        split_mimo_overlap[cell_key] = mimo_group_key
                        partner_key = f"{partner_id}_{carrier}"
                        split_mimo_overlap[partner_key] = mimo_group_key
                        break
        
        # Now determine final cell type with updated priorities
        # 1. If a cell is part of a valid MIMO group (all beams exist), it's MIMO
        # 2. Otherwise, if it's part of a split pair, it's a sector split
        for cell_key, config in cell_configurations.items():
            cell_id = cell_key.split('_')[0]
            carrier = cell_key.split('_')[1]
            
            # Check if this cell is part of a split pair that overlaps with a MIMO group
            if cell_key in split_mimo_overlap:
                mimo_group_key = split_mimo_overlap[cell_key]
                
                # If the MIMO group is valid (all beams exist), mark as MIMO
                if valid_mimo_groups.get(mimo_group_key, False):
                    cell_configurations[cell_key]['final_type'] = "Massive MIMO"
                else:
                    # Otherwise, mark as sector split
                    cell_configurations[cell_key]['final_type'] = "Sector Split"
            # Standard MIMO check (not part of a split/MIMO overlap)
            elif config['is_mimo'] and config['mimo_group']:
                mimo_group_key = f"{tuple(sorted(config['mimo_group']))}_{carrier}"
                if valid_mimo_groups.get(mimo_group_key, False):
                    cell_configurations[cell_key]['final_type'] = "Massive MIMO"
            # Standard sector split check
            elif config['is_split'] and not cell_configurations[cell_key].get('final_type'):
                partner_key = f"{config['split_partner']}_{carrier}"
                # Only mark as sector split if neither this cell nor partner is already marked as MIMO
                if (partner_key in cell_configurations and 
                    cell_configurations[partner_key].get('final_type') != "Massive MIMO"):
                    cell_configurations[cell_key]['final_type'] = "Sector Split"
                    cell_configurations[partner_key]['final_type'] = "Sector Split"
        
        # Prepare sector info for the site (cell_id -> (azimuth, lat, lon))
        # Only include sectors with the same carrier as the cell being analyzed
        sector_info_by_carrier = {}
        for _, ep_row in ep_enodeb_data.iterrows():
            cid = ep_row[mappings["EP Cell ID"]]
            carrier = ep_row[ep_carrier_col]
            if carrier not in sector_info_by_carrier:
                sector_info_by_carrier[carrier] = {}
            sector_info_by_carrier[carrier][cid] = (ep_row[ep_azimuth_col] % 360, ep_row[ep_lat_col], ep_row[ep_lon_col])
        
        print(f"\n[DEBUG] Processing eNodeB: {enodeb}")
        # Process each cell with the final determined type
        for _, ep_row in ep_enodeb_data.iterrows():
            cell_id = ep_row[mappings["EP Cell ID"]]
            carrier = ep_row[ep_carrier_col]
            cell_key = f"{cell_id}_{carrier}"
            
            # Get the cell configuration
            config = cell_configurations.get(cell_key, {
                'is_mimo': False,
                'mimo_group': None,
                'is_split': False,
                'split_partner': None,
                'final_type': ""
            })
            
            cell_type = config.get('final_type', "")
            
            # Only skip Massive MIMO cells
            if cell_type == "Massive MIMO":
                results.append((enodeb, cell_id, 
                              f"No Sector Swap Found - {cell_type}", cell_type))
                continue
            
            azimuth = ep_row[ep_azimuth_col] % 360
            ep_cell_key = ep_row['EP_key']
            cell_lat = ep_row[ep_lat_col]
            cell_lon = ep_row[ep_lon_col]
            
            # Process MR data for this cell
            mr_cell_data = mr_enodeb_data[mr_enodeb_data['MR_key'] == ep_cell_key]
            if mr_cell_data.empty:
                results.append((enodeb, cell_id,
                              "NO MR Data found for the cell", cell_type))
                continue
            # If less than 50 MR points, skip sector swap and mark as such
            if len(mr_cell_data) < 50:
                results.append((enodeb, cell_id,
                              "Less Number of MR Points", cell_type))
                continue

            # --- Only use sectors with the same carrier for direction counts ---
            sector_info = sector_info_by_carrier[carrier]
            print(f"[DEBUG] Sector Info (carrier {carrier}): {sector_info}")
            print(f"[DEBUG] EP Keys: {[row['EP_key'] for _, row in ep_enodeb_data[ep_enodeb_data[ep_carrier_col] == carrier].iterrows()]}")
            print(f"[DEBUG] MR Keys: {mr_enodeb_data['MR_key'].unique().tolist()}")

            # First pass: collect swap candidates and stats for all cells
            swap_candidates = {}
            cell_stats = {}
            split_pairs = set()
            for _, ep_row in ep_enodeb_data[ep_enodeb_data[ep_carrier_col] == carrier].iterrows():
                cell_id = ep_row[mappings["EP Cell ID"]]
                azimuth = ep_row[ep_azimuth_col] % 360
                ep_cell_key = ep_row['EP_key']
                cell_lat = ep_row[ep_lat_col]
                cell_lon = ep_row[ep_lon_col]
                cell_type = cell_configurations.get(f"{cell_id}_{carrier}", {}).get('final_type', "")
                is_split = cell_type == "Sector Split"
                split_partner = cell_configurations.get(f"{cell_id}_{carrier}", {}).get('split_partner')
                is_mimo = cell_type == "Massive MIMO"
                if is_mimo:
                    continue
                mr_cell_data = mr_enodeb_data[mr_enodeb_data['MR_key'] == ep_cell_key]
                if mr_cell_data.empty or len(mr_cell_data) < 50:
                    continue
                direction_counts = {cid: 0 for cid in sector_info}
                for _, mr_row in mr_cell_data.iterrows():
                    mr_lat = mr_row[mr_lat_col]
                    mr_lon = mr_row[mr_lon_col]
                    for other_cid, (other_az, other_lat, other_lon) in sector_info.items():
                        mr_az = self.calculate_azimuth(other_lat, other_lon, mr_lat, mr_lon) % 360
                        az_diff = abs((mr_az - other_az + 180) % 360 - 180)
                        if az_diff <= self.FIXED_BEAMWIDTH / 2:
                            direction_counts[other_cid] += 1
                total_mr = sum(direction_counts.values())
                sorted_counts = sorted(direction_counts.values(), reverse=True)
                max_cell = max(direction_counts, key=lambda cid: direction_counts[cid])
                max_count = direction_counts[max_cell]
                second_max_count = sorted_counts[1] if len(sorted_counts) > 1 else 0
                print(f"[DEBUG] Cell {cell_id} (EP_key: {ep_cell_key}): direction_counts={direction_counts}, total_mr={total_mr}, max_cell={max_cell}, max_count={max_count}, second_max_count={second_max_count}")
                # Always add all cells to swap_candidates for adaptive logic
                swap_candidates[cell_id] = {
                    'target': max_cell,
                    'max_count': max_count,
                    'total_mr': total_mr,
                    'second_max_count': second_max_count,
                    'azimuth': azimuth,
                    'lat': cell_lat,
                    'lon': cell_lon,
                    'ep_cell_key': ep_cell_key,
                    'cell_type': cell_type,
                    'is_split': is_split,
                    'split_partner': split_partner,
                    'direction_counts': direction_counts
                }
                cell_stats[cell_id] = {
                    'azimuth': azimuth,
                    'lat': cell_lat,
                    'lon': cell_lon,
                    'ep_cell_key': ep_cell_key,
                    'cell_type': cell_type,
                    'is_split': is_split,
                    'split_partner': split_partner
                }

            # Second pass: check adaptive logic for all pairs where either cell points to the other
            processed_pairs = set()
            added_cells = set()
            swap_found_cells = set()  # Track cells with swap found
            for cell_id, candidate in swap_candidates.items():
                if not candidate or candidate['total_mr'] == 0:
                    continue
                target = candidate['target']
                if target not in swap_candidates or swap_candidates[target]['total_mr'] == 0:
                    continue
                target_candidate = swap_candidates[target]
                pair = tuple(sorted([cell_id, target]))
                is_split = candidate.get('is_split', False)
                split_partner = candidate.get('split_partner')
                # Get actual direction proportions for the pair
                cell_dir_count = candidate['direction_counts'][target] if target in candidate['direction_counts'] else 0
                cell_ratio = cell_dir_count / candidate['total_mr'] if candidate['total_mr'] > 0 else 0
                target_dir_count = target_candidate['direction_counts'][cell_id] if cell_id in target_candidate['direction_counts'] else 0
                target_ratio = target_dir_count / target_candidate['total_mr'] if target_candidate['total_mr'] > 0 else 0
                adaptive_swap = (cell_ratio > 0.6 and target_ratio > 0.3) or (cell_ratio > 0.3 and target_ratio > 0.6)
                mutual = (swap_candidates[target]['target'] == cell_id)
                strict_swap = (
                    candidate['max_count'] >= 0.7 * candidate['total_mr'] and
                    (candidate['max_count'] - candidate['second_max_count']) >= 0.2 * candidate['total_mr'] and
                    target_candidate['max_count'] >= 0.7 * target_candidate['total_mr'] and
                    (target_candidate['max_count'] - target_candidate['second_max_count']) >= 0.2 * target_candidate['total_mr']
                )
                # For sector split cells, only check swap if both cells are splits
                if is_split:
                    if mutual and pair not in processed_pairs and target_candidate.get('is_split', False):
                        if cell_id == target:
                            continue
                        processed_pairs.add(pair)
                        if (cell_id, target) not in added_cells:
                            print(f"[RESULT DEBUG] (SPLIT) Appending swap for {enodeb}, {cell_id} <-> {target}, type={candidate['cell_type']}")
                            results.append((enodeb, cell_id,
                                          f"Sector Swap Found Between {cell_id} and {target}", candidate['cell_type']))
                            added_cells.add((cell_id, target))
                            swap_found_cells.add((enodeb, cell_id))
                        if (target, cell_id) not in added_cells:
                            print(f"[RESULT DEBUG] (SPLIT) Appending swap for {enodeb}, {target} <-> {cell_id}, type={target_candidate['cell_type']}")
                            results.append((enodeb, target,
                                          f"Sector Swap Found Between {target} and {cell_id}", target_candidate['cell_type']))
                            added_cells.add((target, cell_id))
                            swap_found_cells.add((enodeb, target))
                else:
                    if (mutual and (adaptive_swap or strict_swap)) and pair not in processed_pairs:
                        if cell_id == target:
                            continue
                        processed_pairs.add(pair)
                        if (cell_id, target) not in added_cells:
                            print(f"[RESULT DEBUG] Appending swap for {enodeb}, {cell_id} <-> {target}, type={candidate['cell_type']}")
                            results.append((enodeb, cell_id,
                                          f"Sector Swap Found Between {cell_id} and {target}", candidate['cell_type']))
                            added_cells.add((cell_id, target))
                            swap_found_cells.add((enodeb, cell_id))
                        if (target, cell_id) not in added_cells:
                            print(f"[RESULT DEBUG] Appending swap for {enodeb}, {target} <-> {cell_id}, type={target_candidate['cell_type']}")
                            results.append((enodeb, target,
                                          f"Sector Swap Found Between {target} and {cell_id}", target_candidate['cell_type']))
                            added_cells.add((target, cell_id))
                            swap_found_cells.add((enodeb, target))
            # For cells not in swap_found_cells, add as no swap
            for cell_id, stat in cell_stats.items():
                if (enodeb, cell_id) not in swap_found_cells:
                    results.append((enodeb, cell_id,
                                  "No Sector Swap Found", stat['cell_type']))
        
        # Final deduplication: only one row per cell per swap
        result_df = pd.DataFrame(results, columns=[
            'eNodeb Name', 'Cell ID', 'Result', 'Cell Type'])
        result_df = result_df.drop_duplicates(subset=['eNodeb Name', 'Cell ID', 'Result'])
        return result_df.values.tolist()

    def calculate_distance(self, lat1, lon1, lat2, lon2):
        R = 6371
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = R * c
        return distance * 1000

    def calculate_azimuth(self, lat1, lon1, lat2, lon2):
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlon = lon2 - lon1
        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        azimuth = math.atan2(y, x)
        azimuth = math.degrees(azimuth)
        azimuth = (azimuth + 360) % 360
        return azimuth

    def is_within_beamwidth(self, mr_lat, mr_lon, cell_lat, cell_lon, azimuth, beamwidth):
        actual_azimuth = self.calculate_azimuth(cell_lat, cell_lon, mr_lat, mr_lon)
        azimuth_diff = abs(actual_azimuth - azimuth)
        azimuth_diff = min(azimuth_diff, 360 - azimuth_diff)
        return azimuth_diff <= beamwidth / 2

    def calculate_sector_swap_statistics(self, result_df):
        # Get unique cells and sites with sector swaps
        swap_cells = result_df[result_df['Result'].str.contains('Sector Swap Found', na=False)]
        swap_sites = swap_cells['eNodeb Name'].unique()
        
        # Calculate total counts
        total_cells = result_df.shape[0]
        total_sites = result_df['eNodeb Name'].nunique()
        
        # Calculate sector swap counts
        sector_swap_count = len(swap_cells)
        sector_swap_percentage = (sector_swap_count / total_cells) * 100
        
        # Calculate site-level statistics
        sector_swap_site_count = len(swap_sites)
        sector_swap_site_percentage = (sector_swap_site_count / total_sites) * 100
        
        # Calculate cell type statistics
        split_cells = result_df[result_df['Cell Type'] == "Sector Split"]
        mimo_cells = result_df[result_df['Cell Type'] == "Massive MIMO"]
        
        # Calculate swap statistics by cell type
        split_swaps = swap_cells[swap_cells['Cell Type'] == "Sector Split"]
        normal_swaps = swap_cells[swap_cells['Cell Type'] != "Sector Split"]
        
        return {
            'total_cells': total_cells,
            'sector_swap_count': sector_swap_count,
            'sector_swap_percentage': sector_swap_percentage,
            'sector_swap_site_count': sector_swap_site_count,
            'total_sites': total_sites,
            'sector_swap_site_percentage': sector_swap_site_percentage,
            'split_cells_count': len(split_cells),
            'mimo_cells_count': len(mimo_cells),
            'split_swap_count': len(split_swaps),
            'normal_swap_count': len(normal_swaps)
        }

    def calculate_direction_counts(self, mr_cell_data, ep_data, mappings):
        """
        For a given cell's MR data, count how many MR points are closest (by azimuth) to each sector in the site.
        Returns a dictionary: {cell_id: count, ...}
        """
        if mr_cell_data.empty:
            return {}
        site_id = mr_cell_data.iloc[0][mappings['MR Site ID']]
        carrier = mr_cell_data.iloc[0][mappings['MR Carrier']]
        # Get all sectors for this site and carrier
        ep_sectors = ep_data[(ep_data[mappings['EP Site ID']] == site_id) & (ep_data[mappings['Carrier']] == carrier)]
        sector_info = {}
        for _, ep_row in ep_sectors.iterrows():
            cid = str(ep_row[mappings['EP Cell ID']])
            az = ep_row[mappings['EP Azimuth']] % 360
            lat = ep_row[mappings['EP Latitude']]
            lon = ep_row[mappings['EP Longitude']]
            sector_info[cid] = (az, lat, lon)
        direction_counts = {cid: 0 for cid in sector_info}
        for _, mr_row in mr_cell_data.iterrows():
            mr_lat = mr_row[mappings['MR Latitude']]
            mr_lon = mr_row[mappings['MR Longitude']]
            for other_cid, (other_az, other_lat, other_lon) in sector_info.items():
                mr_az = self.calculate_azimuth(other_lat, other_lon, mr_lat, mr_lon) % 360
                az_diff = abs((mr_az - other_az + 180) % 360 - 180)
                if az_diff <= self.FIXED_BEAMWIDTH / 2:
                    direction_counts[other_cid] += 1
        return direction_counts