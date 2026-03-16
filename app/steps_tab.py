# app/steps_tab.py
# Záložka pro správu kroků montáže a jejich vizuálních prvků
# Umožňuje definovat kroky montáže, přidávat do nich textové a grafické objekty
# Obsahuje editor pro umísťování prvků na kreslicí plátno pro jednotlivé kroky

from typing import List, Dict, Optional
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
    QComboBox,
    QLabel,
    QSpinBox,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsRectItem,
    QFileDialog,
    QGroupBox,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QFrame,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QSizeF, QRectF
from PyQt6.QtGui import QPixmap, QBrush, QPen, QColor, QFont, QIcon, QTransform, QPainterPath

from app.api_client import ApiClient

BACKEND_MEDIA_ROOT = r"C:\Projects\Diplomka\WorkStationBackend\media"
STEP_OBJECTS_SUBDIR = "step_objects"


# ---------- Custom scene to handle clicks for adding objects ----------

class StepScene(QGraphicsScene):
    # Vlastní scéna pro kreslení kroků montáže
    # Umožňuje zachycování kliknutí na plátno pro přidávání nových objektů
    # Emituje signál s normalizovanými souřadnicemi (0..1) místa kliknutí
    canvasClicked = pyqtSignal(float, float)  # normalized x, y in [0..1]

    def __init__(self, width: int = 800, height: int = 600, parent=None):
        super().__init__(parent)
        self.setSceneRect(0, 0, width, height)

    def mousePressEvent(self, event):
        pos = event.scenePos()
        # normalize to 0..1
        w = self.width() or 1.0
        h = self.height() or 1.0
        x_norm = pos.x() / w
        y_norm = pos.y() / h
        self.canvasClicked.emit(x_norm, y_norm)
        super().mousePressEvent(event)


# ---------- Small dialogs ----------

class StepDialog(QDialog):
    """Dialog pro přidávání nebo úpravu kroku montáže (AssemblyStep)."""

    def __init__(self, parent=None, title="Step", initial_data: Optional[Dict] = None):
        super().__init__(parent)
        self.setWindowTitle(title)

        self.input_order = QSpinBox()
        self.input_order.setMinimum(1)
        self.input_title = QLineEdit()
        self.input_description = QLineEdit()

        self.input_title.setPlaceholderText("Step title")
        self.input_description.setPlaceholderText("Optional description")

        if initial_data:
            self.input_order.setValue(initial_data.get("order", 1))
            self.input_title.setText(initial_data.get("title", ""))
            self.input_description.setText(initial_data.get("description", ""))
        else:
            self.input_order.setValue(1)

        form_layout = QFormLayout()
        form_layout.addRow("Order:", self.input_order)
        form_layout.addRow("Title:", self.input_title)
        form_layout.addRow("Description:", self.input_description)

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
            "order": int(self.input_order.value()),
            "title": self.input_title.text().strip(),
            "description": self.input_description.text().strip(),
        }



