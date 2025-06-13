# actual_azimuth_window.py
import sys
import os
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import multiprocessing
import sklearn
from sklearn.cluster import DBSCAN
from matplotlib.patches import Circle
from functools import partial

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
                            QPushButton, QFrame, QTableWidget, QTableWidgetItem,
                            QGridLayout, QScrollArea, QFileDialog, QMessageBox,
                            QGraphicsDropShadowEffect, QComboBox, QDialog, QApplication)
from PyQt6.QtCore import Qt, QSize, QPoint, QTimer
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPainterPath, QPalette, QIcon, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.colors as mcolors
from geo import GeoAnalysisWindow
from tilt import process_site, calculate_actual_coordinates
from grid_azimuth import process_grid_based_site, calculate_grid_center, calculate_bearing, calculate_distance
from azimuth_utils import calculate_actual_azimuth_with_centroid

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

class ResultFilter(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(200)
        self.setStyleSheet("""
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
        self.addItem("All Results")
        self.addItem("Azimuth Issue Cells")

    def update_options(self, results):
        self.clear()
        self.addItem("All Results")
        unique_results = set(row[3] for row in results)  # Assuming 'Result' is column 3
        for result in sorted(unique_results):
            self.addItem(result)

class AzimuthThreshold(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimum(1)
        self.setMaximum(90)  # Maximum azimuth deviation of 90 degrees
        self.setValue(25)  # Default threshold of 25 degrees
        self.setSuffix("°")  # Degree symbol
        self.setFixedWidth(100)
        self.setStyleSheet("""
            QSpinBox {
                border: 1px solid #e2e8f0;
                border-radius: 4px;
                padding: 5px 10px;
                background: white;
            }
            QSpinBox:hover {
                border-color: #4682B4;
            }
        """)

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

        # Draw background circle
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(70, 70, 70))
        painter.drawEllipse(self.progress_width, self.progress_width, 
                          self.width - 2 * self.progress_width, 
                          self.height - 2 * self.progress_width)

        # Draw spinning progress circle
        if self.value < 100:
            self.angle = (self.angle - 5) % 360
            painter.setPen(QPen(QColor("#4682B4"), self.progress_width))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(self.progress_width, self.progress_width, 
                          self.width - 2 * self.progress_width, 
                          self.height - 2 * self.progress_width,
                          self.angle * 16, -120 * 16)

        # Draw progress arc
        painter.setPen(QPen(QColor("#4682B4"), self.progress_width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        span_angle = int(-self.value * 360 / 100 * 16)
        painter.drawArc(self.progress_width, self.progress_width, 
                       self.width - 2 * self.progress_width, 
                       self.height - 2 * self.progress_width,
                       90 * 16, span_angle)

        # Draw percentage text
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
                background-color: rgba(0, 0, 0, 1l);
                border-radius: 10px;
            }
        """)
        layout.addWidget(self.bg_frame)
        
        content_layout = QVBoxLayout(self.bg_frame)
        content_layout.setSpacing(15)
        
        self.progress_bar = CircularProgressBar(self)
        self.progress_bar.setFixedSize(120, 120)
        content_layout.addWidget(self.progress_bar, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.label = QLabel("Processing...", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 10px;
                font-weight: bold;
                margin-top: 10px;
            }
        """)
        content_layout.addWidget(self.label)
        
        self.setFixedSize(200, 200)
        
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update)
        self.animation_timer.start(30)
        self.current_value = 0

    def setValue(self, value):
        if value > self.current_value:
            self.current_value = value
            self.progress_bar.setValue(value)
            if value >= 100:
                QTimer.singleShot(500, self.close)

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
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
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
        title_label.setStyleSheet("color: #1F2937; font-size: 14px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Value and percentage in horizontal layout
        value_layout = QHBoxLayout()
        value_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        value_label = QLabel(str(value))
        value_label.setStyleSheet("color: #1F2937; font-size: 24px; font-weight: bold;")
        
        percentage_label = QLabel(f"{percentage:.1f}%")
        percentage_label.setStyleSheet("color: #6B7280; font-size: 14px; margin-left: 5px;")
        
        value_layout.addWidget(value_label)
        value_layout.addWidget(percentage_label)
        
        main_layout.addLayout(value_layout)
        
        # Progress bar
        self.progress_bar = ProgressBar(percentage)
        main_layout.addWidget(self.progress_bar)

    def get_icon_path(self, title):
        """Get the appropriate icon path based on the metric title"""
        try:
            base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'icons')
            icon_mapping = {
                "Total Azimuth Issue Cells": "inter-freq-icon.svg",
                "Total Sites Affected": "total-cells-icon.svg"
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

class ProgressBar(QFrame):
    def __init__(self, percentage, parent=None):
        super().__init__(parent)
        self.percentage = percentage
        self.setFixedHeight(8)
        self.setStyleSheet("background-color: #F3F4F6; border-radius: 4px;")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#F3F4F6"))
        progress_width = int(self.width() * (self.percentage / 100))
        progress_rect = self.rect()
        progress_rect.setWidth(progress_width)
        painter.fillRect(progress_rect, QColor("#4682B4"))

class MRPlotDialog(QDialog):
    def __init__(self, site_id, site_lat, site_lon, planned_azimuth, cell_id, carrier, mr_points, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"MR Plot - Site {site_id} | Cell {cell_id} ({carrier})")
        self.setMinimumSize(700, 700)
        layout = QVBoxLayout(self)
        fig = Figure(figsize=(7, 7))
        canvas = FigureCanvas(fig)
        layout.addWidget(canvas)
        ax = fig.add_subplot(111)
        # Helper: Google/compass azimuth (0°=N, 90°=E)
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
        # Plot all MR points (longitude=X, latitude=Y)
        coords = mr_points[[parent.mappings['MR Latitude'], parent.mappings['MR Longitude']]].values.astype(float)
        ax.scatter(coords[:, 1], coords[:, 0], s=10, c='gray', alpha=0.5, label='All MR')
        # Cluster with DBSCAN
        if len(coords) > 10:
            clustering = DBSCAN(eps=0.0015, min_samples=10).fit(coords)
            labels = clustering.labels_
            valid = labels != -1
            if np.any(valid):
                main_label = pd.Series(labels[valid]).mode()[0]
                cluster_coords = coords[labels == main_label]
                # Highlight main cluster
                ax.scatter(cluster_coords[:, 1], cluster_coords[:, 0], s=18, c='lime', alpha=0.7, label='Main Cluster')
                # Draw circle around cluster
                center = np.mean(cluster_coords, axis=0)
                dists = np.linalg.norm(cluster_coords - center, axis=1)
                radius = np.percentile(dists, 90)  # 90th percentile for robust circle
                circ = Circle((center[1], center[0]), radius, color='lime', fill=False, lw=2, alpha=0.5)
                ax.add_patch(circ)
                # Draw actual azimuth line (Google convention)
                actual_azimuth = calculate_azimuth(site_lat, site_lon, center[0], center[1])
                import math
                length = 0.01  # ~1km for visual
                az_rad = math.radians(actual_azimuth)
                end_lat = site_lat + length * math.cos(az_rad)
                end_lon = site_lon + length * math.sin(az_rad)
                ax.plot([site_lon, end_lon], [site_lat, end_lat], color='green', lw=3, label='Actual Azimuth')
                # Mark centroid
                ax.scatter([center[1]], [center[0]], c='green', s=60, marker='x')
            else:
                center = np.mean(coords, axis=0)
                actual_azimuth = calculate_azimuth(site_lat, site_lon, center[0], center[1])
                import math
                length = 0.01
                az_rad = math.radians(actual_azimuth)
                end_lat = site_lat + length * math.cos(az_rad)
                end_lon = site_lon + length * math.sin(az_rad)
                ax.plot([site_lon, end_lon], [site_lat, end_lat], color='green', lw=3, label='Actual Azimuth')
                ax.scatter([center[1]], [center[0]], c='green', s=60, marker='x')
        # Site location
        ax.scatter([site_lon], [site_lat], c='black', s=80, marker='*', label='Site')
        # Planned azimuth line (Google convention)
        if planned_azimuth is not None:
            import math
            length = 0.01  # ~1km for visual
            az_rad = math.radians(planned_azimuth)
            end_lat = site_lat + length * math.cos(az_rad)
            end_lon = site_lon + length * math.sin(az_rad)
            ax.plot([site_lon, end_lon], [site_lat, end_lat], 'k--', lw=2, label='Planned Azimuth')
        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')
        ax.set_title(f'MR Distribution and Azimuth\nSite ID: {site_id}   Cell ID: {cell_id}   Carrier: {carrier}')
        ax.legend()
        ax.set_aspect('equal')
        fig.tight_layout()

class AzimuthTable(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("azimuthTable")
        self.setStyleSheet("""
            QFrame#azimuthTable {
                background-color: white;
                border-radius: 10px;
                padding: 10px;
            }
        """)
        self.parent_window = parent
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        header_layout = QHBoxLayout()
        title = QLabel("Azimuth Details")
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
        self.table.setColumnCount(7)  
        self.table.setHorizontalHeaderLabels([
            "eNodeB Name", "Cell ID", "Carrier", 
            "Planned Azimuth", "Actual Azimuth", "Azimuth Difference", "Show MR Plot"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

    def set_data(self, data):
        try:
            self.table.setRowCount(0)
            for row_data in data:
                row = self.table.rowCount()
                self.table.insertRow(row)
                for col, value in enumerate(row_data):
                    item = QTableWidgetItem(str(value))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table.setItem(row, col, item)
                # Add Show MR Plot button
                btn = QPushButton("Show MR Plot")
                btn.setStyleSheet("background-color: #82CA9D; color: #222; border-radius: 4px; padding: 4px 8px;")
                site_id = row_data[0]
                cell_id = row_data[1]
                carrier = row_data[2]
                btn.clicked.connect(partial(self.parent_window.show_mr_plot, site_id, cell_id, carrier))
                self.table.setCellWidget(row, 6, btn)
        except Exception as e:
            print(f"Error setting table data: {str(e)}")

    def export_data(self):
        try:
            file_path, _ = QFileDialog.getSaveFileName(self, "Export Data", "", "CSV Files (*.csv)")
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

class IconLoader:
    @staticmethod
    def load_svg_icon(filename, color="#FFFFFF", size=32):
        try:
            icon_path = resource_path(os.path.join('resources', 'icons', filename))
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
            return QIcon(pixmap)
        except Exception as e:
            print(f"Error loading icon {filename}: {str(e)}")
            return None
        
class ActualAzimuthWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.mr_data = getattr(self.main_window, 'mr_data', None)
        self.ep_data = getattr(self.main_window, 'ep_data', None)
        self.mappings = getattr(self.main_window, 'mappings', None)
        self.beam_width = getattr(self.main_window, 'beam_width', 30)
        self.distance = getattr(self.main_window, 'distance', 500)
        
        self.result_df = None
        self.is_analyzing = False
        self.analyzed_df = None
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        header = self.create_header()
        layout.addLayout(header)

        content = QGridLayout()
        content.setSpacing(10)
        
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.metrics_layout = QHBoxLayout()
        self.metrics_layout.setSpacing(10)
        left_layout.addLayout(self.metrics_layout)
        
        self.charts_layout = QVBoxLayout()
        self.charts_layout.setSpacing(10)
        left_layout.addLayout(self.charts_layout)
        
        content.addWidget(left_widget, 0, 0, 1, 8)
        
        self.azimuth_table = AzimuthTable(parent=self)
        content.addWidget(self.azimuth_table, 0, 8, 1, 4)
        
        content.setColumnStretch(0, 6)
        content.setColumnStretch(8, 4)
        
        layout.addLayout(content)

    def create_header(self):
        header = QHBoxLayout()
        
        left_side = QHBoxLayout()
        
        home_btn = QPushButton()
        home_icon = IconLoader.load_svg_icon("home.svg", color="#3b82f6", size=24)
        if home_icon:
            home_btn.setIcon(home_icon)
            home_btn.setIconSize(QSize(24, 24))
        home_btn.clicked.connect(self.go_home)
        home_btn.setFixedSize(40, 40)
        home_btn.setToolTip("Return to Home")
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
        
        title = QLabel("Actual Azimuth Analysis")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #1e293b;")
        left_side.addWidget(title)
        left_side.addStretch()
        
        header.addLayout(left_side)
        header.addStretch()
        
        right_side = QHBoxLayout()
        
        # Add threshold control
        threshold_label = QLabel("Azimuth Threshold:")
        threshold_label.setStyleSheet("color: #64748b;")
        right_side.addWidget(threshold_label)
        
        self.azimuth_threshold = AzimuthThreshold()
        self.azimuth_threshold.valueChanged.connect(self.on_threshold_changed)
        right_side.addWidget(self.azimuth_threshold)
        
        right_side.addSpacing(20)
        
        filter_label = QLabel("Filter Results:")
        filter_label.setStyleSheet("color: #64748b;")
        right_side.addWidget(filter_label)
        
        self.result_filter = ResultFilter()
        self.result_filter.currentIndexChanged.connect(self.apply_result_filter)
        right_side.addWidget(self.result_filter)
        
        right_side.addSpacing(10)
        
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
        right_side.addWidget(analyze_btn)
        
        geo_btn = QPushButton("Geo Analysis")
        geo_btn.setStyleSheet("""
            QPushButton {
                background-color: #6366f1;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-weight: bold;
                margin-left: 10px;
            }
            QPushButton:hover {
                background-color: #4f46e5;
            }
        """)
        geo_btn.clicked.connect(self.show_geo_window)
        right_side.addWidget(geo_btn)

        header.addLayout(right_side)
        
        return header
    
    # Add this validation method to ActualAzimuthWindow class
    def validate_data_mappings(self):
        """Validate that all required columns exist in the data"""
        try:
            if not all(key in self.mappings for key in [
                'MR Site ID', 'MR Cell ID', 'MR Latitude', 'MR Longitude', 'MR RSRP',
                'EP Site ID', 'EP Cell ID', 'EP Latitude', 'EP Longitude', 'EP Azimuth', 'Carrier'
            ]):
                QMessageBox.warning(self, "Warning", 
                    "Missing required column mappings. Please check column matching.")
                return False

            # Verify MR data columns
            mr_columns = self.mr_data.columns
            for key in ['MR Site ID', 'MR Cell ID', 'MR Latitude', 'MR Longitude', 'MR RSRP']:
                if self.mappings[key] not in mr_columns:
                    QMessageBox.warning(self, "Warning", 
                        f"Column {self.mappings[key]} not found in MR data. Please check column matching.")
                    return False

            # Verify EP data columns
            ep_columns = self.ep_data.columns
            for key in ['EP Site ID', 'EP Cell ID', 'EP Latitude', 'EP Longitude', 'EP Azimuth', 'Carrier']:
                if self.mappings[key] not in ep_columns:
                    QMessageBox.warning(self, "Warning", 
                        f"Column {self.mappings[key]} not found in EP data. Please check column matching.")
                    return False

            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error validating data mappings: {str(e)}")
            return False

    # Then update the load_data method
    def load_data(self):
        try:
            if self.mr_data is None or self.ep_data is None or self.mappings is None:
                QMessageBox.warning(self, "Warning", 
                    "No data available. Please upload data and submit from Upload window first.")
                return False

            # Get fresh data and mappings from main window
            self.mr_data = getattr(self.main_window, 'mr_data', None)
            self.ep_data = getattr(self.main_window, 'ep_data', None)
            self.mappings = getattr(self.main_window, 'mappings', None)

            # Validate mappings with current data
            if not self.validate_data_mappings():
                return False

            # Before analysis, build EP_key to carrier lookup and add Carrier_Lookup to MR data
            if 'Carrier_Lookup' not in self.mr_data.columns:
                ep_key_to_carrier = dict(zip(self.ep_data[self.mappings['EP_key']], self.ep_data[self.mappings['Carrier']]))
                self.mr_data['Carrier_Lookup'] = self.mr_data[self.mappings['MR_key']].map(ep_key_to_carrier)

            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load data: {str(e)}")
            return False

    def analyze_data(self):
        try:
            if self.is_analyzing:
                QMessageBox.warning(self, "Warning", "Analysis already in progress. Please wait.")
                return
                        
            if not self.load_data():
                QMessageBox.warning(self, "Warning", "No data available. Please upload data and submit first.")
                return
            
            self.is_analyzing = True
            progress_dialog = CircularProgressDialog(self)
            progress_dialog.setLabelText("Initializing azimuth analysis...")
            progress_dialog.setValue(0)
            progress_dialog.show()
            QApplication.processEvents()

            try:
                self.clear_layouts()
                progress_dialog.setValue(10)
                progress_dialog.setLabelText("Processing site data...")
                QApplication.processEvents()

                self.calculate_actual_azimuth_with_centroid()

                progress_dialog.setValue(85)
                progress_dialog.setLabelText("Updating display...")
                QApplication.processEvents()

                # Update UI components
                self.update_metrics()
                self.update_charts()
                self.update_table()
                self.result_filter.setCurrentIndex(0)

                progress_dialog.setValue(100)
                progress_dialog.setLabelText("Analysis complete!")
                QApplication.processEvents()

                QTimer.singleShot(500, progress_dialog.close)
                QMessageBox.information(self, "Success", "Azimuth analysis completed successfully!")

            except Exception as e:
                print(f"Analysis error: {str(e)}")
                QMessageBox.critical(self, "Error", f"Failed to analyze azimuth data: {str(e)}")
            finally:
                self.is_analyzing = False
                progress_dialog.close()

        except Exception as e:
            print(f"Outer error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Azimuth analysis failed: {str(e)}")
            self.is_analyzing = False
                    

    def calculate_statistics(self):
        stats = {
            'total_cells': 0,
            'azimuth_issue_count': 0,
            'affected_sites': 0,
            'issue_percentage': 0,
            'sites_percentage': 0,
            'carrier_stats': {}
        }
        
        try:
            if hasattr(self, 'analyzed_df') and self.analyzed_df is not None:
                current_threshold = self.azimuth_threshold.value()
                stats['total_cells'] = len(self.analyzed_df)
                # Convert Azimuth Difference to numeric, ignore non-numeric
                df = self.analyzed_df.copy()
                df['Azimuth Difference'] = pd.to_numeric(df['Azimuth Difference'], errors='coerce')
                # Filter out rows where Azimuth Difference is NaN
                df = df.dropna(subset=['Azimuth Difference'])
                # Calculate issues based on azimuth difference
                issue_mask = df['Azimuth Difference'] > current_threshold
                issue_df = df[issue_mask]
                stats['azimuth_issue_count'] = len(issue_df)
                if stats['total_cells'] > 0:
                    stats['issue_percentage'] = (stats['azimuth_issue_count'] / stats['total_cells']) * 100
                stats['affected_sites'] = len(issue_df['eNodeb Name'].unique())
                total_sites = len(self.analyzed_df['eNodeb Name'].unique())
                if total_sites > 0:
                    stats['sites_percentage'] = (stats['affected_sites'] / total_sites) * 100
                # Calculate carrier statistics
                for carrier in df['Carrier'].unique():
                    carrier_df = df[df['Carrier'] == carrier]
                    carrier_total = len(carrier_df)
                    carrier_issues = len(carrier_df[carrier_df['Azimuth Difference'] > current_threshold])
                    if carrier_total > 0:
                        stats['carrier_stats'][carrier] = {
                            'total': carrier_total,
                            'issues': carrier_issues,
                            'percentage': (carrier_issues / carrier_total) * 100
                        }
        except Exception as e:
            print(f"Error calculating statistics: {str(e)}")
        return stats

    def update_metrics(self):
        try:
            for i in reversed(range(self.metrics_layout.count())):
                item = self.metrics_layout.itemAt(i)
                if item.widget():
                    item.widget().deleteLater()
            
            stats = self.calculate_statistics()
            
            self.metrics_layout.addWidget(MetricCard(
                "Total Azimuth Issue Cells",
                stats['azimuth_issue_count'],
                stats['issue_percentage']
            ))
            self.metrics_layout.addWidget(MetricCard(
                "Total Sites Affected",
                stats['affected_sites'],
                stats['sites_percentage']
            ))
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update metrics: {str(e)}")

    def update_table(self):
        try:
            if not hasattr(self, 'analyzed_df') or self.analyzed_df is None:
                return
            
            table_data = []
            for _, row in self.analyzed_df.iterrows():
                table_data.append([
                    row['eNodeb Name'],
                    row['Cell ID'],
                    row['Carrier'],
                    row['Planned Azimuth'],
                    row['Actual Azimuth'],
                    row['Azimuth Difference'],
                    None
                ])
            self.azimuth_table.set_data(table_data)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update table: {str(e)}")

    def apply_result_filter(self, index):
        try:
            if not hasattr(self, 'analyzed_df') or self.analyzed_df is None:
                return
                
            filter_text = self.result_filter.currentText()
            current_threshold = self.azimuth_threshold.value()
            # Convert Azimuth Difference to numeric for filtering
            df = self.analyzed_df.copy()
            df['Azimuth Difference'] = pd.to_numeric(df['Azimuth Difference'], errors='coerce')
            if filter_text == "All Results":
                filtered_df = self.analyzed_df
            else:  # "Azimuth Issue Cells"
                filtered_df = df[df['Azimuth Difference'] > current_threshold]
            table_data = []
            for _, row in filtered_df.iterrows():
                table_data.append([
                    row['eNodeb Name'],
                    row['Cell ID'],
                    row['Carrier'],
                    row['Planned Azimuth'],
                    row['Actual Azimuth'],
                    row['Azimuth Difference'],
                    None
                ])
            self.azimuth_table.set_data(table_data)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error applying filter: {str(e)}")

    def load_data(self):
        try:
            if self.mr_data is None or self.ep_data is None or self.mappings is None:
                QMessageBox.warning(self, "Warning", 
                    "No data available. Please upload data and submit from Upload window first.")
                return False
                
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load data: {str(e)}")
            return False
        
    def create_carrier_chart(self):
        try:
            if not hasattr(self, 'analyzed_df') or self.analyzed_df is None:
                return None
            current_threshold = self.azimuth_threshold.value()

            fig = Figure(figsize=(8, 4), facecolor='none')
            canvas = FigureCanvas(fig)
            
            fig.subplots_adjust(left=0.2, right=0.95, top=0.9, bottom=0.15)
            
            ax = fig.add_subplot(111)
            
            # Get carrier statistics
            stats = self.calculate_statistics()
            coord_stats = stats['carrier_stats']
            
            if not coord_stats:  # If no data, return None
                return None
                
            carriers = list(coord_stats.keys())
            percentages = [stats['percentage'] for stats in coord_stats.values()]
            labels = [f"{stats['issues']}/{stats['total']}" for stats in coord_stats.values()]
            
            y_pos = np.arange(len(carriers))
            bar_colors = ['#4682B4', '#82CA9D', '#8884D8']
            
            # Add background bars
            for i in y_pos:
                ax.barh(i, 100, color='#F5F5F5', height=0.6, zorder=1)
            
            # Add colored bars
            for i, (percentage, label) in enumerate(zip(percentages, labels)):
                color = bar_colors[i % len(bar_colors)]
                ax.barh(i, percentage, height=0.6, color=color, alpha=0.8, zorder=2)
                
                ax.text(percentage + 0.5, i,
                       f'{percentage:.1f}% ({label})',
                       va='center',
                       ha='left',
                       fontsize=8,
                       color='#666666')
            
            ax.set_yticks(y_pos)
            ax.set_yticklabels(carriers, fontsize=10)
            ax.set_xlim(0, 105)
            
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_visible(False)
            ax.grid(False)
            
            ax.set_title('Azimuth Issues by Carrier',
                         fontsize=11,
                         pad=10,
                         loc='left',
                         color='#666666')
            
            ax.set_xticks(np.arange(0, 101, 20))
            ax.set_xticklabels([])
            ax.tick_params(axis='x', colors='#CCCCCC', length=3)
            
            return canvas
            
        except Exception as e:
            print(f"Error creating carrier chart: {str(e)}")
            return None

    def create_gauge_chart(self, percentage, title):
        try:
            fig = Figure(figsize=(5, 2.8))
            canvas = FigureCanvas(fig)
            
            fig.subplots_adjust(left=0.02, right=0.98, top=0.85, bottom=0.15)
            
            ax = fig.add_subplot(111, projection='polar')
            
            colors = ['#004080', '#3399FF', '#99CCFF']
            bounds = [0, 33, 66, 100]
            
            theta = np.linspace(0, np.pi, 100)
            
            for i in range(len(colors)):
                mask = (theta >= np.pi * bounds[i]/100) & (theta <= np.pi * bounds[i+1]/100)
                ax.plot(theta[mask], [1]*sum(mask), color=colors[i], 
                       linewidth=20, solid_capstyle='round')
            
            pointer_angle = np.pi * percentage / 100
            ax.plot([pointer_angle, pointer_angle], [0, 0.9], 
                    color='black', linewidth=3, zorder=5)
            ax.scatter([pointer_angle], [0], color='black', s=80, zorder=5)
            
            ax.set_rticks([])
            ax.set_xticks([])
            ax.spines['polar'].set_visible(False)
            ax.grid(False)
            
            ax.set_ylim(-0.1, 1.1)
            ax.set_thetamin(0)
            ax.set_thetamax(180)
            
            ax.text(np.pi/2, 0.3, f'{percentage:.0f}%',
                    horizontalalignment='center',
                    verticalalignment='center',
                    fontsize=10,
                    fontweight='bold')
            
            fig.text(0.5, 0.02, title,
                     horizontalalignment='center',
                     verticalalignment='bottom',
                     fontsize=12)
            
            return canvas
        except Exception as e:
            print(f"Error creating gauge chart: {str(e)}")
            return None

    def update_charts(self):
        try:
            while self.charts_layout.count():
                item = self.charts_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    while item.layout().count():
                        child = item.layout().takeAt(0)
                        if child.widget():
                            child.widget().deleteLater()
                    item.layout().setParent(None)
            
            stats = self.calculate_statistics()
            charts_grid = QGridLayout()
            charts_grid.setSpacing(10)
            
            carrier_chart = self.create_carrier_chart()
            if carrier_chart:
                chart_widget = QWidget()
                chart_layout = QVBoxLayout(chart_widget)
                chart_layout.setContentsMargins(10, 10, 10, 10)
                
                frame = QFrame()
                frame.setObjectName("chartFrame")
                frame.setStyleSheet("""
                    QFrame#chartFrame {
                        background-color: white;
                        border-radius: 10px;
                        border: none;
                    }
                """)
                frame_layout = QVBoxLayout(frame)
                frame_layout.setContentsMargins(5, 5, 5, 5)
                frame_layout.addWidget(carrier_chart)
                
                chart_layout.addWidget(frame)
                charts_grid.addWidget(chart_widget, 0, 0, 1, 2)
            
            gauge_widget = QWidget()
            gauge_layout = QGridLayout(gauge_widget)
            gauge_layout.setContentsMargins(0, 0, 0, 0)
            gauge_layout.setSpacing(10)
            
            overall_gauge = self.create_gauge_chart(
                stats['issue_percentage'],
                "Overall Azimuth Issue Ratio"
            )
            if overall_gauge:
                gauge_layout.addWidget(overall_gauge, 0, 0)
            
            row = 0
            col = 1
            if stats['carrier_stats']:
                for carrier, carrier_stats in stats['carrier_stats'].items():
                    gauge = self.create_gauge_chart(
                        carrier_stats['percentage'],
                        f"{carrier} Azimuth Issue Ratio"
                    )
                    if gauge:
                        gauge_layout.addWidget(gauge, row, col)
                        col += 1
                        if col > 1:
                            col = 0
                            row += 1
            
            charts_grid.addWidget(gauge_widget, 1, 0, 1, 2)
            self.charts_layout.addLayout(charts_grid)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update charts: {str(e)}")

    def show_geo_window(self):
        try:
            if not hasattr(self.main_window, 'ep_data') or self.main_window.ep_data is None:
                QMessageBox.warning(self, "Warning", 
                    "No data available. Please upload and submit data first.")
                return

            # Prepare azimuth issue data (Azimuth Issue Cells FANS using EP coordinates and Actual Azimuth)
            if hasattr(self, 'analyzed_df') and self.analyzed_df is not None:
                current_threshold = self.azimuth_threshold.value()
                df = self.analyzed_df.copy()
                df['Azimuth Difference'] = pd.to_numeric(df['Azimuth Difference'], errors='coerce')
                df['Actual Azimuth'] = pd.to_numeric(df['Actual Azimuth'], errors='coerce')
                issue_cells = df[
                    (df['Azimuth Difference'] > current_threshold) &
                    (df['Actual Azimuth'].notnull())
                ][['eNodeb Name', 'Cell ID', 'Carrier', 'Actual Latitude', 'Actual Longitude', 'Actual Azimuth']].copy()
                # The plotting logic in GeoAnalysisWindow should draw FANS/arrows for these cells
                # starting at (Actual Longitude, Actual Latitude) and pointing in Actual Azimuth direction, in red color
                self.geo_window = GeoAnalysisWindow(self.main_window)
                self.geo_window.azimuth_issue_cells = issue_cells
                self.geo_window.setWindowFlag(Qt.WindowType.Window)
                self.geo_window.show()
            else:
                QMessageBox.warning(self, "Warning", 
                    "Please run azimuth analysis first before opening Geo Analysis.")
                return
                    
        except Exception as e:
            print(f"Error in show_geo_window: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to open Geo Analysis window: {str(e)}")

    def clear_layouts(self):
        try:
            while self.metrics_layout.count():
                item = self.metrics_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            while self.charts_layout.count():
                item = self.charts_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    self.clear_layout(item.layout())

        except Exception as e:
            print(f"Error clearing layouts: {str(e)}")

    def clear_layout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self.clear_layout(item.layout())

    def on_threshold_changed(self, value):
        try:
            self.threshold_value = value
            if self.analyzed_df is not None:
                self.update_metrics()
                self.update_charts()
                self.apply_result_filter(self.result_filter.currentIndex())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error updating threshold value: {str(e)}")

    def go_home(self):
        try:
            if self.main_window and hasattr(self.main_window, 'stack'):
                self.main_window.stack.setCurrentIndex(0)
                if hasattr(self.main_window, 'footer'):
                    self.main_window.footer.show()
        except Exception as e:
            print(f"Error navigating home: {str(e)}")

    def resizeEvent(self, event):
        try:
            super().resizeEvent(event)
            if hasattr(self, 'azimuth_table'):
                for col in range(self.azimuth_table.table.columnCount()):
                    self.azimuth_table.table.resizeColumnToContents(col)
        except Exception as e:
            print(f"Error in resize event: {str(e)}")

    def calculate_actual_azimuth_with_centroid(self):
        """
        Use the shared robust centroid-based actual azimuth calculation for each cell.
        """
        results = []
        max_distance = 2000  # meters
        min_points = 30
        for idx, ep_row in self.ep_data.iterrows():
            cell_id = ep_row[self.mappings['EP Cell ID']]
            carrier = ep_row[self.mappings['Carrier']]
            site_id = ep_row[self.mappings['EP Site ID']]
            ep_lat = float(ep_row[self.mappings['EP Latitude']])
            ep_lon = float(ep_row[self.mappings['EP Longitude']])
            planned_azimuth = float(ep_row[self.mappings['EP Azimuth']])
            print(f"\n[DEBUG] Processing Site: {site_id}, Cell: {cell_id}, Carrier: {carrier}")
            actual_azimuth = calculate_actual_azimuth_with_centroid(
                self.mr_data, self.ep_data, self.mappings, site_id, cell_id, carrier, min_points, max_distance
            )
            if actual_azimuth is None:
                print(f"[DEBUG] Not enough MR points or unable to calculate actual azimuth, skipping.")
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
            print(f"[DEBUG] Actual Azimuth: {actual_azimuth}, Azimuth Diff: {azimuth_diff}")
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
        self.analyzed_df = pd.DataFrame(results)

    def show_mr_plot(self, site_id, cell_id, carrier):
        # Find EP row for this cell
        ep_row = self.ep_data[
            (self.ep_data[self.mappings['EP Site ID']] == site_id) &
            (self.ep_data[self.mappings['EP Cell ID']] == cell_id) &
            (self.ep_data[self.mappings['Carrier']] == carrier)
        ]
        if ep_row.empty:
            QMessageBox.warning(self, "Warning", f"No EP data for cell {cell_id} ({carrier}) at site {site_id}")
            return
        ep_row = ep_row.iloc[0]
        site_lat = float(ep_row[self.mappings['EP Latitude']])
        site_lon = float(ep_row[self.mappings['EP Longitude']])
        planned_azimuth = float(ep_row[self.mappings['EP Azimuth']])
        # Filter MR points by Site ID, Cell ID, and Carrier
        mr_points = self.mr_data[
            (self.mr_data[self.mappings['MR Site ID']] == site_id) &
            (self.mr_data[self.mappings['MR Cell ID']] == cell_id) &
            (self.mr_data['Carrier_Lookup'] == carrier)
        ]
        if mr_points.empty:
            QMessageBox.warning(self, "Warning", f"No MR data for cell {cell_id} ({carrier}) at site {site_id}")
            return
        dlg = MRPlotDialog(site_id, site_lat, site_lon, planned_azimuth, cell_id, carrier, mr_points, parent=self)
        dlg.exec()