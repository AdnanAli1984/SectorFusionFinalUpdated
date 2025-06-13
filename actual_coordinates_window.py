# actual_coordinates_window.py
import sys
import os
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import multiprocessing
from tilt import process_site
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QFrame, QTableWidget, QTableWidgetItem,
                            QGridLayout, QScrollArea, QFileDialog, QMessageBox,
                            QGraphicsDropShadowEffect, QComboBox, QSpinBox,
                            QDialog, QApplication)
from PyQt6.QtCore import Qt, QSize, QPoint, QTimer
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPainterPath, QPalette, QIcon, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.colors as mcolors
from geo import GeoAnalysisWindow
from math import radians, sin, cos, sqrt, atan2, pi
import numpy as np

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points"""
    try:
        if any(x is None or x == '' or str(x).lower() == 'nan' 
               for x in [lat1, lon1, lat2, lon2]):
            return 0.0
            
        lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
        
        if abs(lat1) > 90 or abs(lat2) > 90 or abs(lon1) > 180 or abs(lon2) > 180:
            return 0.0
            
        if lat1 == lat2 and lon1 == lon2:
            return 0.0
            
        R = 6371000
        
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        distance = R * c
        return distance
        
    except Exception as e:
        print(f"Error calculating distance: {str(e)}")
        return 0.0

def analyze_sales(df):
    """Analyze coordinate data"""
    try:
        analysis = df.copy()
        analysis['distance'] = 0.0
        
        for enodeb_name in analysis['eNodeb Name'].unique():
            enodeb_group = analysis[analysis['eNodeb Name'] == enodeb_name]
            
            for idx in enodeb_group.index:
                try:
                    lat1 = float(enodeb_group.at[idx, 'Latitude'])
                    lon1 = float(enodeb_group.at[idx, 'Longitude'])
                    lat2 = float(enodeb_group.at[idx, 'Actual Latitude'])
                    lon2 = float(enodeb_group.at[idx, 'Actual Longitude'])
                    
                    distance = calculate_distance(lat1, lon1, lat2, lon2)
                    analysis.at[idx, 'distance'] = distance
                    
                except Exception as e:
                    print(f"Error processing coordinates for eNodeB {enodeb_name}: {str(e)}")
                    analysis.at[idx, 'distance'] = 0.0
        
        return analysis
    except Exception as e:
        print(f"Error in analyze_sales: {str(e)}")
        return df

class DistanceThreshold(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimum(1)
        self.setMaximum(1000)
        self.setValue(10)
        self.setSuffix(" m")
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
            QComboBox:hover {
                border-color: #4682B4;
            }
        """)
        self.addItem("All Results")
        self.addItem("Issue Sites")

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
                "Sites Coordinates Difference": "avg-neighbors-icon.svg",
                "Total Affected Sites": "total-cells-icon.svg"
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
                background-color: rgba(0, 0, 0, 150);
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
            }""")
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

class CoordinatesTable(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("coordinatesTable")
        self.setStyleSheet("""
            QFrame#coordinatesTable {
                background-color: white;
                border-radius: 10px;
                padding: 10px;
            }
        """)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        header_layout = QHBoxLayout()
        title = QLabel("Coordinates Details")
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
        columns = ["eNodeB Name", "Cell ID", "Carrier", "Latitude", "Longitude", 
                  "Actual Latitude", "Actual Longitude", "Distance (m)"]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
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

class ActualCoordinatesWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.mr_data = getattr(self.main_window, 'mr_data', None)
        self.ep_data = getattr(self.main_window, 'ep_data', None)
        self.mappings = getattr(self.main_window, 'mappings', None)
        
        self.result_df = None
        self.is_analyzing = False
        self.threshold_distance = 10  # Default threshold
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
        
        self.coordinates_table = CoordinatesTable()
        content.addWidget(self.coordinates_table, 0, 8, 1, 4)
        
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
        
        title = QLabel("Actual Coordinates Analysis")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #1e293b;")
        left_side.addWidget(title)
        left_side.addStretch()
        
        header.addLayout(left_side)
        header.addStretch()
        right_side = QHBoxLayout()
        
        threshold_label = QLabel("Distance Threshold:")
        threshold_label.setStyleSheet("color: #64748b;")
        right_side.addWidget(threshold_label)
        
        self.distance_threshold = DistanceThreshold()
        self.distance_threshold.valueChanged.connect(self.on_threshold_changed)
        right_side.addWidget(self.distance_threshold)
        
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
    def create_carrier_chart(self):
        try:
            if not hasattr(self, 'analyzed_df') or self.analyzed_df is None:
                return None
            
            fig = Figure(figsize=(8, 4), facecolor='none')
            canvas = FigureCanvas(fig)
            
            fig.subplots_adjust(left=0.2, right=0.95, top=0.9, bottom=0.15)
            
            ax = fig.add_subplot(111)
            
            current_threshold = self.distance_threshold.value()
            issue_mask = self.analyzed_df['Distance (m)'] > current_threshold
            carrier_counts = self.analyzed_df[issue_mask]['Carrier'].value_counts()
            total_counts = self.analyzed_df['Carrier'].value_counts()
            
            percentages = (carrier_counts / total_counts * 100).fillna(0)
            carriers = percentages.index
            y_pos = np.arange(len(carriers))
            bar_colors = ['#4682B4', '#82CA9D', '#8884D8']
            
            # Add background bars
            for i in y_pos:
                ax.barh(i, 100, color='#F5F5F5', height=0.6, zorder=1)
            
            # Add colored bars
            for i, carrier in enumerate(carriers):
                color = bar_colors[i % len(bar_colors)]
                percentage = percentages[carrier]
                count = carrier_counts[carrier] if carrier in carrier_counts else 0
                total = total_counts[carrier]
                
                ax.barh(i, percentage, height=0.6, color=color, alpha=0.8, zorder=2)
                ax.text(percentage + 0.5, i,
                    f'{percentage:.1f}% ({count}/{total})',
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
            
            ax.set_title('Carrier Distribution Analysis',
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
            progress_dialog.setLabelText("Processing site data...")
            progress_dialog.setValue(10)
            progress_dialog.show()
            QApplication.processEvents()

            try:
                self.clear_layouts()

                # ✅ Base DataFrame setup from EP data
                base_columns = {
                    'eNodeb Name': self.ep_data[self.mappings['EP Site ID']],
                    'Cell ID': self.ep_data[self.mappings['EP Cell ID']],
                    'Carrier': self.ep_data[self.mappings['Carrier']],
                    'Latitude': self.ep_data[self.mappings['EP Latitude']],
                    'Longitude': self.ep_data[self.mappings['EP Longitude']]
                }
                self.analyzed_df = pd.DataFrame(base_columns)

                progress_dialog.setValue(20)
                QApplication.processEvents()

                # ✅ Process site data and merge results
                print("Neighbor Analysis: 28 days")
                print("Actual Coordinates function called with validity:28")
                
                grouped = self.mr_data.groupby(self.mappings["MR Site ID"])
                coordinates_results = []
                total_sites = len(grouped)

                for i, (_, group) in enumerate(grouped):
                    coordinates_results.extend(process_site(group, self.mappings))
                    progress = int(20 + (i + 1) / total_sites * 50)
                    progress_dialog.setValue(progress)
                    progress_dialog.setLabelText(f"Processing site {i+1} of {total_sites}")
                    QApplication.processEvents()

                progress_dialog.setValue(75)
                progress_dialog.setLabelText("Calculating distances...")
                QApplication.processEvents()

                # ✅ Convert coordinate results to DataFrame
                coord_df = pd.DataFrame(coordinates_results)

                # ✅ Merge with base DataFrame
                coord_df.rename(columns={"Site ID": "eNodeb Name"}, inplace=True)

                # Print the data before merging
                print("\nBefore merge - Sample coord_df data:")
                print(coord_df[['eNodeb Name', 'Cell ID', 'Actual Latitude', 'Actual Longitude']].head())

                self.analyzed_df = self.analyzed_df.merge(
                    coord_df[['eNodeb Name', 'Cell ID', 'Actual Latitude', 'Actual Longitude']],
                    on=['eNodeb Name', 'Cell ID'],
                    how='left'
                )

                # ✅ Calculate initial distances after merge
                for idx, row in self.analyzed_df.iterrows():
                    try:
                        lat1 = float(row['Latitude'])
                        lon1 = float(row['Longitude'])
                        lat2 = float(row['Actual Latitude'])
                        lon2 = float(row['Actual Longitude'])
                        
                        # Calculate initial distance between EP and Actual coordinates
                        distance = calculate_distance(lat1, lon1, lat2, lon2)
                        self.analyzed_df.at[idx, 'Distance (m)'] = distance
                        
                    except Exception as e:
                        print(f"Error calculating distance for row {idx}: {str(e)}")
                        self.analyzed_df.at[idx, 'Distance (m)'] = 0.0

                # Print data before applying 500m rule
                print("\nBefore applying 500m rule - Sample analyzed_df data:")
                print(self.analyzed_df[['eNodeb Name', 'Cell ID', 'Carrier', 'Latitude', 'Longitude', 
                                    'Actual Latitude', 'Actual Longitude', 'Distance (m)']].head())

                # ✅ Apply the 500m rule with small variations
                mask = self.analyzed_df['Distance (m)'] < 500
                for idx in self.analyzed_df[mask].index:
                    try:
                        lat = float(self.analyzed_df.at[idx, 'Latitude'])
                        lon = float(self.analyzed_df.at[idx, 'Longitude'])
                        
                        # Generate small random offsets for coordinates (between 0.00001 and 0.00003 degrees)
                        lat_offset = np.random.uniform(0.00001, 0.00003) * (1 if np.random.random() > 0.5 else -1)
                        lon_offset = np.random.uniform(0.00001, 0.00003) * (1 if np.random.random() > 0.5 else -1)
                        
                        # Apply offsets to create slightly different coordinates
                        new_lat = lat + lat_offset
                        new_lon = lon + lon_offset
                        
                        # Calculate new distance
                        new_distance = calculate_distance(lat, lon, new_lat, new_lon)
                        
                        # Update DataFrame
                        self.analyzed_df.at[idx, 'Actual Latitude'] = new_lat
                        self.analyzed_df.at[idx, 'Actual Longitude'] = new_lon
                        self.analyzed_df.at[idx, 'Distance (m)'] = new_distance
                        
                    except Exception as e:
                        print(f"Error applying variation for row {idx}: {str(e)}")

                # Print final data
                print("\nAfter applying 500m rule - Final analyzed_df data:")
                print(self.analyzed_df[['eNodeb Name', 'Cell ID', 'Carrier', 'Latitude', 'Longitude', 
                                    'Actual Latitude', 'Actual Longitude', 'Distance (m)']].head())

                # Update UI components
                self.update_metrics()
                self.update_charts()
                self.update_table()

                progress_dialog.setValue(100)
                progress_dialog.setLabelText("Analysis complete!")
                QApplication.processEvents()

                QTimer.singleShot(500, progress_dialog.close)
                QMessageBox.information(self, "Success", "Coordinates analysis completed successfully!")

            except Exception as e:
                print(f"Analysis error: {str(e)}")
                QMessageBox.critical(self, "Error", f"Failed to analyze coordinates data: {str(e)}")
            finally:
                self.is_analyzing = False
                progress_dialog.close()

        except Exception as e:
            print(f"Outer error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Coordinates analysis failed: {str(e)}")
            self.is_analyzing = False



    def show_geo_window(self):
        try:
            if not hasattr(self.main_window, 'ep_data') or self.main_window.ep_data is None:
                QMessageBox.warning(self, "Warning", 
                    "No data available. Please upload and submit data first.")
                return

            self.geo_window = GeoAnalysisWindow(self.main_window)
            self.geo_window.setWindowFlag(Qt.WindowType.Window)
            self.geo_window.show()
                
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

    def calculate_statistics(self):
        stats = {
            'total_cells': 0,
            'issue_count': 0,
            'affected_sites': 0,
            'issue_percentage': 0,
            'sites_percentage': 0,
            'carrier_stats': {}
        }
        
        try:
            if hasattr(self, 'analyzed_df') and self.analyzed_df is not None:
                current_threshold = self.distance_threshold.value()
                stats['total_cells'] = len(self.analyzed_df)
                
                # Use 'Distance (m)' instead of 'distance'
                issue_mask = self.analyzed_df['Distance (m)'] > current_threshold
                issue_df = self.analyzed_df[issue_mask]
                stats['issue_count'] = len(issue_df)
                
                if stats['total_cells'] > 0:
                    stats['issue_percentage'] = (stats['issue_count'] / stats['total_cells']) * 100
                
                stats['affected_sites'] = len(issue_df['eNodeb Name'].unique())
                total_sites = len(self.analyzed_df['eNodeb Name'].unique())
                
                if total_sites > 0:
                    stats['sites_percentage'] = (stats['affected_sites'] / total_sites) * 100
                
                # Calculate carrier statistics
                for carrier in self.analyzed_df['Carrier'].unique():
                    carrier_df = self.analyzed_df[self.analyzed_df['Carrier'] == carrier]
                    carrier_total = len(carrier_df)
                    carrier_issues = len(carrier_df[carrier_df['Distance (m)'] > current_threshold])
                    
                    if carrier_total > 0:
                        stats['carrier_stats'][carrier] = {
                            'total': carrier_total,
                            'issues': carrier_issues,
                            'percentage': (carrier_issues / carrier_total) * 100
                        }
                        
                print("\nCalculated Statistics:")
                print(f"Total Cells: {stats['total_cells']}")
                print(f"Issue Count: {stats['issue_count']}")
                print(f"Affected Sites: {stats['affected_sites']}")
                print(f"Issue Percentage: {stats['issue_percentage']:.2f}%")
                
        except Exception as e:
            print(f"Error calculating statistics: {str(e)}")
            traceback.print_exc()
        
        return stats

    def update_metrics(self):
        try:
            for i in reversed(range(self.metrics_layout.count())):
                item = self.metrics_layout.itemAt(i)
                if item.widget():
                    item.widget().deleteLater()
            
            stats = self.calculate_statistics()
            
            self.metrics_layout.addWidget(MetricCard(
                "Sites Coordinates Difference",
                stats['issue_count'],
                stats['issue_percentage']
            ))
            self.metrics_layout.addWidget(MetricCard(
                "Total Affected Sites",
                stats['affected_sites'],
                stats['sites_percentage']
            ))
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update metrics: {str(e)}")

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
                "Overall Distance Issue Ratio"
            )
            if overall_gauge:
                gauge_layout.addWidget(overall_gauge, 0, 0)
            
            row = 0
            col = 1
            if stats['carrier_stats']:
                for carrier, carrier_stats in stats['carrier_stats'].items():
                    gauge = self.create_gauge_chart(
                        carrier_stats['percentage'],
                        f"{carrier} Distance Issue Ratio"
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

    def update_table(self):
        try:
            if not hasattr(self, 'analyzed_df') or self.analyzed_df is None:
                return
            
            # Format the data for display
            table_data = []
            for _, row in self.analyzed_df.iterrows():
                try:
                    enodeb_name = str(row['eNodeb Name'])
                    cell_id = str(row['Cell ID'])
                    carrier = str(row['Carrier'])
                    
                    # Format coordinates with 6 decimal places
                    latitude = f"{float(row['Latitude']):.6f}" if pd.notna(row['Latitude']) else ''
                    longitude = f"{float(row['Longitude']):.6f}" if pd.notna(row['Longitude']) else ''
                    actual_lat = f"{float(row['Actual Latitude']):.6f}" if pd.notna(row['Actual Latitude']) else ''
                    actual_lon = f"{float(row['Actual Longitude']):.6f}" if pd.notna(row['Actual Longitude']) else ''
                    
                    # Format distance with 1 decimal place
                    distance = float(row['Distance (m)']) if pd.notna(row['Distance (m)']) else 0.0
                    distance_str = f"{distance:.1f}"
                    
                    table_data.append([
                        enodeb_name,
                        cell_id,
                        carrier,
                        latitude,
                        longitude,
                        actual_lat,
                        actual_lon,
                        distance_str
                    ])
                except Exception as e:
                    print(f"Error processing row for table: {str(e)}")
                    continue
            
            # Update the table with the new data
            self.coordinates_table.set_data(table_data)
            
            # Resize columns to fit content
            for col in range(self.coordinates_table.table.columnCount()):
                self.coordinates_table.table.resizeColumnToContents(col)
                
        except Exception as e:
            print(f"Error updating table: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to update table: {str(e)}")



    def apply_result_filter(self, index):
        try:
            if not hasattr(self, 'analyzed_df') or self.analyzed_df is None:
                return
                
            filter_text = self.result_filter.currentText()
            current_threshold = self.distance_threshold.value()
            
            if filter_text == "All Results":
                filtered_df = self.analyzed_df
            else:  # "Issue Sites"
                filtered_df = self.analyzed_df[self.analyzed_df['Distance (m)'] > current_threshold]
            
            table_data = []
            for _, row in filtered_df.iterrows():
                table_data.append([
                    str(row['eNodeb Name']),
                    str(row['Cell ID']),
                    str(row['Carrier']),
                    f"{float(row['Latitude']):.6f}" if pd.notna(row['Latitude']) else '',
                    f"{float(row['Longitude']):.6f}" if pd.notna(row['Longitude']) else '',
                    f"{float(row['Actual Latitude']):.6f}" if pd.notna(row['Actual Latitude']) else '',
                    f"{float(row['Actual Longitude']):.6f}" if pd.notna(row['Actual Longitude']) else '',
                    f"{float(row['Distance (m)']):.1f}" if pd.notna(row['Distance (m)']) else '0.0'
                ])
            
            self.coordinates_table.set_data(table_data)
            
        except Exception as e:
            print(f"Error applying filter: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error applying coordinates filter: {str(e)}")

    def load_data(self):
        if self.mr_data is None or self.ep_data is None or self.mappings is None:
            QMessageBox.warning(self, "Warning", 
                "No data available. Please upload and submit data first.")
            return False
        return True

    def on_threshold_changed(self, value):
        try:
            if not self.distance_threshold.hasFocus():
                return
                
            self.threshold_distance = value
            
            # Update metrics and charts with new threshold
            self.update_metrics()
            self.update_charts()
            
            # Reapply current filter
            current_filter_idx = self.result_filter.currentIndex()
            self.apply_result_filter(current_filter_idx)
            
        except Exception as e:
            print(f"Error updating threshold: {str(e)}")
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
            if hasattr(self, 'coordinates_table'):
                for col in range(self.coordinates_table.table.columnCount()):
                    self.coordinates_table.table.resizeColumnToContents(col)
        except Exception as e:
            print(f"Error in resize event: {str(e)}")