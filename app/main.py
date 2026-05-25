# app/main.py

import sys
from PyQt6.QtWidgets import QApplication

from app.api_client import ApiClient
from app.windows.login_window import LoginWindow
from app.main_window import MainWindow
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from pathlib import Path
import sys
from app.config import load_app_config

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return str(Path(sys._MEIPASS) / relative_path)

    return str(Path(".") / relative_path)

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon("assets/Workstation_logo.ico"))

    app.setStyleSheet("""
    QWidget {
        background-color: #202124;
        color: #e8eaed;
        font-family: "Segoe UI", sans-serif;
        font-size: 10pt;
    }
    QLineEdit, QComboBox, QSpinBox, QTableWidget, QTextEdit {
        background-color: #303134;
        color: #e8eaed;
        border: 1px solid #5f6368;
        selection-background-color: #8ab4f8;
    }
    QPushButton {
        background-color: #8ab4f8;
        color: #202124;
        border: none;
        padding: 6px 14px;
        border-radius: 4px;
        font-weight: 600;
    }
    QPushButton:hover {
        background-color: #9ec1ff;
    }
    QTabWidget::pane {
        border: 1px solid #3c4043;
    }
    QTabBar::tab {
        background: #303134;
        color: #e8eaed;
        padding: 8px 14px;
    }
    QTabBar::tab:selected {
        background: #202124;
        border-bottom: 2px solid #8ab4f8;
    }
    QHeaderView::section {
        background-color: #303134;
        color: #e8eaed;
        padding: 4px;
        border: 1px solid #5f6368;
    }
    """)

    icon_path = resource_path("assets/Workstation_logo.ico")
    app.setWindowIcon(QIcon(icon_path))
    
    config = load_app_config()

    api_client = ApiClient(
        base_url=config["backend_url"].rstrip("/")
    )

    windows = {"login": None, "main": None}

    def show_login():
        # Close main window (if open) and show login
        if windows["main"] is not None:
            windows["main"].close()
            windows["main"] = None

        windows["login"] = LoginWindow(api_client, on_login_success)
        windows["login"].show()

    def on_login_success():
        # Close login and show main app with tabs
        if windows["login"] is not None:
            windows["login"].close()
            windows["login"] = None

        windows["main"] = MainWindow(api_client, on_logout=show_login)
        windows["main"].show()

    # Start at login
    show_login()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
