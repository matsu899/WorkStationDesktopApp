# app/components_tab.py

from typing import List, Dict
import os
import shutil

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QDialog,
    QFormLayout,
    QLineEdit,
    QDialogButtonBox,
    QMessageBox,
    QFileDialog,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QIcon

from app.api_client import ApiClient

# Adjust to your paths
BACKEND_MEDIA_ROOT = r"C:\Projects\Diplomka\WorkStationBackend\media"
COMPONENT_IMAGE_SUBDIR = "components"


class ComponentDialog(QDialog):
    """
    Dialog used both for adding and editing a component.
    If initial_data is provided, fields are pre-filled.
    """

    def __init__(self, parent=None, title="Component", initial_data: Dict | None = None):
        super().__init__(parent)
        self.setWindowTitle(title)

        self.input_code = QLineEdit()
        self.input_name = QLineEdit()
        self.input_unit = QLineEdit()
        self.input_description = QLineEdit()
        self.input_image_path = QLineEdit()

        # Text inside inputs
        self.input_code.setPlaceholderText("e.g. C001")
        self.input_name.setPlaceholderText("Component name")
        self.input_unit.setPlaceholderText("e.g. pcs, kg, 250, ...")
        self.input_description.setPlaceholderText("Optional description")
        self.input_image_path.setPlaceholderText("Path to image file (optional)")

        # Prefill if editing
        if initial_data:
            self.input_code.setText(initial_data.get("component_code", ""))
            self.input_name.setText(initial_data.get("name", ""))
            self.input_unit.setText(initial_data.get("unit", ""))
            self.input_description.setText(initial_data.get("description", ""))

            image_rel = initial_data.get("image_path") or ""
            if image_rel:
                abs_path = os.path.join(BACKEND_MEDIA_ROOT, image_rel)
                self.input_image_path.setText(abs_path)

        img_row_layout = QHBoxLayout()
        img_row_layout.addWidget(self.input_image_path)
        btn_browse = QPushButton("Browse...")
        img_row_layout.addWidget(btn_browse)
        btn_browse.clicked.connect(self._browse_image)

        form_layout = QFormLayout()
        form_layout.addRow("Component code:", self.input_code)
        form_layout.addRow("Name:", self.input_name)
        form_layout.addRow("Unit:", self.input_unit)
        form_layout.addRow("Description:", self.input_description)
        form_layout.addRow("Image:", img_row_layout)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(buttons)

    def _browse_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All files (*)",
        )
        if file_path:
            self.input_image_path.setText(file_path)

    def get_data(self) -> Dict[str, str]:
        return {
            "component_code": self.input_code.text().strip(),
            "name": self.input_name.text().strip(),
            "unit": self.input_unit.text().strip(),
            "description": self.input_description.text().strip(),
            "image_abs_path": self.input_image_path.text().strip(),  # absolute path (if any)
        }


