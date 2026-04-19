# app/run_tab.py
# Záložka pro spouštění montáže v režimu běhu
# Umožňuje zobrazení kroků montáže v režimu projektoru na celou obrazovku
# Sleduje průběh jednotlivých kroků a zaznamenává časy spuštění/dokončení

import time
from typing import List, Dict, Optional, Set
import os
from unittest import result

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QLabel,
    QMessageBox, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QGraphicsTextItem, QGraphicsRectItem, QFrame, QDialog
)
from PyQt6.QtGui import QFont, QBrush, QColor, QPixmap, QPen
from PyQt6.QtCore import Qt, pyqtSignal

from app.api_client import ApiClient
from app.esp_controller import EspController
from app.steps_tab import BACKEND_MEDIA_ROOT
from app.config import load_app_config

WRONG_GATE_ERROR_TYPE_ID = 1

# ---------- Full-screen projection window ----------

class StepRunWindow(QWidget):
    runFinished = pyqtSignal()
    def __init__(self, api_client: ApiClient, assembly_detail: dict, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.assembly_detail = assembly_detail

        self.steps: List[Dict] = sorted(
            assembly_detail.get("steps", []),
            key=lambda s: s.get("order", 0),
        )

        self.current_execution_id: Optional[int] = None
        self.current_step_execution_id: Optional[int] = None
        self.current_step_index: int = 0
        self.finished: bool = False

        # NEW: ESP + run-state
        self.config = load_app_config()
        self.debug_run = self.config.get("debug_run", False)

        self.esp = EspController(
            port_name=self.config.get("esp_port", "COM5"),
            baudrate=self.config.get("esp_baudrate", 115200),
        )
        self.expected_sections: Set[int] = set()
        self.triggered_sections: Set[int] = set()

        # organizer mapping
        self.bin_to_section = {}

        self._connect_esp_signals()
        self._build_ui()

    def _debug(self, *args):
        if self.debug_run:
            print(*args)

    def _connect_esp_signals(self):
        self.esp.gate_triggered.connect(self._handle_gate_trigger)
        self.esp.log_message.connect(self._on_esp_log)
        self.esp.error_received.connect(self._on_esp_error)
        self.esp.connected_changed.connect(self._on_esp_connected_changed)

    def _on_esp_log(self, msg: str):
        self._debug(f"[ESP] {msg}")

    def _on_esp_error(self, msg: str):
        self._debug(f"[ESP ERROR] {msg}")

    def _on_esp_connected_changed(self, connected: bool):
        self._debug(f"[ESP CONNECTED] {connected}")



    def closeEvent(self, event):
        try:
            if self.esp:
                self.esp.clear_sections()
                time.sleep(0.1)
                self.esp.disconnect_port()
        finally:
            super().closeEvent(event)

    # ---------- UI ----------

    def _build_ui(self):
        # Frameless, projector-like window
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        # 16:9 scene
        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(0, 0, 1600, 900)
        self.scene.setBackgroundBrush(Qt.GlobalColor.transparent)

        # Black canvas rectangle (the projected area)
        self.canvas_rect = QGraphicsRectItem(self.scene.sceneRect())
        self.canvas_rect.setBrush(QBrush(QColor(0, 0, 0)))   # black
        self.canvas_rect.setPen(QPen(Qt.PenStyle.NoPen))
        self.canvas_rect.setZValue(-1000)
        self.scene.addItem(self.canvas_rect)

        # Graphics view
        self.view = QGraphicsView(self.scene, self)
        self.view.setFrameShape(QFrame.Shape.NoFrame)
        self.view.setLineWidth(0)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # No extra background, just black canvas in the middle
        self.view.setStyleSheet("")  

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

        # Optional: hide cursor for projector view
        self.setCursor(Qt.CursorShape.BlankCursor)

    
    def showEvent(self, event):
        super().showEvent(event)
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

        if not self.esp.is_connected:
            ok = self.esp.connect_port()
            print("ESP connect result:", ok)

        if self.current_execution_id is None and not self.finished and self.steps:
            self._start_new_execution()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Keep whole 16:9 canvas visible
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    # ---------- Execution control ----------

    def _start_new_execution(self):
        if not self.steps:
            return

        asm_id = self.assembly_detail["id"]
        try:
            exec_data = self.api_client.start_assembly_execution(asm_id)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", f"Cannot start assembly execution:\n{exc}")
            self.close()
            return

        self.current_execution_id = exec_data["id"]
        self.current_step_execution_id = None
        self.current_step_index = 0
        self.finished = False
        self.expected_sections = set()
        self.triggered_sections = set()

        self._start_step(self.current_step_index)

    def _start_step(self, index: int):
        if index < 0 or index >= len(self.steps):
            return

        step = self.steps[index]
        step_id = step["id"]

        try:
            step_exec = self.api_client.start_step_execution(
                self.current_execution_id,
                step_id,
            )
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", f"Cannot start step execution:\n{exc}")
            return

        self.current_step_execution_id = step_exec["id"]
        self.triggered_sections = set()

        self._show_step(step)
        self._prepare_step_guidance(step)

    def _prepare_step_guidance(self, step: Dict):
        self._load_organizer_mapping()
        self.expected_sections = self._resolve_expected_sections(step)
        self._debug("expected_sections =", sorted(self.expected_sections))
        self._push_led_state()

    def _load_organizer_mapping(self):
        slot_states = self.api_client.get_organizer_slot_states(organizer_id=1)

        self.bin_to_section = {}

        for slot in slot_states:
            if not slot.get("is_present"):
                continue
            if slot.get("is_empty"):
                continue

            bin_data = slot.get("bin")
            if not bin_data:
                continue

            bin_id = bin_data.get("id")
            position = slot.get("position")

            if bin_id and position:
                self.bin_to_section[int(bin_id)] = int(position)

        self._debug("bin_to_section =", self.bin_to_section)

    def _resolve_expected_sections(self, step: Dict) -> Set[int]:
        sections: Set[int] = set()

        for rc in step.get("required_components", []):
            preferred_bins = rc.get("preferred_bins", [])

            for bin_data in preferred_bins:
                bin_id = bin_data.get("id")
                if not bin_id:
                    continue

                section = self.bin_to_section.get(int(bin_id))
                if section:
                    sections.add(section)
                    break

        return sections

    def _push_led_state(self):
        self._debug("push_led_state, connected=", self.esp.is_connected, "sections=", sorted(self.expected_sections))
        if self.esp and self.esp.is_connected:
            self.esp.set_sections_by_numbers(sorted(self.expected_sections))
        else:
            print("ESP not connected, LED state not sent")

    def _handle_gate_trigger(self, section: int):
        self._debug(f"Triggered section: {section}")

        if self.finished:
            return

        if section in self.expected_sections:
            self.triggered_sections.add(section)

            # remove picked section from active list
            self.expected_sections.discard(section)
            self._push_led_state()

            # do NOT auto-finish step here
            # user must confirm next step manually
        else:
            self._log_wrong_gate(section)


    def _log_wrong_gate(self, section: int):
        print(f"Wrong gate triggered: {section}")

        try:
            self.api_client.create_error_log({
                "step_execution": self.current_step_execution_id,
                "error_type": WRONG_GATE_ERROR_TYPE_ID,
                "notes": f"Triggered section {section}, expected {sorted(self.expected_sections)}",
            })
        except RuntimeError as exc:
            print(f"Failed to log wrong gate: {exc}")

    def _complete_current_step(self):
        if not self.current_step_execution_id:
            return
        try:
            self.api_client.complete_step_execution(self.current_step_execution_id)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", f"Cannot complete step:\n{exc}")
            return
        self.current_step_execution_id = None

    def _complete_assembly(self):
        if not self.current_execution_id:
            return
        try:
            self.api_client.complete_assembly_execution(self.current_execution_id)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", f"Cannot complete assembly:\n{exc}")
            return
        self.finished = True

    # ---------- Rendering ----------

    def _clear_canvas(self):
        """Remove all items except the black canvas rect."""
        for item in list(self.scene.items()):
            if item is self.canvas_rect:
                continue
            self.scene.removeItem(item)

    def _show_step(self, step: Dict):
        """Draw only step_objects for the given step."""
        self._clear_canvas()

        scene_rect = self.scene.sceneRect()
        w = scene_rect.width()
        h = scene_rect.height()

        for obj in step.get("step_objects", []):
            ox = float(obj.get("position_x", 0.0))
            oy = float(obj.get("position_y", 0.0))
            ow = float(obj.get("width", 0.2))
            oh = float(obj.get("height", 0.1))
            z = int(obj.get("z_index", 0))
            obj_type = obj.get("object_type")

            x = ox * w
            y = oy * h
            width_px = ow * w
            height_px = oh * h

            if obj_type == "text":

                font_size = int(obj.get("font_size", 12))

                rect = QGraphicsRectItem(x, y, width_px, height_px)
                rect.setBrush(QBrush(QColor(0, 0, 0, 200)))  # dark box
                rect.setPen(QPen(QColor(200, 200, 200, 180)))
                rect.setZValue(z)

                text_item = QGraphicsTextItem(obj.get("text_content", ""))
                text_item.setDefaultTextColor(Qt.GlobalColor.white)
                font = QFont()
                font.setPixelSize(font_size)
                text_item.setFont(font)

                br = text_item.boundingRect()
                tx = x + (width_px - br.width()) / 2.0
                ty = y + (height_px - br.height()) / 2.0
                text_item.setPos(tx, ty)
                text_item.setZValue(z + 1)

                self.scene.addItem(rect)
                self.scene.addItem(text_item)

            elif obj_type == "image":
                image_rel = obj.get("image_path") or ""
                abs_path = os.path.join(BACKEND_MEDIA_ROOT, image_rel) if image_rel else ""
                if abs_path and os.path.isfile(abs_path):
                    pixmap = QPixmap(abs_path)
                    if not pixmap.isNull():
                        pixmap = pixmap.scaled(
                            int(width_px),
                            int(height_px),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                        item = QGraphicsPixmapItem(pixmap)
                        item.setPos(x, y)
                        item.setZValue(z)
                        self.scene.addItem(item)
                else:
                    # Fallback: gray box if image missing
                    rect = QGraphicsRectItem(x, y, width_px, height_px)
                    rect.setBrush(QBrush(QColor(80, 80, 80)))
                    rect.setPen(QPen(Qt.GlobalColor.white))
                    rect.setZValue(z)
                    self.scene.addItem(rect)

    def _show_finish_screen(self):
        """Show final minimal screen after last step."""
        self._clear_canvas()

        scene_rect = self.scene.sceneRect()
        w = scene_rect.width()
        h = scene_rect.height()

        text = QGraphicsTextItem(
            "Assembly completed.\n\n"
            "ENTER = start next assembly\n"
            "ESC   = exit run mode"
        )
        text.setDefaultTextColor(Qt.GlobalColor.white)
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        text.setFont(font)

        br = text.boundingRect()
        text.setPos((w - br.width()) / 2.0, (h - br.height()) / 2.0)
        text.setZValue(10)
        self.scene.addItem(text)

    # ---------- Keyboard ----------

    def keyPressEvent(self, event):
        key = event.key()

        # ESC = exit
        if key == Qt.Key.Key_Escape:
            self.close()
            return

        # ENTER on final screen = new execution (same assembly)
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.finished:
                self._start_new_execution()
            return

        # SPACE = next step / finish assembly
        if key == Qt.Key.Key_Space:
            if self.finished:
                # space ignored on final screen
                return

            # only allow advance when all expected gates were triggered
            if self.expected_sections:
                print(f"Cannot advance, still waiting for sections: {sorted(self.expected_sections)}")
                return

            # complete current step
            self._complete_current_step()

            # next step?
            if self.current_step_index + 1 < len(self.steps):
                self.current_step_index += 1
                self._start_step(self.current_step_index)
            else:
                # complete assembly and show finish
                self._complete_assembly()
                self.finished = True
                self.runFinished.emit()
                self.close()

            return

        # default
        super().keyPressEvent(event)


class FinishDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Assembly completed")
        self.setModal(True)
        self.setMinimumSize(500, 220)

        layout = QVBoxLayout(self)

        label = QLabel(
            "Assembly completed.\n\n"
            "ENTER = start next product\n"
            "ESC = end run"
        )
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        label.setFont(font)

        layout.addWidget(label)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accept()
            return
        if key == Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)

# ---------- Run program tab ----------

class RunProgramTab(QWidget):
    def __init__(self, api_client: ApiClient, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.assembly_types: List[Dict] = []
        self._current_run_window: Optional[StepRunWindow] = None

        self._build_ui()
        self._load_assemblies()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Operator instructions 
        help_label = QLabel(
            "Projection controls:\n"
            "• SPACE – next step\n"
            "• ENTER – start next product (after last step)\n"
            "• ESC – end run and return here"
        )
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        # Assembly selection
        row = QHBoxLayout()
        row.addWidget(QLabel("Assembly:"))
        self.combo_assembly = QComboBox()
        row.addWidget(self.combo_assembly, 1)
        self.btn_start = QPushButton("Start run")
        row.addWidget(self.btn_start)
        layout.addLayout(row)

        layout.addStretch()

        self.btn_start.clicked.connect(self._start_run)

    def _load_assemblies(self):
        try:
            self.assembly_types = self.api_client.get_assembly_types()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", f"Cannot load assemblies:\n{exc}")
            return

        self.combo_assembly.blockSignals(True)
        self.combo_assembly.clear()

        for asm in self.assembly_types:
            name = asm.get("name", "")
            version = asm.get("version") or ""
            label = f"{name} (v{version})" if version else name
            self.combo_assembly.addItem(label, asm.get("id"))

        self.combo_assembly.blockSignals(False)

    def _start_run(self):
        idx = self.combo_assembly.currentIndex()
        if idx < 0 or not self.assembly_types:
            QMessageBox.information(self, "No assembly", "Please select an assembly first.")
            return

        asm_id = self.combo_assembly.itemData(idx)
        if not asm_id:
            QMessageBox.warning(self, "Error", "Invalid assembly selected.")
            return

        # Load full assembly detail with steps + step_objects
        try:
            detail = self.api_client.get_assembly_type_detail_full(asm_id)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", f"Cannot load assembly detail:\n{exc}")
            return

        if not detail.get("steps"):
            QMessageBox.information(self, "No steps", "This assembly has no steps defined.")
            return

        run_window = StepRunWindow(self.api_client, detail, parent=self)
        self._current_run_window = run_window
        run_window.runFinished.connect(self._run_finished_flow)
        run_window.showFullScreen()

    def _run_finished_flow(self):
        dlg = FinishDialog(self)
        result = dlg.exec()

        if result == QDialog.DialogCode.Accepted:
            self._start_run()