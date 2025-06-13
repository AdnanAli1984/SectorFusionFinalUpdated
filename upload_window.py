# upload_window.py

import sys
import os
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import numpy as np
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QApplication,
                            QPushButton, QFrame, QFileDialog,
                            QTableWidget, QTableWidgetItem, QScrollArea,
                            QSplitter, QDialog, QComboBox, QMessageBox,
                            QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QSize, QTimer, QPoint
from PyQt6.QtGui import (QColor, QIcon, QPainter, QPixmap, QPen, QFont, QMouseEvent)
from PyQt6.QtSvg import QSvgRenderer
from sectorswap import SectorSwapCalculator
from tilt import process_site
from functions import save_sites, get_sites
import json
from trial_manager import TrialManager
from parameter import ParameterSettingsWindow

LICENSE_FILE_PATH = "License/license.bin"

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

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
                font-size: 14px;
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

class DataLoader(QThread):
    finished = pyqtSignal(pd.DataFrame)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)
    
    def __init__(self, file_paths, file_type):
        super().__init__()
        self.file_paths = file_paths if isinstance(file_paths, list) else [file_paths]
        self.file_type = file_type
    
    def run(self):
        try:
            merged_data = []
            total_files = len(self.file_paths)
            total_rows = 0
            processed_rows = 0
            
            # First pass to get total rows
            for file_path in self.file_paths:
                try:
                    if self.file_type == 'csv':
                        total_rows += sum(1 for _ in open(file_path))
                    else:
                        df = pd.read_excel(file_path)
                        total_rows += len(df)
                except Exception as e:
                    self.error.emit(f"Error counting rows in {file_path}: {str(e)}")
                    return

            self.progress.emit(0)
            
            for file_path in self.file_paths:
                try:
                    if self.file_type == 'csv':
                        chunk_size = 1000
                        chunks = pd.read_csv(file_path, chunksize=chunk_size)
                        file_data = []
                        for chunk in chunks:
                            file_data.append(chunk)
                            processed_rows += len(chunk)
                            progress = int((processed_rows / total_rows) * 100)
                            self.progress.emit(progress)
                        if file_data:
                            df = pd.concat(file_data, ignore_index=True)
                            merged_data.append(df)
                    else:
                        df = pd.read_excel(file_path)
                        processed_rows += len(df)
                        progress = int((processed_rows / total_rows) * 100)
                        self.progress.emit(progress)
                        merged_data.append(df)
                except Exception as e:
                    self.error.emit(f"Error loading file {file_path}: {str(e)}")
                    return

            if merged_data:
                final_df = pd.concat(merged_data, ignore_index=True)
                self.progress.emit(100)
                QThread.msleep(500)
                self.finished.emit(final_df)
            else:
                self.error.emit("No data was loaded")
                
        except Exception as e:
            self.error.emit(str(e))
