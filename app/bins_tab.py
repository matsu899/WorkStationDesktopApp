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
    def __init__(self, parent=None, title="Bin", components=None, initial_data=None):
        super().__init__(parent)
        self.setWindowTitle(title)

        self.components = components or []
        self.combo_component = QComboBox()

        self.combo_component.addItem("(empty)", None)
        for comp in self.components:
            code = comp.get("component_code") or ""
            name = comp.get("name", "")
            label = f"{code} - {name}" if code else name
            self.combo_component.addItem(label, comp.get("id"))

        if initial_data:
            comp_id = initial_data.get("component_id")
            if comp_id is not None:
                for i in range(self.combo_component.count()):
                    if self.combo_component.itemData(i) == comp_id:
                        self.combo_component.setCurrentIndex(i)
                        break

        form_layout = QFormLayout()
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
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["ID", "Bin code", "Component"])
        header = self.table.horizontalHeader()
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Bin code
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)           # Component

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
            bin_code_val = str(b.get("bin_code", "") or "")

            component = b.get("component")
            if component:
                comp_code = component.get("component_code") or ""
                comp_name = component.get("name", "")
                comp_label = f"{comp_code} - {comp_name}" if comp_code else comp_name
            else:
                comp_label = "(empty)"

            self.table.setItem(row, 0, QTableWidgetItem(id_val))
            self.table.setItem(row, 1, QTableWidgetItem(bin_code_val))
            self.table.setItem(row, 2, QTableWidgetItem(comp_label))

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
        bin_code_item = self.table.item(row, 1)

        bin_id = int(id_item.text()) if id_item and id_item.text().isdigit() else None

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
            "bin_code": bin_code_item.text() if bin_code_item else "",
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


        try:
            self.api_client.update_bin(
                bin_id=bin_data["id"],
                component_id=data["component_id"],
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

        try:
            self.api_client.create_bin(
                component_id=data["component_id"],
            )
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self.refresh_bins()
