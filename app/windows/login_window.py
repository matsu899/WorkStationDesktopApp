# app/windows/login_window.py

from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QMessageBox,
)
from PyQt6.QtCore import Qt

from app.api_client import ApiClient


class LoginWindow(QWidget):
    """
    Login window:
    - Server URL
    - Username
    - Password
    """

    def __init__(self, api_client: ApiClient, on_login_success):
        super().__init__()

        self.api_client = api_client
        self.on_login_success = on_login_success

        self._build_ui()
        self._apply_style()

    def _build_ui(self):
        self.setWindowTitle("Workstation – Login")
        self.setFixedSize(420, 260)

        # --- Title ---
        self.label_title = QLabel("Login to Workstation")
        self.label_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # --- Inputs ---
        self.input_server = QLineEdit(self.api_client.base_url)
        self.input_username = QLineEdit()
        self.input_password = QLineEdit()

        self.input_username.setPlaceholderText("Enter username")
        self.input_password.setPlaceholderText("Enter password")
        self.input_password.setEchoMode(QLineEdit.EchoMode.Password)

        # Server label smaller / less prominent
        label_server = QLabel("Server URL:")
        label_username = QLabel("Username:")
        label_password = QLabel("Password:")

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(10)

        form_layout.addRow(label_server, self.input_server)
        form_layout.addRow(label_username, self.input_username)
        form_layout.addRow(label_password, self.input_password)

        # --- Button ---
        self.button_login = QPushButton("Login")
        self.button_login.clicked.connect(self.handle_login)
        self.input_password.returnPressed.connect(self.handle_login)
        self.input_username.returnPressed.connect(self.handle_login)

        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(self.button_login)

        # --- Main layout ---
        layout_main = QVBoxLayout()
        layout_main.setContentsMargins(30, 20, 30, 20)
        layout_main.setSpacing(16)

        layout_main.addWidget(self.label_title)
        layout_main.addSpacing(4)
        layout_main.addLayout(form_layout)
        layout_main.addStretch()
        layout_main.addLayout(button_row)

        self.setLayout(layout_main)

    def _apply_style(self):
        # Global dark style
        self.setStyleSheet("""
        QWidget {
            background-color: #202124;
            color: #e8eaed;
            font-family: "Segoe UI", sans-serif;
            font-size: 10pt;
        }
        QLabel {
            font-size: 10pt;
        }
        QLabel#titleLabel {
            font-size: 16pt;
            font-weight: 600;
        }
        QLineEdit {
            padding: 6px 8px;
            border-radius: 4px;
            border: 1px solid #5f6368;
            background-color: #303134;
            color: #e8eaed;
            selection-background-color: #8ab4f8;
        }
        QLineEdit:focus {
            border: 1px solid #8ab4f8;
        }
        QPushButton {
            padding: 6px 18px;
            border-radius: 4px;
            border: none;
            background-color: #8ab4f8;
            color: #202124;
            font-weight: 600;
        }
        QPushButton:hover {
            background-color: #9ec1ff;
        }
        QPushButton:pressed {
            background-color: #6f9df5;
        }
        QPushButton:disabled {
            background-color: #5f6368;
            color: #9aa0a6;
        }
        """)

        # Give the title a special objectName so it picks #titleLabel
        self.label_title.setObjectName("titleLabel")

    def handle_login(self):
        username = self.input_username.text().strip()
        password = self.input_password.text().strip()
        server_url = self.input_server.text().strip()

        if not self.button_login.isEnabled():
            return

        if not username or not password:
            QMessageBox.warning(self, "Missing data", "Please enter username and password.")
            return

        if server_url and server_url != self.api_client.base_url:
            self.api_client.base_url = server_url.rstrip("/")

        self.button_login.setEnabled(False)
        self.button_login.setText("Logging in...")

        try:
            ok = self.api_client.login(username, password)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", str(exc))
            self.button_login.setEnabled(True)
            self.button_login.setText("Login")
            return

        self.button_login.setEnabled(True)
        self.button_login.setText("Login")

        if not ok:
            QMessageBox.warning(self, "Login failed", "Incorrect username or password.")
        else:
            QMessageBox.information(self, "Success", "Login successful!")
            self.on_login_success()

