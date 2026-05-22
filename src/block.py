import json

from PySide6.QtWidgets import (
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsScene, QGraphicsView,
    QGraphicsSimpleTextItem, QDialog, QFormLayout, QLineEdit, QPushButton,
    QMenu, QHBoxLayout, QComboBox, QWidget, QVBoxLayout, QLabel, QMessageBox,
    QToolButton, QSizePolicy, QFrame
)
from PySide6.QtCore import QRectF, Qt, QTimer, QSizeF, QObject, QEvent
from PySide6.QtGui import QPen, QColor, QFont, QPainter, QFontMetrics, QIntValidator
from .config import *
from .debug_flag import DEBUG_MODE
from .linkml_adapter import action_to_linkml_dict, chemical_to_linkml_dict, normalize_boolean, quantity_to_text
from .procedure_text import format_gas_entry_label


class _SingleChemicalRef:
    """Mutable holder for one embedded chemical dict (solvent, etc.)."""

    def __init__(self, initial=None):
        self.value = dict(initial) if isinstance(initial, dict) else {}


class _UnitDecimalKeyFilter(QObject):
    """Block comma/semicolon key entry in unit numeric fields."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            if event.text() in {",", ";"}:
                return True
            if event.key() in (Qt.Key.Key_Comma, Qt.Key.Key_Semicolon):
                return True
        return super().eventFilter(obj, event)


def sanitize_unit_decimal_text(text: str, *, allow_negative: bool = False) -> str:
    """Keep only an optional leading minus, digits, and at most one '.'."""
    result = []
    has_dot = False
    for ch in text:
        if ch == "-" and allow_negative and not result:
            result.append(ch)
        elif ch == "." and not has_dot:
            result.append(ch)
            has_dot = True
        elif ch.isdigit():
            result.append(ch)
    return "".join(result)


def configure_unit_decimal_input(edit: QLineEdit, min_value: float = 0.0) -> None:
    """Unit field numeric input: '.' decimal separator only, unlimited precision."""
    allow_negative = min_value < 0

    def _on_text_changed(text: str) -> None:
        cleaned = sanitize_unit_decimal_text(text, allow_negative=allow_negative)
        if cleaned == text:
            return
        cursor = len(sanitize_unit_decimal_text(text[: edit.cursorPosition()], allow_negative=allow_negative))
        edit.blockSignals(True)
        edit.setText(cleaned)
        edit.setCursorPosition(min(cursor, len(cleaned)))
        edit.blockSignals(False)

    if getattr(edit, "_unit_decimal_configured", False):
        return

    edit.textChanged.connect(_on_text_changed)
    edit._unit_decimal_key_filter = _UnitDecimalKeyFilter(edit)
    edit.installEventFilter(edit._unit_decimal_key_filter)
    edit._unit_decimal_configured = True


def format_decimal_for_input(text: str) -> str:
    """Normalize stored decimals for display in dot-decimal fields."""
    return str(text).strip().replace(",", ".")


def field_label(field_key: str, action_name: str | None = None) -> str:
    """UI label for a param key, with optional per-action overrides."""
    config = FIELD_CONFIG.get(str(field_key).lower(), {})
    if action_name:
        label = config.get("labels_by_action", {}).get(action_name)
        if label:
            return label
    return config.get("label", str(field_key).capitalize())


def embedded_chemical_filled(chem) -> bool:
    """True when an embedded chemical dict (list item or solvent) has a type or name."""
    if not isinstance(chem, dict) or not chem:
        return False
    return bool(
        str(chem.get("chemical_type", "")).strip()
        or str(chem.get(KEY_NAME, "")).strip()
        or str(chem.get(KEY_FORMULA, "")).strip()
    )


def validate_repeat_amount(text: str) -> int:
    """Repeat count: integer only, at least 1."""
    cleaned = str(text).strip()
    if not cleaned:
        raise ValueError("empty")
    if "." in cleaned or "," in cleaned:
        raise ValueError("decimal")
    if not cleaned.isdigit():
        raise ValueError("not_integer")
    amount = int(cleaned)
    if amount < 1:
        raise ValueError("too_small")
    return amount


def validate_decimal_input(text: str) -> float:
    """Parse the numeric part of a unit field; requires '.' as the decimal separator."""
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("empty")
    if "," in cleaned:
        raise ValueError("comma separator")
    return float(cleaned)
# Style for small primary action buttons (used for compact add buttons)
ADD_BUTTON_STYLE = (
    "QToolButton {"
    "  font-size: 14px;"
    "  color: white;"
    "  background-color: #6b4cff;"
    "  border-radius: 6px;"
    "  border: 1px solid #5a3fe6;"
    "  padding: 0px; margin: 0px;"
    "}"
    "QToolButton:hover { background-color: #5a3fe6; }"
    "QToolButton:pressed { background-color: #4b33bf; }"
)

LIST_ICON_BUTTON_STYLE = (
    "QToolButton {"
    "  background-color: #f8fafc;"
    "  border: 1px solid #e2e8f0;"
    "  border-radius: 5px;"
    "  color: #334155;"
    "}"
    "QToolButton:hover { background-color: #eef2ff; border-color: #c7d2fe; }"
    "QToolButton:pressed { background-color: #e0e7ff; }"
)


class EditDialog(QDialog):
    """Custom QDialog that asks for confirmation when user tries to close without saving."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._accepted_by_user = False
    
    def reject(self):
        """Override reject to ask for confirmation when ESC or close button is pressed."""
        reply = QMessageBox.question(
            self,
            "Close without saving?",
            "Are you sure you want to close this dialog without saving?\n\nThe block will not be created.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel
        )
        if reply == QMessageBox.StandardButton.Ok:
            super().reject()
    
    def set_accepted(self):
        """Mark that the dialog was accepted by user (save button clicked)."""
        self._accepted_by_user = True


class PreviewGraphicsView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setInteractive(False)
        self.setBackgroundBrush(QColor(247, 250, 252))

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        grid_size = 40
        left = int(rect.left()) - (int(rect.left()) % grid_size)
        top = int(rect.top()) - (int(rect.top()) % grid_size)

        painter.setPen(QPen(QColor(226, 232, 240), 1))
        x = left
        while x < rect.right():
            painter.drawLine(x, rect.top(), x, rect.bottom())
            x += grid_size
        y = top
        while y < rect.bottom():
            painter.drawLine(rect.left(), y, rect.right(), y)
            y += grid_size


class PreviewBlockItem(QGraphicsRectItem):
    def __init__(self, label, color, rect, parent=None):
        super().__init__(rect, parent)
        self.setBrush(color)
        self.setPen(QPen(QColor(71, 85, 105), 2))
        self.label = QGraphicsSimpleTextItem(label, self)
        self.label.setBrush(QColor(255, 255, 255))
        font = QFont("Segoe UI", 8, QFont.Bold)
        self.label.setFont(font)
        br = self.label.boundingRect()
        self.label.setPos((rect.width() - br.width()) / 2, (rect.height() - br.height()) / 2)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, False)


