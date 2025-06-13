# responsive_ui.py
from PyQt6.QtWidgets import QApplication, QWidget, QLayout, QSizePolicy
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QFont, QScreen

class ResponsiveUI:
    # Cache for storing scaled values to improve performance
    _scale_cache = {}
    _font_cache = {}
    _size_cache = {}
    
    @staticmethod
    def clear_caches():
        """Clear all caches"""
        ResponsiveUI._scale_cache.clear()
        ResponsiveUI._font_cache.clear()
        ResponsiveUI._size_cache.clear()

    @staticmethod
    def get_screen_size():
        """Get the primary screen size with caching"""
        cache_key = 'screen_size'
        if cache_key not in ResponsiveUI._scale_cache:
            screen = QApplication.primaryScreen()
            size = screen.size()
            ResponsiveUI._scale_cache[cache_key] = (size.width(), size.height())
        return ResponsiveUI._scale_cache[cache_key]

    @staticmethod
    def get_scale_factor():
        """Get the scale factor with caching"""
        cache_key = 'scale_factor'
        if cache_key not in ResponsiveUI._scale_cache:
            width, height = ResponsiveUI.get_screen_size()
            ResponsiveUI._scale_cache[cache_key] = min(width / 1920, height / 1080)
        return ResponsiveUI._scale_cache[cache_key]

    @staticmethod
    def scale_font(base_size):
        """Scale font size with caching"""
        cache_key = f'font_{base_size}'
        if cache_key not in ResponsiveUI._font_cache:
            scale_factor = ResponsiveUI.get_scale_factor()
            ResponsiveUI._font_cache[cache_key] = max(8, int(base_size * scale_factor))
        return ResponsiveUI._font_cache[cache_key]

    @staticmethod
    def scale_size(width, height):
        """Scale widget sizes with caching"""
        cache_key = f'size_{width}_{height}'
        if cache_key not in ResponsiveUI._size_cache:
            scale_factor = ResponsiveUI.get_scale_factor()
            ResponsiveUI._size_cache[cache_key] = QSize(
                int(width * scale_factor),
                int(height * scale_factor)
            )
        return ResponsiveUI._size_cache[cache_key]

    @staticmethod
    def get_responsive_style():
        """Generate responsive styles with icon preservation"""
        scale_factor = ResponsiveUI.get_scale_factor()
        base_font_size = ResponsiveUI.scale_font(10)
        
        return f"""
            QWidget {{
                font-size: {base_font_size}pt;
            }}
            
            QPushButton {{
                padding: {int(6 * scale_factor)}px {int(12 * scale_factor)}px;
                font-size: {base_font_size}pt;
            }}
            
            QTableWidget {{
                gridline-color: #E5E7EB;
                font-size: {base_font_size}pt;
            }}
            
            QHeaderView::section {{
                padding: {int(6 * scale_factor)}px;
                font-size: {base_font_size}pt;
            }}
            
            QLabel {{
                font-size: {base_font_size}pt;
            }}
            
            QComboBox {{
                padding: {int(4 * scale_factor)}px;
                font-size: {base_font_size}pt;
            }}
            
            /* Preserve icon visibility */
            QLabel[iconLabel="true"] {{
                min-width: {int(32 * scale_factor)}px;
                min-height: {int(32 * scale_factor)}px;
            }}
            
            /* Optimize button icons */
            QPushButton[iconButton="true"] {{
                padding: {int(4 * scale_factor)}px;
            }}
        """

    @staticmethod
    def optimize_performance(widget):
        """Apply performance optimizations"""
        # Set widget attributes for better performance
        widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, False)
        
        # Optimize layout updates
        if hasattr(widget, 'layout') and widget.layout():
            layout = widget.layout()
            # Set layout size constraint
            layout.setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)
            
            # Optimize size policies
            widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

    @staticmethod
    def preserve_icons(widget):
        """Preserve icon visibility and scaling"""
        # Handle icon labels
        for label in widget.findChildren(QWidget):
            if hasattr(label, 'pixmap') and callable(getattr(label, 'pixmap')) and label.pixmap():
                label.setProperty('iconLabel', True)
                # Ensure icon scaling maintains aspect ratio
                if hasattr(label, 'setScaledContents'):
                    label.setScaledContents(True)
            elif hasattr(label, 'icon') and callable(getattr(label, 'icon')) and not label.icon().isNull():
                label.setProperty('iconButton', True)

    @staticmethod
    def make_responsive(widget):
        """Make a widget responsive with optimizations"""
        # Apply optimizations first
        ResponsiveUI.optimize_performance(widget)
        ResponsiveUI.preserve_icons(widget)
        
        # Apply responsive styles
        widget.setStyleSheet(widget.styleSheet() + ResponsiveUI.get_responsive_style())
        
        # Scale dimensions if needed
        if widget.sizeHint().isValid():
            scaled_size = ResponsiveUI.scale_size(
                widget.sizeHint().width(),
                widget.sizeHint().height()
            )
            widget.resize(scaled_size)

def initialize_responsive_ui(main_window):
    """Initialize responsive UI with optimizations"""
    # Clear caches
    ResponsiveUI.clear_caches()
    
    # Apply responsive UI
    ResponsiveUI.make_responsive(main_window)
    
    # Set initial window size
    screen = QApplication.primaryScreen()
    screen_size = screen.availableGeometry()
    
    # Calculate window size (80% of screen)
    window_width = int(screen_size.width() * 0.8)
    window_height = int(screen_size.height() * 0.8)
    main_window.resize(window_width, window_height)
    
    # Center window
    center_point = screen_size.center()
    main_window.move(
        center_point.x() - window_width // 2,
        center_point.y() - window_height // 2
    )
    
    # Optimize window attributes
    main_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    main_window.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips)
    
    # Use deferred updates for better performance
    QTimer.singleShot(0, lambda: main_window.update())