import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from editor import Editor

app = QApplication(sys.argv)

# Apply modern stylesheet
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

QLineEdit {
    background-color: white;
    border: 1px solid #d0d4db;
    border-radius: 5px;
    padding: 8px 12px;
    font-size: 13px;
}

QLineEdit:focus {
    border: 2px solid #6b4cff;
    padding: 7px 11px;
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
}
"""

app.setStyle("Fusion")
app.setStyleSheet(stylesheet)

editor = Editor()
editor.container.show()
sys.exit(app.exec())