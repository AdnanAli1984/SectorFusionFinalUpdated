import sys
import os
import pandas as pd
import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QComboBox, QCheckBox, QLineEdit, QGroupBox,
                             QMessageBox)
from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QFont, QPainter, QColor
from PyQt6.QtWebEngineWidgets import QWebEngineView
import folium
import io
import random
import math

class GeoAnalysisWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__()
        self.setWindowFlag(Qt.WindowType.Window)  # Ensure it's a separate window
        self.main_window = parent
        
        # Initialize variables
        self.ep_data = None
        self.mappings = None
        self.available_layers = {}
        self.carrier_colors = {}
        self.current_site = None
        self.map = None
        self.sector_swap_df = None
        self.coordinates_df = None
        self.azimuth_df = None

        # Get data from main window if available
        if parent is not None:
            self.ep_data = getattr(parent, 'ep_data', None)
            self.mappings = getattr(parent, 'mappings', None)

        if self.ep_data is not None and self.mappings is not None:
            # Set Window properties
            self.setWindowTitle("Geo Analysis")
            self.resize(1200, 800)
            
            # Check available analyses
            self.check_available_analyses()
            
            # Create UI
            self.create_ui()
            self.update_theme("light")
        else:
            QMessageBox.warning(self, "Warning", 
                "No data available. Please upload and submit data first.")
            self.close()

    def check_available_analyses(self):
        """Check which analyses are available based on the main window's data"""
        self.available_layers = {
            'sector_swap': False,
            'coordinates': False,
            'azimuth': False
        }
        
        try:
            if self.main_window:
                # Check Sector Swap analysis
                if hasattr(self.main_window, 'sector_swap_window'):
                    window = self.main_window.sector_swap_window
                    if (window and hasattr(window, 'analyzed_df') and 
                        isinstance(window.analyzed_df, pd.DataFrame) and 
                        not window.analyzed_df.empty):
                        self.sector_swap_df = window.analyzed_df
                        self.available_layers['sector_swap'] = True
                
                # Check Coordinates analysis
                if hasattr(self.main_window, 'actual_coordinates_window'):
                    window = self.main_window.actual_coordinates_window
                    if (window and hasattr(window, 'analyzed_df') and 
                        isinstance(window.analyzed_df, pd.DataFrame) and 
                        not window.analyzed_df.empty):
                        self.coordinates_df = window.analyzed_df
                        self.available_layers['coordinates'] = True
                
                # Check Azimuth analysis
                if hasattr(self.main_window, 'actual_azimuth_window'):
                    window = self.main_window.actual_azimuth_window
                    if (window and hasattr(window, 'analyzed_df') and 
                        isinstance(window.analyzed_df, pd.DataFrame) and 
                        not window.analyzed_df.empty):
                        self.azimuth_df = window.analyzed_df
                        self.available_layers['azimuth'] = True
        
        except Exception as e:
            print(f"Error checking analyses: {str(e)}")
        
        return self.available_layers

    def create_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        main_layout.addWidget(content_widget)

        # Map container
        map_container = QWidget()
        map_layout = QVBoxLayout(map_container)
        map_layout.setContentsMargins(0, 0, 0, 0)
        map_layout.setSpacing(0)

        self.map_view = QWebEngineView()
        map_layout.addWidget(self.map_view)

        content_layout.addWidget(map_container, stretch=4)

        # Controls container
        controls_container = QWidget()
        controls_layout = QVBoxLayout(controls_container)
        controls_layout.setContentsMargins(10, 10, 10, 10)
        controls_layout.setSpacing(5)

        # Search controls
        search_layout = QHBoxLayout()
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search for Site ID")
        self.search_bar.returnPressed.connect(self.search_site)
        
        self.search_button = QPushButton("Search")
        self.search_button.setStyleSheet("""
            QPushButton {
                background-color: #4682B4;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3A6E9E;
            }
        """)
        self.search_button.clicked.connect(self.search_site)
        
        search_layout.addWidget(self.search_bar)
        search_layout.addWidget(self.search_button)
        controls_layout.addLayout(search_layout)

        # Layer controls
        layer_group = QGroupBox("Layers")
        layer_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #e2e8f0;
                border-radius: 4px;
                margin-top: 1em;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        layer_layout = QVBoxLayout(layer_group)
        layer_layout.setContentsMargins(5, 5, 5, 5)
        layer_layout.setSpacing(2)

        # Carrier combo
        self.carrier_combo = QComboBox()
        self.carrier_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #e2e8f0;
                border-radius: 4px;
                padding: 5px 10px;
                background: white;
            }
            QComboBox QAbstractItemView::item:hover {
                background: #e6f0fa;
                color: #222;
            }
            QComboBox QAbstractItemView::item:selected {
                background: #b3d8fd;
                color: #222;
            }
        """)
        self.carrier_combo.addItem("All Carriers")
        if self.ep_data is not None and self.mappings is not None:
            unique_carriers = sorted(self.ep_data[self.mappings['Carrier']].unique())
            self.carrier_combo.addItems(unique_carriers)
        layer_layout.addWidget(self.carrier_combo)

        # Create checkboxes
        self.planned_sites_cb = QCheckBox("Planned Sites")
        self.calculated_result_cb = QCheckBox("Actual Result")
        self.sector_swap_cells_cb = QCheckBox("Sector Swap Cells")
        self.azimuth_issue_cells_cb = QCheckBox("Azimuth Issue Cells")
        self.display_labels_cb = QCheckBox("Display Labels")

        # Style checkboxes
        checkbox_style = """
            QCheckBox {
                spacing: 5px;
                padding: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #e2e8f0;
                background: white;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #4682B4;
                background: #4682B4;
                border-radius: 3px;
            }
        """
        self.planned_sites_cb.setStyleSheet(checkbox_style)
        self.calculated_result_cb.setStyleSheet(checkbox_style)
        self.sector_swap_cells_cb.setStyleSheet(checkbox_style)
        self.azimuth_issue_cells_cb.setStyleSheet(checkbox_style)
        self.display_labels_cb.setStyleSheet(checkbox_style)

        # First disable all checkboxes initially
        self.planned_sites_cb.setEnabled(False)
        self.calculated_result_cb.setEnabled(False)
        self.sector_swap_cells_cb.setEnabled(False)
        self.azimuth_issue_cells_cb.setEnabled(False)
        self.display_labels_cb.setEnabled(False)

        # Uncheck all checkboxes initially
        self.planned_sites_cb.setChecked(False)
        self.calculated_result_cb.setChecked(False)
        self.sector_swap_cells_cb.setChecked(False)
        self.azimuth_issue_cells_cb.setChecked(False)
        self.display_labels_cb.setChecked(False)

        # Enable and check base layers if data is present
        if self.ep_data is not None:
            self.planned_sites_cb.setEnabled(True)
            self.display_labels_cb.setEnabled(True)
            self.planned_sites_cb.setChecked(True)
            self.display_labels_cb.setChecked(True)

        # Enable layers based on completed analyses
        if self.available_layers['sector_swap']:
            self.sector_swap_cells_cb.setEnabled(True)
            self.sector_swap_cells_cb.setChecked(True)
            
        if self.available_layers['coordinates']:
            self.calculated_result_cb.setEnabled(True)
            self.calculated_result_cb.setChecked(True)

        if self.available_layers['azimuth']:
            self.azimuth_issue_cells_cb.setEnabled(True)
            self.azimuth_issue_cells_cb.setChecked(True)

        # Add checkboxes to layout in order
        layer_layout.addWidget(self.planned_sites_cb)
        layer_layout.addWidget(self.calculated_result_cb)
        layer_layout.addWidget(self.sector_swap_cells_cb)
        layer_layout.addWidget(self.azimuth_issue_cells_cb)
        layer_layout.addWidget(self.display_labels_cb)

        # Add layer group to controls layout
        controls_layout.addWidget(layer_group)
        
        # Add controls container to main content layout
        content_layout.addWidget(controls_container, stretch=1)

        # Connect all signals
        self.planned_sites_cb.stateChanged.connect(self.update_map)
        self.calculated_result_cb.stateChanged.connect(self.update_map)
        self.sector_swap_cells_cb.stateChanged.connect(self.update_map)
        self.azimuth_issue_cells_cb.stateChanged.connect(self.update_map)
        self.display_labels_cb.stateChanged.connect(self.update_map)
        self.carrier_combo.currentIndexChanged.connect(self.update_map)

        # Initialize map
        self.update_map()

    def refresh_analysis_layers(self):
        """Refresh the available layers and update UI"""
        # Recheck available analyses
        self.available_layers = self.check_available_analyses()
        
        # Enable layers based on completed analyses
        if self.available_layers['sector_swap']:
            self.sector_swap_cells_cb.setEnabled(True)
            self.sector_swap_cells_cb.setChecked(True)
            
        if self.available_layers['coordinates']:
            self.calculated_result_cb.setEnabled(True)
            self.calculated_result_cb.setChecked(True)
            
        if self.available_layers['azimuth']:
            self.azimuth_issue_cells_cb.setEnabled(True)
            self.azimuth_issue_cells_cb.setChecked(True)
        
        # Update the map display
        self.update_map()

    def update_map(self):
        try:
            # Initialize map centered on the sites
            if self.ep_data is not None and self.mappings is not None:
                center_lat = self.ep_data[self.mappings['EP Latitude']].mean()
                center_lon = self.ep_data[self.mappings['EP Longitude']].mean()
                self.map = folium.Map(location=[center_lat, center_lon], zoom_start=14)

                # Always add planned sites if checked and enabled
                if self.planned_sites_cb.isChecked() and self.planned_sites_cb.isEnabled():
                    self.add_planned_sites_layer()

                # Add each analysis layer if it's available, enabled, and checked
                if self.available_layers['sector_swap']:
                    if self.sector_swap_cells_cb.isChecked() and self.sector_swap_cells_cb.isEnabled():
                        self.add_sector_swap_cells_layer()
                
                if self.available_layers['coordinates']:
                    if self.calculated_result_cb.isChecked() and self.calculated_result_cb.isEnabled():
                        self.add_calculated_result_layer()
                
                if self.available_layers['azimuth']:
                    if self.azimuth_issue_cells_cb.isChecked() and self.azimuth_issue_cells_cb.isEnabled():
                        self.add_azimuth_issue_cells_layer()

                # Add labels if enabled and checked
                if self.display_labels_cb.isChecked() and self.display_labels_cb.isEnabled():
                    self.add_labels()

                # Add layer control
                folium.LayerControl().add_to(self.map)

                # Save and display map
                data = io.BytesIO()
                self.map.save(data, close_file=False)
                html_content = data.getvalue().decode()
                
                self.map_view.setHtml(html_content)

        except Exception as e:
            print(f"Error updating map: {str(e)}")

    def add_planned_sites_layer(self):
        if self.ep_data is None or self.mappings is None:
            return
                
        planned_sites = folium.FeatureGroup(name="Planned Sites")
        
        # Plot a marker for each unique site
        for _, site in self.ep_data.drop_duplicates(subset=[self.mappings['EP Site ID']]).iterrows():
            site_id = str(site[self.mappings['EP Site ID']])
            is_highlighted = site_id == str(self.current_site)
            
            marker_color = 'red' if is_highlighted else 'blue'
            marker_radius = 8 if is_highlighted else 3
            marker_opacity = 1.0 if is_highlighted else 0.7

            folium.CircleMarker(
                location=[site[self.mappings['EP Latitude']], site[self.mappings['EP Longitude']]],
                radius=marker_radius,
                color=marker_color,
                fill=True,
                fillColor=marker_color,
                fillOpacity=marker_opacity,
                popup=folium.Popup(
                    f"""<div style='text-align: center;'>
                        <b>Site ID:</b> {site_id}<br>
                        <b>Latitude:</b> {site[self.mappings['EP Latitude']]:.6f}<br>
                        <b>Longitude:</b> {site[self.mappings['EP Longitude']]:.6f}
                    </div>""",
                    max_width=200
                )
            ).add_to(planned_sites)

        # Plot a fan for every (site, cell, carrier) combination
        for _, cell in self.ep_data.iterrows():
            if self.carrier_combo.currentText() == 'All Carriers' or cell[self.mappings['Carrier']] == self.carrier_combo.currentText():
                # Validate and convert azimuth, latitude, longitude
                try:
                    azimuth = float(cell[self.mappings['EP Azimuth']])
                    lat = float(cell[self.mappings['EP Latitude']])
                    lon = float(cell[self.mappings['EP Longitude']])
                except (ValueError, TypeError, KeyError):
                    # Skip plotting if any value is invalid
                    print(f"Skipping fan: Invalid azimuth/lat/lon for Site={cell[self.mappings['EP Site ID']]}, Cell={cell[self.mappings['EP Cell ID']]}, Carrier={cell[self.mappings['Carrier']]}")
                    continue
                # Set beam_width to 25 degrees
                beam_width = 25
                # Prepare popup content
                popup_content = f"""<div style='text-align: center;'>
                    <b>Site ID:</b> {cell[self.mappings['EP Site ID']]}<br>
                    <b>Cell ID:</b> {cell[self.mappings['EP Cell ID']]}<br>
                    <b>Carrier:</b> {cell[self.mappings['Carrier']]}<br>
                    <b>Azimuth:</b> {azimuth}°<br>
                    <b>Latitude:</b> {lat}<br>
                    <b>Longitude:</b> {lon}
                </div>"""
                self.add_fan(
                    planned_sites,
                    [lat, lon],
                    200,
                    azimuth,
                    self.get_color_for_carrier(cell[self.mappings['Carrier']]),
                    0.7,
                    beam_width,
                    popup_content
                )

        planned_sites.add_to(self.map)

    def add_calculated_result_layer(self):
        if not self.available_layers['coordinates']:
            return
            
        result_layer = folium.FeatureGroup(name="Actual Result")
        
        try:
            # First standardize column names
            result_df = self.coordinates_df.copy()
            if 'eNodeb Name' not in result_df.columns and 'eNodeB Name' in result_df.columns:
                result_df = result_df.rename(columns={'eNodeB Name': 'eNodeb Name'})
                
            # Process unique sites
            unique_sites = result_df.drop_duplicates(subset='eNodeb Name')
            
            for _, site in unique_sites.iterrows():
                site_id = str(site['eNodeb Name'])
                is_highlighted = site_id == str(self.current_site)
                
                marker_color = 'red' if is_highlighted else 'black'
                marker_radius = 8 if is_highlighted else 3
                marker_opacity = 1.0 if is_highlighted else 0.7

                folium.CircleMarker(
                    location=[float(site['Actual Latitude']), float(site['Actual Longitude'])],
                    radius=marker_radius,
                    color=marker_color,
                    fill=True,
                    fillColor=marker_color,
                    fillOpacity=marker_opacity,
                    popup=folium.Popup(
                        f"""<div style='text-align: center;'>
                            <b>Site ID:</b> {site_id}<br>
                            <b>Actual Latitude:</b> {float(site['Actual Latitude']):.6f}<br>
                            <b>Actual Longitude:</b> {float(site['Actual Longitude']):.6f}
                        </div>""",
                        max_width=200
                    )
                ).add_to(result_layer)

        except Exception as e:
            print(f"Error in result layer: {str(e)}")

        result_layer.add_to(self.map)

    def add_sector_swap_cells_layer(self):
        if not self.available_layers['sector_swap']:
            return
                
        swap_layer = folium.FeatureGroup(name="Sector Swap Cells")
        try:
            # Filter for swap cells using Result column
            swap_cells = self.sector_swap_df[
                self.sector_swap_df['Result'].str.startswith('Sector Swap Found', na=False)
            ]
            
            # Apply carrier filter
            if self.carrier_combo.currentText() != "All Carriers":
                swap_cells = swap_cells[swap_cells['Carrier'] == self.carrier_combo.currentText()]
            
            # Process cells
            for _, cell in swap_cells.iterrows():
                try:
                    is_highlighted = str(cell['eNodeb Name']) == str(self.current_site)
                    opacity = 0.8 if is_highlighted else 0.5
                    
                    cell_info = f"""<div style='text-align: center;'>
                        <b>Site ID:</b> {cell['eNodeb Name']}<br>
                        <b>Cell ID:</b> {cell['Cell ID']}<br>
                        <b>Carrier:</b> {cell['Carrier']}<br>
                        <b>Azimuth:</b> {cell['Azimuth']}°<br>
                        <b>Result:</b> {cell['Result']}<br>
                        <b>Latitude:</b> {cell['Latitude']:.6f}<br>
                        <b>Longitude:</b> {cell['Longitude']:.6f}
                    </div>"""
                    
                    # Add fan for cells with "Sector Swap Found" result
                    self.add_fan(
                        swap_layer,
                        [float(cell['Latitude']), float(cell['Longitude'])],
                        200,
                        float(cell['Azimuth']),
                        'red',  # Using red color for sector swap cells
                        opacity,
                        25,
                        cell_info
                    )

                except Exception as e:
                    print(f"Error processing swap cell: {str(e)}")

        except Exception as e:
            print(f"Error in sector swap layer: {str(e)}")

        swap_layer.add_to(self.map)

    def add_azimuth_issue_cells_layer(self):
        if not self.available_layers['azimuth']:
            return
            
        azimuth_layer = folium.FeatureGroup(name="Azimuth Issue Cells")
        try:
            # First standardize column names
            azimuth_df = self.azimuth_df.copy()
            if 'eNodeb Name' not in azimuth_df.columns and 'eNodeB Name' in azimuth_df.columns:
                azimuth_df = azimuth_df.rename(columns={'eNodeB Name': 'eNodeb Name'})
            # Convert to numeric, ignore non-numeric (e.g., 'Less Number of MR')
            azimuth_df['Azimuth Difference'] = pd.to_numeric(azimuth_df['Azimuth Difference'], errors='coerce')
            azimuth_df['Actual Azimuth'] = pd.to_numeric(azimuth_df['Actual Azimuth'], errors='coerce')
            # Use threshold from main window if available
            threshold = 25
            if self.main_window and hasattr(self.main_window, 'actual_azimuth_window'):
                threshold = getattr(self.main_window.actual_azimuth_window.azimuth_threshold, 'value', lambda: 25)()
            # Filter for azimuth issues with valid numbers only
            issue_cells = azimuth_df[(azimuth_df['Azimuth Difference'] > threshold) & (azimuth_df['Actual Azimuth'].notnull())]
            # Process cells
            for _, cell in issue_cells.iterrows():
                try:
                    if self.carrier_combo.currentText() == 'All Carriers' or cell['Carrier'] == self.carrier_combo.currentText():
                        is_highlighted = str(cell['eNodeb Name']) == str(self.current_site)
                        opacity = 0.8 if is_highlighted else 0.5
                        cell_info = f"""<div style='text-align: center;'>
                            <b>Site ID:</b> {cell['eNodeb Name']}<br>
                            <b>Cell ID:</b> {cell['Cell ID']}<br>
                            <b>Carrier:</b> {cell['Carrier']}<br>
                            <b>Planned Azimuth:</b> {cell['Planned Azimuth']}°<br>
                            <b>Actual Azimuth:</b> {cell['Actual Azimuth']}°<br>
                            <b>Azimuth Difference:</b> {cell['Azimuth Difference']}°<br>
                            <b>Latitude:</b> {cell['Actual Latitude']:.6f}<br>
                            <b>Longitude:</b> {cell['Actual Longitude']:.6f}
                        </div>"""
                        self.add_fan(
                            azimuth_layer,
                            [float(cell['Actual Latitude']), float(cell['Actual Longitude'])],
                            200,
                            float(cell['Actual Azimuth']),
                            'orange',
                            opacity,
                            25,
                            cell_info
                        )
                except Exception as e:
                    print(f"Error processing azimuth cell: {str(e)}")
        except Exception as e:
            print(f"Error in azimuth layer: {str(e)}")
        azimuth_layer.add_to(self.map)

    def add_labels(self):
        if self.ep_data is None or self.mappings is None:
            return
            
        for _, site in self.ep_data.drop_duplicates(subset=[self.mappings['EP Site ID']]).iterrows():
            site_id = str(site[self.mappings['EP Site ID']])
            is_highlighted = site_id == str(self.current_site)
            
            color = 'red' if is_highlighted else 'black'
            weight = 'bold' if is_highlighted else 'normal'
            size = '12pt' if is_highlighted else '10pt'
            
            location = [site[self.mappings['EP Latitude']], site[self.mappings['EP Longitude']]]

            folium.Marker(
                location=location,
                icon=folium.DivIcon(html=f"""
                    <div class='site-label' style='
                        font-size: {size};
                        color: {color};
                        font-weight: {weight};
                        text-align: center;
                        text-shadow: 1px 1px 1px white;
                    '>
                        {site_id}
                    </div>
                """)
            ).add_to(self.map)

    def add_fan(self, map_obj, center, radius, azimuth, fill_color, fill_opacity, beam_width, popup_content=None):
        try:
            # Validate inputs
            if not all(isinstance(x, (int, float)) for x in center):
                print(f"Invalid center coordinates: {center}")
                return
                
            if not isinstance(azimuth, (int, float)):
                print(f"Invalid azimuth value: {azimuth}")
                return
                
            # Cap beam_width to a reasonable value (never a full circle)
            if beam_width >= 180:
                beam_width = 25  # Default sector width
            
            # Convert radius from meters to degrees (approximately)
            radius_deg = radius / 111000  # 1 degree is approximately 111km

            # Calculate start and end angles
            start_angle = (azimuth - beam_width / 2) % 360
            end_angle = (azimuth + beam_width / 2) % 360

            # Generate points for the fan, handling wrap-around
            points = [center]
            if start_angle < end_angle:
                angles = np.linspace(start_angle, end_angle, 25)
            else:
                # Wrap around 0/360
                angles = np.linspace(start_angle, end_angle + 360, 25) % 360
            for angle in angles:
                rad = math.radians(angle)
                x = center[1] + radius_deg * math.sin(rad)
                y = center[0] + radius_deg * math.cos(rad)
                points.append([y, x])
            points.append(center)  # Close the polygon

            # Create the fan polygon
            fan = folium.Polygon(
                locations=points,
                fill=True,
                fillColor=fill_color,
                fillOpacity=fill_opacity,
                stroke=True,
                color=fill_color,
                weight=1,
                popup=folium.Popup(popup_content, max_width=300) if popup_content else None
            )
            
            # Add to map
            fan.add_to(map_obj)
            
        except Exception as e:
            print(f"Error adding fan: {str(e)}")
            print(f"Center: {center}, Azimuth: {azimuth}, Radius: {radius}")

    def search_site(self):
        search_text = self.search_bar.text().strip()
        if not search_text:
            return

        # First try to find in EP data
        if self.ep_data is not None and self.mappings is not None:
            matching_sites = self.ep_data[self.ep_data[self.mappings['EP Site ID']].astype(str) == search_text]
            if not matching_sites.empty:
                self.current_site = search_text
                site_data = matching_sites.iloc[0]
                lat = site_data[self.mappings['EP Latitude']]
                lon = site_data[self.mappings['EP Longitude']]
                self.map_view.page().runJavaScript(f"map.setView([{lat}, {lon}], 15);")
                self.update_map()
                return

        # Then try in coordinates result
        if self.available_layers['coordinates']:
            matching_sites = self.coordinates_df[self.coordinates_df['eNodeB Name'].astype(str) == search_text]
            if not matching_sites.empty:
                self.current_site = search_text
                site_data = matching_sites.iloc[0]
                lat = site_data['Actual Latitude']
                lon = site_data['Actual Longitude']
                self.map_view.page().runJavaScript(f"map.setView([{lat}, {lon}], 15);")
                self.update_map()
                return

        # If site not found
        self.search_bar.setStyleSheet("background-color: #ffebee;")
        QTimer.singleShot(1000, lambda: self.search_bar.setStyleSheet(""))
        QMessageBox.warning(self, "Site Not Found", f"Site ID '{search_text}' not found.")

    def get_color_for_carrier(self, carrier):
        if carrier not in self.carrier_colors:
            self.carrier_colors[carrier] = '#{:06x}'.format(random.randint(0, 0xFFFFFF))
        return self.carrier_colors[carrier]

    def update_theme(self, theme):
        self.theme = theme
        if theme == "dark":
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #333333;
                    color: #ffffff;
                }
                QPushButton {
                    background-color: #4682B4;
                    color: white;
                    padding: 5px;
                    border: none;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #3A6E9E;
                }
                QLineEdit, QComboBox {
                    background-color: #555555;
                    color: #ffffff;
                    border: 1px solid #777777;
                    padding: 3px;
                }
                QCheckBox, QGroupBox {
                    color: #ffffff;
                }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #f0f0f0;
                    color: #333333;
                }
                QPushButton {
                    background-color: #4682B4;
                    color: white;
                    padding: 5px;
                    border: none;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #3A6E9E;
                }
                QLineEdit, QComboBox {
                    background-color: #ffffff;
                    color: #333333;
                    border: 1px solid #cccccc;
                    padding: 3px;
                }
                QCheckBox, QGroupBox {
                    color: #333333;
                }
            """)

    def show_message(self, title, message):
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.exec()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = GeoAnalysisWindow()
    window.resize(1200, 800)
    window.show()
    sys.exit(app.exec())