class ComponentsTab(QWidget):
    def __init__(self, api_client: ApiClient, parent=None):
        super().__init__(parent)
        self.api_client = api_client

        self._build_ui()
        self.refresh_components()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # --- Buttons row ---
        btn_row = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh")
        self.btn_add = QPushButton("Add component")
        self.btn_edit = QPushButton("Edit selected")

        self.btn_refresh.clicked.connect(self.refresh_components)
        self.btn_add.clicked.connect(self.add_component)
        self.btn_edit.clicked.connect(self.edit_selected_component)

        btn_row.addWidget(self.btn_refresh)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_edit)
        btn_row.addStretch()

        # --- Table ---
        # 6 columns: ID, Image, Code, Name, Unit, Description
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "Image", "Code", "Name", "Unit", "Description"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Image
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Code
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)           # Name
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Unit
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)           # Description

        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setIconSize(QSize(48, 48))

        # Double-click to edit
        self.table.itemDoubleClicked.connect(self._on_item_double_clicked)

        layout.addLayout(btn_row)
        layout.addWidget(self.table)

    def refresh_components(self):
        try:
            components = self.api_client.get_components()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self._populate_table(components)

    def _populate_table(self, components: List[Dict]):
        self.table.setRowCount(0)

        for comp in components:
            row = self.table.rowCount()
            self.table.insertRow(row)

            id_val = str(comp.get("id", ""))
            code_val = str(comp.get("component_code", "") or "")
            name_val = str(comp.get("name", "") or "")
            unit_val = str(comp.get("unit", "") or "")
            desc_val = str(comp.get("description", "") or "")
            image_rel = comp.get("image_path") or ""

            # ID
            self.table.setItem(row, 0, QTableWidgetItem(id_val))

            # Image
            image_item = QTableWidgetItem()
            if image_rel:
                abs_path = os.path.join(BACKEND_MEDIA_ROOT, image_rel)
                pixmap = QPixmap(abs_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        48,
                        48,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    image_item.setIcon(QIcon(scaled))
            self.table.setItem(row, 1, image_item)

            # Code, Name, Unit, Description
            code_item = QTableWidgetItem(code_val)
            name_item = QTableWidgetItem(name_val)
            unit_item = QTableWidgetItem(unit_val)
            desc_item = QTableWidgetItem(desc_val)

            # Show description 
            if desc_val:
                for it in (name_item, desc_item):
                    it.setToolTip(desc_val)

            self.table.setItem(row, 2, code_item)
            self.table.setItem(row, 3, name_item)
            self.table.setItem(row, 4, unit_item)
            self.table.setItem(row, 5, desc_item)

        if components:
            self.table.resizeRowsToContents()

    # ---- Helpers for selection / editing ----

    def _get_selected_row(self) -> int:
        selection = self.table.selectionModel().selectedRows()
        if not selection:
            return -1
        return selection[0].row()

    def _get_component_data_from_row(self, row: int) -> Dict:
        if row < 0:
            return {}

        id_item = self.table.item(row, 0)
        code_item = self.table.item(row, 2)
        name_item = self.table.item(row, 3)
        unit_item = self.table.item(row, 4)
        desc_item = self.table.item(row, 5)

        comp_id = int(id_item.text()) if id_item and id_item.text().isdigit() else None


        try:
            components = self.api_client.get_components()
        except RuntimeError:
            components = []

        image_rel = ""
        for comp in components:
            if comp.get("id") == comp_id:
                image_rel = comp.get("image_path") or ""
                description = comp.get("description") or ""
                # override desc_item text with real description in case of mismatch
                desc_text = description
                break
        else:
            desc_text = desc_item.text() if desc_item else ""

        return {
            "id": comp_id,
            "component_code": code_item.text() if code_item else "",
            "name": name_item.text() if name_item else "",
            "unit": unit_item.text() if unit_item else "",
            "description": desc_text,
            "image_path": image_rel,
        }

    def _on_item_double_clicked(self, item):
        row = item.row()
        self._edit_component_at_row(row)

    def edit_selected_component(self):
        row = self._get_selected_row()
        if row < 0:
            QMessageBox.information(self, "No selection", "Please select a component first.")
            return
        self._edit_component_at_row(row)

    def _edit_component_at_row(self, row: int):
        comp_data = self._get_component_data_from_row(row)
        if not comp_data or comp_data["id"] is None:
            QMessageBox.warning(self, "Error", "Could not load component data.")
            return

        dlg = ComponentDialog(self, title="Edit component", initial_data=comp_data)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        new_data = dlg.get_data()

        if not new_data["component_code"] or not new_data["name"]:
            QMessageBox.warning(self, "Missing data", "Code and Name are required.")
            return

        if not new_data["unit"]:
            QMessageBox.warning(self, "Missing data", "Unit is required.")
            return

        # Handle image
        image_abs = new_data["image_abs_path"]
        image_rel = comp_data["image_path"] or ""

        if image_abs:
            if not os.path.isfile(image_abs):
                QMessageBox.warning(self, "Image error", "Selected image file does not exist.")
            else:
                dest_dir = os.path.join(BACKEND_MEDIA_ROOT, COMPONENT_IMAGE_SUBDIR)
                os.makedirs(dest_dir, exist_ok=True)

                _, ext = os.path.splitext(image_abs)
                safe_code = new_data["component_code"] or "component"
                dest_filename = f"{safe_code}{ext}"
                dest_path = os.path.join(dest_dir, dest_filename)

                try:
                    shutil.copy2(image_abs, dest_path)
                    image_rel = f"{COMPONENT_IMAGE_SUBDIR}/{dest_filename}"
                except OSError as exc:
                    QMessageBox.warning(self, "Image error", f"Could not copy image:\n{exc}")

        try:
            self.api_client.update_component(
                component_id=comp_data["id"],
                component_code=new_data["component_code"],
                name=new_data["name"],
                unit=new_data["unit"],
                description=new_data["description"],
                image_path=image_rel,
            )
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self.refresh_components()

    # ---- Add new component ----

    def add_component(self):
        dlg = ComponentDialog(self, title="Add component")
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        data = dlg.get_data()
        if not data["component_code"] or not data["name"]:
            QMessageBox.warning(self, "Missing data", "Code and Name are required.")
            return

        if not data["unit"]:
            QMessageBox.warning(self, "Missing data", "Unit is required.")
            return

        
        relative_image_path = ""
        if data["image_abs_path"]:
            src_path = data["image_abs_path"]

            if not os.path.isfile(src_path):
                QMessageBox.warning(self, "Image error", "Selected image file does not exist.")
            else:
                dest_dir = os.path.join(BACKEND_MEDIA_ROOT, COMPONENT_IMAGE_SUBDIR)
                os.makedirs(dest_dir, exist_ok=True)

                _, ext = os.path.splitext(src_path)
                safe_code = data["component_code"] or "component"
                dest_filename = f"{safe_code}{ext}"
                dest_path = os.path.join(dest_dir, dest_filename)

                try:
                    shutil.copy2(src_path, dest_path)
                    relative_image_path = f"{COMPONENT_IMAGE_SUBDIR}/{dest_filename}"
                except OSError as exc:
                    QMessageBox.warning(self, "Image error", f"Could not copy image:\n{exc}")

        try:
            self.api_client.create_component(
                component_code=data["component_code"],
                name=data["name"],
                unit=data["unit"],
                description=data["description"],
                image_path=relative_image_path,
            )
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self.refresh_components()
