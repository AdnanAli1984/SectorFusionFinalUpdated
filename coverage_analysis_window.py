# coverage_analysis_window.py
import sys
import os
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import multiprocessing

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QFrame, QTableWidget, QTableWidgetItem,
                            QGridLayout, QScrollArea, QFileDialog, QMessageBox,
                            QGraphicsDropShadowEffect, QComboBox, QDialog, QApplication)
from PyQt6.QtCore import Qt, QSize, QPoint, QTimer
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPainterPath, QPalette, QIcon, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from coverage_calculator import CoverageCalculator
from responsive_ui import ResponsiveUI

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
            QComboBox:hover {
                border-color: #4682B4;
            }
        """)
        self.addItem("All Results")
        self.addItem("Poor Coverage Cells")
        self.addItem("Overshooting Cells")

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
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
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
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #1F2937; font-size: 14px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        value_layout = QHBoxLayout()
        value_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Customize value display for Average RSRP
        if "RSRP" in title:
            value_label = QLabel(value)  # Already formatted as "X.X dBm"
        else:
            value_label = QLabel(str(value))
        value_label.setStyleSheet("color: #1F2937; font-size: 24px; font-weight: bold;")
        
        # Don't show percentage for Average RSRP
        if "RSRP" not in title:
            percentage_label = QLabel(f"{percentage:.1f}%")
            percentage_label.setStyleSheet("color: #6B7280; font-size: 14px; margin-left: 5px;")
            value_layout.addWidget(percentage_label)
        
        value_layout.addWidget(value_label)
        main_layout.addLayout(value_layout)
        
        # Add progress bar except for Average RSRP
        if "RSRP" not in title:
            self.progress_bar = ProgressBar(percentage)
            main_layout.addWidget(self.progress_bar)

    def get_icon_path(self, title):
        try:
            base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'icons')
            icon_mapping = {
                "Total Cells": "total-cells-icon.svg",
                "Poor Coverage Cells": "inter-freq-icon.svg",
                "Average RSRP": "avg-neighbors-icon.svg",
                "Overshooting Cells": "total-relations-icon.svg"
            }
            
            if title in icon_mapping:
                icon_path = os.path.join(base_path, icon_mapping[title])
                if os.path.exists(icon_path):
                    return icon_path
            return None
        except Exception as e:
            print(f"Error getting icon path: {str(e)}")
            return None
        
class CoverageTable(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("coverageTable")
        self.setStyleSheet("""
            QFrame#coverageTable {
                background-color: white;
                border-radius: 10px;
                padding: 10px;
            }
        """)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        header_layout = QHBoxLayout()
        title = QLabel("Coverage Details")
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
        
        # Create scroll area for table
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: white;
            }
        """)
        
        # Create table
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
        
        columns = [
            'Site ID', 'Cell ID', 'Carrier',
            '0-300m Coverage', '300-500m Coverage', 
            '500-700m Coverage', '700-1000m Coverage', '>1000m Coverage',
            'RSRP -40 to -70', 'RSRP -70 to -85',
            'RSRP -85 to -95', 'RSRP -95 to -105', 'RSRP <-105',
            'Overall Coverage Score', 'Total MR Points', 'Coverage Status'
        ]
        
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.horizontalHeader().setStretchLastSection(True)
        
        scroll_area.setWidget(self.table)
        layout.addWidget(scroll_area)

    def set_data(self, data):
        try:
            # Clear existing rows
            self.table.setRowCount(0)
            
            # Set new row count
            self.table.setRowCount(len(data))
            
            print(f"Setting table data for {len(data)} rows")
            
            # Get column headers
            headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
            
            # Populate table
            for row_idx, row in data.iterrows():
                for col_idx, header in enumerate(headers):
                    value = str(row[header])
                    item = QTableWidgetItem(value)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    
                    # Color code columns
                    if col_idx >= 3 and col_idx <= 7:  # Distance ranges
                        try:
                            coverage = float(value.strip('%'))
                            if coverage >= 80:
                                item.setBackground(QColor("#d1fae5"))  # Green
                            elif coverage >= 50:
                                item.setBackground(QColor("#fef3c7"))  # Yellow
                            else:
                                item.setBackground(QColor("#fee2e2"))  # Red
                        except:
                            pass
                    
                    elif col_idx >= 8 and col_idx <= 12:  # RSRP ranges
                        try:
                            rsrp_value = float(value.strip('%'))
                            if rsrp_value >= 70:
                                item.setBackground(QColor("#d1fae5"))  # Green
                            elif rsrp_value >= 40:
                                item.setBackground(QColor("#fef3c7"))  # Yellow
                            else:
                                item.setBackground(QColor("#fee2e2"))  # Red
                        except:
                            pass
                            
                    elif col_idx == 13:  # Overall score
                        try:
                            score = float(value.strip('%'))
                            if score >= 80:
                                item.setBackground(QColor("#d1fae5"))  # Green
                            elif score >= 50:
                                item.setBackground(QColor("#fef3c7"))  # Yellow
                            else:
                                item.setBackground(QColor("#fee2e2"))  # Red
                        except:
                            pass
                            
                    elif col_idx == 15:  # Coverage status
                        if value == "Poor Coverage":
                            item.setBackground(QColor("#fee2e2"))  # Red background
                            item.setForeground(QColor("#991b1b"))  # Dark red text
                        elif value == "Good Coverage":
                            item.setBackground(QColor("#d1fae5"))  # Green background
                            item.setForeground(QColor("#065f46"))  # Dark green text
                        elif value == "No MR Data":
                            item.setBackground(QColor("#f3f4f6"))  # Gray background
                            item.setForeground(QColor("#4b5563"))  # Dark gray text
                    
                    self.table.setItem(row_idx, col_idx, item)
            
            # Adjust column widths
            for col in range(self.table.columnCount()):
                self.table.resizeColumnToContents(col)
            
            print(f"Table updated successfully with {self.table.rowCount()} rows")
            
        except Exception as e:
            print(f"Error setting table data: {str(e)}")
            raise

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

class CoverageAnalysisWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        ResponsiveUI.make_responsive(self)
        self.main_window = parent
        self.mr_data = getattr(self.main_window, 'mr_data', None)
        self.ep_data = getattr(self.main_window, 'ep_data', None)
        self.mappings = getattr(self.main_window, 'mappings', None)
        
        self.result_df = None
        self.is_analyzing = False
        self._analysis_state = {
            'result_df': None,
            'metrics': None,
            'current_filter': 0
        }
         # Initialize/restore state from main window if it exists
        if hasattr(self.main_window, '_coverage_analysis_state'):
            saved_state = self.main_window._coverage_analysis_state
            if saved_state and saved_state.get('result_df') is not None:
                self.result_df = saved_state['result_df'].copy()
                self.update_metrics()
                self.update_charts()
                self.update_table()
                if hasattr(self, 'result_filter'):
                    self.result_filter.setCurrentIndex(saved_state.get('current_filter', 0))
        self.coverage_calculator = CoverageCalculator()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        header = self.create_header()
        layout.addLayout(header)

        content = QGridLayout()
        content.setSpacing(10)
        
        # Left side with metrics and charts
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Metrics section
        self.metrics_layout = QHBoxLayout()
        self.metrics_layout.setSpacing(10)
        left_layout.addLayout(self.metrics_layout)
        
        # Charts section
        self.charts_layout = QVBoxLayout()
        self.charts_layout.setSpacing(10)
        left_layout.addLayout(self.charts_layout)
        
        content.addWidget(left_widget, 0, 0, 1, 8)
        
        # Right side with table
        self.coverage_table = CoverageTable()
        content.addWidget(self.coverage_table, 0, 8, 1, 4)
        
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
        
        title = QLabel("MR Coverage Analysis")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #1e293b;")
        left_side.addWidget(title)
        left_side.addStretch()
        
        header.addLayout(left_side)
        header.addStretch()
        
        right_side = QHBoxLayout()
        
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

        header.addLayout(right_side)
        
        return header

    def analyze_data(self):
        try:
            if self.is_analyzing:
                QMessageBox.warning(self, "Warning", "Analysis already in progress. Please wait.")
                return
                
            if not self.load_data():
                QMessageBox.warning(self, "Warning", "No data available. Please upload and submit data first.")
                return
            
            self.is_analyzing = True
            progress_dialog = CircularProgressDialog(self)
            progress_dialog.setLabelText("Initializing coverage analysis...")
            progress_dialog.setValue(0)
            progress_dialog.show()
            QApplication.processEvents()
            
            try:
                self.clear_layouts()
                progress_dialog.setValue(10)
                progress_dialog.setLabelText("Processing data for all cells...")
                QApplication.processEvents()
                
                # Process all cells from EP data
                with ThreadPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
                    # Get unique site_id, cell_id combinations from EP data
                    unique_cells = self.ep_data[[
                        self.mappings['EP Site ID'],
                        self.mappings['EP Cell ID'],
                        self.mappings['Carrier']
                    ]].drop_duplicates()
                    
                    total_cells = len(unique_cells)
                    progress_dialog.setLabelText(f"Processing {total_cells} cells...")
                    QApplication.processEvents()
                    
                    # Process coverage analysis
                    self.result_df = self.coverage_calculator.analyze_coverage(
                        self.mr_data,
                        self.ep_data,
                        self.mappings,
                        executor=executor,
                        progress_callback=lambda p: self.update_progress(progress_dialog, p)
                    )
                
                progress_dialog.setValue(85)
                progress_dialog.setLabelText("Updating display...")
                QApplication.processEvents()
                
                # Update UI with results
                self.update_metrics()
                self.update_charts()
                self.update_table()
                self.result_filter.setCurrentIndex(0)
                
                progress_dialog.setValue(100)
                progress_dialog.setLabelText("Analysis complete!")
                QApplication.processEvents()
                
                # Show results summary
                total_cells = len(self.result_df)
                cells_with_data = len(self.result_df[self.result_df['Coverage Status'] != 'No MR Data'])
                QMessageBox.information(
                    self, 
                    "Analysis Complete", 
                    f"Coverage analysis completed successfully!\n\n"
                    f"Total Cells Analyzed: {total_cells}\n"
                    f"Cells with MR Data: {cells_with_data}\n"
                    f"Cells without MR Data: {total_cells - cells_with_data}"
                )
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to analyze coverage data: {str(e)}")
            finally:
                self.is_analyzing = False
                progress_dialog.close()
                    
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Coverage analysis failed: {str(e)}")
            self.is_analyzing = False

    def update_progress(self, dialog, progress):
        dialog.setValue(progress)
        if hasattr(self, 'result_df') and self.result_df is not None:
            processed = len(self.result_df)
            total = len(self.ep_data)
            dialog.setLabelText(f"Analyzing coverage: {progress}% ({processed}/{total} cells)")
        else:
            dialog.setLabelText(f"Analyzing coverage: {progress}%")
        QApplication.processEvents()

    def update_progress(self, dialog, progress):
        dialog.setValue(progress)
        dialog.setLabelText(f"Analyzing coverage: {progress}%")
        QApplication.processEvents()

    def update_metrics(self):
        try:
            # Clear existing metrics
            for i in reversed(range(self.metrics_layout.count())):
                item = self.metrics_layout.itemAt(i)
                if item.widget():
                    item.widget().deleteLater()
            
            # Calculate metrics
            metrics = self.coverage_calculator.calculate_metrics(
                self.result_df,
                self.mr_data,
                self.mappings
            )
            
            # Add metric cards
            self.metrics_layout.addWidget(MetricCard(
                "Total Cells",
                metrics['total_cells'],
                100.0
            ))
            
            self.metrics_layout.addWidget(MetricCard(
                "Poor Coverage Cells",
                metrics['poor_coverage']['count'],
                metrics['poor_coverage']['percentage']
            ))
            
            self.metrics_layout.addWidget(MetricCard(
                "Average RSRP",
                f"{metrics['average_rsrp']:.1f} dBm",
                100.0
            ))
            
            self.metrics_layout.addWidget(MetricCard(
                "Overshooting Cells",
                metrics['overshooting']['count'],
                metrics['overshooting']['percentage']
            ))
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update metrics: {str(e)}")

    def create_coverage_chart(self):
        try:
            if not hasattr(self, 'result_df') or self.result_df is None:
                return None
            
            # Create figure with responsive size
            fig = Figure(figsize=(8, 5), dpi=100, facecolor='none')
            canvas = FigureCanvas(fig)
            
            # Adjust layout to prevent text cutoff
            fig.subplots_adjust(left=0.12, right=0.95, top=0.9, bottom=0.25)
            
            ax = fig.add_subplot(111)
            
            # Calculate average coverage for each distance range
            coverage_ranges = [
                '0-300m Coverage', '300-500m Coverage',
                '500-700m Coverage', '700-1000m Coverage', '>1000m Coverage'
            ]
            
            averages = []
            for col in coverage_ranges:
                avg = self.result_df[col].str.rstrip('%').astype(float).mean()
                averages.append(avg)
            
            # Create bar chart
            x_pos = np.arange(len(coverage_ranges))
            bars = ax.bar(x_pos, averages, align='center', alpha=0.8, width=0.6)
            
            # Use the same colors as RSRP ranges in reverse order
            # RSRP colors: Best -> Worst = ['#4682B4', '#82CA9D', '#FFD700', '#FFA07A', '#FF8C8C']
            # For coverage: Closest -> Farthest = Best -> Worst
            rsrp_colors = ['#4682B4', '#82CA9D', '#FFD700', '#FFA07A', '#FF8C8C']
            
            # Apply colors directly in order
            for i, bar in enumerate(bars):
                bar.set_color(rsrp_colors[i])
            
            # Customize chart
            ax.set_ylabel('Coverage Percentage', fontsize=10, labelpad=10)
            ax.set_title('Coverage Distribution by Distance', pad=20, fontsize=12)
            ax.set_xticks(x_pos)
            ax.set_xticklabels([r.replace(' Coverage', '') for r in coverage_ranges], 
                            rotation=45, ha='right', fontsize=9)
            
            # Add value labels on top of bars
            for i, v in enumerate(averages):
                ax.text(i, v + 1, f'{v:.1f}%', ha='center', va='bottom', fontsize=9)
            
            # Customize grid and axes
            ax.grid(True, axis='y', linestyle='--', alpha=0.7)
            ax.set_ylim(0, max(averages) * 1.2)  # Dynamic y-limit with 20% padding
            
            # Remove top and right spines
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            # Tight layout to prevent label cutoff
            fig.tight_layout()
            
            return canvas
            
        except Exception as e:
            print(f"Error creating coverage chart: {str(e)}")
            return None

    def create_rsrp_chart(self):
        try:
            if not hasattr(self, 'result_df') or self.result_df is None:
                return None
            
            # Create figure with responsive size
            fig = Figure(figsize=(8, 5), dpi=100, facecolor='none')
            canvas = FigureCanvas(fig)
            
            # Adjust layout to prevent text cutoff
            fig.subplots_adjust(left=0.12, right=0.95, top=0.9, bottom=0.25)
            
            ax = fig.add_subplot(111)
            
            # Calculate average RSRP percentages for each range
            rsrp_ranges = [
                'RSRP -40 to -70', 'RSRP -70 to -85',
                'RSRP -85 to -95', 'RSRP -95 to -105', 'RSRP <-105'
            ]
            
            averages = []
            for col in rsrp_ranges:
                avg = self.result_df[col].str.rstrip('%').astype(float).mean()
                averages.append(avg)
            
            # Create bar chart
            x_pos = np.arange(len(rsrp_ranges))
            bars = ax.bar(x_pos, averages, align='center', alpha=0.8, width=0.6)
            
            # Define RSRP colors
            rsrp_colors = ['#4682B4', '#82CA9D', '#FFD700', '#FFA07A', '#FF8C8C']
            
            # Apply colors directly
            for bar, color in zip(bars, rsrp_colors):
                bar.set_color(color)
            
            # Customize chart
            ax.set_ylabel('Percentage of Measurements', fontsize=10, labelpad=10)
            ax.set_title('RSRP Distribution', pad=20, fontsize=12)
            ax.set_xticks(x_pos)
            ax.set_xticklabels([r.replace('RSRP ', '') for r in rsrp_ranges], 
                            rotation=45, ha='right', fontsize=9)
            
            # Add value labels on top of bars
            for i, v in enumerate(averages):
                ax.text(i, v + 1, f'{v:.1f}%', ha='center', va='bottom', fontsize=9)
            
            # Customize grid and axes
            ax.grid(True, axis='y', linestyle='--', alpha=0.7)
            ax.set_ylim(0, max(averages) * 1.2)  # Dynamic y-limit with 20% padding
            
            # Remove top and right spines
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            # Tight layout to prevent label cutoff
            fig.tight_layout()
            
            return canvas
            
        except Exception as e:
            print(f"Error creating RSRP chart: {str(e)}")
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
            
            charts_grid = QGridLayout()
            charts_grid.setSpacing(10)
            
            # Add coverage distance chart
            coverage_chart = self.create_coverage_chart()
            if coverage_chart:
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
                frame_layout.addWidget(coverage_chart)
                
                chart_layout.addWidget(frame)
                charts_grid.addWidget(chart_widget, 0, 0)
            
            # Add RSRP distribution chart
            rsrp_chart = self.create_rsrp_chart()
            if rsrp_chart:
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
                frame_layout.addWidget(rsrp_chart)
                
                chart_layout.addWidget(frame)
                charts_grid.addWidget(chart_widget, 0, 1)
            
            self.charts_layout.addLayout(charts_grid)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update charts: {str(e)}")

    def update_table(self):
        try:
            if not hasattr(self, 'result_df') or self.result_df is None:
                return
            
            # Convert Site ID and Cell ID to strings for sorting
            sorted_df = self.result_df.copy()
            sorted_df['Site ID'] = sorted_df['Site ID'].astype(str)
            sorted_df['Cell ID'] = sorted_df['Cell ID'].astype(str)
            
            # Sort by Site ID and Cell ID
            sorted_df = sorted_df.sort_values(['Site ID', 'Cell ID'])
            
            # Reset table before adding new data
            self.coverage_table.table.setRowCount(0)
            
            # Set the row count
            self.coverage_table.table.setRowCount(len(sorted_df))
            
            # Update table with all cells
            self.coverage_table.set_data(sorted_df)
            
            # Debug info
            total_cells = len(sorted_df)
            cells_with_data = len(sorted_df[sorted_df['Coverage Status'] != 'No MR Data'])
            cells_without_data = total_cells - cells_with_data
            
            print(f"\nUpdating table with {total_cells} total cells:")
            print(f"DataFrame shape: {sorted_df.shape}")
            print(f"Unique Sites: {sorted_df['Site ID'].nunique()}")
            print(f"Unique Cells: {len(sorted_df)}")
            print(f"- {cells_with_data} cells with MR data")
            print(f"- {cells_without_data} cells without MR data\n")
            
        except Exception as e:
            print(f"Error in update_table: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to update table: {str(e)}")

    def apply_result_filter(self, index):
        try:
            if not hasattr(self, 'result_df') or self.result_df is None:
                return
                
            filter_text = self.result_filter.currentText()
            
            if filter_text == "All Results":
                filtered_df = self.result_df
            elif filter_text == "Poor Coverage Cells":
                filtered_df = self.result_df[
                    (self.result_df['Coverage Status'] == 'Poor Coverage')
                ]
            else:  # "Overshooting Cells"
                filtered_df = self.result_df[
                    self.result_df['>1000m Coverage'].str.rstrip('%').astype(float) > 10
                ]
            
            # Sort filtered results
            filtered_df = filtered_df.sort_values(['Site ID', 'Cell ID'])
            
            # Update table with filtered data
            self.coverage_table.set_data(filtered_df)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error applying filter: {str(e)}")

    def load_data(self):
        try:
            if self.mr_data is None or self.ep_data is None or self.mappings is None:
                QMessageBox.warning(self, "Warning", 
                    "No data available. Please upload data and submit from Upload window first.")
                return False
            
            # Print data information for debugging
            print(f"EP Data shape: {self.ep_data.shape}")
            print(f"Unique sites in EP data: {len(self.ep_data[self.mappings['EP Site ID']].unique())}")
            print(f"Unique cells in EP data: {len(self.ep_data[[self.mappings['EP Site ID'], self.mappings['EP Cell ID']]].drop_duplicates())}")
                
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load data: {str(e)}")
            return False

    def clear_layouts(self):
        try:
            # Clear metrics layout
            while self.metrics_layout.count():
                item = self.metrics_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            # Clear charts layout
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

    def go_home(self):
        try:
            if self.main_window and hasattr(self.main_window, 'stack'):
                # Save current state before navigating
                if hasattr(self, 'result_df') and self.result_df is not None:
                    self.main_window._coverage_analysis_state = {
                        'result_df': self.result_df.copy(),
                        'current_filter': self.result_filter.currentIndex()
                    }
                
                self.main_window.stack.setCurrentIndex(0)
                if hasattr(self.main_window, 'footer'):
                    self.main_window.footer.show()
        except Exception as e:
            print(f"Error navigating home: {str(e)}")

    def resizeEvent(self, event):
        try:
            super().resizeEvent(event)
            if hasattr(self, 'coverage_table'):
                for col in range(self.coverage_table.table.columnCount()):
                    self.coverage_table.table.resizeColumnToContents(col)
        except Exception as e:
            print(f"Error in resize event: {str(e)}")
            
# IconLoader class for loading SVG icons
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