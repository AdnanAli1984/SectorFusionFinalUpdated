# neighbor_audit_window.py
import sys
import os
import pandas as pd
import numpy as np
from math import radians, sin, cos, sqrt, atan2
from concurrent.futures import ThreadPoolExecutor
import multiprocessing

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QFrame, QTableWidget, QTableWidgetItem,
                            QGridLayout, QScrollArea, QFileDialog, QMessageBox,
                            QGraphicsDropShadowEffect, QDialog, QComboBox,QApplication,
                            QSlider)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen, QFont,QPixmap,QIcon
from PyQt6.QtSvg import QSvgRenderer

class ModernSlider(QWidget):
    def __init__(self, title, min_val, max_val, default_val, unit="", parent=None):
        super().__init__(parent)
        self.setup_ui(title, min_val, max_val, default_val, unit)
    
    def setup_ui(self, title, min_val, max_val, default_val, unit):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        header = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #1e293b; font-size: 14px;")
        self.value_label = QLabel(f"{default_val}{unit}")
        self.value_label.setStyleSheet("color: #64748b; font-size: 14px;")
        
        header.addWidget(title_label)
        header.addWidget(self.value_label)
        layout.addLayout(header)
        
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(min_val, max_val)
        self.slider.setValue(default_val)
        self.slider.valueChanged.connect(
            lambda v: self.value_label.setText(f"{v}{unit}"))
        
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: #e2e8f0;
                border-radius: 2px;
                margin: 8px 0;
            }
            QSlider::handle:horizontal {
                width: 16px;
                height: 16px;
                margin: -6px 0;
                background: #3b82f6;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #2563eb;
            }
        """)
        
        slider_container = QWidget()
        slider_layout = QVBoxLayout(slider_container)
        slider_layout.setContentsMargins(0, 8, 0, 8)
        slider_layout.addWidget(self.slider)
        
        layout.addWidget(slider_container)

class SettingsPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsPanel")
        self.setStyleSheet("""
            QFrame#settingsPanel {
                background-color: white;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Settings Title
        title = QLabel("Analysis Settings")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1F2937;")
        layout.addWidget(title)
        
        # Search Radius Slider
        self.radius_slider = ModernSlider("Search Radius", 500, 10000, 5000, "m")
        layout.addWidget(self.radius_slider)
        
        # Max Neighbors Slider
        self.max_neighbors_slider = ModernSlider("Maximum Neighbors per Cell", 1, 32, 32, "")
        layout.addWidget(self.max_neighbors_slider)
        
        layout.addStretch()

class CircularProgressBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = 0
        self.angle = 0
        self.width = 120
        self.height = 120
        self.progress_width = 10
        self.setFixedSize(self.width, self.height)
    
    def setValue(self, value):
        self.value = value
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background circle
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(70, 70, 70))
        painter.drawEllipse(self.progress_width, self.progress_width,
                          self.width - 2 * self.progress_width,
                          self.height - 2 * self.progress_width)

        # Spinning progress circle
        if self.value < 100:
            self.angle = (self.angle - 5) % 360
            painter.setPen(QPen(QColor("#4682B4"), self.progress_width))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(self.progress_width, self.progress_width,
                          self.width - 2 * self.progress_width,
                          self.height - 2 * self.progress_width,
                          self.angle * 16, -120 * 16)

        # Progress arc
        painter.setPen(QPen(QColor("#4682B4"), self.progress_width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        span_angle = int(-self.value * 360 / 100 * 16)
        painter.drawArc(self.progress_width, self.progress_width,
                       self.width - 2 * self.progress_width,
                       self.height - 2 * self.progress_width,
                       90 * 16, span_angle)

        # Percentage text
        painter.setPen(QColor("white"))
        painter.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, f"{self.value}%")

class CircularProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.bg_frame = QFrame(self)
        self.bg_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 150);
                border-radius: 10px;
            }
        """)
        layout.addWidget(self.bg_frame)
        
        content_layout = QVBoxLayout(self.bg_frame)
        content_layout.setSpacing(15)
        
        self.progress_bar = CircularProgressBar(self)
        content_layout.addWidget(self.progress_bar, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.label = QLabel("Processing...", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 10px;
                font-weight: bold;
            }
        """)
        content_layout.addWidget(self.label)
        
        self.setFixedSize(200, 200)
        
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update)
        self.animation_timer.start(30)

    def setValue(self, value):
        self.progress_bar.setValue(value)

    def setLabelText(self, text):
        self.label.setText(text)

    def showEvent(self, event):
        super().showEvent(event)
        if self.parent():
            parent_rect = self.parent().geometry()
            self.move(parent_rect.center() - self.rect().center())
            
    def closeEvent(self, event):
        self.animation_timer.stop()
        super().closeEvent(event)

