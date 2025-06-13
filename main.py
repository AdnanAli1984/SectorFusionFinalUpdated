import sys
import os
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QMessageBox,
                            QHBoxLayout, QGridLayout, QPushButton, QLabel, 
                            QStackedWidget, QFrame, QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize,QPoint
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap,QMouseEvent
from PyQt6.QtSvg import QSvgRenderer
from upload_window import UploadDataWindow
from sector_swap_window import SectorSwapWindow
from actual_azimuth_window import ActualAzimuthWindow
from actual_tilt_window import ActualTiltWindow
from actual_coordinates_window import ActualCoordinatesWindow
from PyQt6.QtWebEngineWidgets import QWebEngineView
from upload_window import CircularProgressDialog
from geo import GeoAnalysisWindow
from neighbor_audit_window import NeighborAuditWindow
from coverage_analysis_window import CoverageAnalysisWindow
from functions import read_encrypted_license, get_days_for_feature, get_license_info
from datetime import datetime
from validate import LicenseValidator
import os


LICENSE_FILE_PATH = "License/license.bin"

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

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
            return pixmap
        except Exception as e:
            print(f"Error loading icon {filename}: {str(e)}")
            return None

class ModernButton(QFrame):
    clicked = pyqtSignal()
    
    def __init__(self, icon_name, text, color, callback=None, parent=None, enabled=True):
        super().__init__(parent)
        self.callback = callback
        self.is_enabled = enabled
        self.original_color = color
        self.setup_ui(icon_name, text, color)
    
    def setup_ui(self, icon_name, text, color):
        self.setObjectName("modernButton")
        self.setFixedSize(250, 120)
        
        # Add shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Icon container
        icon_container = QWidget()
        icon_container.setFixedSize(40, 40)
        icon_layout = QVBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Icon
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_pixmap = IconLoader.load_svg_icon(icon_name)
        if icon_pixmap:
            self.icon_label.setPixmap(icon_pixmap)
        icon_layout.addWidget(self.icon_label)
        
        layout.addWidget(icon_container, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Text
        self.text_label = QLabel(text)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_label.setWordWrap(True)
        self.text_label.setStyleSheet("""
            color: white;
            font-size: 14px;
            font-weight: bold;
        """)
        layout.addWidget(self.text_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border-radius: 12px;
                border: none;
            }}
            QFrame:hover {{
                background-color: {self.adjust_color(color, 0.9)};
            }}
        """)
        self.set_enabled(self.is_enabled)
    
    def set_enabled(self, enabled):
        self.is_enabled = enabled
        if enabled:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {self.original_color};
                    border-radius: 12px;
                    border: none;
                }}
                QFrame:hover {{
                    background-color: {self.adjust_color(self.original_color, 0.9)};
                }}
            """)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #64748b;
                    border-radius: 12px;
                    border: none;
                }
            """)
            self.setCursor(Qt.CursorShape.ArrowCursor)
    
    def adjust_color(self, color, factor):
        color = QColor(color)
        h = color.hueF()
        s = color.saturationF()
        v = min(1.0, color.valueF() * factor)
        color.setHsvF(h, s, v)
        return color.name()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.callback:
            self.callback()

class ModernMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.dragPos = None
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("Sector Fusion")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(1200, 800)
        
        # Main widget
        main_widget = QWidget()
        main_widget.setObjectName("mainWidget")
        
        # Add shadow to main widget
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 0)
        main_widget.setGraphicsEffect(shadow)
        
        self.setCentralWidget(main_widget)
        
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # Header
        header = self.create_header()
        main_layout.addWidget(header)
        
        # Create main content
        self.main_content = QWidget()
        main_content_layout = QVBoxLayout(self.main_content)
        
        # Button grid
        button_grid = self.create_button_grid()
        main_content_layout.addWidget(button_grid)
        
        # Placeholder content
        placeholder = self.create_placeholder()
        main_content_layout.addWidget(placeholder)
        
        # Create stacked widget
        self.stack = QStackedWidget()
        self.stack.addWidget(self.main_content)
        
        main_layout.addWidget(self.stack)
        
        # Footer - Only show on main page
        self.footer = QLabel("© 2025 Agile Loop All rights reserved.")
        self.footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer.setStyleSheet("""
            QLabel {
                color: #666666;
                padding: 20px;
            }
        """)
        main_layout.addWidget(self.footer)
        
        self.stack.currentChanged.connect(self.on_stack_changed)
        
        self.apply_styles()

    def on_stack_changed(self, index):
        # Show footer only on main page (index 0)
        self.footer.setVisible(index == 0)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update()
    
    def create_header(self):
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 0, 10, 0)
        
        # Logo and title
        logo_layout = QHBoxLayout()
        
        # Update logo to use apollo-icon.svg
        logo = QLabel()
        logo.setFixedSize(40, 40)
        apollo_icon = IconLoader.load_svg_icon('AgileNew.svg', color="#0088FF", size=40)
        if apollo_icon:
            logo.setPixmap(apollo_icon)
        logo.setStyleSheet("background: transparent; border-radius: 12px;")
        logo_layout.addWidget(logo)
        
        title = QLabel("Sector Fusion")
        title.setStyleSheet("""
            color: #1a1a1a;
            font-size: 24px;
            font-weight: bold;
        """)
        logo_layout.addWidget(title)
        
        header_layout.addLayout(logo_layout)
        header_layout.addStretch()
        
        # Window controls remain the same
        for symbol, color, callback in [
            ("−", "#666", self.showMinimized),
            ("□", "#666", self.toggleMaximize),
            ("×", "#ff4444", self.close)
        ]:
            btn = QPushButton(symbol)
            btn.setFixedSize(30, 30)
            btn.clicked.connect(callback)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: #f0f0f0;
                    border-radius: 15px;
                    color: {color};
                    font-size: 16px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: {'#ffecec' if color == '#ff4444' else '#e0e0e0'};
                }}
            """)
            header_layout.addWidget(btn)
        return header
    
    def create_button_grid(self):
        licenses_data = []
        available_features = set()  
        
        if LICENSE_FILE_PATH:
            license_exists = os.path.exists(LICENSE_FILE_PATH)
        else:
            license_exists = False
        
        if license_exists:
            categories = []
            site_limit = 0
            licenses_list = read_encrypted_license(file_path=LICENSE_FILE_PATH)
            current_date = datetime.now()
            greatest_site_limit = 0
            for license in licenses_list:
                expiry_date = datetime.strptime(license["expiry_date"], "%Y-%m-%d")
                for item in license["categories"]:
                    if isinstance(item, int):
                        site_limit = item
                    else:
                        categories.append(item)
                if site_limit > greatest_site_limit:
                    greatest_site_limit = site_limit
                if current_date <= expiry_date:
                    licenses_data.append(license)
                    if "categories" in license:
                        available_features.update(categories)
        
        container = QWidget()
        grid_layout = QGridLayout(container)
        grid_layout.setSpacing(20)
        
        feature_mapping = {
            "Sector Swap": "Sector_Swap",
            "Actual Site Coordinates": "Actual_Coordinates",
            "Actual Antenna Azimuth": "Actual_Azimuth",
            "Actual Antenna Tilt": "Actual_Tilt",
            "Cell Neighbor Analysis": "Neighbor_Analysis",
            "MR Coverage Analysis": "Coverage_Analysis"
        }
        
        buttons = [
            ("upload.svg", "Upload Data", "#4287f5", lambda: self.showUploadWindow(site_limit=greatest_site_limit), False),
            ("settings.svg", "Sector Swap", "#22c55e", lambda: self.showSectorSwapWindow(data=licenses_data), False),
            ("map-pin.svg", "Actual Site Coordinates", "#a855f7", lambda: self.showActualCoordinatesWindow(data=licenses_data), False),
            ("compass.svg", "Actual Antenna Azimuth", "#f97316", lambda: self.showActualAzimuthWindow(data=licenses_data), False),
            # ("git-commit.svg", "Actual Antenna Tilt", "#ef4444", lambda: self.showActualTiltWindow(licenses_data), False),
            ("signal.svg", "MR Coverage Analysis", "#14b8a6", lambda: self.showCoverageWindow(data=licenses_data), False),
            ("share-2.svg", "Cell Neighbor Analysis", "#eab308", lambda: self.showNeighborWindow(data=licenses_data), False),
            ("map.svg", "Geo Analysis", "#6366f1", lambda: self.showGeoWindow(), True),
            ("license-manager.svg", "License Manager", "#3ba1f5", lambda: self.license_manager_window(), True)
        ]
        
        for i, (icon, text, color, callback, is_exempt) in enumerate(buttons):
            if is_exempt:
                button_enabled = True
            elif text == "Upload Data":
                button_enabled = bool(licenses_data)  
            else:
                feature_name = feature_mapping.get(text)
                if not licenses_data:
                    button_enabled = False
                else:
                    button_enabled = feature_name in available_features
            
            if button_enabled:
                button = ModernButton(icon, text, color, callback, enabled=button_enabled)
            else:
                button = ModernButton(icon, text, color, None, enabled=button_enabled)
            grid_layout.addWidget(button, i // 4, i % 4)
        
        grid_layout.setContentsMargins(0, 0, 0, 0)
        return container
    
    def open_geo_analysis(self): 
        self.geo_window = GeoAnalysisWindow(self)
        self.geo_window.show()

    def create_placeholder(self):
        placeholder = QWidget()
        layout = QVBoxLayout(placeholder)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_pixmap = IconLoader.load_svg_icon("map.svg", color="#666666", size=48)
        if icon_pixmap:
            icon_label.setPixmap(icon_pixmap)
        
        text = QLabel("Upload Cell Level MR Data in .csv fromat & Engineerig Parameter Network Data in Upload Module and Set Parameter settings to proceed for Analysis of each module")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text.setStyleSheet("""
            color: #666666;
            font-size: 16px;
            margin-top: 10px;
        """)
        
        layout.addWidget(icon_label)
        layout.addWidget(text)
        
        return placeholder
    
    def apply_styles(self):
        self.setStyleSheet("""
            #mainWidget {
                background: #f6f6f9;
                border-radius: 20px;
            }
        """)
    
    def toggleMaximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self.update()
    
    def mousePressEvent(self, event):
        # Disable dragging
        event.ignore()

    def mouseMoveEvent(self, event):
        # Disable dragging
        event.ignore()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragPos = None
    
    def showUploadWindow(self, site_limit:int):
        print("Upload function called")
        if not hasattr(self, 'upload_window'):
            self.upload_window = UploadDataWindow(self, site_limit=site_limit)
            self.stack.addWidget(self.upload_window)
        self.stack.setCurrentWidget(self.upload_window)
        if hasattr(self, 'footer'):
            self.footer.hide()
    
    def showSectorSwapWindow(self, data):
        validity = get_days_for_feature(data, "Sector_Swap")
        print(f"Sector Swap function called with validity:{validity}")
        
        if validity == 0:
            QMessageBox.critical(self, "Error", "Your license for Sector Swap has expired. Please contact our support team to obtain a new license key.")
            return
        else:
            # QMessageBox.information(self, "Information", f"This feature is valid for {validity} days.")
            if not hasattr(self, 'sector_swap_window'):
                self.sector_swap_window = SectorSwapWindow(self)
                self.stack.addWidget(self.sector_swap_window)
            self.stack.setCurrentWidget(self.sector_swap_window)
            if hasattr(self, 'footer'):
                self.footer.hide()
    
    def showActualCoordinatesWindow(self, data):
        validity = get_days_for_feature(data, "Actual_Coordinates")
        print(f"Actual Coordinates function called with validity:{validity}")
        
        if validity == 0:
            QMessageBox.critical(self, "Error", "Your license for Actual Site Coordinates has expired. Please contact our support team to obtain a new license key.")
            return
        else:
            # QMessageBox.information(self, "Information", f"This feature is valid for {validity} days.")
            if not hasattr(self, 'actual_coordinates_window'):
                self.actual_coordinates_window = ActualCoordinatesWindow(self)
                self.stack.addWidget(self.actual_coordinates_window)
            self.stack.setCurrentWidget(self.actual_coordinates_window)
            if hasattr(self, 'footer'):
                self.footer.hide()

    def showActualAzimuthWindow(self, data):
        validity = get_days_for_feature(data, "Actual_Azimuth")
        print(f"Actual Azimuth function called with validity:{validity}")
        
        if validity == 0:
            QMessageBox.critical(self, "Error", "Your license for Actual Antenna Azimuth has expired. Please contact our support team to obtain a new license key.")
            return
        else:
            # QMessageBox.information(self, "Information", f"This feature is valid for {validity} days.")
            if not hasattr(self, 'actual_azimuth_window'):
                self.actual_azimuth_window = ActualAzimuthWindow(self)
                self.stack.addWidget(self.actual_azimuth_window)
            self.stack.setCurrentWidget(self.actual_azimuth_window)
            if hasattr(self, 'footer'):
                self.footer.hide()

    # def showActualTiltWindow(self, data):
    #     validity = get_days_for_feature(data, "Actual_Tilt")
    #     print(f"Actual Tilt function called with validity:{validity}")
        
    #     if validity == 0:
    #         QMessageBox.critical(self, "Error", "Your license for Actual Antenna Tilt has expired. Please contact our support team to obtain a new license key.")
    #         return
    #     else:
    #         # QMessageBox.information(self, "Information", f"This feature is valid for {validity} days.")
    #         if not hasattr(self, 'actual_tilt_window'):
    #             self.actual_tilt_window = ActualTiltWindow(self)
    #             self.stack.addWidget(self.actual_tilt_window)
    #         self.stack.setCurrentWidget(self.actual_tilt_window)
    #         if hasattr(self, 'footer'):
    #             self.footer.hide()
    
    def showCoverageWindow(self, data):
        validity = get_days_for_feature(data, "Coverage_Analysis")
        print(f"Coverage Analysis function called with validity:{validity}")
    
        if validity == 0:
            QMessageBox.critical(self, "Error", "Your license for Coverage Analysis has expired. Please contact our support team to obtain a new license key.")
            return
        else:
            try:
                # Initialize coverage analysis state if it doesn't exist
                if not hasattr(self, '_coverage_analysis_state'):
                    self._coverage_analysis_state = {
                        'result_df': None,
                        'metrics': None,
                        'current_filter': 0
                    }
                
                if not hasattr(self, 'coverage_analysis_window'):
                    self.coverage_analysis_window = CoverageAnalysisWindow(self)
                    self.stack.addWidget(self.coverage_analysis_window)
                    
                self.stack.setCurrentWidget(self.coverage_analysis_window)
                if hasattr(self, 'footer'):
                    self.footer.hide()
                    
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open Coverage Analysis window: {str(e)}")
                print(f"Error in showCoverageWindow: {str(e)}")
        # try:
        #     print("MR Coverage function called")
        #     if not hasattr(self, 'coverage_window'):
        #         self.coverage_window = CoverageAnalysisWindow(self)
        #         self.stack.addWidget(self.coverage_window)
        #     self.stack.setCurrentWidget(self.coverage_window)
        #     if hasattr(self, 'footer'):
        #         self.footer.hide()
        # except Exception as e:
        #     QMessageBox.critical(self, "Error", f"Failed to open MR Coverage Analysis window: {str(e)}")

    def showNeighborWindow(self, data):
        try:
            validity = get_days_for_feature(data, "Neighbor_Analysis")
            print(f"Neighbor function called with validity:{validity}")
            if validity == 0:
                QMessageBox.critical(self, "Error", "Your license for Cell Neighbor Analysis has expired. Please contact our support team to obtain a new license key.")
                return
            else:
                # QMessageBox.information(self, "Information", f"This feature is valid for {validity} days.")
                if not hasattr(self, 'neighbor_window'):
                    self.neighbor_window = NeighborAuditWindow(self)
                    if hasattr(self.neighbor_window, 'calculator'): 
                        self.stack.addWidget(self.neighbor_window)
                        self.stack.setCurrentWidget(self.neighbor_window)
                        if hasattr(self, 'footer'):
                            self.footer.hide()
                else:
                    self.stack.setCurrentWidget(self.neighbor_window)
                    if hasattr(self, 'footer'):
                        self.footer.hide()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open Neighbor Analysis window: {str(e)}")
    
    def showGeoWindow(self):
        try:
            print("Geo function called")
            if not hasattr(self, 'ep_data') or self.ep_data is None:
                QMessageBox.warning(self, "Warning", 
                    "No data available. Please upload and submit data first.")
                return

            # Add debug prints for analysis data
            if hasattr(self, 'actual_coordinates_window'):
                if hasattr(self.actual_coordinates_window, 'analyzed_df'):
                    print("\nCoordinates analysis DataFrame columns:", 
                        self.actual_coordinates_window.analyzed_df.columns.tolist())
                else:
                    print("\nNo coordinates analysis data available")
                    
            if hasattr(self, 'actual_azimuth_window'):
                if hasattr(self.actual_azimuth_window, 'analyzed_df'):
                    print("\nAzimuth analysis DataFrame columns:", 
                        self.actual_azimuth_window.analyzed_df.columns.tolist())
                else:
                    print("\nNo azimuth analysis data available")

            if hasattr(self, 'sector_swap_window'):
                if hasattr(self.sector_swap_window, 'analyzed_df'):
                    print("\nSector Swap analysis DataFrame columns:", 
                        self.sector_swap_window.analyzed_df.columns.tolist())
                else:
                    print("\nNo sector swap analysis data available")

            # Create and show the geo window as a top-level window
            self.geo_window = GeoAnalysisWindow(self)  # Keep a reference
            self.geo_window.setWindowFlag(Qt.WindowType.Window)  # Make it a separate window
            self.geo_window.show()  # Explicitly show the window
                
        except Exception as e:
            print(f"Error in showGeoWindow: {str(e)}")  # For debugging
            QMessageBox.critical(self, "Error", f"Failed to open Geo Analysis window: {str(e)}")

    def license_manager_window(self):
        self.license_manager = LicenseValidator()
        self.license_manager.show()
        if not os.path.exists(LICENSE_FILE_PATH):
            self.close()
        

def main_func():
    app = QApplication(sys.argv)
    
    app.setStyle("Fusion")
    
    font = app.font()
    font.setFamily("Segoe UI")
    app.setFont(font)
    
    window = ModernMainWindow()
    
    if LICENSE_FILE_PATH:
        license_exists = os.path.exists(LICENSE_FILE_PATH)
    else:
        license_exists = None
    
    if license_exists is None:
        QMessageBox.warning(window, "Missing License Information", "License information for this device is missing. To use features of this application, please obtain a valid license key from our support team.")
        window.showMaximized()
    elif license_exists is False:
        QMessageBox.warning(window, "Missing License Information", "License for this device is missing. To use features of this application, please obtain a valid license key from our support team.")
        window.showMaximized()
    else:
        license_info = get_license_info()
        QMessageBox.information(window, "License Information", f"{license_info}", QMessageBox.StandardButton.Ok)
        window.showMaximized()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    multiprocessing.freeze_support()
    main_func()