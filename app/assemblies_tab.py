# app/assemblies_tab.py
# Záložka pro správu typů montáží v GUI aplikace
# Umožňuje seznam, přidávání, úpravy typů montáží a správu jejich obrázků

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
    QCheckBox,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QIcon

from app.api_client import ApiClient

# Same media root as in components_tab
BACKEND_MEDIA_ROOT = r"C:\Projects\Diplomka\WorkStationBackend\media"
ASSEMBLY_IMAGE_SUBDIR = "assemblies"


class AssemblyTypeDialog(QDialog):
    """
    Dialog pro přidávání nebo úpravu typu montáže.
    Umožňuje zadat název, verzi, popis a vybrat obrázek montáže.
    """

    def __init__(self, parent=None, title="Assembly", initial_data: Dict | None = None):
        super().__init__(parent)
        self.setWindowTitle(title)

        self.input_name = QLineEdit()
        self.input_version = QLineEdit()
        self.input_description = QLineEdit()
        self.checkbox_active = QCheckBox("Is active")
        self.input_image_path = QLineEdit()

        self.input_name.setPlaceholderText("Assembly name")
        self.input_version.setPlaceholderText("e.g. 1.0")
        self.input_description.setPlaceholderText("Optional description")
        self.input_image_path.setPlaceholderText("Path to image file (optional)")

        if initial_data:
            self.input_name.setText(initial_data.get("name", ""))
            self.input_version.setText(initial_data.get("version", "1.0"))
            self.input_description.setText(initial_data.get("description", ""))
            self.checkbox_active.setChecked(bool(initial_data.get("is_active", True)))

            image_rel = initial_data.get("image_path") or ""
            if image_rel:
                abs_path = os.path.join(BACKEND_MEDIA_ROOT, image_rel)
                self.input_image_path.setText(abs_path)
        else:
            self.checkbox_active.setChecked(True)
            self.input_version.setText("1.0")

        img_row_layout = QHBoxLayout()
        img_row_layout.addWidget(self.input_image_path)
        btn_browse = QPushButton("Browse...")
        img_row_layout.addWidget(btn_browse)
        btn_browse.clicked.connect(self._browse_image)

        form_layout = QFormLayout()
        form_layout.addRow("Name:", self.input_name)
        form_layout.addRow("Version:", self.input_version)
        form_layout.addRow("Description:", self.input_description)
        form_layout.addRow("Active:", self.checkbox_active)
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
            "name": self.input_name.text().strip(),
            "version": self.input_version.text().strip(),
            "description": self.input_description.text().strip(),
            "is_active": self.checkbox_active.isChecked(),
            "image_abs_path": self.input_image_path.text().strip(),
        }