class NeighborCalculator:
    def __init__(self):
        pass
    
    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points in meters."""
        R = 6371000  # Earth's radius in meters
        
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
    
    def calculate_azimuth_difference(self, az1, az2):
        """Calculate minimum angle between two azimuths."""
        diff = abs(az1 - az2)
        return min(diff, 360 - diff)
    
    def find_neighbors(self, ep_data, mappings, search_radius, max_neighbors, progress_callback=None):
        """Find neighbors with real-time progress updates"""
        try:
            neighbors_list = []
            total_cells = len(ep_data)
            processed_cells = 0
            
            # Initial progress update
            if progress_callback:
                progress_callback(10, "Starting neighbor calculation...")
            
            # Process each cell
            for idx1, serving_cell in ep_data.iterrows():
                cell_neighbors = []
                
                # Calculate progress percentage
                progress = min(85, 10 + (processed_cells / total_cells * 75))
                if progress_callback and processed_cells % max(1, total_cells // 100) == 0:
                    progress_callback(int(progress), f"Processing cell {processed_cells + 1} of {total_cells}")
                
                for idx2, neighbor_cell in ep_data.iterrows():
                    if idx1 != idx2:  # Don't compare cell with itself
                        try:
                            # Use the mapped column names directly
                            distance = self.calculate_distance(
                                float(serving_cell[mappings['EP Latitude']]), 
                                float(serving_cell[mappings['EP Longitude']]),
                                float(neighbor_cell[mappings['EP Latitude']]), 
                                float(neighbor_cell[mappings['EP Longitude']])
                            )
                            
                            if distance <= search_radius:
                                azimuth_diff = self.calculate_azimuth_difference(
                                    float(serving_cell[mappings['EP Azimuth']]), 
                                    float(neighbor_cell[mappings['EP Azimuth']])
                                )
                                
                                # Determine neighbor type based on carrier
                                neighbor_type = "Intra-Frequency" if (
                                    serving_cell[mappings['Carrier']] == neighbor_cell[mappings['Carrier']]
                                ) else "Inter-Frequency"
                                
                                cell_neighbors.append({
                                    'Serving Site': serving_cell[mappings['EP Site ID']],
                                    'Serving Cell': serving_cell[mappings['EP Cell ID']],
                                    'Neighbor Site': neighbor_cell[mappings['EP Site ID']],
                                    'Neighbor Cell': neighbor_cell[mappings['EP Cell ID']],
                                    'Distance': round(distance, 2),
                                    'Azimuth Difference': round(azimuth_diff, 2),
                                    'Neighbor Type': neighbor_type,
                                    'Serving Carrier': serving_cell[mappings['Carrier']],
                                    'Neighbor Carrier': neighbor_cell[mappings['Carrier']]
                                })
                        except Exception as e:
                            print(f"Error processing neighbor comparison: {str(e)}")
                            continue
                
                # Sort neighbors by distance and take top max_neighbors
                cell_neighbors.sort(key=lambda x: x['Distance'])
                cell_neighbors = cell_neighbors[:max_neighbors]
                neighbors_list.extend(cell_neighbors)
                
                processed_cells += 1
            
            # Final progress update
            if progress_callback:
                progress_callback(85, "Finalizing results...")
            
            return pd.DataFrame(neighbors_list)
            
        except Exception as e:
            raise Exception(f"Error in neighbor calculation: {str(e)}")

class NeighborTable(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("neighborTable")
        self.setStyleSheet("""
            QFrame#neighborTable {
                background-color: white;
                border-radius: 10px;
                padding: 10px;
            }
        """)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        header_layout = QHBoxLayout()
        title = QLabel("Neighbor Relations")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1F2937;")
        
        export_btn = QPushButton("Export")
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #4682B4;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #3A6E9E;
            }
        """)
        export_btn.clicked.connect(self.export_data)
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(export_btn)
        layout.addLayout(header_layout)
        
        self.table = QTableWidget()
        self.table.setStyleSheet("""
            QTableWidget {
                border: none;
                gridline-color: #E5E7EB;
            }
            QHeaderView::section {
                background-color: #F9FAFB;
                padding: 8px;
                border: none;
                font-weight: bold;
                color: #4B5563;
            }
        """)
        columns = ["Serving Site", "Serving Cell", "Neighbor Site", "Neighbor Cell", 
                  "Distance", "Azimuth Difference", "Neighbor Type", 
                  "Serving Carrier", "Neighbor Carrier"]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

    def set_data(self, data):
        try:
            self.table.setRowCount(0)
            for row_idx, row in data.iterrows():
                self.table.insertRow(row_idx)
                for col_idx, value in enumerate(row):
                    item = QTableWidgetItem(str(value))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table.setItem(row_idx, col_idx, item)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to set table data: {str(e)}")

    def export_data(self):
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export Neighbors", "", "CSV Files (*.csv)")
            if file_path:
                data = []
                headers = []
                for j in range(self.table.columnCount()):
                    headers.append(self.table.horizontalHeaderItem(j).text())
                
                for row in range(self.table.rowCount()):
                    row_data = []
                    for col in range(self.table.columnCount()):
                        item = self.table.item(row, col)
                        row_data.append(item.text() if item else '')
                    data.append(row_data)
                
                df = pd.DataFrame(data, columns=headers)
                df.to_csv(file_path, index=False)
                QMessageBox.information(self, "Success", "Data exported successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export data: {str(e)}")

