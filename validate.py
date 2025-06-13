import sys
import os
import uuid
import json
import base64
import hashlib
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QLineEdit, QPushButton, QLabel, 
                            QFrame, QTextEdit, QMessageBox, QErrorMessage)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt
from functions import validate_license_key, read_encrypted_license
import os

LICENSE_FILE_PATH = "License/license.bin"

class LicenseValidator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("License Key Validator")
        self.setMinimumSize(800, 600)
        
        # Create icons directory if it doesn't exist
        if not os.path.exists('icons'):
            os.makedirs('icons')
            
        # Create SVG icons
        self.create_svg_icons()
        self.setup_ui()
        self.setup_styling()
        
        # Get current MAC address
        self.mac_address = self.get_mac_address()
        self.mac_display.setText(self.mac_address)
        self.error_dialog = QErrorMessage()
        self.license_info = self.get_license_info()
        if self.license_info is not None:
            self.info_display.setPlainText(self.license_info)
    
    def closeEvent(self, event):
        try:
            self.close()
            # from main import ModernMainWindow
            # self.parent = ModernMainWindow()
            # self.parent.showMaximized()
            # super().closeEvent(event)
        except Exception as e:
            print(f"Error during close: {str(e)}")
            
    def get_mac_address(self):
        mac = uuid.getnode()
        return ':'.join(f'{(mac >> i) & 0xff:02x}' for i in range(0, 48, 8)[::-1])

    def create_svg_icons(self):
        # Copy icon
        copy_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white">
            <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
        </svg>"""
        
        # Validate icon
        validate_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white">
            <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-2 16l-4-4 1.41-1.41L10 14.17l6.59-6.59L18 9l-8 8z"/>
        </svg>"""

        # Reset icon
        reset_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white">
            <path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z"/>
        </svg>"""

        # Paste icon
        paste_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white">
            <path d="M19 2h-4.18C14.4.84 13.3 0 12 0c-1.3 0-2.4.84-2.82 2H5c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-7 0c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1zm7 18H5V4h2v3h10V4h2v16z"/>
        </svg>"""

        # Save icons to files
        icon_files = {
            'copy.svg': copy_svg,
            'validate.svg': validate_svg,
            'reset.svg': reset_svg,
            'paste.svg': paste_svg
        }
        
        for filename, content in icon_files.items():
            filepath = os.path.join('icons', filename)
            if not os.path.exists(filepath):
                with open(filepath, 'w') as f:
                    f.write(content)

    def setup_ui(self):
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # MAC Address Display Section
        mac_frame = self.create_frame()
        mac_layout = QHBoxLayout(mac_frame)
        
        mac_label = QLabel("System MAC Address:")
        self.mac_display = QLineEdit()
        self.mac_display.setReadOnly(True)
        
        copy_mac_button = QPushButton()
        copy_mac_button.setIcon(QIcon("icons/copy.svg"))
        copy_mac_button.setFixedSize(40, 40)
        copy_mac_button.setToolTip("Copy MAC Address")
        copy_mac_button.clicked.connect(self.copy_mac_address)
        
        mac_layout.addWidget(mac_label)
        mac_layout.addWidget(self.mac_display)
        mac_layout.addWidget(copy_mac_button)
        main_layout.addWidget(mac_frame)

        # License Key Input Section
        key_frame = self.create_frame()
        key_layout = QHBoxLayout(key_frame)
        
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Enter or paste license key here")
        
        paste_button = QPushButton()
        paste_button.setIcon(QIcon("icons/paste.svg"))
        paste_button.setFixedSize(40, 40)
        paste_button.setToolTip("Paste License Key")
        paste_button.clicked.connect(self.paste_key)
        
        key_layout.addWidget(self.key_input)
        key_layout.addWidget(paste_button)
        main_layout.addWidget(key_frame)

        # Buttons Section
        buttons_frame = self.create_frame()
        buttons_layout = QHBoxLayout(buttons_frame)
        
        self.validate_button = QPushButton("Validate License")
        self.validate_button.setIcon(QIcon("icons/validate.svg"))
        self.validate_button.setFixedHeight(50)
        self.validate_button.clicked.connect(self.validate_license)
        
        self.reset_button = QPushButton("Reset")
        self.reset_button.setIcon(QIcon("icons/reset.svg"))
        self.reset_button.setFixedHeight(50)
        self.reset_button.clicked.connect(self.reset_ui)
        
        buttons_layout.addWidget(self.validate_button)
        buttons_layout.addWidget(self.reset_button)
        main_layout.addWidget(buttons_frame)

        # License Information Display Section
        info_frame = self.create_frame()
        info_layout = QVBoxLayout(info_frame)
        
        info_label = QLabel("License Information:")
        self.info_display = QTextEdit()
        self.info_display.setReadOnly(True)
        self.info_display.setPlaceholderText("License information will appear here after validation")
        
        info_layout.addWidget(info_label)
        info_layout.addWidget(self.info_display)
        main_layout.addWidget(info_frame)

    def create_frame(self):
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 10px;
                border: 1px solid #e5e7eb;
            }
        """)
        return frame

    def setup_styling(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f3f4f6;
            }
            QLineEdit, QTextEdit {
                color: #374151;
                padding: 8px;
                border: 1px solid #e5e7eb;
                border-radius: 5px;
                background-color: white;
                font-size: 14px;
            }
            QPushButton {
                background-color: #2563eb;
                border-radius: 5px;
                padding: 8px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton#reset_button {
                background-color: #dc2626;
            }
            QPushButton#reset_button:hover {
                background-color: #b91c1c;
            }
            QLabel {
                font-size: 14px;
                color: #374151;
                font-weight: bold;
            }
        """)
        
        self.reset_button.setObjectName("reset_button")

    def copy_mac_address(self):
        """Copy MAC address to clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.mac_display.text())

    def paste_key(self):
        """Paste license key from clipboard"""
        clipboard = QApplication.clipboard()
        self.key_input.setText(clipboard.text())

    def reset_ui(self):
        """Reset UI to initial state"""
        self.key_input.clear()
        self.info_display.clear()
        self.info_display.setPlaceholderText("License information will appear here after validation")

    def get_license_info(self):
        try:
            data = read_encrypted_license(file_path=LICENSE_FILE_PATH)
            if isinstance(data, list) and len(data) == 0:
                return "No license information found"
            else:
                info_text = ""
                for item in data:
                    expiry_date = datetime.strptime(item["expiry_date"], "%Y-%m-%d")
                    current_date = datetime.now()
                    remaining_days = (expiry_date - current_date).days
                    if remaining_days <= 0:
                        validity = "Expired"
                        remaining_days = 0
                    else:
                        validity = "Valid"
                    categories = item["categories"]
                    category_list = []
                    site_limit = 50
                    for category in categories:
                        if isinstance(category, int):
                            site_limit = category
                        else:
                            category_list.append(category.replace("_", " "))
                        
                    text = f"""
                    License ID: {item["id"]}
                    License Status: {validity}
                    Device Address: {item["device_address"]}
                    Expiration Date: {item["expiry_date"]}
                    Days Remaining: {remaining_days}
                    Enabled Features: {", ".join(category_list)}
                    Number of allowed sites: {site_limit}"""
                    info_text = info_text+"\n"+text+"\n"
                return info_text
        except Exception as e:
            print(str(e))
            return None
    
    def validate_license(self):
        """Validate license key and save to file if valid"""
        license_key = self.key_input.text().strip()
        if not license_key:
            QMessageBox.warning(self, "Validation Error", "Please enter a license key")
            return

        try:
            status, data = validate_license_key(license_key=license_key, device_address=self.mac_address)
            if status is False:
                self.error_dialog.showMessage(message=data)
                self.reset_ui()
            else:
                info_text = ""
                for item in data:
                    categories = item["categories"]
                    category_list = []
                    site_limit = 50
                    for category in categories:
                        if isinstance(category, int):
                            site_limit = category
                        else:
                            category_list.append(category.replace("_", " "))
                        
                    text = f"""
                    License ID: {item["id"]}
                    License Status: {item["status"]}
                    Device Address: {item["device_address"]}
                    Expiration Date: {item["expiry_date"]}
                    Days Remaining: {item["remaining_days"]}
                    Enabled Features: {", ".join(category_list)}
                    Number of allowed sites: {site_limit}
                    """
                    info_text = info_text+"\n"+text+"\n"
                self.info_display.setPlainText(info_text)
            QMessageBox.information(self, "Success", "License validated and saved successfully!")
            self.close()
            from main import ModernMainWindow
            self.parent = ModernMainWindow()
            self.parent.showMaximized()
            # if self.parent():
            #     self.parent().show()

        except Exception as e:
            QMessageBox.critical(self, "Validation Error", str(e))
            self.info_display.setPlainText("License validation failed")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LicenseValidator()
    window.show()
    sys.exit(app.exec())