class AssembliesTab(QWidget):
    """
    Záložka pro správu typů montáží: seznam, přidávání, úpravy.
    Zobrazuje všechny dostupné typy montáží a umožňuje jejich správu.
    """

    def __init__(self, api_client: ApiClient, parent=None):
        super().__init__(parent)
        self.api_client = api_client

        self._build_ui()
        self.refresh_assemblies()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # --- Buttons row ---
        btn_row = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh")
        self.btn_add = QPushButton("Add assembly")
        self.btn_edit = QPushButton("Edit selected")

        self.btn_refresh.clicked.connect(self.refresh_assemblies)
        self.btn_add.clicked.connect(self.add_assembly)
        self.btn_edit.clicked.connect(self.edit_selected_assembly)

        btn_row.addWidget(self.btn_refresh)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_edit)
        btn_row.addStretch()

        # --- Table ---
        # Columns: ID, Image, Name, Version, Active, Description
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Image", "Name", "Version", "Active", "Description"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Image
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)           # Name
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Version
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Active
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)           # Description

        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setIconSize(QSize(48, 48))

        self.table.itemDoubleClicked.connect(self._on_item_double_clicked)

        layout.addLayout(btn_row)
        layout.addWidget(self.table)

    def refresh_assemblies(self):
        try:
            assemblies = self.api_client.get_assembly_types()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self._populate_table(assemblies)

    def _populate_table(self, assemblies: List[Dict]):
        self.table.setRowCount(0)

        for asm in assemblies:
            row = self.table.rowCount()
            self.table.insertRow(row)

            id_val = str(asm.get("id", ""))
            name_val = str(asm.get("name", "") or "")
            version_val = str(asm.get("version", "") or "")
            desc_val = str(asm.get("description", "") or "")
            is_active = bool(asm.get("is_active", True))
            image_rel = asm.get("image_path") or ""

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

            name_item = QTableWidgetItem(name_val)
            version_item = QTableWidgetItem(version_val)
            active_item = QTableWidgetItem("Yes" if is_active else "No")
            desc_item = QTableWidgetItem(desc_val)

            if desc_val:
                name_item.setToolTip(desc_val)
                desc_item.setToolTip(desc_val)

            self.table.setItem(row, 2, name_item)
            self.table.setItem(row, 3, version_item)
            self.table.setItem(row, 4, active_item)
            self.table.setItem(row, 5, desc_item)

        if assemblies:
            self.table.resizeRowsToContents()

    # ---- Selection helpers ----

    def _get_selected_row(self) -> int:
        selection = self.table.selectionModel().selectedRows()
        if not selection:
            return -1
        return selection[0].row()

    def _get_assembly_type_data_from_row(self, row: int) -> Dict:
        if row < 0:
            return {}

        id_item = self.table.item(row, 0)
        name_item = self.table.item(row, 2)
        version_item = self.table.item(row, 3)
        active_item = self.table.item(row, 4)
        desc_item = self.table.item(row, 5)

        asm_id = int(id_item.text()) if id_item and id_item.text().isdigit() else None
        is_active = (active_item.text().lower().startswith("y")) if active_item else True
        description = desc_item.text() if desc_item else ""

        # Re-fetch from API to get correct image_path
        try:
            assemblies = self.api_client.get_assembly_types()
        except RuntimeError:
            assemblies = []

        image_rel = ""
        for asm in assemblies:
            if asm.get("id") == asm_id:
                image_rel = asm.get("image_path") or ""
                # prefer backend description
                description = asm.get("description") or description
                break

        return {
            "id": asm_id,
            "name": name_item.text() if name_item else "",
            "version": version_item.text() if version_item else "",
            "description": description,
            "is_active": is_active,
            "image_path": image_rel,
        }

    def _on_item_double_clicked(self, item):
        row = item.row()
        self._edit_assembly_at_row(row)

    def edit_selected_assembly(self):
        row = self._get_selected_row()
        if row < 0:
            QMessageBox.information(self, "No selection", "Please select an assembly first.")
            return
        self._edit_assembly_at_row(row)

    def _edit_assembly_at_row(self, row: int):
        asm_data = self._get_assembly_type_data_from_row(row)
        if not asm_data or asm_data["id"] is None:
            QMessageBox.warning(self, "Error", "Could not load assembly data.")
            return

        dlg = AssemblyTypeDialog(self, title="Edit assembly", initial_data=asm_data)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        new_data = dlg.get_data()

        if not new_data["name"]:
            QMessageBox.warning(self, "Missing data", "Name is required.")
            return

        image_abs = new_data["image_abs_path"]
        image_rel = asm_data["image_path"] or ""

        if image_abs:
            if not os.path.isfile(image_abs):
                QMessageBox.warning(self, "Image error", "Selected image file does not exist.")
            else:
                dest_dir = os.path.join(BACKEND_MEDIA_ROOT, ASSEMBLY_IMAGE_SUBDIR)
                os.makedirs(dest_dir, exist_ok=True)

                _, ext = os.path.splitext(image_abs)
                safe_name = (new_data["name"] or "assembly").replace(" ", "_")
                dest_filename = f"{safe_name}{ext}"
                dest_path = os.path.join(dest_dir, dest_filename)

                try:
                    shutil.copy2(image_abs, dest_path)
                    image_rel = f"{ASSEMBLY_IMAGE_SUBDIR}/{dest_filename}"
                except OSError as exc:
                    QMessageBox.warning(self, "Image error", f"Could not copy image:\n{exc}")

        try:
            self.api_client.update_assembly_type(
                assembly_type_id=asm_data["id"],
                name=new_data["name"],
                description=new_data["description"],
                version=new_data["version"] or "1.0",
                is_active=new_data["is_active"],
                image_path=image_rel,
            )
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self.refresh_assemblies()

    def add_assembly(self):
        dlg = AssemblyTypeDialog(self, title="Add assembly")
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        data = dlg.get_data()
        if not data["name"]:
            QMessageBox.warning(self, "Missing data", "Name is required.")
            return

        relative_image_path = ""
        if data["image_abs_path"]:
            src_path = data["image_abs_path"]

            if not os.path.isfile(src_path):
                QMessageBox.warning(self, "Image error", "Selected image file does not exist.")
            else:
                dest_dir = os.path.join(BACKEND_MEDIA_ROOT, ASSEMBLY_IMAGE_SUBDIR)
                os.makedirs(dest_dir, exist_ok=True)

                _, ext = os.path.splitext(src_path)
                safe_name = (data["name"] or "assembly").replace(" ", "_")
                dest_filename = f"{safe_name}{ext}"
                dest_path = os.path.join(dest_dir, dest_filename)

                try:
                    shutil.copy2(src_path, dest_path)
                    relative_image_path = f"{ASSEMBLY_IMAGE_SUBDIR}/{dest_filename}"
                except OSError as exc:
                    QMessageBox.warning(self, "Image error", f"Could not copy image:\n{exc}")

        try:
            self.api_client.create_assembly_type(
                name=data["name"],
                description=data["description"],
                version=data["version"] or "1.0",
                is_active=data["is_active"],
                image_path=relative_image_path,
            )
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self.refresh_assemblies()