class MetricCard(QFrame):
    def __init__(self, title, value, percentage, parent=None):
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setStyleSheet("""
            QFrame#metricCard {
                background-color: white;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)
        
        # Main vertical layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Center everything
        
        # Icon at the top
        icon_label = QLabel()
        icon_label.setFixedSize(40, 40)
        icon_path = self.get_icon_path(title)
        if icon_path:
            try:
                renderer = QSvgRenderer(icon_path)
                pixmap = QPixmap(40, 40)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                icon_label.setPixmap(pixmap)
            except Exception as e:
                print(f"Error loading icon for {title}: {str(e)}")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Title in bold and centered
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            color: #1F2937; 
            font-size: 14px; 
            font-weight: bold;
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Value and percentage
        value_layout = QHBoxLayout()
        value_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        value_label = QLabel(str(value))
        value_label.setStyleSheet("color: #1F2937; font-size: 24px; font-weight: bold;")
        
        percentage_label = QLabel(f"{percentage:.1f}%")
        percentage_label.setStyleSheet("color: #6B7280; font-size: 14px; margin-left: 5px;")
        
        value_layout.addWidget(value_label)
        value_layout.addWidget(percentage_label)
        
        main_layout.addLayout(value_layout)

    def get_icon_path(self, title):
        """Get the appropriate icon path based on the metric title"""
        try:
            base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'icons')
            icon_mapping = {
                "Total Cells": "total-cells-icon.svg",
                "Total Neighbor Relations": "total-relations-icon.svg",
                "Average Neighbors per Cell": "avg-neighbors-icon.svg",
                "Intra-Frequency Relations": "intra-freq-icon.svg",
                "Inter-Frequency Relations": "inter-freq-icon.svg"
            }
            
            if title in icon_mapping:
                icon_path = os.path.join(base_path, icon_mapping[title])
                if os.path.exists(icon_path):
                    return icon_path
                print(f"Icon file not found: {icon_path}")
            return None
        except Exception as e:
            print(f"Error getting icon path: {str(e)}")
            return None

    def update_metrics(self):
        try:
            # Clear existing metrics
            for i in reversed(range(self.metrics_layout.count())):
                item = self.metrics_layout.itemAt(i)
                if item.widget():
                    item.widget().deleteLater()
            
            # Calculate metrics
            total_cells = len(self.ep_data)
            total_relations = len(self.result_df)
            avg_neighbors = total_relations / total_cells if total_cells > 0 else 0
            
            # Count intra/inter frequency relations
            intra_freq = len(self.result_df[
                self.result_df['Neighbor Type'] == 'Intra-Frequency'])
            inter_freq = len(self.result_df[
                self.result_df['Neighbor Type'] == 'Inter-Frequency'])
            
            # Add metric cards without icons
            self.metrics_layout.addWidget(MetricCard(
                "Total Cells",
                total_cells,
                100.0
            ))
            
            self.metrics_layout.addWidget(MetricCard(
                "Total Neighbor Relations",
                total_relations,
                (total_relations / (total_cells * 32)) * 100 if total_cells > 0 else 0
            ))
            
            self.metrics_layout.addWidget(MetricCard(
                "Average Neighbors per Cell",
                f"{avg_neighbors:.1f}",
                (avg_neighbors / 32) * 100
            ))
            
            self.metrics_layout.addWidget(MetricCard(
                "Intra-Frequency Relations",
                intra_freq,
                (intra_freq / total_relations) * 100 if total_relations > 0 else 0
            ))
            
            self.metrics_layout.addWidget(MetricCard(
                "Inter-Frequency Relations",
                inter_freq,
                (inter_freq / total_relations) * 100 if total_relations > 0 else 0
            ))
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update metrics: {str(e)}")

class IconLoader:
    @staticmethod
    def load_svg_icon(filename, color="#FFFFFF", size=32):
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'icons', filename)
            if not os.path.exists(icon_path):
                print(f"Icon not found: {icon_path}")
                return None
            
            renderer = QSvgRenderer(icon_path)
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(pixmap)
            renderer.render(painter)
            
            if color != "#FFFFFF":
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(pixmap.rect(), QColor(color))
            
            painter.end()
            return QIcon(pixmap)  # Return QIcon instead of just pixmap
        except Exception as e:
            print(f"Error loading icon {filename}: {str(e)}")
            return None
        
class NeighborAuditWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        
        # Check if data is available
        if not self.validate_data():
            QMessageBox.warning(
                self, 
                "Warning", 
                "Please upload and match the required data before using the Neighbor Analysis."
            )
            if self.main_window and hasattr(self.main_window, 'stack'):
                self.main_window.stack.setCurrentIndex(0)
                if hasattr(self.main_window, 'footer'):
                    self.main_window.footer.show()
            return
        
        self.ep_data = getattr(self.main_window, 'ep_data', None)
        self.mappings = getattr(self.main_window, 'mappings', None)
        self.result_df = None
        self.calculator = NeighborCalculator()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Header
        header = self.create_header()
        layout.addLayout(header)

        # Settings and Content Grid
        content = QGridLayout()
        content.setSpacing(10)
        
        # Settings Panel on Left
        self.settings_panel = SettingsPanel()
        content.addWidget(self.settings_panel, 0, 0, 1, 3)
        
        # Metrics Panel
        metrics_widget = QWidget()
        self.metrics_layout = QHBoxLayout(metrics_widget)
        self.metrics_layout.setSpacing(10)
        content.addWidget(metrics_widget, 0, 3, 1, 9)
        
        # Neighbor Table
        self.neighbor_table = NeighborTable()
        content.addWidget(self.neighbor_table, 1, 0, 1, 12)
        
        layout.addLayout(content)

    def validate_data(self):
        """Check if required data is available and valid"""
        try:
            # Check if main window and data exists
            if not hasattr(self.main_window, 'ep_data') or self.main_window.ep_data is None:
                QMessageBox.warning(
                    self, 
                    "Warning", 
                    "Please upload EP data in the Upload Data window first."
                )
                return False

            if not hasattr(self.main_window, 'mappings') or self.main_window.mappings is None:
                QMessageBox.warning(
                    self, 
                    "Warning", 
                    "Please match columns in the Upload Data window first."
                )
                return False

            # Check required columns
            required_columns = [
                'EP Site ID', 'EP Cell ID', 'EP Latitude', 
                'EP Longitude', 'EP Azimuth', 'Carrier'
            ]
            
            missing_columns = []
            for col in required_columns:
                if col not in self.main_window.mappings:
                    missing_columns.append(col)
            
            if missing_columns:
                QMessageBox.warning(
                    self, 
                    "Warning", 
                    f"The following required columns are not mapped:\n{', '.join(missing_columns)}\n\n"
                    "Please map these columns in the Upload Data window."
                )
                return False

            # Validate column data types
            ep_data = self.main_window.ep_data
            mappings = self.main_window.mappings

            try:
                pd.to_numeric(ep_data[mappings['EP Latitude']])
                pd.to_numeric(ep_data[mappings['EP Longitude']])
                pd.to_numeric(ep_data[mappings['EP Azimuth']])
            except Exception:
                QMessageBox.warning(
                    self, 
                    "Warning", 
                    "Latitude, Longitude, or Azimuth columns contain invalid numeric data.\n"
                    "Please check your data in the Upload Data window."
                )
                return False

            return True

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error validating data: {str(e)}")
            return False

    def create_header(self):
        header = QHBoxLayout()
        
        # Left side with home button and title
        left_side = QHBoxLayout()
        
        home_btn = QPushButton()
        home_icon = IconLoader.load_svg_icon("home.svg", color="#3b82f6", size=24)  # Changed to blue color and better size
        if home_icon:
            home_btn.setIcon(home_icon)
            home_btn.setIconSize(QSize(24, 24))
        home_btn.clicked.connect(self.go_home)
        home_btn.setFixedSize(40, 40)
        home_btn.setToolTip("Return to Home")  # Added tooltip
        home_btn.setStyleSheet("""
            QPushButton {
                background: #f1f5f9;
                border-radius: 8px;
                padding: 6px;
            }
            QPushButton:hover {
                background: #e2e8f0;
                border: 1px solid #3b82f6;
            }
            QToolTip {
                background-color: #1e293b;
                color: white;
                border: none;
                padding: 6px;
                border-radius: 4px;
                font-size: 12px;
            }
        """)
        left_side.addWidget(home_btn)
        
        title = QLabel("Neighbor Audit Analysis")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #1e293b;")
        left_side.addWidget(title)
        left_side.addStretch()
        
        header.addLayout(left_side)
        header.addStretch()
        
        # Analyze button
        analyze_btn = QPushButton("Analyze")
        analyze_btn.setStyleSheet("""
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
        analyze_btn.clicked.connect(self.analyze_data)
        header.addWidget(analyze_btn)
        
        return header

    def analyze_data(self):
        """Analyze neighbor relations with real-time progress updates"""
        try:
            if not self.load_data():
                return
            
            # Get settings values
            search_radius = self.settings_panel.radius_slider.slider.value()
            max_neighbors = self.settings_panel.max_neighbors_slider.slider.value()
            
            # Create and show progress dialog immediately
            progress_dialog = CircularProgressDialog(self)
            progress_dialog.setLabelText("Initializing neighbor analysis...")
            progress_dialog.setValue(0)
            progress_dialog.show()
            QApplication.processEvents()  # Ensure dialog shows immediately
            
            try:
                # Update progress for initialization
                progress_dialog.setLabelText("Loading data...")
                progress_dialog.setValue(5)
                QApplication.processEvents()
                
                def progress_callback(progress, message=None):
                    progress_dialog.setValue(progress)
                    if message:
                        progress_dialog.setLabelText(message)
                    QApplication.processEvents()
                
                # Calculate neighbors with progress updates
                total_cells = len(self.ep_data)
                batch_size = max(1, total_cells // 100)  # For progress updates
                
                progress_dialog.setLabelText("Analyzing neighbor relations...")
                self.result_df = self.calculator.find_neighbors(
                    self.ep_data,
                    self.mappings,
                    search_radius,
                    max_neighbors,
                    progress_callback
                )
                
                # Update metrics display
                progress_dialog.setLabelText("Updating metrics...")
                progress_dialog.setValue(90)
                QApplication.processEvents()
                
                self.update_metrics()
                
                # Update neighbor table
                progress_dialog.setLabelText("Populating results table...")
                progress_dialog.setValue(95)
                QApplication.processEvents()
                
                self.neighbor_table.set_data(self.result_df)
                
                # Complete
                progress_dialog.setValue(100)
                progress_dialog.setLabelText("Analysis complete!")
                QApplication.processEvents()
                
                QTimer.singleShot(500, progress_dialog.close)
                QMessageBox.information(
                    self, "Success", "Neighbor analysis completed successfully!"
                )
                
            except Exception as e:
                progress_dialog.close()
                QMessageBox.critical(
                    self, "Error", f"Failed to analyze neighbors: {str(e)}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error in neighbor analysis: {str(e)}")

    def update_metrics(self):
        try:
            # Clear existing metrics
            for i in reversed(range(self.metrics_layout.count())):
                item = self.metrics_layout.itemAt(i)
                if item.widget():
                    item.widget().deleteLater()
            
            # Calculate metrics
            total_cells = len(self.ep_data)
            total_relations = len(self.result_df)
            avg_neighbors = total_relations / total_cells if total_cells > 0 else 0
            
            # Count intra/inter frequency relations
            intra_freq = len(self.result_df[
                self.result_df['Neighbor Type'] == 'Intra-Frequency'])
            inter_freq = len(self.result_df[
                self.result_df['Neighbor Type'] == 'Inter-Frequency'])
            
            # Add metric cards
            self.metrics_layout.addWidget(MetricCard(
                "Total Cells",
                total_cells,
                100.0
            ))
            
            self.metrics_layout.addWidget(MetricCard(
                "Total Neighbor Relations",
                total_relations,
                (total_relations / (total_cells * 32)) * 100 
                if total_cells > 0 else 0
            ))
            
            self.metrics_layout.addWidget(MetricCard(
                "Average Neighbors per Cell",
                f"{avg_neighbors:.1f}",
                (avg_neighbors / 32) * 100
            ))
            
            self.metrics_layout.addWidget(MetricCard(
                "Intra-Frequency Relations",
                intra_freq,
                (intra_freq / total_relations) * 100 
                if total_relations > 0 else 0
            ))
            
            self.metrics_layout.addWidget(MetricCard(
                "Inter-Frequency Relations",
                inter_freq,
                (inter_freq / total_relations) * 100 
                if total_relations > 0 else 0
            ))
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update metrics: {str(e)}")

    def load_data(self):
        if self.ep_data is None or self.mappings is None:
            QMessageBox.warning(self, "Warning", 
                "No data available. Please upload and submit data first.")
            return False
        return True

    def go_home(self):
        try:
            if self.main_window and hasattr(self.main_window, 'stack'):
                self.main_window.stack.setCurrentIndex(0)
                if hasattr(self.main_window, 'footer'):
                    self.main_window.footer.show()
        except Exception as e:
            print(f"Error navigating home: {str(e)}")


