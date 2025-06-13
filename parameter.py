import sys
import json
import os
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtCore import QByteArray
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QLineEdit, QComboBox, 
                            QPushButton, QFrame, QTableWidget, QTableWidgetItem,
                            QHeaderView, QMessageBox, QSizePolicy, QToolButton)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon, QPainter, QColor
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtCore import QByteArray

# Define trash bin icon SVG
TRASH_ICON_SVG = '''
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M3 6h18"/>
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
    <line x1="10" y1="11" x2="10" y2="17"/>
    <line x1="14" y1="11" x2="14" y2="17"/>
</svg>
'''

class DeleteButtonWidget(QWidget):
    def __init__(self, table, row):
        super().__init__()
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 0, 5, 0)
        
        delete_button = QToolButton()
        
        # Create custom icon from SVG
        renderer = QSvgRenderer(QByteArray(TRASH_ICON_SVG.encode()))
        icon_size = 20
        icon = QIcon()
        
        # Create normal state icon (gray)
        pixmap_normal = QPixmap(icon_size, icon_size)
        pixmap_normal.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap_normal)
        renderer.render(painter)
        painter.end()
        
        # Create hover state icon (red)
        pixmap_hover = QPixmap(icon_size, icon_size)
        pixmap_hover.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap_hover)
        painter.setPen(QColor("#dc3545"))  # Red color for hover
        renderer.render(painter)
        painter.end()
        
        # Set both states to the icon
        icon.addPixmap(pixmap_normal, QIcon.Mode.Normal)
        icon.addPixmap(pixmap_hover, QIcon.Mode.Selected)
        
        delete_button.setIcon(icon)
        delete_button.setIconSize(QPixmap(icon_size, icon_size).size())
        delete_button.setToolTip("Delete Row")
        delete_button.clicked.connect(lambda: table.removeRow(row))
        delete_button.setStyleSheet("""
            QToolButton {
                border: none;
                padding: 3px;
            }
            QToolButton:hover {
                background-color: #ffebee;
                border-radius: 3px;
            }
        """)
        
        layout.addWidget(delete_button)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setLayout(layout)

class ParameterSettingsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings_file = 'Parameter_Settings.json'
        self.initUI()
        self.center_on_screen()
        self.load_settings()

    def center_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        self.resize(int(screen.width() * 0.8), int(screen.height() * 0.8))
        frame_geometry = self.frameGeometry()
        center_point = QApplication.primaryScreen().availableGeometry().center()
        frame_geometry.moveCenter(center_point)
        self.move(frame_geometry.topLeft())

    def initUI(self):
        self.setWindowTitle("Parameter Settings")
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)
        
        title_label = QLabel("Parameter Settings")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        main_layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.layer_options = ["L1800", "L2100", "L900", "L2600", "L700", "L800"]
        
        self.create_sector_split_frame()
        self.create_massive_mimo_frame()
        
        main_layout.addWidget(self.sector_frame)
        main_layout.addWidget(self.mimo_frame)
        
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 10, 0, 0)
        
        save_button = QPushButton("Save")
        save_button.setFixedWidth(120)
        save_button.clicked.connect(self.save_settings)
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        
        main_layout.addWidget(button_container)
        
        self.apply_styles()

    def create_sector_split_frame(self):
        self.sector_frame = QFrame()
        self.sector_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.sector_frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        
        layout = QVBoxLayout(self.sector_frame)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title = QLabel("Sector Split Cell ID")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)
        
        # Create table with an extra column for delete button
        self.sector_table = QTableWidget(0, 5)
        self.sector_table.setHorizontalHeaderLabels(["Sector", "Parrent ID", "Child ID", "Layer", ""])
        
        header = self.sector_table.horizontalHeader()
        for i in range(4):  # First 4 columns stretch
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        # Last column (delete button) fixed width
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(4, 50)
        
        self.sector_table.verticalHeader().setDefaultSectionSize(40)
        layout.addWidget(self.sector_table)
        
        add_button = QPushButton("Add")
        add_button.setFixedWidth(100)
        add_button.clicked.connect(lambda: self.add_row(self.sector_table))
        layout.addWidget(add_button, alignment=Qt.AlignmentFlag.AlignLeft)

    def create_massive_mimo_frame(self):
        self.mimo_frame = QFrame()
        self.mimo_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.mimo_frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        
        layout = QVBoxLayout(self.mimo_frame)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title = QLabel("Massive MIMO Cell ID")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)
        
        # Create table with an extra column for delete button
        self.mimo_table = QTableWidget(0, 7)
        self.mimo_table.setHorizontalHeaderLabels(["Sector", "Beam0", "Beam1", "Beam2", "Beam3", "Layer", ""])
        
        header = self.mimo_table.horizontalHeader()
        for i in range(6):  # First 6 columns stretch
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        # Last column (delete button) fixed width
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(6, 50)
        
        self.mimo_table.verticalHeader().setDefaultSectionSize(40)
        layout.addWidget(self.mimo_table)
        
        add_button = QPushButton("Add")
        add_button.setFixedWidth(100)
        add_button.clicked.connect(lambda: self.add_row(self.mimo_table))
        layout.addWidget(add_button, alignment=Qt.AlignmentFlag.AlignLeft)

    def add_row(self, table):
        row_position = table.rowCount()
        table.insertRow(row_position)
        
        # Add empty editable cells
        for col in range(table.columnCount() - 2):  # -2 for Layer and Delete columns
            item = QTableWidgetItem("")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row_position, col, item)
        
        # Add layer combo box
        layer_combo = QComboBox()
        layer_combo.addItems(self.layer_options)
        layer_combo.setStyleSheet("""
            QComboBox {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
                min-width: 100px;
            }
        """)
        table.setCellWidget(row_position, table.columnCount() - 2, layer_combo)
        
        # Add delete button
        delete_widget = DeleteButtonWidget(table, row_position)
        table.setCellWidget(row_position, table.columnCount() - 1, delete_widget)

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QFrame {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
            QTableWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                gridline-color: #ddd;
                background-color: white;
                selection-background-color: #e8f0fe;
            }
            QTableWidget::item {
                padding: 8px;
                border: none;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 12px;
                border: none;
                border-bottom: 1px solid #ddd;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton {
                background-color: #007bff;
                color: white;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 13px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QComboBox {
                padding: 5px;
                border: 1px solid #ddd;
                border-radius: 4px;
                min-width: 120px;
            }
        """)

    def save_settings(self):
        try:
            data = {
                "sector_split": self.get_table_data(self.sector_table),
                "massive_mimo": self.get_table_data(self.mimo_table)
            }
            
            with open(self.settings_file, 'w') as f:
                json.dump(data, f, indent=4)
            
            QMessageBox.information(self, "Success", "Settings saved successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving settings: {str(e)}")

    def load_settings(self):
        if not os.path.exists(self.settings_file):
            return
        
        try:
            with open(self.settings_file, 'r') as f:
                data = json.load(f)
            
            if "sector_split" in data:
                self.load_table_data(self.sector_table, data["sector_split"])
            
            if "massive_mimo" in data:
                self.load_table_data(self.mimo_table, data["massive_mimo"])
            
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Error loading previous settings: {str(e)}")

    def get_table_data(self, table):
        data = []
        for row in range(table.rowCount()):
            row_data = {}
            # Exclude the last column (delete button)
            for col in range(table.columnCount() - 1):
                header = table.horizontalHeaderItem(col).text()
                if col == table.columnCount() - 2:  # Layer column
                    combo = table.cellWidget(row, col)
                    value = combo.currentText()
                else:
                    item = table.item(row, col)
                    value = item.text() if item else ""
                row_data[header] = value
            data.append(row_data)
        return data

    def load_table_data(self, table, data):
        table.setRowCount(0)
        
        for row_data in data:
            row_position = table.rowCount()
            table.insertRow(row_position)
            
            # Add data cells (excluding delete button column)
            for col in range(table.columnCount() - 1):
                header = table.horizontalHeaderItem(col).text()
                value = row_data.get(header, "")
                
                if col == table.columnCount() - 2:  # Layer column
                    combo = QComboBox()
                    combo.addItems(self.layer_options)
                    combo.setCurrentText(value)
                    table.setCellWidget(row_position, col, combo)
                else:
                    item = QTableWidgetItem(value)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(row_position, col, item)
            
            # Add delete button
            delete_widget = DeleteButtonWidget(table, row_position)
            table.setCellWidget(row_position, table.columnCount() - 1, delete_widget)

def main():
    app = QApplication(sys.argv)
    window = ParameterSettingsWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()