class ProcedurePreviewDialog(QDialog):
    def __init__(self, procedure_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Procedure Preview")
        self.resize(1100, 780)

        from .editor import Editor

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.preview_editor = Editor()
        preview_data = procedure_data or {}
        if isinstance(preview_data, dict):
            flows = preview_data.get("preview_flows") or preview_data.get("flows", [])
            preview_data = {
                "protocol_name": preview_data.get("protocol_name", DEFAULT_PROTOCOL_NAME),
                "total_flows": len(flows),
                "flows": flows,
            }
        self.preview_editor.load_protocol_data(preview_data, include_hidden=True)
        self.preview_editor.set_preview_mode(True)

        layout.addWidget(self.preview_editor.container)

class Block(QGraphicsRectItem):
    def __init__(self, action, params, editor=None):
        super().__init__(0, 0, 140, 60)
        self.action = action
        self.params = params
        self.editor = editor
        self.block_id = None
        
        # Pointers for Action Flow
        self.next_block = None   # Horizontal Right
        self.prev_block = None   # Horizontal Left
        self.below_block = None  # Vertical Down (Action)
        self.above_block = None  # Vertical Up (Action)
        
        # Pointer for Chemical Stack
        self.chem_below = None   # Points to the first ChemicalBlock
        self.subproduct_below = None # Points to the SubproductBlock (if any)
        
        self.orientation = "horizontal" # Default orientation
        self.is_first = False
        self.connected = False
        self.chain_drag_mode = False

        self.support_id = None  # e.g., CT1 for a change temperature support action
        self.support_color = None
        self.influence_list = [] # list of ids of support actions currently influencing this block (for badges)
        self.available_influences = []
        self.disabled_influences = set()
        
        # Hover tooltip support
        self.hover_timer = QTimer()
        self.hover_timer.timeout.connect(self.show_details_tooltip)
        self.hover_timer.setSingleShot(True)
        self.setAcceptHoverEvents(True)

        self.setFlags(
            QGraphicsRectItem.ItemIsMovable |
            QGraphicsRectItem.ItemIsSelectable
        )
        self.update_visual_style()

        self.text = QGraphicsTextItem(self)
        self.update_text()

    def paint(self, painter, option, widget=None):
        """paints action blocks with dynamic chevrons or subproduct shape."""
        from PySide6.QtGui import QPainterPath, QPainter
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        w, h = rect.width(), rect.height()
        arrow_size = 18 
        m = 4 
        path = QPainterPath()

        if self.action == "SubProductCreation":
            # upward arrow for subproducts
            path.moveTo(w / 2, m)
            path.lineTo(w - m, m + arrow_size)
            path.lineTo(w - m, h - m)
            path.lineTo(m, h - m)
            path.lineTo(m, m + arrow_size)
            path.closeSubpath()
        else:
            # standard action blocks
            has_left_indent = self.prev_block is not None
            has_top_indent = self.above_block is not None and not isinstance(self.above_block, ChemicalBlock)
            is_horz = self.orientation == "horizontal"
            is_vert = self.orientation == "vertical"

            path.moveTo(m, m)
            if has_top_indent:
                notch_w = 26
                path.lineTo(w / 2 - notch_w, m)
                path.lineTo(w / 2, m + arrow_size)
                path.lineTo(w / 2 + notch_w, m)
            
            if is_horz:
                path.lineTo(w - m - arrow_size, m)
                path.lineTo(w - m, h / 2)
                path.lineTo(w - m - arrow_size, h - m)
            else:
                path.lineTo(w - m, m)
                if is_vert:
                    path.lineTo(w - m, h - m - arrow_size)
                else:
                    path.lineTo(w - m, h - m)

            if is_vert:
                path.lineTo(w / 2, h - m)
                path.lineTo(m, h - m - arrow_size)
            else:
                path.lineTo(m, h - m)

            if has_left_indent:
                path.lineTo(m + arrow_size, h / 2)
            
            path.closeSubpath()

        # rendering body
        painter.setOpacity(0.15)
        painter.setBrush(QColor(0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path.translated(2, 2))
        
        painter.setOpacity(1.0)
        painter.setBrush(self.brush())
        pen = QPen(self.pen())
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(path)
        
        # draw influence badges on top
        self._draw_influence_badges(painter)
    
    def _draw_influence_badges(self, painter):
        """draw smaller badges with custom 4-1-1 distribution and rotation support."""
        rect = self.rect()
        w, h = rect.width(), rect.height()
        is_vert = self.orientation == "vertical"
        
        # save painter state before applying rotation
        painter.save()

        # rotate drawing context for vertical orientation
        if is_vert:
            painter.translate(w, 0)
            painter.rotate(90)
            # treat block dimensions as swapped for coordinate logic
            v_w, v_h = h, w 
        else:
            v_w, v_h = w, h

        # logic for start indents relative to flow direction
        has_start_indent = (self.prev_block is not None) if not is_vert else \
                           (self.above_block is not None and not isinstance(self.above_block, ChemicalBlock))
        
        is_action = not isinstance(self, ChemicalBlock)
        arrow_size = 18
        margin = 4 
        v_nudge = 2
        badge_w = 22 
        badge_h = 12 
        gap = 3 
        
        # x-offsets to avoid clipping with arrows/sockets
        x_offset_left = (arrow_size - 7) if has_start_indent else 2
        x_offset_right = arrow_size if is_action else 2

        # 1. draw own id badge at top-left for support actions
        if self.support_id and self.action != "SubProductCreation":
            painter.setPen(Qt.PenStyle.NoPen)
            bg_color = getattr(self, 'support_color', QColor(44, 62, 80, 220))
            painter.setBrush(bg_color)
            
            badge_rect = QRectF(margin + x_offset_left, 
                                margin + v_nudge, 
                                badge_w, badge_h)
            painter.drawRoundedRect(badge_rect, 2, 2)
            
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Segoe UI", 6, QFont.Bold))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, self.support_id)

        # 2. draw influence list badges with specific placement rule
        if hasattr(self, 'influence_list') and self.influence_list:
            painter.setFont(QFont("Segoe UI", 6, QFont.Bold))
            
            for i, influence in enumerate(self.influence_list):
                if i < 4:
                    # bottom row: grow left from bottom-right
                    x = v_w - margin - x_offset_right - badge_w - (i * (badge_w + gap))
                    y = v_h - margin - badge_h - v_nudge
                elif i == 4:
                    # top-right corner
                    x = v_w - margin - x_offset_right - badge_w
                    y = margin + v_nudge
                elif i == 5:
                    # top-left corner
                    x = margin + x_offset_left
                    y = margin + v_nudge
                else:
                    # overflow row
                    x = v_w - margin - x_offset_right - badge_w - ((i - 3) * (badge_w + gap))
                    y = margin + v_nudge

                badge_rect = QRectF(x, y, badge_w, badge_h)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(influence["color"])
                painter.drawRoundedRect(badge_rect, 2, 2)
                
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, influence["id"])

        # restore painter original state
        painter.restore()
    
    def _draw_vertical_path(self, path, w, h, arrow_size):
        """Draws a block with a downward pointing arrow."""
        path.moveTo(4, 4)
        path.lineTo(w - 4, 4)
        path.lineTo(w - 4, h - arrow_size - 4)
        path.lineTo(w / 2, h - 4)
        path.lineTo(4, h - arrow_size - 4)
        path.closeSubpath()
    
    def update_visual_style(self):
        """Update the visual style based on first status and connected state"""
        if self.is_first:
            self.setBrush(QColor(255, 159, 64))  # Orange for first block
        else:
            self.setBrush(QColor(107, 76, 255))  # Purple for normal blocks
        
        if self.is_first:
            self.default_pen = QPen(QColor(230, 126, 34), 3)  # Darker orange
        else:
            self.default_pen = QPen(QColor(88, 56, 220), 3)  # Darker purple
        
        if self.connected:
            self.setPen(QPen(QColor(46, 204, 113), 3))  # Green
        else:
            self.setPen(self.default_pen)

    def set_connected(self, connected: bool):
        """Mark visual connected state (changes border color)"""
        self.connected = connected
        if connected:
            self.setPen(QPen(QColor(255, 193, 7), 3))  # Yellow
        else:
            self.setPen(self.default_pen)

    def _get_balanced_text(self, text):
        """splits camelcase text into two balanced lines."""
        # Extract words by uppercase letters
        words = []
        current_word = ""
        for i, char in enumerate(text):
            if char.isupper() and i > 0:
                words.append(current_word)
                current_word = char
            else:
                current_word += char
        words.append(current_word)

        # Handle simple cases
        if len(words) == 1:
            return words[0]
        if len(words) == 2:
            return f"{words[0]}\n{words[1]}"

        # Balance multiple words into two lines
        best_split = ""
        min_diff = float('inf')

        for i in range(1, len(words)):
            line1 = " ".join(words[:i])
            line2 = " ".join(words[i:])
            diff = abs(len(line1) - len(line2))
            
            if diff < min_diff:
                min_diff = diff
                best_split = f"{line1}\n{line2}"

        return best_split

    def update_text(self):
        """rotate and center text, with special logic for anchored subproducts."""
        display_text = self._get_balanced_text(self.action)
        self.text.setPlainText(display_text)
        
        is_multiline = "\n" in display_text
        font = QFont("Segoe UI", 10, QFont.Bold)
        self.text.setFont(font)
        self.text.setDefaultTextColor(QColor(255, 255, 255))
        
        block_rect = self.rect()
        arrow_size = 18
        
        # Action block above check
        has_top_action = self.above_block is not None and not isinstance(self.above_block, ChemicalBlock)

        option = self.text.document().defaultTextOption()
        option.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text.document().setDefaultTextOption(option)
        
        # special case for subproduct (upward arrow at the top)
        if self.action == "SubProductCreation":
            self.text.setRotation(90)
            # define available height inside the body (below the arrow tip)
            self.text.setTextWidth(block_rect.height() - arrow_size - 10)
            text_rect = self.text.boundingRect()
            
            x = (block_rect.width() + text_rect.height()) / 2
            # start calculation after the arrow tip
            top_offset = arrow_size
            y = top_offset + (block_rect.height() - top_offset - text_rect.width()) / 2
            self.text.setPos(x, y)
            return

        # standard orientation logic
        if self.orientation == "horizontal":
            self.text.setRotation(0)
            self.text.setTextWidth(block_rect.width() - 20)
            text_rect = self.text.boundingRect()
            x = (block_rect.width() - text_rect.width()) / 2
            y = (block_rect.height() - text_rect.height()) / 2
            if has_top_action and is_multiline:
                y += 6 
        else:
            self.text.setRotation(90)
            self.text.setTextWidth(block_rect.height() - 20)
            text_rect = self.text.boundingRect()
            x = (block_rect.width() + text_rect.height()) / 2
            y = (block_rect.height() - text_rect.width()) / 2
            
        self.text.setPos(x, y)
    
    def mouseDoubleClickEvent(self, event):
        """opens editor except for subproduct creation which is automatic."""
        if self.action != "SubProductCreation":
            self.open_editor()

    def hoverEnterEvent(self, event):
        """Start the timer when mouse enters the block"""
        self.hover_timer.start(500)  # 0.5 seconds
        
    def hoverLeaveEvent(self, event):
        """Stop the timer and hide tooltip when mouse leaves"""
        self.hover_timer.stop()
        self.hide_details_tooltip()
    
    def show_details_tooltip(self):
        """Show the block details as a tooltip"""
        details_text = f"{self.action}\n"
        for key, value in self.params.items():
            details_text += f"{key}: {value}\n"
        self.setToolTip(details_text.strip())

    def to_linkml_dict(self):
        """Return a LinkML-aligned representation of this block."""
        attached_chemicals = []
        curr = getattr(self, "chem_below", None)
        while curr:
            if hasattr(curr, "to_linkml_dict"):
                attached_chemicals.append(curr.to_linkml_dict())
            curr = curr.below_block

        payload = action_to_linkml_dict(self.action, self.params, attached_chemicals)
        payload["block_id"] = self.block_id
        return payload
    
    def hide_details_tooltip(self):
        """Hide the tooltip"""
        self.setToolTip("")

    def debug_print_structure(self):
        """Print a readable snapshot of the grid, action flows, and chemical stacks."""
        if not DEBUG_MODE or not self.editor:
            return

        print("\n[DEBUG] ===== Grid structure snapshot =====")
        for idx, b in enumerate(self.editor.blocks):
            def rid(x): return hex(id(x)) if x is not None else "None"
            
            # Identify the block type and its orientation
            b_type = b.__class__.__name__
            orient = getattr(b, 'orientation', 'N/A')
            
            print(
                f"[{idx}] {b_type}('{b.action}') id={hex(id(b))} | "
                f"Orient={orient} | "
                f"H_prev={rid(b.prev_block)} H_next={rid(b.next_block)} | "
                f"V_above={rid(b.above_block)} V_below={rid(b.below_block)} | "
                f"Chem_Stack={rid(getattr(b, 'chem_below', None))}"
            )

        # 1. Show Horizontal Action Chains
        print("[DEBUG] Horizontal Action Flows:")
        h_seen = set()
        for b in self.editor.blocks:
            if not isinstance(b, ChemicalBlock) and b.prev_block is None and b not in h_seen:
                h_chain = []
                cur = b
                while cur:
                    h_chain.append(f"{cur.action}")
                    h_seen.add(cur)
                    cur = cur.next_block
                if len(h_chain) > 1:
                    print("  (H) " + " <-> ".join(h_chain))

        # 2. Show Vertical Action Chains
        print("[DEBUG] Vertical Action Flows:")
        v_seen = set()
        for b in self.editor.blocks:
            # We only follow above_block if it's not a ChemicalBlock
            is_v_head = b.above_block is None or isinstance(b.above_block, ChemicalBlock)
            if not isinstance(b, ChemicalBlock) and is_v_head and b not in v_seen:
                v_chain = []
                cur = b
                while cur and not isinstance(cur, ChemicalBlock):
                    v_chain.append(f"{cur.action}")
                    v_seen.add(cur)
                    cur = cur.below_block
                if len(v_chain) > 1:
                    print("  (V) " + " | ".join(v_chain))

        # 3. Show Chemical Stacks per Action
        print("[DEBUG] Chemical Ingredient Stacks:")
        for b in self.editor.blocks:
            if not isinstance(b, ChemicalBlock) and b.chem_below:
                c_stack = []
                cur_c = b.chem_below
                while cur_c:
                    c_stack.append(f"{cur_c.params.get('name', cur_c.action)}")
                    cur_c = cur_c.below_block
                print(f"  [{b.action}] uses -> " + " + ".join(c_stack))

        print("[DEBUG] ===== end snapshot =====\n")

    def mousePressEvent(self, event):
        """handle mouse press, bringing item to front and blocking subproduct drag."""
        if event.button() == Qt.RightButton:
            self.show_context_menu(event)
            return

        # check for anchored subproduct
        is_subproduct = self.action == "SubProductCreation" and self.above_block
        is_ctrl = event.modifiers() == Qt.ControlModifier

        # bring to foreground always
        self.setZValue(1000)

        if is_subproduct and not is_ctrl:
            from PySide6.QtWidgets import QToolTip
            from PySide6.QtGui import QCursor
            QToolTip.showText(QCursor.pos(), "Subproduct is anchored to its parent", self.editor)
            event.accept()
            return 

        if self.editor and not is_ctrl:
            # handle detachment logic only for movable actions
            if self.action != "SubProductCreation":
                old_above, old_below = self.above_block, self.below_block
                if old_above or old_below:
                    old_p, old_c = self.editor._pluck_vertical(self)
                    if old_p: self.editor.reflow_entire_cluster(old_p)
                    if old_c: self.editor.reflow_entire_cluster(old_c)

            if self.orientation == "vertical":
                old_p, old_n = self.editor._pluck_horizontal(self)
                if old_p: self.editor.reflow_entire_cluster(old_p)
                if old_n: self.editor.reflow_entire_cluster(old_n)

        if is_ctrl:
            self.chain_drag_mode = True
            super().mousePressEvent(event)
            return

        # call base implementation for normal blocks to allow selection/drag
        super().mousePressEvent(event)
    
    def delete_block(self):
        """removes the block and correctly stitches or nullifies all pointers."""
        if not self.editor:
            return

        if hasattr(self.editor, "open_entity_procedures"):
            self.editor.open_entity_procedures.pop(self, None)
        if hasattr(self, "imported_procedure"):
            self.imported_procedure = None

        # remove from the editor's tracking list
        if self in self.editor.blocks:
            self.editor.blocks.remove(self)

        # identify all possible neighbors
        p_h, n_h = self.prev_block, self.next_block
        p_v, n_v = self.above_block, self.below_block

        # 1. repair horizontal chain
        if p_h: p_h.next_block = n_h
        if n_h: n_h.prev_block = p_h

        # 2. repair vertical chain (Action flow or Chemical stacks)
        if p_v:
            if isinstance(self, ChemicalBlock):
                # if parent is another chemical, use below_block
                if isinstance(p_v, ChemicalBlock):
                    p_v.below_block = n_v
                else:
                    # if parent is an action, use chem_below
                    p_v.chem_below = n_v
            else:
                # for standard action flow
                if not isinstance(p_v, ChemicalBlock):
                    p_v.below_block = n_v
        
        if n_v:
            n_v.above_block = p_v
            n_v.update()

        # 3. special case: if this is a subproduct, clear the parent's anchor
        if self.action == "SubProductCreation" and p_v:
            if hasattr(p_v, 'subproduct_below'):
                p_v.subproduct_below = None

        # 4. special case: if this block has an anchored subproduct, delete it too
        if hasattr(self, 'subproduct_below') and self.subproduct_below:
            # this creates a recursive deletion of the sub-branch
            self.subproduct_below.delete_block()

        # 5. clear all local pointers to prevent memory leaks or ghost links
        self.prev_block = self.next_block = self.above_block = self.below_block = self.chem_below = None
        if hasattr(self, 'subproduct_below'):
            self.subproduct_below = None

        # 6. final visual and sequence updates
        scene = self.scene()
        if scene:
            scene.removeItem(self)
        
        # sync positions of the remaining blocks in the old clusters
        anchors = [p_h, n_h, p_v, n_v]
        seen = set()
        for anchor in anchors:
            if not anchor or anchor in seen:
                continue
            cluster = self.editor.get_full_cluster(anchor)
            seen.update(cluster)
            self.editor._reflow_component_layout(anchor)

        self.editor.update_linked_sequence()
        # force influence refresh so subproduct substance fields are updated
        self.editor.update_support_logic()

    def mouseReleaseEvent(self, event):
        """Handle mouse release events"""
        if self.chain_drag_mode:
            self.chain_drag_mode = False
            # Don't perform linking operations for chain drag
        else:
            super().mouseReleaseEvent(event)
            # Notify editor to check for linking based on block type
            if self.editor:
                if isinstance(self, ChemicalBlock):
                    # Chemical blocks can only link vertically
                    self.editor.check_and_link_vertical_blocks(self)
                else:
                    # Action blocks link horizontally
                    self.editor.check_and_link_horizontal_blocks(self)
                    # Also check if any chemical blocks need to be repositioned
                    self.editor.check_and_link_vertical_blocks(self)
                # Print debug snapshot of the whole structure after linking
                try:
                    if self.editor:
                        self.debug_print_structure()
                except Exception as e:
                    if DEBUG_MODE:
                        print(f"[DEBUG] Error printing structure: {e}")

    def mouseMoveEvent(self, event):
        """Handle mouse move events including chain dragging"""
        if self.chain_drag_mode:
            # Move the entire chain (both directions from this block)
            delta = event.scenePos() - event.lastScenePos()
            self.move_chain(delta.x(), delta.y())
        else:
            # Normal single-block movement
            super().mouseMoveEvent(event)
            if self.editor:
                self.editor.preview_link(self)


    def show_context_menu(self, event):
        """show context menu with orientation, first action, and subproduct branch options."""
        menu = QMenu()
        is_connected = bool(self.prev_block or self.next_block or self.above_block or 
                            self.below_block or self.chem_below)

        # 1. orientation (not for chemicals or subproducts)
        if ENABLE_VERTICAL_ORIENTATION_TOGGLE and not isinstance(self, ChemicalBlock) and self.action != "SubProductCreation":
            label = "Set Vertical" if self.orientation == "horizontal" else "Set Horizontal"
            toggle = menu.addAction(label)
            if is_connected:
                toggle.setEnabled(False)
                toggle.setText(f"{label} (Disconnect first)")
            else:
                toggle.triggered.connect(self.toggle_orientation)
            menu.addSeparator()

        # 2. specific option for separate block
        if self.action == "Separate":
            # check if the helper exists in editor
            sub_opt = menu.addAction("➕ Add Subproduct Branch")
            # disable if a subproduct is already attached
            sub_opt.setEnabled(self.subproduct_below is None)
            sub_opt.triggered.connect(lambda: self.editor.add_subproduct_branch(self))
            menu.addSeparator()

        # 3. first logic (not for chemicals or subproducts)
        if not isinstance(self, ChemicalBlock) and self.action != "SubProductCreation":
            if self.is_first:
                menu.addAction("Unmark as First").triggered.connect(self.make_first)
            else:
                act = menu.addAction("Make it First")
                if self.has_first_in_path():
                    act.setEnabled(False)
                    act.setText("Make it First (Chain has start)")
                else:
                    act.triggered.connect(self.make_first)
            menu.addSeparator()

        # 4. influence toggles for elementary actions
        if isinstance(self, ElementaryAction) and self.available_influences:
            influences_menu = menu.addMenu("Influences")
            for influence in self.available_influences:
                inf_id = influence.get("id")
                if not inf_id:
                    continue
                inf_action = influence.get("action")
                is_locked = inf_action in LOCKED_INFLUENCE_ACTIONS
                menu_action = influences_menu.addAction(inf_id)
                menu_action.setCheckable(True)
                menu_action.setChecked(True if is_locked else inf_id not in self.disabled_influences)
                if is_locked:
                    menu_action.setEnabled(False)
                else:
                    menu_action.toggled.connect(
                        lambda checked, _id=inf_id: self._toggle_influence(_id, checked)
                    )
            menu.addSeparator()
        
        menu.addAction("Delete").triggered.connect(self.delete_block)
        menu.exec(event.screenPos())

    def _toggle_influence(self, influence_id: str, enabled: bool) -> None:
        for influence in self.available_influences:
            if influence.get("id") == influence_id and influence.get("action") in LOCKED_INFLUENCE_ACTIONS:
                return
        if enabled:
            self.disabled_influences.discard(influence_id)
        else:
            self.disabled_influences.add(influence_id)
        if self.editor:
            self.editor.update_support_logic()
    
    def toggle_orientation(self, target_orient=None):
        """switches or sets orientation (140x60 <-> 60x140)."""
        self.prepareGeometryChange()
        
        if target_orient:
            self.orientation = target_orient
        else:
            self.orientation = "vertical" if self.orientation == "horizontal" else "horizontal"
        
        if self.orientation == "vertical":
            self.setRect(0, 0, 60, 140)
        else:
            self.setRect(0, 0, 140, 60)
            
        self.update_text()
        self.update()
        
        if self.editor:
            self.editor.reflow_entire_cluster(self)

    def _get_spaced_text(self, text):
        """inserts spaces before uppercase letters in a camelcase string."""
        result = ""
        for i, char in enumerate(text):
            if i > 0 and char.isupper():
                result += " " + char
            else:
                result += char
        return result
    
    def has_first_in_path(self):
        """Checks if any block in the current logical path (upstream or downstream) is already 'is_first'."""
        
        # Check Upstream (Ancestors)
        visited_up = set()
        def check_up(b):
            if not b or b in visited_up: return False
            visited_up.add(b)
            if b != self and getattr(b, 'is_first', False): return True
            # Action flow ancestors
            parents = [b.prev_block]
            if b.above_block and not isinstance(b.above_block, ChemicalBlock):
                parents.append(b.above_block)
            return any(check_up(p) for p in parents)

        # Check Downstream (Descendants)
        visited_down = set()
        def check_down(b):
            if not b or b in visited_down: return False
            visited_down.add(b)
            if b != self and getattr(b, 'is_first', False): return True
            # Action flow descendants
            children = [b.next_block]
            if b.below_block and not isinstance(b.below_block, ChemicalBlock):
                children.append(b.below_block)
            return any(check_down(c) for c in children)

        return check_up(self) or check_down(self)

    def make_first(self):
        """Toggles the 'is_first' state and isolates the head if activating."""
        if not self.editor: return
        self.prepareGeometryChange()

        if self.is_first:
            self.is_first = False
        else:
            self.is_first = True
            # Store neighbors for reflow
            old_p, old_a = self.prev_block, self.above_block
            
            # Break incoming connections (An entry point cannot have parents)
            if self.prev_block:
                self.prev_block.next_block = None
                self.prev_block = None
            if self.above_block and not isinstance(self.above_block, ChemicalBlock):
                self.above_block.below_block = None
                self.above_block = None
            
            # Close the gaps left behind
            if old_p: self.editor.reflow_entire_cluster(old_p)
            if old_a: self.editor.reflow_entire_cluster(old_a)

        self.update_visual_style()
        self.update()
        self.editor.reflow_entire_cluster(self)
        self.editor.update_linked_sequence()
    
    def move_chain(self, dx, dy):
        """moves the entire graph including all branches (actions, chemicals, subproducts)."""
        visited = set()
        def _move_recursive(b):
            if not b or b in visited: return
            visited.add(b)
            b.setPos(b.pos().x() + dx, b.pos().y() + dy)
            # follow all directions
            _move_recursive(b.prev_block)
            _move_recursive(b.next_block)
            _move_recursive(b.above_block)
            _move_recursive(b.below_block)
            _move_recursive(b.chem_below)
            if hasattr(b, 'subproduct_below'):
                _move_recursive(b.subproduct_below)
            
        _move_recursive(self)

    def _get_field_widget(self, key, value):
        """Creates appropriate widget based on FIELD_CONFIG registry."""
        config = FIELD_CONFIG.get(key.lower(), {})
        f_type = config.get("type", "text")
        
        if f_type == "unit":
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)

            edit = QLineEdit()
            edit.setPlaceholderText(config.get("placeholder", "Value"))
            
            v_min = -273.15 if key.lower() == KEY_TEMPERATURE else 0.0
            configure_unit_decimal_input(edit, min_value=v_min)

            combo = QComboBox()
            # Unit fields should always have a concrete default unit selected
            combo.addItems(config.get("units", []))

            str_val = str(value).strip()
            if " " in str_val:
                parts = str_val.split(" ")
                edit.setText(format_decimal_for_input(parts[0]))
                idx = combo.findText(parts[1])
                if idx >= 0: combo.setCurrentIndex(idx)
            elif str_val and str_val not in config.get("defaults", []):
                edit.setText(format_decimal_for_input(str_val))
            else:
                edit.setText("")

            layout.addWidget(edit, 2)
            layout.addWidget(combo, 1)
            return container, (edit, combo)
        
        elif f_type == "dropdown":
            combo = QComboBox()
            # Add placeholder item first so untouched fields export as ""
            combo.addItem("Select...")
            combo.addItems(config.get("options", []))
            # Set the current value only if it exists and is not empty
            current_val = str(value).strip()
            if current_val:
                idx = combo.findText(current_val)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            return combo, combo

        elif f_type == "single_chemical":
            chem_value = value if isinstance(value, dict) else {}
            single_ref = _SingleChemicalRef(chem_value)

            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(6)

            button_layout = QHBoxLayout()
            button_layout.setContentsMargins(0, 0, 0, 0)
            button_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

            add_btn = QToolButton()
            add_btn.setText("+ Add")
            add_btn.setToolTip(config.get("placeholder", "Add chemical"))
            add_btn.setAutoRaise(False)
            add_btn.setFixedHeight(28)
            add_btn.setMinimumWidth(60)
            add_btn.setStyleSheet(ADD_BUTTON_STYLE)
            add_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

            row_container = QWidget()
            row_layout = QVBoxLayout(row_container)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)

            def _row_label(chem: dict) -> str:
                chem_type = chem.get("chemical_type", "Unknown")
                name = chem.get(KEY_NAME, "").strip()
                formula = chem.get(KEY_FORMULA, "").strip()
                if name:
                    return f"{chem_type}: {name}"
                if formula:
                    return f"{chem_type}: {formula}"
                return chem_type

            def _update_row():
                while row_layout.count():
                    child = row_layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                has_chem = bool(single_ref.value)
                add_btn.setVisible(not has_chem)
                if not has_chem:
                    return

                chem = single_ref.value
                row_text = _row_label(chem)
                row_widget = QWidget()
                row_widget.setFixedHeight(28)
                inner = QHBoxLayout(row_widget)
                inner.setContentsMargins(0, 0, 0, 0)
                inner.setSpacing(6)

                text_label = QLabel()
                text_label.setToolTip(row_text)
                text_label.setStyleSheet(
                    "background-color: #e0e7ff; color: #3730a3; padding: 4px 8px; "
                    "border-radius: 4px; font-size: 11px; border: 1px solid #c7d2fe;"
                )
                text_label.setFixedHeight(28)
                text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                fm = QFontMetrics(text_label.font())
                text_label.setText(fm.elidedText(row_text, Qt.TextElideMode.ElideRight, 220))

                edit_btn = QToolButton()
                edit_btn.setText("✎")
                edit_btn.setFixedSize(22, 22)
                edit_btn.setStyleSheet(LIST_ICON_BUTTON_STYLE)

                remove_btn = QToolButton()
                remove_btn.setText("✕")
                remove_btn.setFixedSize(22, 22)
                remove_btn.setStyleSheet(
                    LIST_ICON_BUTTON_STYLE
                    + "QToolButton { font-weight: bold; color: #6b7280; }"
                    + "QToolButton:hover { color: #ef4444; }"
                )

                def _remove():
                    single_ref.value = {}
                    _update_row()

                def _edit():
                    from .editor import pick_embedded_chemical

                    parent_dialog = self.editor if self.editor else self
                    picked = pick_embedded_chemical(
                        parent_dialog,
                        single_ref.value,
                        for_solvent=config.get("for_solvent", key == KEY_SOLVENT),
                    )
                    if picked:
                        single_ref.value = picked
                        _update_row()

                edit_btn.clicked.connect(_edit)
                remove_btn.clicked.connect(_remove)
                inner.addWidget(text_label, 1)
                inner.addWidget(edit_btn, 0, Qt.AlignmentFlag.AlignVCenter)
                inner.addWidget(remove_btn, 0, Qt.AlignmentFlag.AlignVCenter)
                row_layout.addWidget(row_widget)

            def _add():
                from .editor import pick_embedded_chemical

                parent_dialog = self.editor if self.editor else self
                picked = pick_embedded_chemical(
                    parent_dialog,
                    {},
                    for_solvent=config.get("for_solvent", key == KEY_SOLVENT),
                )
                if picked:
                    single_ref.value = picked
                    _update_row()

            add_btn.clicked.connect(_add)
            button_layout.addWidget(add_btn)
            layout.addLayout(button_layout)
            layout.addWidget(row_container)
            _update_row()

            return container, single_ref

        elif f_type == "list":
            # Create compact chemical list widget with add button and tags
            list_value = value if isinstance(value, list) else (value or [])
            is_gas_list = key == KEY_GASES

            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(6)

            # Add button row
            button_layout = QHBoxLayout()
            button_layout.setContentsMargins(0, 0, 0, 0)
            button_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
            
            # Compact add button that shows the label without causing elision
            add_btn = QToolButton()
            add_btn.setText("+ Add")
            add_btn.setToolTip("Add chemical")
            # make it visible: keep compact height but allow enough width for the text
            add_btn.setAutoRaise(False)
            add_btn.setFixedHeight(28)
            add_btn.setMinimumWidth(60)
            add_btn.setStyleSheet(ADD_BUTTON_STYLE)
            add_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            
            def _add_chemical():
                from .editor import (
                    MixtureChemicalDialog,
                    MixtureChemicalParametersDialog,
                    UnifiedChemicalDetailsDialog,
                    get_chemical_default_params,
                    normalize_preparation_procedure,
                )

                parent_dialog = self.editor if self.editor else self

                dlg = MixtureChemicalDialog(parent_dialog)
                if dlg.exec() != QDialog.Accepted:
                    return

                details_dialog = UnifiedChemicalDetailsDialog(parent_dialog)
                if details_dialog.exec() != QDialog.Accepted:
                    return

                params_dlg = MixtureChemicalParametersDialog(
                    dlg.selected_chemical_type,
                    parent_dialog,
                    initial_params=get_chemical_default_params(dlg.selected_chemical_type),
                )
                if params_dlg.exec() != QDialog.Accepted:
                    return

                new_chem = {
                    "chemical_type": dlg.selected_chemical_type,
                    **params_dlg.chemical_params,
                    **details_dialog.first_level_fields,
                    KEY_CONCENTRATION: dlg.concentration,
                }
                if details_dialog.imported_procedure:
                    new_chem[KEY_PREPARATION_PROCEDURE] = normalize_preparation_procedure(
                        details_dialog.imported_procedure
                    )

                chem_name = new_chem.get(KEY_NAME, "").strip()
                if not chem_name:
                    QMessageBox.warning(
                        parent_dialog,
                        "Missing Chemical Name",
                        f"Chemical '{dlg.selected_chemical_type}' must have a name field filled.",
                    )
                    return

                list_value.append(new_chem)
                _update_tags()
            
            add_btn.clicked.connect(_add_chemical)
            button_layout.addWidget(add_btn)
            layout.addLayout(button_layout)
            
            # Rows area for showing added items
            rows_container = QWidget()
            rows_layout = QVBoxLayout(rows_container)
            rows_layout.setContentsMargins(0, 0, 0, 0)
            rows_layout.setSpacing(4)
            
            def _update_tags():
                # Clear existing rows
                while rows_layout.count():
                    child = rows_layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                
                # Add one compact row per chemical
                for idx, chem in enumerate(list_value):
                    if is_gas_list:
                        row_text = format_gas_entry_label(chem)
                    else:
                        chem_type = chem.get("chemical_type", "Unknown")
                        formula = chem.get(KEY_FORMULA, "—")
                        conc = chem.get(KEY_CONCENTRATION, "")
                        row_text = f"{chem_type}: {formula}"
                        if conc:
                            row_text += f" ({conc})"

                    row_widget = QWidget()
                    row_widget.setFixedHeight(28)
                    row_layout = QHBoxLayout(row_widget)
                    row_layout.setContentsMargins(0, 0, 0, 0)
                    row_layout.setSpacing(6)

                    text_label = QLabel()
                    text_label.setToolTip(row_text)
                    text_label.setStyleSheet(
                        "background-color: #e0e7ff; color: #3730a3; padding: 4px 8px; "
                        "border-radius: 4px; font-size: 11px; border: 1px solid #c7d2fe;"
                    )
                    text_label.setFixedHeight(28)
                    text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                    text_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
                    fm = QFontMetrics(text_label.font())
                    text_label.setText(fm.elidedText(row_text, Qt.TextElideMode.ElideRight, 220))
                    
                    # Edit and Remove buttons
                    edit_btn = QToolButton()
                    edit_btn.setText("✎")
                    edit_btn.setFixedSize(22, 22)
                    edit_btn.setStyleSheet(LIST_ICON_BUTTON_STYLE)

                    remove_btn = QToolButton()
                    remove_btn.setText("✕")
                    remove_btn.setFixedSize(22, 22)
                    remove_btn.setStyleSheet(
                        LIST_ICON_BUTTON_STYLE
                        + "QToolButton { font-weight: bold; color: #6b7280; }"
                        + "QToolButton:hover { color: #ef4444; }"
                    )

                    def _remove(check=False, i=idx):
                        if 0 <= i < len(list_value):
                            del list_value[i]
                            _update_tags()

                    def _edit(check=False, i=idx):
                        from .editor import (
                            MixtureChemicalDialog,
                            MixtureChemicalParametersDialog,
                            UnifiedChemicalDetailsDialog,
                            get_chemical_default_params,
                            normalize_preparation_procedure,
                        )
                        parent_dialog = self.editor if self.editor else self
                        chem = list_value[i]

                        dlg = MixtureChemicalDialog(
                            parent_dialog,
                            initial_type=chem.get("chemical_type", "Substance"),
                            initial_concentration=chem.get(KEY_CONCENTRATION, ""),
                        )
                        if dlg.exec() != QDialog.Accepted:
                            return

                        # First Level Chemical Details (ID, Producer, Purity, Procedure)
                        details_dialog = UnifiedChemicalDetailsDialog(parent_dialog)
                        # Pre-fill with existing values
                        details_dialog.id_edit.setText(chem.get(KEY_ENTITY_ID, ""))
                        details_dialog.producer_edit.setText(chem.get(KEY_PRODUCER, ""))
                        details_dialog.purity_edit.setText(chem.get(KEY_ENTITY_PURITY, ""))
                        details_dialog.cas_edit.setText(chem.get(KEY_CAS_NUMBER, ""))
                        if KEY_PREPARATION_PROCEDURE in chem:
                            details_dialog.imported_procedure = normalize_preparation_procedure(
                                chem[KEY_PREPARATION_PROCEDURE]
                            )
                            details_dialog._set_status("✓ Procedure loaded", "success")
                        if details_dialog.exec() != QDialog.Accepted:
                            return

                        params_dlg = MixtureChemicalParametersDialog(
                            dlg.selected_chemical_type,
                            parent_dialog,
                            initial_params={**get_chemical_default_params(dlg.selected_chemical_type), **chem},
                        )
                        if params_dlg.exec() != QDialog.Accepted:
                            return

                        updated = {"chemical_type": dlg.selected_chemical_type, **params_dlg.chemical_params, **details_dialog.first_level_fields, KEY_CONCENTRATION: dlg.concentration}
                        if details_dialog.imported_procedure:
                            updated[KEY_PREPARATION_PROCEDURE] = normalize_preparation_procedure(
                                details_dialog.imported_procedure
                            )
                        
                        # Validate that chemical has a name (required for all chemicals)
                        chem_name = updated.get(KEY_NAME, "").strip()
                        if not chem_name:
                            QMessageBox.warning(parent_dialog, "Missing Chemical Name", f"Chemical '{dlg.selected_chemical_type}' must have a name field filled.")
                            return
                        
                        list_value[i] = updated
                        _update_tags()

                    edit_btn.clicked.connect(_edit)
                    remove_btn.clicked.connect(_remove)

                    row_layout.addWidget(text_label, 1)
                    row_layout.addWidget(edit_btn, 0, Qt.AlignmentFlag.AlignVCenter)
                    row_layout.addWidget(remove_btn, 0, Qt.AlignmentFlag.AlignVCenter)

                    rows_layout.addWidget(row_widget)
                
                rows_layout.addStretch()
            
            _update_tags()
            layout.addWidget(rows_container)
            
            # tracker will be the actual list object
            return container, list_value
        
        else:
            edit = QLineEdit(str(value))
            edit.setPlaceholderText(config.get("placeholder", f"Enter {key}..."))
            if self.action == "Repeat" and key == KEY_AMOUNT:
                edit.setValidator(QIntValidator(1, 999_999, edit))
            return edit, edit

    def open_editor(self):
        """opens a dialog to edit block parameters. skips if no parameters."""
        if not self.params:
            return

        self._editor_accepted = False

        is_chemical = isinstance(self, ChemicalBlock)
        params_for_dialog = self.params.copy()

        is_fixed_mixture = self.action == "Dispersion"
        can_switch_to_mixture = (
            self.action in {"BioProducts", "HeterogeneousCatalysts", "Molecules", "Polymers", "Media"}
            and not is_fixed_mixture
        )
        if is_fixed_mixture:
            params_for_dialog[KEY_ENTITY_TYPE] = "Mixture"
            params_for_dialog.setdefault(KEY_CHEMICAL_LIST, [])
            params_for_dialog.setdefault(KEY_SOLVENT, {})
        if can_switch_to_mixture:
            params_for_dialog.setdefault(KEY_CHEMICAL_LIST, [])
        if self.action == "Media":
            params_for_dialog.setdefault(KEY_ENTITY_TYPE, "Substance")
        params_for_dialog.pop(KEY_MIXTURE_TYPE, None)

        hidden_chemical_keys = [KEY_PREPARATION_PROCEDURE, KEY_ENTITY_ID, KEY_PRODUCER, KEY_ENTITY_PURITY, KEY_CAS_NUMBER]

        dialog = EditDialog(self.editor if self.editor else None)
        dialog.setWindowTitle(self.action)
        dialog.setMinimumWidth(400)
        main_layout = QVBoxLayout(dialog)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(20, 20, 20, 20)

        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        main_layout.addLayout(form_layout)

        input_map = {}
        row_widgets = {}
        row_labels = {}  # Store label widgets for visibility control

        if is_chemical:
            ordered_keys = [key for key in params_for_dialog.keys() if key not in hidden_chemical_keys]
        else:
            ordered_keys = list(params_for_dialog.keys())

        # Extract entity_type if exists and move it to the front
        entity_type_key = None
        if KEY_ENTITY_TYPE in ordered_keys:
            ordered_keys.remove(KEY_ENTITY_TYPE)
            if not is_fixed_mixture:
                entity_type_key = KEY_ENTITY_TYPE
        if is_fixed_mixture:
            ordered_keys = [k for k in ordered_keys if k != KEY_ENTITY_TYPE]

        required_keys: list[str] = []
        optional_keys: list[str] = []
        entity_type_value = params_for_dialog.get(KEY_ENTITY_TYPE, "")
        force_required_keys = set()
        if self.action in {"Mixture", "Dispersion"}:
            force_required_keys.update({KEY_CHEMICAL_LIST})
        if is_fixed_mixture:
            force_required_keys.add(KEY_SOLVENT)

        main_conditional_keys: list[str] = []
        if can_switch_to_mixture:
            main_conditional_keys.append(KEY_CHEMICAL_LIST)
        if is_fixed_mixture:
            main_conditional_keys = [KEY_SOLVENT]
        
        for key in ordered_keys:
            if key in main_conditional_keys:
                continue
            if key == KEY_MIXTURE_TYPE:
                continue
            # When entity_type is Mixture, chemical_list is required
            if key in force_required_keys or (entity_type_value == "Mixture" and key == KEY_CHEMICAL_LIST):
                required_keys.append(key)
            elif is_field_required(key, params=params_for_dialog, action_name=self.action):
                required_keys.append(key)
            else:
                optional_keys.append(key)

        def _add_field(target_layout: QFormLayout, key: str, show: bool = True) -> dict | None:
            """Add field to layout. Returns row index if added, None if hidden."""
            if not show:
                return None
                
            value = params_for_dialog.get(key, "")
            # Retrieve label from config. Fallback to capitalized key string
            label = field_label(key, self.action)

            widget, tracker = self._get_field_widget(key, value)
            # Explicitly create label widget to ensure proper visibility control
            label_widget = QLabel(label + ":")
            target_layout.addRow(label_widget, widget)
            input_map[key] = tracker
            row_widgets[key] = widget
            row_labels[key] = label_widget  # Store label widget for later visibility control
            return {"widget": widget, "tracker": tracker, "label": label}

        # Add entity_type field first if it exists
        entity_type_widget = None
        if entity_type_key:
            result = _add_field(form_layout, entity_type_key, show=True)
            if result:
                entity_type_widget = result["widget"]
                # Add visual separator after entity_type field
                separator = QFrame()
                separator.setFrameShape(QFrame.HLine)
                separator.setFrameShadow(QFrame.Sunken)
                separator.setStyleSheet("color: #d1d5db;")
                form_layout.addRow(separator)

        for key in required_keys:
            _add_field(form_layout, key)

        for key in main_conditional_keys:
            _add_field(form_layout, key)

        # For chemicals that can switch between Substance and Mixture types,
        # ensure NAME is added to the visible fields if not already present
        if can_switch_to_mixture and KEY_NAME not in row_labels:
            if KEY_NAME in optional_keys:
                optional_keys.remove(KEY_NAME)  # Will be added below
            _add_field(form_layout, KEY_NAME)

        advanced_container = None
        advanced_toggle = None
        if optional_keys:
            advanced_toggle = QToolButton()
            advanced_toggle.setText("Advanced parameters")
            advanced_toggle.setCheckable(True)
            advanced_toggle.setChecked(False)
            advanced_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            advanced_toggle.setArrowType(Qt.ArrowType.RightArrow)
            advanced_toggle.setStyleSheet(
                "QToolButton {"
                "  background-color: #f8fafc;"
                "  color: #334155;"
                "  border-radius: 8px;"
                "  padding: 6px 12px;"
                "  font-weight: 600;"
                "  border: 1px solid #e2e8f0;"
                "}"
                "QToolButton:hover { background-color: #f1f5f9; }"
                "QToolButton:pressed { background-color: #e2e8f0; }"
            )

            advanced_container = QWidget()
            advanced_layout = QFormLayout(advanced_container)
            advanced_layout.setSpacing(12)
            advanced_container.setVisible(False)

            def _toggle_advanced(checked: bool) -> None:
                advanced_container.setVisible(checked)
                advanced_toggle.setArrowType(
                    Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
                )
                dialog.adjustSize()

            advanced_toggle.toggled.connect(_toggle_advanced)

            main_layout.addWidget(advanced_toggle)
            main_layout.addWidget(advanced_container)

            for key in optional_keys:
                _add_field(advanced_layout, key)

        def _update_conditional_fields() -> None:
            current_type = entity_type_widget.currentText() if entity_type_widget else entity_type_value
            show_mixture_fields = is_fixed_mixture or (current_type == "Mixture" and can_switch_to_mixture)

            # NAME field is always visible (Mixtures and regular entities both have names)
            # Show/hide mixture-specific fields based on entity type
            for cond_key in main_conditional_keys:
                if cond_key in row_widgets and cond_key in row_labels:
                    should_show = show_mixture_fields
                    row_labels[cond_key].setVisible(should_show)
                    row_widgets[cond_key].setVisible(should_show)

            # Resize dialog to adapt to shown/hidden fields
            main_layout.invalidate()
            QTimer.singleShot(0, dialog.adjustSize)

        # Handler for entity_type changes to show/hide conditional fields
        if entity_type_widget and isinstance(entity_type_widget, QComboBox):
            def on_entity_type_changed():
                _update_conditional_fields()
            
            entity_type_widget.currentTextChanged.connect(on_entity_type_changed)

        _update_conditional_fields()

        preview_btn = None
        # Check if chemical has imported procedure (visually indicated)
        if is_chemical and self.imported_procedure:
            preview_btn = QPushButton("Preview")

            def show_preview():
                procedure = None
                if self.editor and getattr(self, "block_id", None) is not None:
                    procedure = self.editor.get_open_entity_procedure(self.block_id)
                if not procedure:
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.information(dialog, "Preview", "No procedure available for this chemical entity.")
                    return

                self._preview_window = ProcedurePreviewDialog(procedure, parent=dialog)
                self._preview_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
                self._preview_window.show()

            preview_btn.clicked.connect(show_preview)

        save_btn = QPushButton("Save Changes")
        button_row = QHBoxLayout()
        if preview_btn:
            button_row.addWidget(preview_btn)
        button_row.addStretch()
        button_row.addWidget(save_btn)
        main_layout.addLayout(button_row)

        def apply_changes():
            new_params = self.params.copy()
            current_type = entity_type_widget.currentText() if entity_type_widget else entity_type_value

            def is_empty_value(val):
                if val is None:
                    return True
                if isinstance(val, str):
                    return val.strip() == ""
                if isinstance(val, (list, dict, tuple, set)):
                    return len(val) == 0
                return False

            for k, tracker in input_map.items():
                if isinstance(tracker, tuple):
                    # For Unit fields (LineEdit, ComboBox)
                    edit_field, combo_field = tracker
                    raw_value = edit_field.text().strip()
                    unit_text = combo_field.currentText().strip()
                    # enforce numeric-only values for unit fields
                    if raw_value:
                        try:
                            validate_decimal_input(raw_value)
                        except ValueError:
                            label = FIELD_CONFIG.get(k.lower(), {}).get("label", k.capitalize())
                            QMessageBox.warning(
                                dialog,
                                "Invalid Value",
                                f"'{label}' must be a number using '.' as decimal separator (e.g. 12.5).",
                            )
                            edit_field.setFocus()
                            return
                    value = f"{raw_value} {unit_text}" if raw_value else ""
                elif isinstance(tracker, QComboBox):
                    # For standalone Dropdown fields
                    value = tracker.currentText().strip()
                    # Convert placeholder "Select..." back to empty string
                    if value == "Select...":
                        value = ""
                elif isinstance(tracker, list):
                    # For list fields, tracker is the list itself
                    value = tracker
                elif isinstance(tracker, _SingleChemicalRef):
                    value = dict(tracker.value)
                else:
                    # For standard Text fields (LineEdit)
                    value = tracker.text().strip()

                if k == KEY_AMOUNT and self.action == "Repeat" and value:
                    try:
                        value = str(validate_repeat_amount(value))
                    except ValueError:
                        QMessageBox.warning(
                            dialog,
                            "Invalid Value",
                            "'Amount' must be a whole number greater than or equal to 1 (no decimals).",
                        )
                        tracker.setFocus()
                        return

                if k == KEY_OPEN_FLAME:
                    value = normalize_boolean(value)
                elif k in {
                    KEY_DURATION, KEY_ADD_QUANTITY, KEY_TEMPERATURE, KEY_MIN_SIZE, KEY_MAX_SIZE, KEY_SPEED,
                    KEY_FLOW_RATE, KEY_PRESSURE, KEY_RAMP, KEY_POWER, KEY_VOLUME,
                    KEY_QUANTITY, KEY_CONCENTRATION
                }:
                    value = quantity_to_text(value)

                field_required = (
                    k in force_required_keys
                    or is_field_required(k, params=new_params, action_name=self.action)
                )
                if field_required and is_empty_value(value):
                    label = field_label(k, self.action)
                    QMessageBox.warning(dialog, "Missing Required Field", f"'{label}' is required.")
                    if isinstance(tracker, tuple):
                        tracker[0].setFocus()
                    elif isinstance(tracker, _SingleChemicalRef):
                        pass
                    elif isinstance(tracker, list):
                        pass
                    else:
                        tracker.setFocus()
                    return

                new_params[k] = value

            for req_key in force_required_keys:
                if req_key not in new_params:
                    continue
                req_value = new_params[req_key]
                req_label = field_label(req_key, self.action)
                if req_key == KEY_CHEMICAL_LIST:
                    if not isinstance(req_value, list) or len(req_value) == 0:
                        QMessageBox.warning(
                            dialog,
                            "Missing Required Field",
                            f"'{req_label}' is required. Add at least one chemical.",
                        )
                        return
                elif req_key == KEY_SOLVENT:
                    if not embedded_chemical_filled(req_value):
                        QMessageBox.warning(
                            dialog,
                            "Missing Required Field",
                            f"'{req_label}' is required. Use '+ Add' to select a chemical.",
                        )
                        return

            if is_fixed_mixture:
                new_params[KEY_ENTITY_TYPE] = "Mixture"
                new_params.setdefault(KEY_CHEMICAL_LIST, [])
            elif can_switch_to_mixture:
                if current_type == "Mixture":
                    new_params[KEY_ENTITY_TYPE] = "Mixture"
                    new_params.setdefault(KEY_CHEMICAL_LIST, [])
                else:
                    new_params[KEY_ENTITY_TYPE] = "Substance"
                    new_params.pop(KEY_CHEMICAL_LIST, None)
            new_params.pop(KEY_MIXTURE_TYPE, None)

            self.params.update(new_params)
            self._editor_accepted = True

            self.update_text()
            if self.editor:
                self.editor.refresh_procedure_guide()
            dialog.set_accepted()
            dialog.accept()

        save_btn.clicked.connect(apply_changes)
        dialog.adjustSize()
        dialog.exec()
    
    def get_editor_accepted(self) -> bool:
        """Return whether the last editor dialog was accepted by the user."""
        return getattr(self, '_editor_accepted', False)


