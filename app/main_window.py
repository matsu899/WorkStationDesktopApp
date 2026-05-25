# app/main_window.py

from PyQt6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QLabel,
    QToolBar,
    QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from app.api_client import ApiClient
from app.components_tab import ComponentsTab
from app.assemblies_tab import AssembliesTab
from app.bins_tab import BinsTab
from app.steps_tab import StepsTab
from app.run_tab import RunProgramTab
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl
from app.config import load_app_config
from PyQt6.QtGui import QIcon

class MainWindow(QMainWindow):
    """
    Main application window after login.
    Contains tabs for:
    - Components
    - Assemblies
    - Assembly steps
    - Run program (step guidance)
    - Users
    - Statistics
    """

    def __init__(self, api_client: ApiClient, on_logout):
        super().__init__()
        self.api_client = api_client
        self.on_logout = on_logout

        self.setWindowTitle("Workstation")
        self.setWindowIcon(QIcon("assets/Workstation_logo.ico"))
        self.resize(1000, 700)

        self._build_ui()

    def _build_ui(self):
        # --- Tabs ---
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        self.last_normal_tab = 0

        # Components tab
        self.tab_components = ComponentsTab(self.api_client)
        self.tabs.addTab(self.tab_components, "Components")

        # Bins tab
        self.tab_bins = BinsTab(self.api_client)
        self.tabs.addTab(self.tab_bins, "Bins")


        # Assemblies tab (AssemblyType)
        self.tab_assemblies = AssembliesTab(self.api_client)
        self.tabs.addTab(self.tab_assemblies, "Assemblies")

        # Steps tab (Assembly steps)
        self.tab_steps = StepsTab(self.api_client)
        self.tabs.addTab(self.tab_steps, "Assembly steps")

        # Run program tab
        self.tab_run = RunProgramTab(self.api_client)
        self.tabs.addTab(self.tab_run, "Run program")

        self.users_tab_index = self.tabs.addTab(QWidget(), "Users")
        self.stats_tab_index = self.tabs.addTab(QWidget(), "Statistics")

        self.tabs.currentChanged.connect(self._handle_special_tabs)

        # --- Toolbar with Logout ---
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        action_logout = QAction("Logout", self)
        action_logout.triggered.connect(self._handle_logout)

        toolbar.addAction(action_logout)

    def _handle_logout(self):
        reply = QMessageBox.question(
            self,
            "Logout",
            "Log out and return to login screen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Clear token so API calls fail until next login
            self.api_client.token = None
            self.on_logout()

    def _handle_special_tabs(self, index: int):
        config = load_app_config()

        if index == self.users_tab_index:
            QDesktopServices.openUrl(
                QUrl(f"{config['backend_url']}/admin/")
            )
            self.tabs.setCurrentIndex(self.last_normal_tab)

        elif index == self.stats_tab_index:
            QDesktopServices.openUrl(
                QUrl(config["grafana_url"])
            )
            self.tabs.setCurrentIndex(self.last_normal_tab)

        else:
            self.last_normal_tab = index