# app/main.py

import sys
from PyQt6.QtWidgets import QApplication

from app.api_client import ApiClient
from app.windows.login_window import LoginWindow
from app.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    api_client = ApiClient(base_url="http://127.0.0.1:8000")

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