class ElementaryAction(Block):
    """Elementary action block - inherits from ActionBlock with purple color"""
    def update_visual_style(self):
        """Update the visual style based on first status and connected state"""
        if self.is_first:
            self.setBrush(QColor(255, 159, 64))  # Modern orange for first block
        else:
            self.setBrush(QColor(107, 76, 255))  # Modern purple for normal blocks
        
        if self.is_first:
            self.default_pen = QPen(QColor(230, 126, 34), 3)  # Darker orange
        else:
            self.default_pen = QPen(QColor(88, 56, 220), 3)  # Darker purple
        
        if self.connected:
            self.setPen(QPen(QColor(255, 193, 7), 3))  # Modern yellow
        else:
            self.setPen(self.default_pen)


class SupportAction(Block):
    """Support action block - inherits from ActionBlock with blue color"""
    def update_visual_style(self):
        """Update the visual style based on first status and connected state"""
        if self.is_first:
            self.setBrush(QColor(255, 159, 64))  # Modern orange for first block
        else:
            self.setBrush(QColor(52, 152, 219))  # Modern blue for support blocks
        
        if self.is_first:
            self.default_pen = QPen(QColor(230, 126, 34), 3)  # Darker orange
        else:
            self.default_pen = QPen(QColor(41, 128, 185), 3)  # Darker blue
        
        if self.connected:
            self.setPen(QPen(QColor(255, 193, 7), 3))  # Modern yellow
        else:
            self.setPen(self.default_pen)