class ProjectLoader(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
    
    def run(self):
        try:
            # Start loading - 10%
            self.progress.emit(10, "Starting project load...")
            
            with open(self.file_path, 'r') as f:
                project_data = json.load(f)
            
            # Loading MR data - 25%
            self.progress.emit(25, "Loading MR data...")
            mr_data = pd.DataFrame.from_dict(project_data["mr_data"])
            
            # Loading EP data - 50%
            self.progress.emit(50, "Loading EP data...")
            ep_data = pd.DataFrame.from_dict(project_data["ep_data"])
            
            # Loading mappings and settings - 75%
            self.progress.emit(75, "Loading settings...")
            
            # Prepare the result dictionary
            result = {
                "mr_data": mr_data,
                "ep_data": ep_data,
                "mappings": project_data["mappings"],
                "result_df": pd.DataFrame.from_dict(project_data["result_df"]) if project_data.get("result_df") else None,
                "parameter_settings": project_data.get("parameter_settings")
            }
            
            # Complete - 100%
            self.progress.emit(100, "Loading complete!")
            self.finished.emit(result)
            
        except Exception as e:
            self.error.emit(str(e))

class UploadFrame(QFrame):
    clicked = pyqtSignal()
    
    def __init__(self, icon_name, title, subtitle, parent=None):
        super().__init__(parent)
        self.setup_ui(icon_name, title, subtitle)
        self.dragPos = None

    def setup_ui(self, icon_name, title, subtitle):
        self.setObjectName("uploadFrame")
        self.setFixedHeight(120)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon_label = QLabel()
        icon = IconLoader.load_svg_icon(icon_name, color="#3b82f6")
        if icon:
            icon_label.setPixmap(icon.pixmap(32, 32))
        layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #1e293b; font-size: 14px; font-weight: bold;")
        layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(subtitle_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.setStyleSheet("""
            QFrame#uploadFrame {
                border: 2px dashed #e2e8f0;
                border-radius: 8px;
                background: white;
            }
            QFrame#uploadFrame:hover {
                border-color: #3b82f6;
                background: #f0f9ff;
            }
        """)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

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

class ColumnMatchDialog(QDialog):
    def __init__(self, mr_columns, ep_columns, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setStyleSheet("""
            QDialog {
                background-color: #f0f0f0;
                border: 1px solid #cccccc;
            }
            QLabel {
                font-size: 14px;
            }
            QComboBox {
                padding: 5px;
                border: 1px solid #cccccc;
                border-radius: 3px;
                min-width: 200px;
            }
            QPushButton {
                background-color: #4682B4;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #3A6E9E;
            }
        """)

        layout = QVBoxLayout(self)
        
        title_layout = QHBoxLayout()
        title_label = QLabel("Match Columns")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        close_button = QPushButton("×")
        close_button.setFixedSize(30, 30)
        close_button.clicked.connect(self.reject)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addWidget(close_button)
        layout.addLayout(title_layout)

        self.mappings = {}
        required_mappings = {
            "MR Site ID": mr_columns,
            "MR Cell ID": mr_columns,
            "MR Latitude": mr_columns,
            "MR Longitude": mr_columns,
            "MR RSRP": mr_columns,
            "EP Site ID": ep_columns,
            "EP Cell ID": ep_columns,
            "EP Azimuth": ep_columns,
            "EP Latitude": ep_columns,
            "EP Longitude": ep_columns,
            "Carrier": ep_columns
            }

        for param, columns in required_mappings.items():
            row_layout = QHBoxLayout()
            label = QLabel(param)
            combo = QComboBox()
            combo.addItems(columns)
            row_layout.addWidget(label)
            row_layout.addWidget(combo)
            layout.addLayout(row_layout)
            self.mappings[param] = combo

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        layout.addWidget(ok_button)

    def get_mappings(self):
        return {param: combo.currentText() for param, combo in self.mappings.items()}

class UploadDataWindow(QWidget):
    def __init__(self, parent=None, site_limit:int = 0):
        super().__init__(parent)
        self.main_window = parent
        self.thread_pool = ThreadPoolExecutor(max_workers=multiprocessing.cpu_count())
        self.mr_data = None
        self.ep_data = None
        self.result_df = None
        self.mappings = {}
        self.site_limit = site_limit
        self.trial_manager = TrialManager()
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        header = self.create_header()
        layout.addLayout(header)
        
        content = QSplitter()
        
        left_panel = self.create_left_panel()
        content.addWidget(left_panel)
        
        right_panel = self.create_right_panel()
        content.addWidget(right_panel)
        
        content.setStretchFactor(0, 1)
        content.setStretchFactor(1, 2)
        
        layout.addWidget(content)
        
        self.apply_styles()
    
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
        
        title = QLabel("Upload Data")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #1e293b;")
        left_side.addWidget(title)
        left_side.addStretch()
        
        header.addLayout(left_side)
        header.addStretch()
        
        reset_btn = QPushButton("Reset")
        reset_btn.setIcon(IconLoader.load_svg_icon("reset.svg", color="#64748b"))
        reset_btn.clicked.connect(self.reset_all)
        reset_btn.setStyleSheet("""
            QPushButton {
                color: #64748b;
                background: #f1f5f9;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #e2e8f0;
            }
        """)

        save_project_btn = QPushButton("Save Project")
        save_project_btn.setIcon(IconLoader.load_svg_icon("save.svg", color="#3b82f6"))
        save_project_btn.clicked.connect(self.save_project)
        save_project_btn.setStyleSheet("""
            QPushButton {
                color: #3b82f6;
                background: #eff6ff;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #dbeafe;
            }
        """)

        load_project_btn = QPushButton("Load Project")
        load_project_btn.setIcon(IconLoader.load_svg_icon("load.svg", color="#8b5cf6"))
        load_project_btn.clicked.connect(self.load_project)
        load_project_btn.setStyleSheet("""
            QPushButton {
                color: #8b5cf6;
                background: #f5f3ff;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #ede9fe;
            }
        """)

        header.addWidget(reset_btn)
        header.addWidget(save_project_btn)
        header.addWidget(load_project_btn)
        
        return header
    
    def create_left_panel(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)
        
        layout.addWidget(QLabel("Data Upload"))
        
        mr_upload = UploadFrame("upload.svg", "Upload MR Data", ".csv files only")
        mr_upload.clicked.connect(self.upload_mr_data)
        layout.addWidget(mr_upload)
        
        ep_upload = UploadFrame("upload.svg", "Upload EP Data", ".csv, .xlsx, .xls files")
        ep_upload.clicked.connect(self.upload_ep_data)
        layout.addWidget(ep_upload)
        
        param_settings = UploadFrame("settings.svg", "Parameter Settings", "Configure sector split & massive MIMO")
        param_settings.clicked.connect(self.showParameterSettings)
        layout.addWidget(param_settings)
        
        match_btn = QPushButton("Match Columns")
        match_btn.clicked.connect(self.match_columns)
        match_btn.setStyleSheet("""
            QPushButton {
                background: #8b5cf6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #7c3aed;
            }
        """)
        layout.addWidget(match_btn)
        
        submit_btn = QPushButton("Submit")
        submit_btn.clicked.connect(self.submit_data)
        submit_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #2563eb;
            }
        """)
        layout.addWidget(submit_btn)
        
        layout.addStretch()
        
        return widget

    def showParameterSettings(self):
        try:
            param_window = ParameterSettingsWindow()
            param_window.show()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open Parameter Settings: {str(e)}")
    
    def create_right_panel(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        layout.addWidget(QLabel("MR Data"))
        self.mr_table = QTableWidget()
        self.mr_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                background: white;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QHeaderView::section {
                background: #f8fafc;
                padding: 8px;
                border: none;
                border-bottom: 1px solid #e2e8f0;
            }
        """)
        layout.addWidget(self.mr_table)
        
        layout.addWidget(QLabel("EP Data"))
        self.ep_table = QTableWidget()
        self.ep_table.setStyleSheet(self.mr_table.styleSheet())
        layout.addWidget(self.ep_table)
        
        return widget
    
    def apply_styles(self):
        self.setStyleSheet("""
            QWidget {
                font-family: 'Segoe UI', sans-serif;
            }
            QLabel {
                color: #1e293b;
            }
            #settingsFrame {
                background: white;
                border-radius: 8px;
                padding: 16px;
            }
        """)

    def show_error(self, message, progress_dialog=None):
        if progress_dialog:
            progress_dialog.close()
        QMessageBox.critical(self, "Error", str(message))

    def show_custom_message(self, title, message):
        QMessageBox.information(self, title, message)

    def upload_mr_data(self):
        try:
            file_paths, _ = QFileDialog.getOpenFileNames(
                self, "Upload MR Data", "", "CSV Files (*.csv)")
            
            if file_paths:
                progress_dialog = CircularProgressDialog(self)
                progress_dialog.setLabelText("Loading MR Data...")
                progress_dialog.show()
                
                self.loader = DataLoader(file_paths, 'csv')
                self.loader.progress.connect(progress_dialog.setValue)
                self.loader.finished.connect(
                    lambda df: QTimer.singleShot(500, lambda: self.on_mr_data_loaded(df, progress_dialog)))
                self.loader.error.connect(
                    lambda e: self.show_error(e, progress_dialog))
                self.loader.start()
        except Exception as e:
            self.show_custom_message("Error", f"Error uploading MR data: {str(e)}")

    def upload_ep_data(self):
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Upload EP Data", "", 
                "All Supported Files (*.csv *.xlsx *.xls);;CSV Files (*.csv);;Excel Files (*.xlsx *.xls)")
            
            if file_path:
                progress_dialog = CircularProgressDialog(self)
                progress_dialog.setLabelText("Loading EP Data...")
                progress_dialog.show()
                
                file_type = 'csv' if file_path.endswith('.csv') else 'excel'
                self.loader = DataLoader([file_path], file_type)
                self.loader.progress.connect(progress_dialog.setValue)
                self.loader.finished.connect(lambda df: self.on_ep_data_loaded(df, progress_dialog))
                self.loader.error.connect(lambda e: self.show_error(e, progress_dialog))
                self.loader.start()
        except Exception as e:
            self.show_custom_message("Error", f"Error uploading EP data: {str(e)}")
    
    def limit_sites_data(self, mr_data, ep_data, site_id_mapping_mr, site_id_mapping_ep, site_limit=0):
        if site_limit < 0:
            raise ValueError("site_limit cannot be negative")
        
        actual_limit = 50 if site_limit == 0 else site_limit
        
        mr_sites = mr_data[site_id_mapping_mr].unique()
        ep_sites = ep_data[site_id_mapping_ep].unique()
        
        all_sites = pd.unique(np.concatenate([mr_sites, ep_sites]))
        total_sites = len(all_sites)
        
        warning_info = {
            'exceeds_limit': total_sites > actual_limit,
            'total_sites': total_sites,
            'limit': actual_limit,
            'sites_removed': max(0, total_sites - actual_limit)
        }
        
        selected_sites = all_sites[:actual_limit]
        
        filtered_mr = mr_data[mr_data[site_id_mapping_mr].isin(selected_sites)].copy()
        filtered_ep = ep_data[ep_data[site_id_mapping_ep].isin(selected_sites)].copy()
        return filtered_mr, filtered_ep, warning_info

    def show_data_limitation_warning(self, warning_info, stats_before, stats_after):
        if warning_info['exceeds_limit']:
            limit_type = "default limit of 50 sites" if warning_info['limit'] == 50 else f"limit of {warning_info['limit']} sites"
            
            warning_message = QMessageBox(self)
            warning_message.setIcon(QMessageBox.Icon.Warning)
            warning_message.setWindowTitle("Data Limitation Warning")
            warning_message.setText("Data has been limited due to site count restrictions")
            
            detailed_text = (
                f"Your data contains {warning_info['total_sites']} unique sites, which exceeds the {limit_type}.\n\n"
                f"• {warning_info['sites_removed']} sites have been removed\n"
                f"• Only the first {warning_info['limit']} sites will be used\n\n"
                f"Before limiting:\n"
                f"- Total unique sites: {stats_before['total_unique_sites']}\n"
                f"- MR unique sites: {stats_before['mr_unique_sites']}\n"
                f"- EP unique sites: {stats_before['ep_unique_sites']}\n"
                f"- Common sites: {stats_before['common_sites']}\n\n"
                f"After limiting:\n"
                f"- Total unique sites: {stats_after['total_unique_sites']}\n"
                f"- MR unique sites: {stats_after['mr_unique_sites']}\n"
                f"- EP unique sites: {stats_after['ep_unique_sites']}\n"
                f"- Common sites: {stats_after['common_sites']}"
            )
            warning_message.setDetailedText(detailed_text)
            warning_message.setStandardButtons(QMessageBox.StandardButton.Ok)
            warning_message.exec()

    def get_site_stats(self, mr_data, ep_data, site_id_mapping_mr, site_id_mapping_ep):
        mr_sites = set(mr_data[site_id_mapping_mr].unique())
        ep_sites = set(ep_data[site_id_mapping_ep].unique())
        return {
            'total_unique_sites': len(mr_sites.union(ep_sites)),
            'mr_unique_sites': len(mr_sites),
            'ep_unique_sites': len(ep_sites),
            'common_sites': len(mr_sites.intersection(ep_sites))
        }
    
    def on_mr_data_loaded(self, data, progress_dialog):
        try:
            self.mr_data = data
            if self.ep_data is not None and hasattr(self, 'mappings') and self.mappings:
                mr_site_col = self.mappings["MR Site ID"]
                ep_site_col = self.mappings["EP Site ID"]
                
                stats_before = self.get_site_stats(self.mr_data, self.ep_data, mr_site_col, ep_site_col)
                
                self.mr_data, self.ep_data, warning_info = self.limit_sites_data(
                    self.mr_data, 
                    self.ep_data,
                    mr_site_col,
                    ep_site_col,
                    self.site_limit
                )
                
                stats_after = self.get_site_stats(self.mr_data, self.ep_data, mr_site_col, ep_site_col)
                
                self.update_table(self.mr_table, self.mr_data)
                self.update_table(self.ep_table, self.ep_data)
                
                if warning_info['exceeds_limit']:
                    self.show_data_limitation_warning(warning_info, stats_before, stats_after)
                
                message = "Data loaded successfully!"
            else:
                self.update_table(self.mr_table, self.mr_data)
                message = "MR Data loaded successfully!"
            
            progress_dialog.setValue(100)
            QThread.msleep(500)
            progress_dialog.close()
            self.show_custom_message("Success", message)
        except Exception as e:
            self.show_error(f"Error updating table: {str(e)}", progress_dialog)

    def validate_ep_sites(self, ep_data, site_id_column):
        try:
            check_saved_sites = get_sites(file_path=LICENSE_FILE_PATH)
            if check_saved_sites is not None and check_saved_sites is not False:
                saved_sites = check_saved_sites
                current_sites = set(ep_data[site_id_column].unique().tolist())
            
                if saved_sites == current_sites:
                    return True, "Site IDs match previous data."
                else:
                    message = "Site IDs do not match previous data"
                    return False, message
            else:
                current_sites = sorted(ep_data[site_id_column].unique().tolist())
                save_sites(file_path=LICENSE_FILE_PATH, sites=current_sites)
                return True, "Sites have been saved"
        except Exception as e:
            return False, f"Error validating sites: {str(e)}"

    def on_ep_data_loaded(self, data, progress_dialog):
        try:
            if self.site_limit == 0 and "EP Site ID" in self.mappings:
                is_valid, message = self.validate_ep_sites(data, self.mappings["EP Site ID"])
                if not is_valid:
                    progress_dialog.close()
                    self.show_custom_message("Site ID Mismatch", message)
                    return
            
            self.ep_data = data
            if self.mr_data is not None and hasattr(self, 'mappings') and self.mappings:
                mr_site_col = self.mappings["MR Site ID"]
                ep_site_col = self.mappings["EP Site ID"]
                
                stats_before = self.get_site_stats(self.mr_data, self.ep_data, mr_site_col, ep_site_col)
                self.mr_data, self.ep_data, warning_info = self.limit_sites_data(
                    self.mr_data, 
                    self.ep_data,
                    mr_site_col,
                    ep_site_col,
                    self.site_limit
                )
                
                stats_after = self.get_site_stats(self.mr_data, self.ep_data, mr_site_col, ep_site_col)
                
                self.update_table(self.mr_table, self.mr_data)
                self.update_table(self.ep_table, self.ep_data)
                
                if warning_info['exceeds_limit'] or self.site_limit > 0:
                    self.show_data_limitation_warning(warning_info, stats_before, stats_after)
                
                message = "Data loaded successfully!"
            else:
                self.update_table(self.ep_table, self.ep_data)
                message = "EP Data loaded successfully!"
                
                if self.site_limit > 0:
                    self.show_custom_message("Site Limit Applied", 
                        f"Note: Your data will be limited to {self.site_limit} sites when processing.")
                
            progress_dialog.setValue(100)
            QThread.msleep(500)
            progress_dialog.close()
            self.show_custom_message("Success", message)
        except Exception as e:
            self.show_error(f"Error loading EP data: {str(e)}", progress_dialog)

    def update_table(self, table, data):
        try:
            if data is None or data.empty:
                return

            table.setRowCount(0)
            table.setColumnCount(len(data.columns))
            table.setHorizontalHeaderLabels(data.columns)

            with ThreadPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
                chunk_size = 1000
                for i in range(0, len(data), chunk_size):
                    chunk = data.iloc[i:i+chunk_size]
                    executor.submit(self.load_table_chunk, table, chunk, i)
            
            for i in range(len(data.columns)):
                table.resizeColumnToContents(i)
        except Exception as e:
            self.show_custom_message("Error", f"Error updating table: {str(e)}")

    def load_table_chunk(self, table, chunk, start_row):
        try:
            for i, (_, row) in enumerate(chunk.iterrows()):
                row_position = start_row + i
                table.insertRow(row_position)
                for j, value in enumerate(row):
                    item = QTableWidgetItem(str(value))
                    table.setItem(row_position, j, item)
        except Exception as e:
            print(f"Error loading table chunk: {str(e)}")

    def match_columns(self):
        try:
            if self.mr_data is None or self.ep_data is None:
                self.show_custom_message("Warning", "Please load both MR and EP data before matching columns.")
                return

            dialog = ColumnMatchDialog(self.mr_data.columns, self.ep_data.columns, self)
            if dialog.exec():
                self.mappings = dialog.get_mappings()
                
                # Create key columns for joining
                self.mr_data['MR_key'] = self.mr_data[self.mappings["MR Site ID"]].astype(str) + '_' + self.mr_data[self.mappings["MR Cell ID"]].astype(str)
                self.ep_data['EP_key'] = self.ep_data[self.mappings["EP Site ID"]].astype(str) + '_' + self.ep_data[self.mappings["EP Cell ID"]].astype(str)
                
                # Trial version validation
                if self.site_limit == 0:  # Trial version
                    ep_keys = self.ep_data['EP_key'].unique().tolist()
                    is_valid, message = self.trial_manager.validate_sites(ep_keys)
                    
                    if not is_valid:
                        self.show_custom_message("Trial Version Restriction", message)
                        return
                    
                    # Register sites if first time
                    self.trial_manager.register_sites(ep_keys)
                
                self.show_custom_message("Success", "Columns matched successfully!")
        except Exception as e:
            self.show_custom_message("Error", f"Error matching columns: {str(e)}")

    def submit_data(self):
        try:
            if not self.mappings:
                self.show_custom_message("Warning", "Please match columns before submitting.")
                return

            if self.mr_data is None or self.ep_data is None:
                self.show_custom_message("Warning", "Please load both MR and EP data before submitting.")
                return

            # Trial version validation before submitting
            if self.site_limit == 0:  # Trial version
                ep_keys = self.ep_data['EP_key'].unique().tolist()
                is_valid, message = self.trial_manager.validate_sites(ep_keys)
                
                if not is_valid:
                    self.show_custom_message("Trial Version Restriction", message)
                    return

            # Store the data for analysis windows to access
            if self.main_window:
                self.main_window.mr_data = self.mr_data
                self.main_window.ep_data = self.ep_data
                self.main_window.mappings = self.mappings
                
                # Navigate back to home screen
                self.main_window.stack.setCurrentIndex(0)
                if hasattr(self.main_window, 'footer'):
                    self.main_window.footer.show()
                    
                self.show_custom_message("Success", "Data submitted successfully! You can now proceed with analysis.")
                
        except Exception as e:
            self.show_custom_message("Error", f"Error submitting data: {str(e)}")

    def save_project(self):
        try:
            if self.mr_data is None or self.ep_data is None:
                self.show_custom_message("Warning", "Please load MR and EP data before saving a project.")
                return

            file_path, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "Project Files (*.prj)")
            if file_path:
                progress_dialog = CircularProgressDialog(self)
                progress_dialog.setLabelText("Saving project...")
                progress_dialog.show()
                
                try:
                    progress_dialog.setValue(25)
                    project_data = {
                        "mr_data": self.mr_data.to_dict(),
                        "ep_data": self.ep_data.to_dict(),
                        "mappings": self.mappings,
                        "result_df": self.result_df.to_dict() if self.result_df is not None else None
                    }
                    
                    # Add parameter settings if they exist
                    if os.path.exists('Parameter_Settings.json'):
                        with open('Parameter_Settings.json', 'r') as f:
                            param_settings = json.load(f)
                        project_data['parameter_settings'] = param_settings
                    
                    progress_dialog.setValue(75)
                    with open(file_path, 'w') as f:
                        json.dump(project_data, f)
                    
                    progress_dialog.setValue(100)
                    QTimer.singleShot(500, lambda: self.show_custom_message(
                        "Success", f"Project saved successfully to {file_path}"))
                        
                except Exception as e:
                    self.show_custom_message("Error", f"Failed to save project: {str(e)}")
                finally:
                    progress_dialog.close()
                    
        except Exception as e:
            self.show_custom_message("Error", f"Error saving project: {str(e)}")

    def load_project(self):
        try:
            file_path, _ = QFileDialog.getOpenFileName(self, "Load Project", "", "Project Files (*.prj)")
            if file_path:
                progress_dialog = CircularProgressDialog(self)
                progress_dialog.show()
                
                # Create and setup the project loader
                self.project_loader = ProjectLoader(file_path)
                
                # Connect signals
                self.project_loader.progress.connect(
                    lambda value, text: self.update_progress(progress_dialog, value, text))
                self.project_loader.finished.connect(
                    lambda result: self.on_project_loaded(result, progress_dialog))
                self.project_loader.error.connect(
                    lambda e: self.show_error(f"Failed to load project: {e}", progress_dialog))
                
                # Start loading
                self.project_loader.start()
                
        except Exception as e:
            self.show_custom_message("Error", f"Error loading project: {str(e)}")

    def update_progress(self, dialog, value, text):
        dialog.setValue(value)
        dialog.setLabelText(text)

    def on_project_loaded(self, result, progress_dialog):
        try:
            # Update the data
            self.mr_data = result["mr_data"]
            self.ep_data = result["ep_data"]
            self.mappings = result["mappings"]
            self.result_df = result["result_df"]
            
            # Save parameter settings if present
            if result.get("parameter_settings"):
                with open('Parameter_Settings.json', 'w') as f:
                    json.dump(result["parameter_settings"], f, indent=4)
            
            # Update tables
            self.update_table(self.mr_table, self.mr_data)
            self.update_table(self.ep_table, self.ep_data)
            
            # Close progress dialog and show success message
            QTimer.singleShot(500, progress_dialog.close)
            self.show_custom_message("Success", "Project loaded successfully!")
            
        except Exception as e:
            self.show_error(f"Error finalizing project load: {str(e)}", progress_dialog)

    def reset_all(self):
        try:
            # Reset upload window data
            self.mr_data = None
            self.ep_data = None
            self.result_df = None
            self.mappings = {}
            
            # Clear tables
            self.mr_table.setRowCount(0)
            self.mr_table.setColumnCount(0)
            self.ep_table.setRowCount(0)
            self.ep_table.setColumnCount(0)
            
            results_dir = "results"
            if not os.path.exists(results_dir):
                os.makedirs(results_dir, exist_ok=True)
            temp_path = os.path.join(results_dir, 'temp_result.csv')
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            
            # Reset and reinitialize other windows
            if self.main_window:
                # Reset Sector Swap Window
                if hasattr(self.main_window, 'sector_swap_window'):
                    if self.main_window.sector_swap_window:
                        self.main_window.sector_swap_window.close()
                    delattr(self.main_window, 'sector_swap_window')
                
                # Reset Coordinates Window
                if hasattr(self.main_window, 'actual_coordinates_window'):
                    if self.main_window.actual_coordinates_window:
                        self.main_window.actual_coordinates_window.close()
                    delattr(self.main_window, 'actual_coordinates_window')
                
                # Reset Azimuth Window
                if hasattr(self.main_window, 'actual_azimuth_window'):
                    if self.main_window.actual_azimuth_window:
                        self.main_window.actual_azimuth_window.close()
                    delattr(self.main_window, 'actual_azimuth_window')
                
                # Reset Tilt Window
                if hasattr(self.main_window, 'actual_tilt_window'):
                    if self.main_window.actual_tilt_window:
                        self.main_window.actual_tilt_window.close()
                    delattr(self.main_window, 'actual_tilt_window')

                # Reset Neighbor Audit Window
                if hasattr(self.main_window, 'neighbor_window'):
                    if self.main_window.neighbor_window:
                        # Reset settings to default
                        if hasattr(self.main_window.neighbor_window, 'settings_panel'):
                            settings = self.main_window.neighbor_window.settings_panel
                            settings.radius_slider.slider.setValue(5000)
                            settings.max_neighbors_slider.slider.setValue(32)
                        
                        # Clear metrics
                        if hasattr(self.main_window.neighbor_window, 'metrics_layout'):
                            while self.main_window.neighbor_window.metrics_layout.count():
                                item = self.main_window.neighbor_window.metrics_layout.takeAt(0)
                                if item.widget():
                                    item.widget().deleteLater()
                        
                        # Clear table
                        if hasattr(self.main_window.neighbor_window, 'neighbor_table'):
                            self.main_window.neighbor_window.neighbor_table.table.setRowCount(0)

                        self.main_window.neighbor_window.close()
                    delattr(self.main_window, 'neighbor_window')

                # Return to main window
                self.main_window.stack.setCurrentIndex(0)
                if hasattr(self.main_window, 'footer'):
                    self.main_window.footer.show()
            
            self.show_custom_message("Reset Complete", 
                                   "All data, settings and analysis windows have been reset.\n"
                                   "You can now load new data and perform new analysis.")
            
        except Exception as e:
            self.show_custom_message("Error", f"Error during reset: {str(e)}")
            
    def go_home(self):
        try:
            if self.main_window and hasattr(self.main_window, 'stack'):
                self.main_window.stack.setCurrentIndex(0)
                if hasattr(self.main_window, 'footer'):
                    self.main_window.footer.show()
        except Exception as e:
            print(f"Error navigating home: {str(e)}")

    def closeEvent(self, event):
        try:
            self.thread_pool.shutdown(wait=False)
            super().closeEvent(event)
        except Exception as e:
            print(f"Error in close event: {str(e)}")