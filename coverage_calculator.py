# coverage.py
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from math import radians, sin, cos, sqrt, atan2

class CoverageCalculator:
    def __init__(self):
        # Define distance ranges for coverage analysis
        self.distance_ranges = [
            (0, 300),
            (300, 500),
            (500, 700),
            (700, 1000),
            (1000, float('inf'))
        ]
        
        # Define RSRP ranges for signal strength analysis
        self.rsrp_ranges = [
            (-40, -70),   # Excellent signal
            (-70, -85),   # Good signal
            (-85, -95),   # Fair signal
            (-95, -105),  # Poor signal
            (-float('inf'), -105)  # Very poor signal
        ]

    def process_cell(self, site_id, cell_id, ep_lat, ep_lon, carrier, mr_data, mappings):
        """Process individual cell coverage data"""
        try:
            # Create default result for cells with no MR data
            base_result = [
                site_id,
                cell_id,
                carrier,
                "0.0%", "0.0%", "0.0%", "0.0%", "0.0%",  # Distance ranges
                "0.0%", "0.0%", "0.0%", "0.0%", "0.0%",  # RSRP ranges
                "0.0%",  # Overall score
                "0",     # Total points
                "No MR Data"  # Coverage status
            ]
            
            # Filter MR data for this cell
            cell_mr = mr_data[
                (mr_data[mappings['MR Site ID']] == site_id) &
                (mr_data[mappings['MR Cell ID']] == cell_id)
            ]
            
            if cell_mr.empty:
                return base_result
            
            # Get total MR points for this cell
            total_mr_points = len(cell_mr)
            
            # Calculate distances and collect RSRP values
            distances = []
            rsrp_values = []
            
            for _, row in cell_mr.iterrows():
                try:
                    mr_lat = float(row[mappings['MR Latitude']])
                    mr_lon = float(row[mappings['MR Longitude']])
                    distance = self.calculate_distance(ep_lat, ep_lon, mr_lat, mr_lon)
                    rsrp = float(row[mappings['MR RSRP']])
                    
                    distances.append(distance)
                    rsrp_values.append(rsrp)
                except Exception as e:
                    print(f"Error processing measurement: {str(e)}")
                    continue
            
            if not distances:
                return base_result
                
            distances = np.array(distances)
            rsrp_values = np.array(rsrp_values)
            
            # Calculate distance range distributions
            coverage_stats = []
            for min_dist, max_dist in self.distance_ranges[:-1]:
                range_mask = (distances >= min_dist) & (distances < max_dist)
                points_in_range = np.sum(range_mask)
                coverage_ratio = (points_in_range / total_mr_points) * 100
                coverage_stats.append(f"{coverage_ratio:.1f}%")
            
            # Handle >1000m range
            range_mask = (distances >= 1000)
            points_in_range = np.sum(range_mask)
            coverage_ratio = (points_in_range / total_mr_points) * 100
            coverage_stats.append(f"{coverage_ratio:.1f}%")
            
            # Calculate RSRP distributions
            rsrp_stats = []
            poor_rsrp_count = 0
            
            # Debug info
            print(f"\nProcessing cell {site_id}-{cell_id}")
            print(f"Total points: {total_mr_points}")
            print(f"RSRP values range: {np.min(rsrp_values):.1f} to {np.max(rsrp_values):.1f}")
            
            # Calculate RSRP distributions
            # First handle the <-105 range
            below_105_mask = (rsrp_values < -105)
            below_105_count = np.sum(below_105_mask)
            below_105_ratio = (below_105_count / total_mr_points) * 100
            
            # Then handle the remaining ranges from best to worst
            rsrp_counts = {
                "-40 to -70": np.sum((rsrp_values >= -70) & (rsrp_values > -40)),
                "-70 to -85": np.sum((rsrp_values >= -85) & (rsrp_values < -70)),
                "-85 to -95": np.sum((rsrp_values >= -95) & (rsrp_values < -85)),
                "-95 to -105": np.sum((rsrp_values >= -105) & (rsrp_values < -95)),
                "<-105": below_105_count
            }
            
            # Convert counts to percentages
            rsrp_stats = [
                f"{(rsrp_counts['-40 to -70'] / total_mr_points * 100):.1f}%",
                f"{(rsrp_counts['-70 to -85'] / total_mr_points * 100):.1f}%",
                f"{(rsrp_counts['-85 to -95'] / total_mr_points * 100):.1f}%",
                f"{(rsrp_counts['-95 to -105'] / total_mr_points * 100):.1f}%",
                f"{(rsrp_counts['<-105'] / total_mr_points * 100):.1f}%"
            ]
            
            # Debug print the distributions
            for range_name, count in rsrp_counts.items():
                print(f"{range_name}: {count} points ({(count/total_mr_points*100):.1f}%)")
            
            # Calculate overall score
            distance_weights = [1.0, 0.8, 0.6, 0.4, 0.2]
            rsrp_weights = [1.0, 0.8, 0.6, 0.4, 0.2]
            
            coverage_values = [float(x.strip('%')) for x in coverage_stats]
            rsrp_values_pct = [float(x.strip('%')) for x in rsrp_stats]
            
            weighted_coverage = sum(v * w for v, w in zip(coverage_values, distance_weights))
            weighted_rsrp = sum(v * w for v, w in zip(rsrp_values_pct, rsrp_weights))
            
            overall_score = (weighted_coverage + weighted_rsrp) / (sum(distance_weights) + sum(rsrp_weights))
            
            # Determine coverage status
            poor_rsrp_count = rsrp_counts['<-105']
            poor_coverage_ratio = (poor_rsrp_count / total_mr_points) * 100
            coverage_status = "Poor Coverage" if poor_coverage_ratio > 50 else "Good Coverage"
            
            return [
                site_id,
                cell_id,
                carrier,
                *coverage_stats,
                *rsrp_stats,
                f"{overall_score:.1f}%",
                str(total_mr_points),
                coverage_status
            ]
            
        except Exception as e:
            print(f"Error processing cell {site_id}-{cell_id}: {str(e)}")
            return base_result

    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points in meters"""
        try:
            R = 6371  # Earth's radius in kilometers
            
            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            
            return R * c * 1000  # Convert to meters
        except Exception as e:
            print(f"Error calculating distance: {str(e)}")
            return 0

    def analyze_coverage(self, mr_data, ep_data, mappings, executor=None, progress_callback=None):
        """Analyze coverage for all cells"""
        try:
            results = []
            processed_cells = 0
            
            # Get all unique combinations of site_id, cell_id, and carrier from EP data
            cell_combinations = ep_data[[
                mappings['EP Site ID'],
                mappings['EP Cell ID'],
                mappings['Carrier']
            ]].drop_duplicates()
            
            total_cells = len(cell_combinations)
            
            # Process each unique cell from EP data
            for _, row in cell_combinations.iterrows():
                try:
                    site_id = row[mappings['EP Site ID']]
                    cell_id = row[mappings['EP Cell ID']]
                    carrier = row[mappings['Carrier']]
                    
                    # Get EP coordinates
                    ep_cell_data = ep_data[
                        (ep_data[mappings['EP Site ID']] == site_id) &
                        (ep_data[mappings['EP Cell ID']] == cell_id)
                    ]
                    
                    if not ep_cell_data.empty:
                        ep_lat = float(ep_cell_data[mappings['EP Latitude']].iloc[0])
                        ep_lon = float(ep_cell_data[mappings['EP Longitude']].iloc[0])
                        
                        result = self.process_cell(
                            site_id, cell_id, ep_lat, ep_lon,
                            carrier, mr_data, mappings
                        )
                        
                        if result:
                            results.append(result)
                    else:
                        # Add row with no data if EP coordinates not found
                        results.append([
                            site_id,
                            cell_id,
                            carrier,
                            "0.0%", "0.0%", "0.0%", "0.0%", "0.0%",  # Distance ranges
                            "0.0%", "0.0%", "0.0%", "0.0%", "0.0%",  # RSRP ranges
                            "0.0%",  # Overall score
                            "0",     # Total points
                            "No EP Data"  # Coverage status
                        ])
                    
                    processed_cells += 1
                    if progress_callback:
                        progress = int((processed_cells / total_cells) * 100)
                        progress_callback(progress)
                        
                except Exception as e:
                    print(f"Error processing cell {site_id}-{cell_id}: {str(e)}")
                    continue
            
            # Convert results to DataFrame
            columns = [
                'Site ID', 'Cell ID', 'Carrier',
                '0-300m Coverage', '300-500m Coverage', 
                '500-700m Coverage', '700-1000m Coverage', '>1000m Coverage',
                'RSRP -40 to -70', 'RSRP -70 to -85',
                'RSRP -85 to -95', 'RSRP -95 to -105', 'RSRP <-105',
                'Overall Coverage Score', 'Total MR Points', 'Coverage Status'
            ]
            
            result_df = pd.DataFrame(results, columns=columns)
            
            # Sort by site_id, cell_id
            result_df = result_df.sort_values(['Site ID', 'Cell ID'])
            
            return result_df
            
        except Exception as e:
            print(f"Error in analyze_coverage: {str(e)}")
            return pd.DataFrame()

    def calculate_metrics(self, result_df, mr_data, mappings):
        """Calculate coverage metrics for all sites"""
        try:
            total_cells = len(result_df)
            metrics = {}

            # Calculate Poor Coverage Cells
            poor_coverage_cells = len(result_df[result_df['Coverage Status'] == 'Poor Coverage'])
            metrics['poor_coverage'] = {
                'count': poor_coverage_cells,
                'percentage': (poor_coverage_cells / total_cells * 100) if total_cells > 0 else 0
            }

            # Calculate Average RSRP across all MR measurements
            all_rsrp_values = mr_data[mappings['MR RSRP']].astype(float)
            avg_rsrp = all_rsrp_values.mean()
            metrics['average_rsrp'] = avg_rsrp

            # Calculate Overshooting Cells (>1000m ratio > 10%)
            overshooting_cells = len(result_df[
                result_df['>1000m Coverage'].str.rstrip('%').astype(float) > 10
            ])
            metrics['overshooting'] = {
                'count': overshooting_cells,
                'percentage': (overshooting_cells / total_cells * 100) if total_cells > 0 else 0
            }

            metrics['total_cells'] = total_cells

            return metrics
        except Exception as e:
            print(f"Error calculating metrics: {str(e)}")
            return {
                'total_cells': 0,
                'poor_coverage': {'count': 0, 'percentage': 0},
                'average_rsrp': 0,
                'overshooting': {'count': 0, 'percentage': 0}
            }