class ChemicalBlock(Block):
    """Chemical action block"""
    def __init__(self, action, params, editor=None):
        QGraphicsRectItem.__init__(self, 0, 0, 120, 50)
        self.action = action
        self.params = params
        self.editor = editor
        self.imported_procedure = None
        self.block_id = None
        
        self.orientation = "horizontal" 
        
        self.next_block = None  
        self.prev_block = None  
        self.below_block = None  
        self.above_block = None  
        self.chem_below = None 
        self.is_first = False
        self.connected = False
        self.chain_drag_mode = False
        
        # Hover tooltip support
        self.hover_timer = QTimer()
        self.hover_timer.timeout.connect(self.show_details_tooltip)
        self.hover_timer.setSingleShot(True)
        self.setAcceptHoverEvents(True)

        self.setFlags(
            QGraphicsRectItem.ItemIsMovable |
            QGraphicsRectItem.ItemIsSelectable
        )
        self.update_visual_style()

        self.text = QGraphicsTextItem(self)
        self.update_text()
    
    def paint(self, painter, option, widget=None):
        """paints a simple rectangle for chemical entities without chevrons."""
        from PySide6.QtGui import QPainter

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        m = 4 # margin to match action blocks line alignment
        
        # draw main rectangle body
        painter.setOpacity(1.0)
        painter.setBrush(self.brush())
        painter.setPen(self.pen())
        painter.drawRect(rect.adjusted(m, m, -m, -m))
    
    def update_visual_style(self):
        """Update the visual style based on first status and connected state"""
        if self.is_first:
            self.setBrush(QColor(255, 159, 64))  # Modern orange for first block
        else:
            self.setBrush(QColor(46, 204, 113))  # Modern green for chemical blocks
        
        if self.is_first:
            self.default_pen = QPen(QColor(230, 126, 34), 3)  # Darker orange
        else:
            self.default_pen = QPen(QColor(39, 174, 96), 3)  # Darker green
        
        if self.connected:
            self.setPen(QPen(QColor(255, 193, 7), 3))  # Modern yellow
        else:
            self.setPen(self.default_pen)
    
    def toggle_orientation(self, target_orient=None):
        """switches chemical orientation (120x50 <-> 50x120)."""
        self.prepareGeometryChange()
        
        if target_orient:
            self.orientation = target_orient
        else:
            self.orientation = "vertical" if self.orientation == "horizontal" else "horizontal"
        
        if self.orientation == "vertical":
            self.setRect(0, 0, 50, 120)
        else:
            self.setRect(0, 0, 120, 50)
            
        self.update_text()
        self.update()

    def update_text(self):
        """splits chemical name into 2 lines and centers it."""
        raw_name = self.params.get(KEY_NAME, self.action) or self.action
        # reuse the balancing logic from the base Block class
        display_text = self._get_balanced_text(raw_name)
        self.text.setPlainText(display_text)
        
        font = QFont("Segoe UI", 8, QFont.Bold)
        self.text.setFont(font)
        self.text.setDefaultTextColor(QColor(255, 255, 255))
        
        # align lines to center
        option = self.text.document().defaultTextOption()
        option.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text.document().setDefaultTextOption(option)
        
        block_rect = self.rect()
        
        if self.orientation == "horizontal":
            self.text.setRotation(0)
            self.text.setTextWidth(block_rect.width())
            x = 0
            y = (block_rect.height() - self.text.boundingRect().height()) / 2
        else:
            self.text.setRotation(90)
            self.text.setTextWidth(block_rect.height())
            # center rotated text
            x = (block_rect.width() + self.text.boundingRect().height()) / 2
            y = (block_rect.height() - self.text.boundingRect().width()) / 2
            
        self.text.setPos(x, y)

    def to_linkml_dict(self):
        """Return a LinkML-aligned representation of this chemical block."""
        payload = chemical_to_linkml_dict(self.action, self.params)
        payload["block_id"] = self.block_id
        return payload
