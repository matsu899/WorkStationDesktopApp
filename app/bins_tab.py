# app/bins_tab.py
# Záložka pro správu přihráděk (bins) - fyzických míst skladování komponent
# Umožňuje seznam, přidávání, úpravy přihráděk a přiřazení komponent k jednotlivým místům

from typing import List, Dict

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
    QComboBox,
)
from PyQt6.QtCore import Qt

from app.api_client import ApiClient


class BinDialog(QDialog):
    """
    Dialog pro přidávání nebo úpravu přihrádk y.
    Umožňuje uživateli vybrat komponentu ze seznamu nebo ponechat přihrádku prázdnou.
    """

    def __init__(self, parent=None, title="Bin", components: List[Dict] | None = None, initial_data: Dict | None = None):
        super().__init__(parent)
        self.setWindowTitle(title)

        self.components = components or []

        self.input_box_code = QLineEdit()
        self.input_location = QLineEdit()
        self.combo_component = QComboBox()

        self.input_box_code.setPlaceholderText("Unique bin code, e.g. BIN-01")
        self.input_location.setPlaceholderText("Location, e.g. Shelf A1")

        # First item = empty bin
        self.combo_component.addItem("(empty)", None)
        for comp in self.components:
            code = comp.get("component_code") or ""
            name = comp.get("name", "")
            label = f"{code} - {name}" if code else name
            self.combo_component.addItem(label, comp.get("id"))

        # Prefill if editing
        if initial_data:
            self.input_box_code.setText(initial_data.get("box_code", ""))
            self.input_location.setText(initial_data.get("location", ""))

            comp_id = initial_data.get("component_id")
            if comp_id is not None:
                for i in range(self.combo_component.count()):
                    if self.combo_component.itemData(i) == comp_id:
                        self.combo_component.setCurrentIndex(i)
                        break

        form_layout = QFormLayout()
        form_layout.addRow("Box code:", self.input_box_code)
        form_layout.addRow("Location:", self.input_location)
        form_layout.addRow("Component:", self.combo_component)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(buttons)

    def get_data(self) -> Dict:
        return {
            "box_code": self.input_box_code.text().strip(),
            "location": self.input_location.text().strip(),
            "component_id": self.combo_component.currentData(),  
        }


class BinsTab(QWidget):
    """
    Záložka pro správu přihráděk: seznam, přidávání, úpravy.
    Spravuje fyzická místa skladování a jejich obsah.
    """

    def __init__(self, api_client: ApiClient, parent=None):
        super().__init__(parent)
        self.api_client = api_client

        self._build_ui()
        self.refresh_bins()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # --- Buttons row ---
        btn_row = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh")
        self.btn_add = QPushButton("Add bin")
        self.btn_edit = QPushButton("Edit selected")

        self.btn_refresh.clicked.connect(self.refresh_bins)
        self.btn_add.clicked.connect(self.add_bin)
        self.btn_edit.clicked.connect(self.edit_selected_bin)

        btn_row.addWidget(self.btn_refresh)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_edit)
        btn_row.addStretch()

        # --- Table ---
        # Columns: ID, Box code, Component, Location
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["ID", "Box code", "Component", "Location"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Box code
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)           # Component
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)           # Location

        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self.table.itemDoubleClicked.connect(self._on_item_double_clicked)

        layout.addLayout(btn_row)
        layout.addWidget(self.table)

    def refresh_bins(self):
        try:
            bins = self.api_client.get_bins()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self._populate_table(bins)

    def _populate_table(self, bins: List[Dict]):
        self.table.setRowCount(0)

        for b in bins:
            row = self.table.rowCount()
            self.table.insertRow(row)

            id_val = str(b.get("id", ""))
            box_code_val = str(b.get("box_code", "") or "")
            component = b.get("component")
            if component:
                comp_code = component.get("component_code") or ""
                comp_name = component.get("name", "")
                comp_label = f"{comp_code} - {comp_name}" if comp_code else comp_name
            else:
                comp_label = "(empty)"
            location_val = str(b.get("location", "") or "")

            self.table.setItem(row, 0, QTableWidgetItem(id_val))
            self.table.setItem(row, 1, QTableWidgetItem(box_code_val))

            comp_item = QTableWidgetItem(comp_label)
            self.table.setItem(row, 2, comp_item)

            loc_item = QTableWidgetItem(location_val)
            self.table.setItem(row, 3, loc_item)

        if bins:
            self.table.resizeRowsToContents()

    # ---- Helpers for selection / editing ----

    def _get_selected_row(self) -> int:
        selection = self.table.selectionModel().selectedRows()
        if not selection:
            return -1
        return selection[0].row()

    def _get_bin_data_from_row(self, row: int) -> Dict:
        if row < 0:
            return {}

        id_item = self.table.item(row, 0)
        box_code_item = self.table.item(row, 1)
        loc_item = self.table.item(row, 3)

        bin_id = int(id_item.text()) if id_item and id_item.text().isdigit() else None

        # Get full bin from API (to know current component_id)
        try:
            bins = self.api_client.get_bins()
        except RuntimeError:
            bins = []

        component_id = None
        for b in bins:
            if b.get("id") == bin_id:
                comp = b.get("component")
                if comp:
                    component_id = comp.get("id")
                break

        return {
            "id": bin_id,
            "box_code": box_code_item.text() if box_code_item else "",
            "location": loc_item.text() if loc_item else "",
            "component_id": component_id,
        }

    def _on_item_double_clicked(self, item):
        row = item.row()
        self._edit_bin_at_row(row)

    def edit_selected_bin(self):
        row = self._get_selected_row()
        if row < 0:
            QMessageBox.information(self, "No selection", "Please select a bin first.")
            return
        self._edit_bin_at_row(row)

    def _edit_bin_at_row(self, row: int):
        bin_data = self._get_bin_data_from_row(row)
        if not bin_data or bin_data["id"] is None:
            QMessageBox.warning(self, "Error", "Could not load bin data.")
            return

        # Load components for dropdown
        try:
            components = self.api_client.get_components()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", f"Cannot load components:\n{exc}")
            return

        dlg = BinDialog(
            self,
            title="Edit bin",
            components=components,
            initial_data=bin_data,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        data = dlg.get_data()
        if not data["box_code"]:
            QMessageBox.warning(self, "Missing data", "Box code is required.")
            return

        try:
            self.api_client.update_bin(
                bin_id=bin_data["id"],
                box_code=data["box_code"],
                component_id=data["component_id"],
                location=data["location"],
            )
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self.refresh_bins()

    def add_bin(self):
        # Load components for dropdown
        try:
            components = self.api_client.get_components()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", f"Cannot load components:\n{exc}")
            return

        dlg = BinDialog(self, title="Add bin", components=components)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        data = dlg.get_data()
        if not data["box_code"]:
            QMessageBox.warning(self, "Missing data", "Box code is required.")
            return

        try:
            self.api_client.create_bin(
                box_code=data["box_code"],
                component_id=data["component_id"],
                location=data["location"],
            )
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self.refresh_bins()
