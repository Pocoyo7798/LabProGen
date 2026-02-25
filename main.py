import sys
import resources_rc
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from editor import Editor

# Initialize the application
app = QApplication(sys.argv)

# Application stylesheet with modern laboratory theme
stylesheet = """
QApplication {
    font-family: 'Segoe UI', 'Ubuntu', sans-serif;
}

QMainWindow, QDialog, QWidget {
    background-color: #f5f7fa;
}

QPushButton {
    background-color: #6b4cff;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 10px 16px;
    font-weight: 600;
    font-size: 13px;
    min-height: 36px;
}

QPushButton:hover {
    background-color: #7d5cff;
}

QPushButton:pressed {
    background-color: #5a3de8;
}

/* Style for zoom buttons specifically */
QPushButton#zoom_in, QPushButton#zoom_out {
    background-color: rgba(107, 76, 255, 150);
    color: white;
    border-radius: 3px;
    font-size: 14px;
    font-weight: bold;
    min-width: 24px;
    max-width: 24px;
    min-height: 24px;
    max-height: 24px;
    padding: 0px;
}

QPushButton#zoom_in:hover, QPushButton#zoom_out:hover {
    background-color: rgba(107, 76, 255, 255);
}

QPushButton#zoom_in:pressed, QPushButton#zoom_out:pressed {
    background-color: #5a3de8;
}

QLineEdit, QComboBox {
    background-color: white;
    color: #2c3e50;
    border: 1px solid #d0d4db;
    border-radius: 5px;
    padding: 8px 12px;
    font-size: 13px;
    min-height: 20px;
}

QComboBox {
    combobox-popup: 0;
}

QLineEdit:focus, QComboBox:focus {
    border: 2px solid #6b4cff;
    padding: 7px 11px;
}

/* Custom drop-down area styling */
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 30px;
    border-left: 1px solid #d0d4db;
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
    background-color: #f8f9fb;
}

QComboBox::drop-down:hover {
    background-color: #f0f2f5;
}

/* Custom arrow using the PNG resource */
QComboBox::down-arrow {
    image: url(":/icons/arrow_down.png");
    subcontrol-origin: padding;
    subcontrol-position: center;
    width: 12px;
    height: 12px;
}

QComboBox::down-arrow:on {
    image: url(":/icons/arrow_down.png");
}

/* Dropdown list styling */
QComboBox QAbstractItemView {
    background-color: white;
    color: #2c3e50;
    border: 1px solid #d0d4db;
    selection-background-color: #f0f2f5;
    selection-color: #6b4cff;
    outline: none;
}

QComboBox QAbstractItemView::item {
    min-height: 30px;
}

QFormLayout {
    spacing: 12px;
}

QLabel {
    font-weight: 500;
    color: #2c3e50;
    font-size: 13px;
}

QDialog {
    background-color: #f5f7fa;
}

QGraphicsView {
    background-color: #ffffff;
    border: 1px solid #e0e4eb;
    border-radius: 8px;
    outline: none;
}

/* Context Menu styling */
QMenu {
    background-color: #ffffff;
    color: #2c3e50;
    border: 1px solid #d0d4db;
    border-radius: 4px; 
    padding: 4px 0px; 
}

QMenu::item {
    padding: 6px 24px 6px 20px;
    background-color: transparent;
}

QMenu::item:selected {
    background-color: #f0f2f5;
    color: #6b4cff;
}

QMenu::item:disabled {
    color: #a1a8b3;
    background-color: transparent;
}

QMenu::separator {
    height: 1px;
    background: #e0e4eb;
    margin: 4px 8px;
}
"""

# Apply global application style and stylesheet
app.setStyle("Fusion")
app.setStyleSheet(stylesheet)

# Create and show the editor
editor = Editor()
editor.container.show()

# Start the event loop
sys.exit(app.exec())