class TextObjectDialog(QDialog):
    """Dialog to create/edit a text StepObject."""

    def __init__(self, parent=None, initial_text: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Text object")

        self.input_text = QLineEdit()
        self.input_text.setText(initial_text)
        self.input_text.setPlaceholderText("Text to display")

        form_layout = QFormLayout()
        form_layout.addRow("Text:", self.input_text)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(buttons)

    def get_text(self) -> str:
        return self.input_text.text().strip()


class RequiredComponentDialog(QDialog):
    """Dialog for adding/editing StepRequiredComponent."""

    def __init__(
        self,
        parent=None,
        components: List[Dict] = None,
        bins: List[Dict] = None,
        title="Required component",
        initial_data: Optional[Dict] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)

        components = components or []
        bins = bins or []

        self.combo_component = QComboBox()
        self.combo_bin = QComboBox()
        self.spin_quantity = QSpinBox()
        self.spin_quantity.setMinimum(1)

        self.combo_component.addItem("Select component...", None)
        for c in components:
            code = c.get("component_code") or ""
            name = c.get("name", "")
            label = f"{code} - {name}" if code else name
            self.combo_component.addItem(label, c.get("id"))

        self.combo_bin.addItem("(no bin)", None)
        for b in bins:
            bin_code = b.get("bin_code", "")
            comp = b.get("component")
            if comp:
                comp_code = comp.get("component_code") or ""
                comp_name = comp.get("name", "")
                comp_label = f"{comp_code} - {comp_name}" if comp_code else comp_name
                label = f"{bin_code} ({comp_label})" if bin_code else comp_label
            else:
                label = bin_code or f"Bin {b.get('id')}"
            self.combo_bin.addItem(label, b.get("id"))

        if initial_data:
            # preselect component
            comp_id = initial_data.get("component_id")
            preferred_bins = initial_data.get("preferred_bins") or []
            bin_id = preferred_bins[0].get("id") if preferred_bins else None
            qty = initial_data.get("quantity", 1)
            self.spin_quantity.setValue(qty)

            if comp_id is not None:
                for i in range(self.combo_component.count()):
                    if self.combo_component.itemData(i) == comp_id:
                        self.combo_component.setCurrentIndex(i)
                        break

            if bin_id is not None:
                for i in range(self.combo_bin.count()):
                    if self.combo_bin.itemData(i) == bin_id:
                        self.combo_bin.setCurrentIndex(i)
                        break

        form_layout = QFormLayout()
        form_layout.addRow("Component:", self.combo_component)
        form_layout.addRow("Bin:", self.combo_bin)
        form_layout.addRow("Quantity:", self.spin_quantity)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(buttons)

    def get_data(self) -> Dict:
        selected_bin = self.combo_bin.currentData()
        return {
            "component_id": self.combo_component.currentData(),
            "preferred_bin_ids": [selected_bin] if selected_bin is not None else [],
            "quantity": int(self.spin_quantity.value()),
        }


class ResizableRectItem(QGraphicsRectItem):
    HANDLE_SIZE = 30.0  # bigger = easier to grab

    def __init__(self, x, y, w, h, *args, **kwargs):
        # rect is in LOCAL coordinates (0,0,w,h)
        super().__init__(0, 0, w, h, *args, **kwargs)

        # position is in SCENE coordinates
        self.setPos(x, y)

        self._resizing = False
        self._resize_start_pos = QPointF()
        self._original_rect = self.rect()
        self.setAcceptHoverEvents(True)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

    def _clamp_to_scene(self):
        """Clamp the item to stay within scene bounds."""
        scene_rect = self.scene().sceneRect() if self.scene() else None
        if not scene_rect:
            return
        
        pos = self.pos()
        r = self.rect()
        
        # Clamp position
        new_x = max(0, min(pos.x(), scene_rect.width() - r.width()))
        new_y = max(0, min(pos.y(), scene_rect.height() - r.height()))
        
        if new_x != pos.x() or new_y != pos.y():
            self.setPos(new_x, new_y)

    def _recenter_text_children(self):
        """Recenter all text children in the rect."""
        r = self.rect()  # local rect (0..w, 0..h)
        for child in self.childItems():
            if isinstance(child, QGraphicsTextItem):
                padding = 8
                text_width = max(10.0, r.width() - 2 * padding)

                child.setTextWidth(text_width)
                child.document().setTextWidth(text_width)

                br = child.boundingRect()

                x = (r.width() - br.width()) / 2.0
                y = (r.height() - br.height()) / 2.0

                child.setPos(x, y)


    def mousePressEvent(self, event):
        r = self.rect()
        pos = event.pos()
        in_x = (r.right() - self.HANDLE_SIZE) <= pos.x() <= r.right()
        in_y = (r.bottom() - self.HANDLE_SIZE) <= pos.y() <= r.bottom()
        if in_x and in_y:
            self._resizing = True
            self._resize_start_pos = pos
            self._original_rect = QRectF(r)
            event.accept()
        else:
            self._resizing = False
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            delta = event.pos() - self._resize_start_pos
            new_w = max(40.0, self._original_rect.width() + delta.x())
            new_h = max(30.0, self._original_rect.height() + delta.y())

            new_rect = QRectF(self._original_rect.topLeft(), QSizeF(new_w, new_h))
            self.setRect(new_rect)

            # recenter text children
            self._recenter_text_children()

            self.update()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        self._resizing = False
        self._clamp_to_scene()
        super().mouseReleaseEvent(event)

    def hoverMoveEvent(self, event):
        r = self.rect()
        pos = event.pos()
        in_x = (r.right() - self.HANDLE_SIZE) <= pos.x() <= r.right()
        in_y = (r.bottom() - self.HANDLE_SIZE) <= pos.y() <= r.bottom()
        if in_x and in_y:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            new_pos = value
            scene_rect = self.scene().sceneRect()
            r = self.rect()

            x = max(scene_rect.left(),
                    min(new_pos.x(), scene_rect.right() - r.width()))
            y = max(scene_rect.top(),
                    min(new_pos.y(), scene_rect.bottom() - r.height()))

            return QPointF(x, y)
        return super().itemChange(change, value)



class ResizablePixmapItem(QGraphicsPixmapItem):
    HANDLE_SIZE = 30.0

    def __init__(self, pixmap: QPixmap, *args, **kwargs):
        super().__init__(pixmap, *args, **kwargs)
        self._original_pixmap = pixmap
        self._resizing = False
        self._resize_start_pos = QPointF()
        self._original_rect = self.boundingRect()
        self.setAcceptHoverEvents(True)

        # allow moving/selecting
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
    
    def _clamp_to_scene(self):
        scene_rect = self.scene().sceneRect() if self.scene() else None
        if not scene_rect:
            return

        pos = self.pos()
        br = self.boundingRect()
        new_x = max(scene_rect.left(),
                    min(pos.x(), scene_rect.right() - br.width()))
        new_y = max(scene_rect.top(),
                    min(pos.y(), scene_rect.bottom() - br.height()))

        if new_x != pos.x() or new_y != pos.y():
            self.setPos(new_x, new_y)

    
    def shape(self):
        """Override shape to use bounding rect instead of pixmap alpha channel.
        This allows clicking on transparent areas of PNG images."""
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def mousePressEvent(self, event):
        r = self.boundingRect()
        pos = event.pos()
        in_x = (r.right() - self.HANDLE_SIZE) <= pos.x() <= r.right()
        in_y = (r.bottom() - self.HANDLE_SIZE) <= pos.y() <= r.bottom()
        if in_x and in_y:
            self._resizing = True
            self._resize_start_pos = pos
            self._original_rect = QRectF(r)
            event.accept()
        else:
            self._resizing = False
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            delta = event.pos() - self._resize_start_pos
            new_w = max(40.0, self._original_rect.width() + delta.x())
            new_h = max(40.0, self._original_rect.height() + delta.y())

            # Clamp to scene bounds
            scene_rect = self.scene().sceneRect() if self.scene() else None
            if scene_rect is not None:
                pos = self.pos()
                max_w = max(40.0, scene_rect.right() - pos.x())
                max_h = max(40.0, scene_rect.bottom() - pos.y())
                new_w = min(new_w, max_w)
                new_h = min(new_h, max_h)

            scaled = self._original_pixmap.scaled(
                int(new_w),
                int(new_h),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.setPixmap(scaled)
            self.update()
        else:
            super().mouseMoveEvent(event)



    def mouseReleaseEvent(self, event):
        self._resizing = False
        self._clamp_to_scene()
        super().mouseReleaseEvent(event)

    def hoverMoveEvent(self, event):
        r = self.boundingRect()
        pos = event.pos()
        in_x = (r.right() - self.HANDLE_SIZE) <= pos.x() <= r.right()
        in_y = (r.bottom() - self.HANDLE_SIZE) <= pos.y() <= r.bottom()
        if in_x and in_y:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            new_pos = value
            scene_rect = self.scene().sceneRect()
            br = self.boundingRect()

            x = max(scene_rect.left(),
                    min(new_pos.x(), scene_rect.right() - br.width()))
            y = max(scene_rect.top(),
                    min(new_pos.y(), scene_rect.bottom() - br.height()))

            return QPointF(x, y)
        return super().itemChange(change, value)



# ---------- Main Step Editor Tab ----------

class StepsTab(QWidget):
    """
    Step editor:
    LEFT  = assembly + steps list
    CENTER = canvas (StepObjects)
    RIGHT = required components for selected step
    """

    def __init__(self, api_client: ApiClient, parent=None):
        super().__init__(parent)
        self.api_client = api_client

        self.assembly_types: List[Dict] = []
        self.current_assembly_detail: Optional[Dict] = None
        self.current_step: Optional[Dict] = None  # Selected step dict

        self._pending_add_mode: Optional[str] = None  # "text" or "image"

        self._build_ui()
        self._load_assemblies()

    # ---------- UI build ----------

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        left_panel = QVBoxLayout()
        asm_row = QHBoxLayout()
        asm_row.addWidget(QLabel("Assembly:"))
        self.combo_assembly = QComboBox()
        self.btn_reload_asm = QPushButton("Reload")
        asm_row.addWidget(self.combo_assembly, 1)
        asm_row.addWidget(self.btn_reload_asm)

        self.combo_assembly.currentIndexChanged.connect(self._on_assembly_changed)
        self.btn_reload_asm.clicked.connect(self._load_assemblies)

        self.table_steps = QTableWidget(0, 3)
        self.table_steps.setHorizontalHeaderLabels(["ID", "Order", "Title"])
        header = self.table_steps.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_steps.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_steps.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_steps.itemDoubleClicked.connect(self._on_step_double_clicked)

        step_btn_row = QHBoxLayout()
        self.btn_add_step = QPushButton("Add step")
        self.btn_edit_step = QPushButton("Edit step")
        self.btn_delete_step = QPushButton("Delete step")
        step_btn_row.addWidget(self.btn_add_step)
        step_btn_row.addWidget(self.btn_edit_step)
        step_btn_row.addWidget(self.btn_delete_step)

        self.btn_add_step.clicked.connect(self.add_step)
        self.btn_edit_step.clicked.connect(self.edit_selected_step)
        self.btn_delete_step.clicked.connect(self.delete_selected_step)

        left_panel.addLayout(asm_row)
        left_panel.addWidget(self.table_steps)
        left_panel.addLayout(step_btn_row)

        # CENTER: canvas toolbar + graphics view
        center_panel = QVBoxLayout()
        canvas_toolbar = QHBoxLayout()
        self.btn_add_text_obj = QPushButton("Add text")
        self.btn_add_image_obj = QPushButton("Add image")
        self.btn_delete_obj = QPushButton("Delete selected")
        self.btn_save_layout = QPushButton("Save layout")

        canvas_toolbar.addWidget(QLabel("Font size (px):"))
        self.spin_font_size = QSpinBox()
        self.spin_font_size.setMinimum(6)
        self.spin_font_size.setMaximum(72)
        self.spin_font_size.setValue(10)
        self.spin_font_size.setMaximumWidth(80)
        canvas_toolbar.addWidget(self.spin_font_size)

        canvas_toolbar.addWidget(self.btn_add_text_obj)
        canvas_toolbar.addWidget(self.btn_add_image_obj)
        canvas_toolbar.addWidget(self.btn_delete_obj)
        canvas_toolbar.addWidget(self.btn_save_layout)
        canvas_toolbar.addStretch()

        # One 16:9 scene, with explicit canvas rect
        self.scene = StepScene(1600, 900)
        self.scene.setSceneRect(0, 0, 1600, 900)
        self.scene.setBackgroundBrush(Qt.GlobalColor.transparent)

        # Black 16:9 canvas *inside* the scene
        self.canvas_rect = QGraphicsRectItem(self.scene.sceneRect())
        self.canvas_rect.setBrush(QBrush(QColor(0, 0, 0)))      # black fill
        self.canvas_rect.setPen(QPen(Qt.PenStyle.NoPen))        # no border
        self.canvas_rect.setZValue(-1000)
        self.scene.addItem(self.canvas_rect)

        self.view = QGraphicsView(self.scene)
        self.view.setFrameShape(QFrame.Shape.NoFrame)
        self.view.setLineWidth(0)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setAlignment(Qt.AlignmentFlag.AlignCenter)

        
        self.view.setSizePolicy(QSizePolicy.Policy.Expanding,
                                QSizePolicy.Policy.Expanding)

        center_panel.addLayout(canvas_toolbar)
        center_panel.addWidget(self.view)


        # transparent background, no frame/border
        self.view.setBackgroundBrush(Qt.GlobalColor.transparent)
        self.view.setFrameShape(QFrame.Shape.NoFrame)
        self.view.setLineWidth(0)
        self.view.setStyleSheet("background: transparent; border: none;")

        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)




        self.view.setDragMode(QGraphicsView.DragMode.NoDrag)

        self.scene.canvasClicked.connect(self._on_canvas_clicked)
        self.btn_add_text_obj.clicked.connect(self._start_add_text_object)
        self.btn_add_image_obj.clicked.connect(self._start_add_image_object)
        self.btn_delete_obj.clicked.connect(self._delete_selected_object)
        self.spin_font_size.valueChanged.connect(self._on_font_size_changed)
        self.btn_save_layout.clicked.connect(self._save_layout_changes)

        center_panel.addLayout(canvas_toolbar)
        center_panel.addWidget(self.view)

        # RIGHT: required components
        right_panel = QVBoxLayout()

        rc_group = QGroupBox("Required components for step")
        rc_layout = QVBoxLayout(rc_group)

        self.table_required = QTableWidget(0, 4)
        self.table_required.setHorizontalHeaderLabels(["ID", "Component", "Bin", "Qty"])
        rh = self.table_required.horizontalHeader()
        rh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        rh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        rh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        rh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_required.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_required.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        rc_btn_row = QHBoxLayout()
        self.btn_add_required = QPushButton("Add")
        self.btn_edit_required = QPushButton("Edit")
        self.btn_delete_required = QPushButton("Delete")
        rc_btn_row.addWidget(self.btn_add_required)
        rc_btn_row.addWidget(self.btn_edit_required)
        rc_btn_row.addWidget(self.btn_delete_required)

        self.btn_add_required.clicked.connect(self.add_required_component)
        self.btn_edit_required.clicked.connect(self.edit_selected_required_component)
        self.btn_delete_required.clicked.connect(self.delete_selected_required_component)

        rc_layout.addWidget(self.table_required)
        rc_layout.addLayout(rc_btn_row)

        right_panel.addWidget(rc_group)
        right_panel.addStretch()

        main_layout.addLayout(left_panel, 2)
        main_layout.addLayout(center_panel, 6)
        main_layout.addLayout(right_panel, 2)

    # ---------- Assembly / steps loading ----------

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
            version = asm.get("version", "")
            label = f"{name} (v{version})" if version else name
            self.combo_assembly.addItem(label, asm.get("id"))

        self.combo_assembly.blockSignals(False)

        if self.assembly_types:
            self.combo_assembly.setCurrentIndex(0)
            self._on_assembly_changed(0)
        else:
            self.current_assembly_detail = None
            self._populate_steps_table([])

    def _on_assembly_changed(self, index: int):
        asm_id = self.combo_assembly.itemData(index) if index >= 0 else None
        if not asm_id:
            self.current_assembly_detail = None
            self._populate_steps_table([])
            self._clear_canvas()
            self._populate_required_components([])
            return

        try:
            detail = self.api_client.get_assembly_type_detail_full(asm_id)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", f"Cannot load assembly detail:\n{exc}")
            return

        # detail: { id, name, ..., steps: [...] }
        steps = detail.get("steps", [])
        steps = sorted(steps, key=lambda s: s.get("order", 0))

        self.current_assembly_detail = detail
        self._populate_steps_table(steps)

        if steps:
            self._select_step_by_index(0)
        else:
            self.current_step = None
            self._clear_canvas()
            self._populate_required_components([])

    def _populate_steps_table(self, steps: List[Dict]):
        self.table_steps.setRowCount(0)

        for step in steps:
            row = self.table_steps.rowCount()
            self.table_steps.insertRow(row)

            id_val = str(step.get("id", ""))
            order_val = str(step.get("order", "") or "")
            title_val = str(step.get("title", "") or "")

            self.table_steps.setItem(row, 0, QTableWidgetItem(id_val))
            self.table_steps.setItem(row, 1, QTableWidgetItem(order_val))
            self.table_steps.setItem(row, 2, QTableWidgetItem(title_val))

        if steps:
            self.table_steps.resizeRowsToContents()

    def _get_steps_list(self) -> List[Dict]:
        if not self.current_assembly_detail:
            return []
        steps = self.current_assembly_detail.get("steps", [])
        return sorted(steps, key=lambda s: s.get("order", 0))

    def _select_step_by_index(self, row: int):
        steps = self._get_steps_list()
        if not steps or row < 0 or row >= len(steps):
            self.current_step = None
            self._clear_canvas()
            self._populate_required_components([])
            return

        step = steps[row]
        self.current_step = step
        self.table_steps.selectRow(row)
        self._load_step_into_editor(step)

    def _on_step_double_clicked(self, item):
        row = item.row()
        self._select_step_by_index(row)

    def _get_selected_step_row(self) -> int:
        sel = self.table_steps.selectionModel().selectedRows()
        if not sel:
            return -1
        return sel[0].row()

    def _get_step_by_id(self, step_id: int) -> Optional[Dict]:
        for s in self._get_steps_list():
            if s.get("id") == step_id:
                return s
        return None

    # ---------- Step CRUD ----------

    def add_step(self):
        if not self.current_assembly_detail:
            QMessageBox.information(self, "No assembly", "Please select an assembly first.")
            return

        steps = self._get_steps_list()
        max_order = max((s.get("order", 0) for s in steps), default=0)
        initial = {"order": max_order + 1, "title": "", "description": ""}

        dlg = StepDialog(self, title="Add step", initial_data=initial)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        data = dlg.get_data()
        if not data["title"]:
            QMessageBox.warning(self, "Missing data", "Title is required.")
            return

        asm_id = self.current_assembly_detail["id"]

        try:
            self.api_client.create_step(
                assembly_id=asm_id,
                order=data["order"],
                title=data["title"],
                description=data["description"],
            )
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        # reload assembly detail
        self._on_assembly_changed(self.combo_assembly.currentIndex())

    def edit_selected_step(self):
        row = self._get_selected_step_row()
        if row < 0:
            QMessageBox.information(self, "No selection", "Please select a step first.")
            return
        self._edit_step_at_row(row)

    def _edit_step_at_row(self, row: int):
        steps = self._get_steps_list()
        if not steps or row < 0 or row >= len(steps):
            return
        step = steps[row]

        dlg = StepDialog(self, title="Edit step", initial_data=step)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        new_data = dlg.get_data()
        if not new_data["title"]:
            QMessageBox.warning(self, "Missing data", "Title is required.")
            return

        asm_id = self.current_assembly_detail["id"]
        try:
            self.api_client.update_step(
                step_id=step["id"],
                assembly_id=asm_id,
                order=new_data["order"],
                title=new_data["title"],
                description=new_data["description"],
            )
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self._on_assembly_changed(self.combo_assembly.currentIndex())
        # re-select this step (by id)
        updated_step = self._get_step_by_id(step["id"])
        if updated_step:
            steps = self._get_steps_list()
            for i, s in enumerate(steps):
                if s["id"] == updated_step["id"]:
                    self._select_step_by_index(i)
                    break

    def delete_selected_step(self):
        row = self._get_selected_step_row()
        if row < 0:
            QMessageBox.information(self, "No selection", "Please select a step first.")
            return

        steps = self._get_steps_list()
        if not steps or row < 0 or row >= len(steps):
            return

        step = steps[row]
        reply = QMessageBox.question(
            self,
            "Delete step",
            f"Delete step {step.get('order')} – '{step.get('title')}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self.api_client.delete_step(step["id"])
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self._on_assembly_changed(self.combo_assembly.currentIndex())

    # ---------- Load a step into the center + right ----------

    def _load_step_into_editor(self, step: Dict):
        """Load a step's objects + required components into canvas & right panel."""
        self._draw_step_objects(step)
        self._populate_required_components(step.get("required_components", []))

    # ---------- Canvas (StepObjects) ----------

    def _clear_canvas(self):
        """Remove all items except the black canvas."""
        for item in list(self.scene.items()):
            if item is self.canvas_rect:
                continue
            self.scene.removeItem(item)

    def _draw_step_objects(self, step: Dict):
        self._clear_canvas()

        objects = step.get("step_objects", [])
        r = self.scene.sceneRect()
        w = r.width()
        h = r.height()

        for obj in objects:
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
                # Rect item (resizable + movable)
                font_size = int(obj.get("font_size", 40))
                rect = ResizableRectItem(x, y, width_px, height_px)

                rect.setBrush(QBrush(QColor(0, 0, 0, 0)))  # fully transparent
                rect.setPen(QPen(QColor(200, 200, 200, 120)))  # light border

                rect.setZValue(z)
                rect.setData(0, ("step_object", obj["id"]))  # tag for save/delete

                rect.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
                rect.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
                rect.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

                # Text is now a CHILD of the rect (moves together)
                text_item = QGraphicsTextItem(obj.get("text_content", ""), rect)
                text_item.setDefaultTextColor(Qt.GlobalColor.white)
                font = QFont()
                font.setPixelSize(font_size)
                text_item.setFont(font)

                # Center text inside rect - use the rect's method to ensure consistency
                rect._recenter_text_children()

                self.scene.addItem(rect)


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
                        item = ResizablePixmapItem(pixmap)
                        item.setPos(x, y)
                        item.setZValue(z)
                        item.setData(0, ("step_object", obj["id"]))

                        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
                        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
                        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
                        
                        self.scene.addItem(item)
                else:
                    # fallback rect
                    rect = ResizableRectItem(x, y, width_px, height_px)
                    rect.setBrush(QBrush(QColor(150, 150, 150, 120)))
                    rect.setPen(QPen(Qt.GlobalColor.black))
                    rect.setZValue(z)
                    rect.setData(0, ("step_object", obj["id"]))
                    rect.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
                    rect.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
                    rect.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
                    self.scene.addItem(rect)


        # (later we can enable selection/dragging of items here)

    def _start_add_text_object(self):
        if not self.current_step:
            QMessageBox.information(self, "No step", "Select a step first.")
            return
        self._pending_add_mode = "text"

    def _start_add_image_object(self):
        if not self.current_step:
            QMessageBox.information(self, "No step", "Select a step first.")
            return
        self._pending_add_mode = "image"

    def _on_canvas_clicked(self, x_norm: float, y_norm: float):
        if not self._pending_add_mode or not self.current_step:
            return

        mode = self._pending_add_mode
        self._pending_add_mode = None  # reset

        step_id = self.current_step["id"]

        if mode == "text":
            dlg = TextObjectDialog(self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            text = dlg.get_text()
            if not text:
                return
            
            font_size = self.spin_font_size.value()
            
            # Create a temporary text item to measure its size
            temp_text = QGraphicsTextItem(text)
            font = QFont()
            font.setPixelSize(font_size)
            temp_text.setFont(font)
            
            # Measure the text
            br = temp_text.boundingRect()
            text_width = br.width()
            text_height = br.height()
            
            # Add padding around the text (8px on each side = 16px total)
            padding = 8.0
            box_width_px = text_width + (padding * 2)
            box_height_px = text_height + (padding * 2)
            
            # Convert to normalized coordinates
            w = self.scene.width()
            h = self.scene.height()
            width = box_width_px / w if w > 0 else 0.1
            height = box_height_px / h if h > 0 else 0.1
            
            z_index = 0

            try:
                self.api_client.create_step_object(
                    step_id=step_id,
                    object_type="text",
                    position_x=x_norm,
                    position_y=y_norm,
                    width=width,
                    height=height,
                    z_index=z_index,
                    text_content=text,
                    image_path="",
                    font_size=font_size,
                )
            except RuntimeError as exc:
                QMessageBox.critical(self, "Error", str(exc))
                return

        elif mode == "image":
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select image",
                "",
                "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All files (*)",
            )
            if not file_path:
                return

            # copy image into media/step_objects
            dest_dir = os.path.join(BACKEND_MEDIA_ROOT, STEP_OBJECTS_SUBDIR)
            os.makedirs(dest_dir, exist_ok=True)

            base = os.path.basename(file_path)
            dest_path = os.path.join(dest_dir, base)
            try:
                shutil.copy2(file_path, dest_path)
            except OSError as exc:
                QMessageBox.warning(self, "Image error", f"Could not copy image:\n{exc}")
                return

            rel_path = f"{STEP_OBJECTS_SUBDIR}/{base}"
            width = 0.3
            height = 0.3
            z_index = 0

            try:
                self.api_client.create_step_object(
                    step_id=step_id,
                    object_type="image",
                    position_x=x_norm,
                    position_y=y_norm,
                    width=width,
                    height=height,
                    z_index=z_index,
                    text_content="",
                    image_path=rel_path,
                )
            except RuntimeError as exc:
                QMessageBox.critical(self, "Error", str(exc))
                return

        # reload step from server (via assembly detail)
        self._reload_current_step_from_server()

    def _delete_selected_object(self):
        # we look for a selected item with our tag
        for item in self.scene.selectedItems():
            tag = item.data(0)
            if isinstance(tag, tuple) and tag[0] == "step_object":
                obj_id = tag[1]
                try:
                    self.api_client.delete_step_object(obj_id)
                except RuntimeError as exc:
                    QMessageBox.critical(self, "Error", str(exc))
                    return
                self._reload_current_step_from_server()
                return

    def _reload_current_step_from_server(self):
        """After adding/removing objects, reload assembly detail and refresh this step."""
        if not self.current_assembly_detail:
            return

        asm_id = self.current_assembly_detail["id"]
        try:
            detail = self.api_client.get_assembly_type_detail_full(asm_id)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", f"Cannot reload assembly detail:\n{exc}")
            return

        self.current_assembly_detail = detail
        steps = self._get_steps_list()
        if not self.current_step:
            self._populate_steps_table(steps)
            self._clear_canvas()
            self._populate_required_components([])
            return

        step_id = self.current_step["id"]
        new_step = None
        for s in steps:
            if s.get("id") == step_id:
                new_step = s
                break
        self._populate_steps_table(steps)

        if new_step:
            # select row of this step
            for i, s in enumerate(steps):
                if s.get("id") == step_id:
                    self.table_steps.selectRow(i)
                    break
            self.current_step = new_step
            self._load_step_into_editor(new_step)
        else:
            self.current_step = None
            self._clear_canvas()
            self._populate_required_components([])

    # ---------- Required components (right panel) ----------

    def _populate_required_components(self, required: List[Dict]):
        self.table_required.setRowCount(0)

        for rc in required:
            row = self.table_required.rowCount()
            self.table_required.insertRow(row)

            id_val = str(rc.get("id", ""))
            comp = rc.get("component")
            bin_ = rc.get("bin")
            qty_val = str(rc.get("quantity", 1))

            if comp:
                comp_code = comp.get("component_code") or ""
                comp_name = comp.get("name", "")
                comp_label = f"{comp_code} - {comp_name}" if comp_code else comp_name
            else:
                comp_label = "(unknown)"

            if bin_:
                bin_box = bin_.get("box_code", "")
                bin_label = bin_box or f"Bin {bin_.get('id')}"
            else:
                bin_label = "(no bin)"

            self.table_required.setItem(row, 0, QTableWidgetItem(id_val))
            self.table_required.setItem(row, 1, QTableWidgetItem(comp_label))
            self.table_required.setItem(row, 2, QTableWidgetItem(bin_label))
            self.table_required.setItem(row, 3, QTableWidgetItem(qty_val))

        if required:
            self.table_required.resizeRowsToContents()

    def _get_selected_required_row(self) -> int:
        sel = self.table_required.selectionModel().selectedRows()
        if not sel:
            return -1
        return sel[0].row()

    def _get_required_by_row(self, row: int) -> Optional[Dict]:
        if not self.current_step:
            return None
        required = self.current_step.get("required_components", [])
        if row < 0 or row >= len(required):
            return None
        return required[row]

    def add_required_component(self):
        if not self.current_step:
            QMessageBox.information(self, "No step", "Select a step first.")
            return

        try:
            components = self.api_client.get_components()
            bins = self.api_client.get_bins()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", f"Cannot load components/bins:\n{exc}")
            return

        dlg = RequiredComponentDialog(
            self,
            components=components,
            bins=bins,
            title="Add required component",
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        data = dlg.get_data()
        if not data["component_id"]:
            QMessageBox.warning(self, "Missing data", "Component is required.")
            return

        try:
            self.api_client.create_step_required_component(
                step_id=self.current_step["id"],
                component_id=data["component_id"],
                preferred_bin_ids=data["preferred_bin_ids"],
                quantity=data["quantity"],
            )
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self._reload_current_step_from_server()

    def edit_selected_required_component(self):
        row = self._get_selected_required_row()
        if row < 0:
            QMessageBox.information(self, "No selection", "Select a required component first.")
            return

        rc = self._get_required_by_row(row)
        if not rc:
            return

        initial_data = {
            "component_id": rc.get("component", {}).get("id") if rc.get("component") else None,
            "preferred_bin_ids": [b.get("id") for b in rc.get("preferred_bins", []) if b.get("id") is not None],
            "quantity": rc.get("quantity", 1),
        }

        try:
            components = self.api_client.get_components()
            bins = self.api_client.get_bins()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", f"Cannot load components/bins:\n{exc}")
            return

        dlg = RequiredComponentDialog(
            self,
            components=components,
            bins=bins,
            title="Edit required component",
            initial_data=initial_data,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        data = dlg.get_data()
        if not data["component_id"]:
            QMessageBox.warning(self, "Missing data", "Component is required.")
            return

        try:
            self.api_client.update_step_required_component(
                src_id=rc["id"],
                step_id=self.current_step["id"],
                component_id=data["component_id"],
                preferred_bin_ids=data["preferred_bin_ids"],
                quantity=data["quantity"],
            )
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self._reload_current_step_from_server()

    def delete_selected_required_component(self):
        row = self._get_selected_required_row()
        if row < 0:
            QMessageBox.information(self, "No selection", "Select a required component first.")
            return

        rc = self._get_required_by_row(row)
        if not rc:
            return

        reply = QMessageBox.question(
            self,
            "Delete required component",
            "Delete this required component from the step?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self.api_client.delete_step_required_component(rc["id"])
        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self._reload_current_step_from_server()

    def _get_selected_step_object_item(self):
        """Return the selected QGraphicsItem that represents a step_object, or None."""
        for item in self.scene.selectedItems():
            tag = item.data(0)
            if isinstance(tag, tuple) and tag[0] == "step_object":
                return item
        return None

    def _on_font_size_changed(self, size: int):
        """Update font size for selected text object."""
        item = self._get_selected_step_object_item()
        if not item:
            return  # silently ignore if nothing selected
        
        # Only works on ResizableRectItem with text children
        if not isinstance(item, ResizableRectItem):
            return
        
        for child in item.childItems():
            if isinstance(child, QGraphicsTextItem):
                font = child.font()
                font.setPixelSize(size)
                child.setFont(font)
                # Recenter text after font change
                item._recenter_text_children()
                self.scene.update()
                break

        # Update in-memory object so it gets saved
        tag = item.data(0)
        obj_id = tag[1] if isinstance(tag, tuple) else None
        if obj_id is None or not self.current_step:
            return

        objs = self.current_step.get("step_objects", [])
        for o in objs:
            if o.get("id") == obj_id:
                o["font_size"] = int(size)
                break

    def _scale_selected_object(self, factor: float):
        """
        Grow/shrink selected object by multiplying its width/height (normalized)
        by factor. This only changes local data and redraws the step.
        """
        if not self.current_step:
            QMessageBox.information(self, "No step", "Select a step first.")
            return

        item = self._get_selected_step_object_item()
        if not item:
            QMessageBox.information(self, "No selection", "Select an object on the canvas first.")
            return

        tag = item.data(0)
        obj_id = tag[1]

        # Find object in current_step data
        objs = self.current_step.get("step_objects", [])
        obj = None
        for o in objs:
            if o.get("id") == obj_id:
                obj = o
                break
        if not obj:
            return

        # Adjust normalized width/height
        width = float(obj.get("width", 0.2)) * factor
        height = float(obj.get("height", 0.1)) * factor

        # Clamp to avoid crazy values
        width = max(0.05, min(width, 2.0))
        height = max(0.05, min(height, 2.0))

        obj["width"] = width
        obj["height"] = height

        # Just redraw from current_step, no API call yet
        self._draw_step_objects(self.current_step)

    def _save_layout_changes(self):
        """
        Go through all step_objects of current_step, read their geometry
        from the scene (pos + size), and update them via API.
        """
        if not self.current_step:
            QMessageBox.information(self, "No step", "Select a step first.")
            return

        step_id = self.current_step["id"]
        objs = self.current_step.get("step_objects", [])
        if not objs:
            QMessageBox.information(self, "Nothing to save", "This step has no objects.")
            return

        scene_rect = self.scene.sceneRect()
        w = scene_rect.width() or 1.0
        h = scene_rect.height() or 1.0

        # Map id -> backend object data
        objs_by_id = {o["id"]: o for o in objs if "id" in o}

        try:
            for item in self.scene.items():
                tag = item.data(0)
                if not (isinstance(tag, tuple) and tag[0] == "step_object"):
                    continue

                obj_id = tag[1]
                obj = objs_by_id.get(obj_id)
                if not obj:
                    continue

                # position in scene coordinates
                pos = item.pos()
                x_px = pos.x()
                y_px = pos.y()

                # size in scene coordinates (local bounding rect)
                br = item.boundingRect()
                width_px = br.width()
                height_px = br.height()

                pos_x = x_px / w
                pos_y = y_px / h
                width = width_px / w
                height = height_px / h

                z_index = int(item.zValue())

                object_type = obj.get("object_type")
                text_content = obj.get("text_content", "")
                image_path = obj.get("image_path", "")
                font_size = int(obj.get("font_size", 10))

                # Update via API with new geometry
                self.api_client.update_step_object(
                    obj_id=obj_id,
                    step_id=step_id,
                    object_type=object_type,
                    position_x=pos_x,
                    position_y=pos_y,
                    width=width,
                    height=height,
                    z_index=z_index,
                    text_content=text_content,
                    image_path=image_path,
                    font_size=font_size,
                )

        except RuntimeError as exc:
            QMessageBox.critical(self, "Error", f"Error saving layout:\n{exc}")
            return

        # Reload from server so local data matches DB
        self._reload_current_step_from_server()
        QMessageBox.information(self, "Saved", "Step layout saved.")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.scene is not None and self.view is not None:
            self.view.fitInView(self.scene.sceneRect(),
                                Qt.AspectRatioMode.KeepAspectRatio)




