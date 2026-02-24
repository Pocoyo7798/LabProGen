import sys
from PySide6.QtWidgets import (
    QApplication, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsLineItem,
    QDialog, QFormLayout, QLineEdit, QPushButton, QMenu,
    QHBoxLayout, QComboBox, QWidget
)
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import QPen, QColor, QFont, QDoubleValidator
from config import FIELD_CONFIG, KEY_NAME, KEY_TEMPERATURE, KEY_DURATION, KEY_COMPONENT, KEY_FORMULA, KEY_SMILES, KEY_STRUCTURE
import debug_flag
import json

class Block(QGraphicsRectItem):
    def __init__(self, action, params, editor=None):
        super().__init__(0, 0, 140, 60)
        self.action = action
        self.params = params
        self.editor = editor
        
        # Pointers for Action Flow
        self.next_block = None   # Horizontal Right
        self.prev_block = None   # Horizontal Left
        self.below_block = None  # Vertical Down (Action)
        self.above_block = None  # Vertical Up (Action)
        
        # Pointer for Chemical Stack
        self.chem_below = None   # Points to the first ChemicalBlock
        
        self.orientation = "horizontal" # Default orientation
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
        """Paints the block with a centered notch on top that matches the incoming arrow size."""
        from PySide6.QtGui import QPainterPath, QPainter
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        w, h = rect.width(), rect.height()
        arrow_size = 18 
        m = 4 # margin
        path = QPainterPath()

        has_left_indent = self.prev_block is not None
        has_top_indent = self.above_block is not None and not isinstance(self.above_block, ChemicalBlock)
        is_horz = self.orientation == "horizontal"
        is_vert = self.orientation == "vertical"

        # --- 1. Start at top-left ---
        path.moveTo(m, m)

        # --- 2. Top edge ---
        if has_top_indent:
            # Notch width is 2x arrow size to accommodate the incoming vertical arrow
            notch_half_width = 26
            
            path.lineTo(w / 2 - notch_half_width, m) # Straight line to notch start
            path.lineTo(w / 2, m + arrow_size)       # Depth of the notch
            path.lineTo(w / 2 + notch_half_width, m) # Straight line to notch end
        
        # Stop before the Top-Right corner if we need to start a horizontal arrow
        if is_horz:
            path.lineTo(w - m - arrow_size, m)
        else:
            path.lineTo(w - m, m)

        # --- 3. Right edge ---
        if is_horz:
            path.lineTo(w - m, h / 2)
            path.lineTo(w - m - arrow_size, h - m)
        else:
            if is_vert:
                path.lineTo(w - m, h - m - arrow_size) # Stop before bottom arrow starts
            else:
                path.lineTo(w - m, h - m)

        # --- 4. Bottom edge ---
        if is_vert:
            path.lineTo(w / 2, h - m)
            path.lineTo(m, h - m - arrow_size)
        else:
            path.lineTo(m, h - m)

        # --- 5. Left edge ---
        if has_left_indent:
            path.lineTo(m + arrow_size, h / 2)
        
        path.closeSubpath()

        # Rendering
        painter.setOpacity(0.15)
        painter.setBrush(QColor(0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path.translated(2, 2)) # Shadow
        
        painter.setOpacity(1.0)
        painter.setBrush(self.brush())
        
        pen = QPen(self.pen())
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(path)
    
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

    def update_text(self):
        """splits text by uppercase letters and centers it."""
        # logic to split multiple words action names
        formatted_action = ""
        for i, char in enumerate(self.action):
            if i > 0 and char.isupper():
                formatted_action += "\n" + char
            else:
                formatted_action += char
        
        self.text.setPlainText(formatted_action)
        
        font = QFont("Segoe UI", 10)
        font.setBold(True)
        self.text.setFont(font)
        self.text.setDefaultTextColor(QColor(255, 255, 255))
        
        # adjust alignment
        option = self.text.document().defaultTextOption()
        option.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text.document().setDefaultTextOption(option)
        self.text.setTextWidth(self.rect().width()) # ensures alignment works
        
        text_rect = self.text.boundingRect()
        block_rect = self.rect()
        
        if self.orientation == "horizontal":
            self.text.setRotation(0)
            x = 0
            y = (block_rect.height() - text_rect.height()) / 2
        else:
            self.text.setRotation(90)
            # reposition for vertical orientation
            x = (block_rect.width() + text_rect.height()) / 2
            y = (block_rect.height() - text_rect.width()) / 2
            
        self.text.setPos(x, y)
    
    def mouseDoubleClickEvent(self, event):
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
        if not debug_flag.DEBUG_MODE or not self.editor:
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
        """Handle mouse press and detach block from chains before dragging."""
        if event.button() == Qt.RightButton:
            self.show_context_menu(event)
            return

        if self.editor:
            # handle vertical detachment
            old_above = self.above_block
            old_below = self.below_block

            if old_above or old_below:
                old_p, old_c = self.editor._pluck_vertical(self)
                if old_p:
                    self.editor.reflow_entire_cluster(old_p)
                if old_c:
                    self.editor.reflow_entire_cluster(old_c)

            # handle horizontal detachment for vertical blocks
            if self.orientation == "vertical":
                old_p, old_n = self.editor._pluck_horizontal(self)
                if old_p:
                    self.editor.reflow_entire_cluster(old_p)
                if old_n:
                    self.editor.reflow_entire_cluster(old_n)

        # move entire cluster if control is pressed
        if event.modifiers() == Qt.ControlModifier:
            self.chain_drag_mode = True
            self.setZValue(1000)
            super().mousePressEvent(event)
            return

        # normal single block movement
        self.setZValue(1000)
        super().mousePressEvent(event)
    
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
                    if debug_flag.DEBUG_MODE:
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
        """Show context menu. Only allows manual orientation for Action blocks."""
        menu = QMenu()

        is_connected = bool(self.prev_block or self.next_block or 
                            self.above_block or self.below_block or self.chem_below)

        # 1. Orientation toggle. Only for Actions, not for ChemicalBlocks
        if not isinstance(self, ChemicalBlock):
            label = "Set Vertical" if self.orientation == "horizontal" else "Set Horizontal"
            toggle_orient = menu.addAction(label)
            if is_connected:
                toggle_orient.setEnabled(False)
                toggle_orient.setText(f"{label} (Disconnect first)")
            else:
                toggle_orient.triggered.connect(self.toggle_orientation)
            menu.addSeparator()

        # 2. 'First' logic: Only for Actions
        if not isinstance(self, ChemicalBlock):
            if self.is_first:
                menu.addAction("Unmark as First").triggered.connect(self.make_first)
            else:
                action_first = menu.addAction("Make it First")
                if self.has_first_in_path():
                    action_first.setEnabled(False)
                    action_first.setText("Make it First (Chain already has a start)")
                else:
                    action_first.triggered.connect(self.make_first)
            menu.addSeparator()
        
        # 3. Delete
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
    
    def delete_block(self):
        """Removes the block and stitches all 3 possible chains (Horizontal, Vertical, Chemicals)."""
        if not self.editor: return

        # Remove from main list
        if self in self.editor.blocks:
            self.editor.blocks.remove(self)

        # Stitch Horizontal
        if self.prev_block or self.next_block:
            p, n = self.prev_block, self.next_block
            if p: p.next_block = n
            if n: n.prev_block = p
            # Reflow the remaining horizontal chain
            head = self.editor.find_chain_start(p if p else n)
            self.editor.reflow_chain(head)

        # Stitch Vertical Action Flow
        if self.above_block or self.below_block:
            # Only stitch if parent and child are Actions
            if not isinstance(self.above_block, ChemicalBlock):
                a, b = self.above_block, self.below_block
                if a: a.below_block = b
                if b: b.above_block = a
                # Reflow vertical
                top = self
                while top.above_block: top = top.above_block
                self.editor.reflow_chain(top)

        # Handle Chemical Stack
        if self.chem_below:
            # If we delete the action, the chemicals lose their parent
            self.chem_below.above_block = None

        # Clear its own pointers
        self.prev_block = self.next_block = self.above_block = self.below_block = self.chem_below = None
        
        if self.scene():
            self.scene().removeItem(self)
        self.editor.update_linked_sequence()

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
        """Moves the entire connected cluster as a single unit."""
        visited = set()
        def _move_recursive(b):
            if not b or b in visited: return
            visited.add(b)
            b.setPos(b.pos().x() + dx, b.pos().y() + dy)
            # Move all directions
            _move_recursive(b.prev_block)
            _move_recursive(b.next_block)
            _move_recursive(b.above_block)
            _move_recursive(b.below_block)
            _move_recursive(b.chem_below)
            
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
        
        else:
            edit = QLineEdit(str(value))
            edit.setPlaceholderText(config.get("placeholder", f"Enter {key}..."))
            return edit, edit

    def open_editor(self):
        """Opens a dialog to edit block parameters based on registry settings."""
        dialog = QDialog()
        dialog.setWindowTitle(self.action)
        dialog.setFixedWidth(400)
        form_layout = QFormLayout(dialog)
        form_layout.setSpacing(12)
        form_layout.setContentsMargins(20, 20, 20, 20)

        input_map = {}
        for key, value in self.params.items():
            # Retrieve label from config. Fallback to capitalized key string
            config = FIELD_CONFIG.get(key.lower(), {})
            label = config.get("label", key.capitalize())
            
            widget, tracker = self._get_field_widget(key, value)
            form_layout.addRow(label + ":", widget)
            input_map[key] = tracker

        save_btn = QPushButton("Save Changes")
        form_layout.addWidget(save_btn)

        def apply_changes():
            for k, tracker in input_map.items():
                if isinstance(tracker, tuple):
                    edit_field, combo_field = tracker
                    self.params[k] = f"{edit_field.text()} {combo_field.currentText()}"
                else:
                    self.params[k] = tracker.text()
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
        # Call parent's parent __init__ to avoid Block.__init__
        QGraphicsRectItem.__init__(self, 0, 0, 114, 30)
        self.action = action
        self.params = params
        self.editor = editor
        
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
        self.text.setPos(5, 10)
        self.update_text()
    
    def paint(self, painter, option, widget=None):
        """Paint a simple rectangle instead of the chevron shape"""
        from PySide6.QtGui import QPainter

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()

        # Draw shadow effect
        painter.setOpacity(0.15)
        painter.setBrush(QColor(0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(rect.translated(2, 2))
        
        # Draw main rectangle
        painter.setOpacity(1.0)
        painter.setBrush(self.brush())
        painter.setPen(self.pen())
        painter.drawRect(rect)
    
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
        """switches or sets chemical orientation (114x30 <-> 30x114)."""
        self.prepareGeometryChange()
        
        if target_orient:
            self.orientation = target_orient
        else:
            self.orientation = "vertical" if self.orientation == "horizontal" else "horizontal"
        
        if self.orientation == "vertical":
            self.setRect(0, 0, 30, 114)
        else:
            self.setRect(0, 0, 114, 30)
            
        self.update_text()
        self.update()
    
    def update_text(self):
        """Update text and rotation to display the chemical name centered."""
        chemical_name = self.params.get(KEY_NAME, self.action) or self.action
        self.text.setPlainText(chemical_name)
        
        font = QFont("Segoe UI", 8)
        font.setBold(True)
        self.text.setFont(font)
        self.text.setDefaultTextColor(QColor(255, 255, 255))
        
        text_rect = self.text.boundingRect()
        block_rect = self.rect()
        
        if self.orientation == "horizontal":
            self.text.setRotation(0)
            x = (block_rect.width() - text_rect.width()) / 2
            y = (block_rect.height() - text_rect.height()) / 2
        else:
            self.text.setRotation(90)
            x = (block_rect.width() + text_rect.height()) / 2
            y = (block_rect.height() - text_rect.width()) / 2
            
        self.text.setPos(x, y)