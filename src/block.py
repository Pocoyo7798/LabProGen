import json

from PySide6.QtWidgets import (
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsScene, QGraphicsView,
    QGraphicsSimpleTextItem, QDialog, QFormLayout, QLineEdit, QPushButton,
    QMenu, QHBoxLayout, QComboBox, QWidget, QVBoxLayout, QLabel, QMessageBox
)
from PySide6.QtCore import QRectF, Qt, QTimer, QSizeF
from PySide6.QtGui import QPen, QColor, QFont, QDoubleValidator, QPainter
from .config import *
from .debug_flag import DEBUG_MODE


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
        if isinstance(preview_data, dict) and preview_data.get("preview_flows"):
            preview_data = {
                "protocol_name": preview_data.get("protocol_name", "laboratory procedure"),
                "total_flows": len(preview_data.get("preview_flows", [])),
                "flows": preview_data.get("preview_flows", []),
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
        if p_h: self.editor.reflow_entire_cluster(p_h)
        elif n_h: self.editor.reflow_entire_cluster(n_h)
        if p_v: self.editor.reflow_entire_cluster(p_v)
        elif n_v: self.editor.reflow_entire_cluster(n_v)

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
        if not isinstance(self, ChemicalBlock) and self.action != "SubProductCreation":
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
        
        menu.addAction("Delete").triggered.connect(self.delete_block)
        menu.exec(event.screenPos())
    
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
            val = QDoubleValidator(v_min, 999999.0, 2)
            val.setNotation(QDoubleValidator.Notation.StandardNotation)
            edit.setValidator(val)

            combo = QComboBox()
            combo.addItems(config.get("units", []))

            str_val = str(value).strip()
            if " " in str_val:
                parts = str_val.split(" ")
                edit.setText(parts[0])
                idx = combo.findText(parts[1])
                if idx >= 0: combo.setCurrentIndex(idx)
            elif str_val and str_val not in config.get("defaults", []):
                edit.setText(str_val)
            else:
                edit.setText("")

            layout.addWidget(edit, 2)
            layout.addWidget(combo, 1)
            return container, (edit, combo)
        
        elif f_type == "dropdown":
            combo = QComboBox()
            combo.addItems(config.get("options", []))
            # Set the current value if it exists in params
            current_val = str(value)
            idx = combo.findText(current_val)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            return combo, combo
        
        else:
            edit = QLineEdit(str(value))
            edit.setPlaceholderText(config.get("placeholder", f"Enter {key}..."))
            return edit, edit

    def open_editor(self):
        """opens a dialog to edit block parameters. skips if no parameters."""
        if not self.params:
            return

        is_chemical = isinstance(self, ChemicalBlock)
        params_for_dialog = self.params.copy()

        hidden_chemical_keys = [KEY_ENTITY_PRIVACY, KEY_ENTITY_ID, KEY_PRODUCER, KEY_PRIVATE_PURITY]

        dialog = QDialog()
        dialog.setWindowTitle(self.action)
        dialog.setFixedWidth(400)
        form_layout = QFormLayout(dialog)
        form_layout.setSpacing(12)
        form_layout.setContentsMargins(20, 20, 20, 20)

        input_map = {}
        row_widgets = {}

        if is_chemical:
            ordered_keys = [key for key in params_for_dialog.keys() if key not in hidden_chemical_keys]
        else:
            ordered_keys = list(params_for_dialog.keys())

        for key in ordered_keys:
            value = params_for_dialog.get(key, "")
            # Retrieve label from config. Fallback to capitalized key string
            config = FIELD_CONFIG.get(key.lower(), {})
            label = config.get("label", key.capitalize())
            
            widget, tracker = self._get_field_widget(key, value)
            form_layout.addRow(label + ":", widget)
            input_map[key] = tracker
            row_widgets[key] = widget

        preview_btn = None
        if is_chemical and self.params.get(KEY_ENTITY_PRIVACY) == "Open Entity":
            preview_btn = QPushButton("Preview")

            def show_preview():
                procedure = None
                if self.editor and getattr(self, "block_id", None) is not None:
                    procedure = self.editor.get_open_entity_procedure(self.block_id)
                if not procedure:
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.information(dialog, "Preview", "No procedure imported for this open entity.")
                    return

                self._preview_window = ProcedurePreviewDialog(procedure, parent=dialog)
                self._preview_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
                self._preview_window.show()

            preview_btn.clicked.connect(show_preview)

        save_btn = QPushButton("Save Changes")
        if preview_btn:
            form_layout.addRow(preview_btn, save_btn)
        else:
            form_layout.addWidget(save_btn)

        def apply_changes():
            new_params = self.params.copy()

            for k, tracker in input_map.items():
                if isinstance(tracker, tuple):
                    # For Unit fields (LineEdit, ComboBox)
                    edit_field, combo_field = tracker
                    raw_value = edit_field.text().strip()
                    value = f"{raw_value} {combo_field.currentText()}" if raw_value else ""
                elif isinstance(tracker, QComboBox):
                    # For standalone Dropdown fields
                    value = tracker.currentText().strip()
                else:
                    # For standard Text fields (LineEdit)
                    value = tracker.text().strip()

                if is_field_required(k, params=new_params, action_name=self.action) and not value:
                    label = FIELD_CONFIG.get(k.lower(), {}).get("label", k.capitalize())
                    QMessageBox.warning(dialog, "Missing Required Field", f"'{label}' is required.")
                    if isinstance(tracker, tuple):
                        tracker[0].setFocus()
                    else:
                        tracker.setFocus()
                    return

                new_params[k] = value

            self.params.update(new_params)

            self.update_text()
            dialog.accept()

        save_btn.clicked.connect(apply_changes)
        dialog.exec()


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
