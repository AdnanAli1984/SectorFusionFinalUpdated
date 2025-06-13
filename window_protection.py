
import os
import pandas as pd
import numpy as np
from PyQt6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QFrame, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

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
        
        # Label
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
        
        self.setFixedSize(200, 100)

    def setLabelText(self, text):
        self.label.setText(text)

    def setValue(self, value):
        pass  # Placeholder for progress updates

    def showEvent(self, event):
        super().showEvent(event)
        if self.parent():
            parent_rect = self.parent().geometry()
            self.move(parent_rect.center() - self.rect().center())

class WindowProtection:
    @staticmethod
    def protect_method(method):
        def wrapper(self, *args, **kwargs):
            try:
                return method(self, *args, **kwargs)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                return None
        return wrapper

    @staticmethod
    def protect_load_data(method):
        def wrapper(self, *args, **kwargs):
            try:
                temp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp_result.csv')
                if not os.path.exists(temp_path):
                    return False
                self.result_df = pd.read_csv(temp_path)
                return True
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load data: {str(e)}")
                return False
        return wrapper

    @staticmethod
    def protect_analyze(method):
        def wrapper(self, *args, **kwargs):
            try:
                if getattr(self, 'is_analyzing', False):
                    QMessageBox.warning(self, "Warning", 
                                      "Analysis already in progress. Please wait.")
                    return

                if not self.load_data():
                    QMessageBox.warning(self, "Warning", 
                        "No data available. Please upload data and run calculation first.")
                    return

                setattr(self, 'is_analyzing', True)
                progress_dialog = CircularProgressDialog(self)
                progress_dialog.setLabelText("Analyzing data...")
                progress_dialog.show()

                try:
                    method(self, *args, **kwargs)
                    progress_dialog.setValue(100)
                    QMessageBox.information(self, "Success", 
                                          "Analysis completed successfully!")
                except Exception as e:
                    QMessageBox.critical(self, "Error", 
                                       f"Analysis failed: {str(e)}")
                finally:
                    setattr(self, 'is_analyzing', False)
                    progress_dialog.close()

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Analysis failed: {str(e)}")
                setattr(self, 'is_analyzing', False)
        return wrapper

    @staticmethod
    def protect_filter(method):
        def wrapper(self, *args, **kwargs):
            try:
                if not hasattr(self, 'result_df') or self.result_df is None:
                    return
                return method(self, *args, **kwargs)
            except Exception as e:
                QMessageBox.critical(self, "Error", 
                                   f"Error applying filter: {str(e)}")
        return wrapper

    @staticmethod
    def protect_threshold(method):
        def wrapper(self, value, *args, **kwargs):
            try:
                if hasattr(self, 'result_df') and self.result_df is not None:
                    setattr(self, 'threshold_distance', value)
                    return method(self, value, *args, **kwargs)
            except Exception as e:
                QMessageBox.critical(self, "Error", 
                                   f"Error updating threshold: {str(e)}")
        return wrapper

    @staticmethod
    def protect_ui_update(method):
        def wrapper(self, *args, **kwargs):
            try:
                return method(self, *args, **kwargs)
            except Exception as e:
                QMessageBox.critical(self, "Error", 
                                   f"Failed to update UI: {str(e)}")
        return wrapper

def protect_window(window_class):
    """
    Class decorator to add protection to window classes
    """
    # Add is_analyzing flag
    setattr(window_class, 'is_analyzing', False)
    
    # Protect analyze method
    if hasattr(window_class, 'analyze_data'):
        setattr(window_class, 'analyze_data', 
                WindowProtection.protect_analyze(getattr(window_class, 'analyze_data')))
    
    # Protect load_data method
    if hasattr(window_class, 'load_data'):
        setattr(window_class, 'load_data', 
                WindowProtection.protect_load_data(getattr(window_class, 'load_data')))
    
    # Protect filter method
    if hasattr(window_class, 'apply_result_filter'):
        setattr(window_class, 'apply_result_filter', 
                WindowProtection.protect_filter(getattr(window_class, 'apply_result_filter')))
    
    # Protect threshold method
    if hasattr(window_class, 'on_threshold_changed'):
        setattr(window_class, 'on_threshold_changed', 
                WindowProtection.protect_threshold(getattr(window_class, 'on_threshold_changed')))
    
    # Protect UI update methods
    for method_name in ['update_metrics', 'update_charts', 'update_table']:
        if hasattr(window_class, method_name):
            setattr(window_class, method_name, 
                    WindowProtection.protect_ui_update(getattr(window_class, method_name)))
    
    return window_class

