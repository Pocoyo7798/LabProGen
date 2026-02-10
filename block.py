import sys
from PySide6.QtWidgets import (
    QApplication, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsLineItem,
    QDialog, QFormLayout, QLineEdit, QPushButton, QMenu
)
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import QPen, QColor, QFont
import debug_flag
import json

class Block(QGraphicsRectItem):
    def __init__(self, action, params, editor=None):
        super().__init__(0, 0, 140, 60)
        self.action = action
        self.params = params
        self.editor = editor
        self.next_block = None  # Reference to the next block in the sequence (horizontal)
        self.prev_block = None  # Reference to the previous block (horizontal)
        self.below_block = None  # Reference to blocks below (vertical connection)
        self.above_block = None  # Reference to block above (vertical connection)
        self.is_first = False  # Whether this is the first action in the sequence
        self.connected = False  # whether currently connected to a neighbor
        self.chain_drag_mode = False  # Whether we're dragging the entire chain
        
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
        self.text.setPos(20, 10)
        self.update_text()

    def paint(self, painter, option, widget=None):
        from PySide6.QtGui import QPainterPath, QPainter

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        w = rect.width()
        h = rect.height()

        # Chevron dimensions
        arrow_width = 18  # Width of the arrow point

        path = QPainterPath()

        if self.is_first:
            # First block: flat back (left), arrow on right
            path.moveTo(4, 4)
            path.lineTo(w - arrow_width - 4, 4)
            path.lineTo(w - 4, h / 2)
            path.lineTo(w - arrow_width - 4, h - 4)
            path.lineTo(4, h - 4)
            path.lineTo(4, 4)
        else:
            # Normal block: arrow on left and right
            path.moveTo(4, 4)
            path.lineTo(w - arrow_width - 4, 4)
            path.lineTo(w - 4, h / 2)
            path.lineTo(w - arrow_width - 4, h - 4)
            path.lineTo(4, h - 4)
            path.lineTo(arrow_width + 4, h / 2)
            path.lineTo(4, 4)

        # Close the path
        path.closeSubpath()

        # Draw shadow effect
        painter.setOpacity(0.15)
        shadow_path = QPainterPath(path)
        painter.setBrush(QColor(0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(shadow_path.translated(2, 2))
        
        # Draw main shape
        painter.setOpacity(1.0)
        painter.setBrush(self.brush())
        painter.setPen(self.pen())
        painter.drawPath(path)
    
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
            self.setPen(QPen(QColor(46, 204, 113), 3))  # Modern green
        else:
            self.setPen(self.default_pen)

    def set_connected(self, connected: bool):
        """Mark visual connected state (changes border color)"""
        self.connected = connected
        if connected:
            self.setPen(QPen(QColor(255, 193, 7), 3))  # Modern yellow
        else:
            self.setPen(self.default_pen)

    def update_text(self):
        # Insert newline before each uppercase letter
        formatted_action = ""
        for i, char in enumerate(self.action):
            if char.isupper() and i > 0:
                formatted_action += "\n" + char
            else:
                formatted_action += char
        
        self.text.setPlainText(formatted_action)
        
        # Set modern font
        font = QFont("Segoe UI", 10)
        font.setBold(True)
        self.text.setFont(font)
        self.text.setDefaultTextColor(QColor(255, 255, 255))
        
        # Center the text in the block
        text_rect = self.text.boundingRect()
        block_rect = self.rect()
        
        # Calculate centered position
        x = (block_rect.width() - text_rect.width()) / 2
        y = (block_rect.height() - text_rect.height()) / 2
        
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
        """Print a readable snapshot of the editor blocks and their links.

        This prints each block in `self.editor.blocks` with its id, type,
        action name, position and references to prev/next/above/below.
        Shows only chains (horizontal and vertical), isolated blocks are omitted.
        """
        # Check simple module-level debug flag
        if not debug_flag.DEBUG_MODE:
            return
        if not self.editor:
            print("[DEBUG] No editor reference available for this block")
            return

        print("\n[DEBUG] ===== Blocks structure snapshot =====")
        for idx, b in enumerate(self.editor.blocks):
            try:
                px = b.pos().x()
                py = b.pos().y()
            except Exception:
                px = py = None

            def rid(x):
                return hex(id(x)) if x is not None else None

            print(
                f"[{idx}] {b.__class__.__name__}('{b.action}') id={hex(id(b))} pos=({px},{py}) "
                f"prev={rid(b.prev_block)} next={rid(b.next_block)} "
                f"above={rid(b.above_block)} below={rid(b.below_block)} connected={b.connected}"
            )

        # Show horizontal chains (action blocks linked left-right via prev/next)
        # Chemical blocks are vertical-only and should not appear in horizontal chains.
        print("[DEBUG] Horizontal chains (left <-> ... <-> right):")
        h_seen = set()
        for b in self.editor.blocks:
            # Skip chemical blocks when enumerating horizontal chains
            if isinstance(b, ChemicalBlock):
                continue
            if b.prev_block is None and b not in h_seen:
                # Start of a horizontal chain (no prev_block)
                h_chain = []
                cur = b
                while cur and not isinstance(cur, ChemicalBlock):
                    h_chain.append(f"{cur.__class__.__name__}('{cur.action}')")
                    h_seen.add(cur)
                    cur = cur.next_block
                # Print only if it's actually a chain (more than 1 action)
                # or if this action has a chemical attached below (shows vertical children)
                if len(h_chain) > 1 or (hasattr(b, 'below_block') and b.below_block is not None):
                    print("  " + " <-> ".join(h_chain))

        # Show vertical chains (chemicals linked top-bottom via above/below)
        print("[DEBUG] Vertical chains (top -> ... -> bottom):")
        v_seen = set()
        for b in self.editor.blocks:
            if b.above_block is None and b not in v_seen:
                # This is the start of a vertical chain (no above_block)
                v_chain = []
                cur = b
                while cur:
                    v_chain.append(f"{cur.__class__.__name__}('{cur.action}')")
                    v_seen.add(cur)
                    cur = cur.below_block
                # Only print if it's actually a chain (more than 1 element)
                if len(v_chain) > 1:
                    print("  " + " -> ".join(v_chain))

        print("[DEBUG] ===== end snapshot =====\n")

    def mousePressEvent(self, event):
        """Handle mouse press events including right-click and Ctrl+click"""
        if event.button() == Qt.RightButton:
            self.show_context_menu(event)
        elif event.modifiers() == Qt.ControlModifier:
            # Ctrl+click: enable chain drag mode
            self.chain_drag_mode = True
            # Bring block to foreground
            self.setZValue(1000)
            super().mousePressEvent(event)
        else:
            # Bring block to foreground
            self.setZValue(1000)
            super().mousePressEvent(event)

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

    def show_context_menu(self, event):
        """Show context menu on right-click"""
        menu = QMenu()
        if not self.is_first:
            make_first_action = menu.addAction("Make it First")
            make_first_action.triggered.connect(self.make_first)
        else:
            menu.addAction("This is the First action")
        
        # Add delete option
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(self.delete_block)
        
        menu.exec(event.screenPos())

    def delete_block(self):
        """Delete this block from the scene and update connections accordingly
        """
        if not self.editor:
            return

        # Remove from editor's list (capture presence first)
        if self in self.editor.blocks:
            self.editor.blocks.remove(self)

        # Update horizontal chain connections (for action blocks)
        if self.prev_block:
            self.prev_block.next_block = self.next_block
        if self.next_block:
            self.next_block.prev_block = self.prev_block

        # If deleted block was in the middle of a horizontal chain, shift the right chain left
        try:
            if self.prev_block and self.next_block and self.editor:
                prev = self.prev_block
                right = self.next_block
                prev_pos = prev.pos()
                prev_w = prev.rect().width()
                overlap = 20
                desired_right_x = prev_pos.x() + prev_w - overlap
                current_right_x = right.pos().x()
                shift = desired_right_x - current_right_x
                # Move the right chain to close the gap
                if abs(shift) > 0.1:
                    self.editor.push_chain(right, shift)
                    # Align vertical position
                    try:
                        self.editor.align_chain_vertical(right, prev_pos.y())
                    except Exception:
                        pass
                    # Reposition chemical blocks below the moved right chain to stay glued
                    b = right
                    while b:
                        if isinstance(b, (ElementaryAction, SupportAction)) and b.below_block:
                            action_rect = b.rect()
                            chem_rect = b.below_block.rect()
                            snap_x = b.pos().x() + (action_rect.width() - chem_rect.width()) * 0.25
                            snap_y = b.pos().y() + action_rect.height()
                            b.below_block.setPos(snap_x, snap_y)
                            try:
                                self.editor.update_chemical_chain_below(b.below_block, snap_x, snap_y)
                            except Exception:
                                pass
                        b = b.next_block
        except Exception:
            pass

        # Update vertical connections (for chemical blocks or if chemical is below this action)
        if self.above_block and self.below_block:
            # Reattach the child under the parent so the chain closes the gap
            parent = self.above_block
            child = self.below_block
            parent.below_block = child
            child.above_block = parent

            # Reposition child directly below parent
            try:
                parent_pos = parent.pos()
                parent_rect = parent.rect()
                child_rect = child.rect()
                snap_x = parent_pos.x() + (parent_rect.width() - child_rect.width()) * 0.25
                snap_y = parent_pos.y() + parent_rect.height()
                child.setPos(snap_x, snap_y)
                # Update sub-chain below
                self.editor.update_chemical_chain_below(child, snap_x, snap_y)
            except Exception:
                pass

            # Ensure connected visuals
            parent.set_connected(True)
            child.set_connected(True)
        else:
            # If only child exists, orphan it
            if self.below_block:
                self.below_block.above_block = None
                self.below_block.set_connected(False)
            # If only parent exists, remove its reference to this block
            if self.above_block:
                self.above_block.below_block = None
                # Update connected state of block above based on its type
                if isinstance(self.above_block, ChemicalBlock):
                    self.above_block.set_connected(bool(self.above_block.above_block or self.above_block.below_block))
                else:
                    self.above_block.set_connected(bool(
                        self.above_block.prev_block or 
                        self.above_block.next_block or 
                        self.above_block.below_block
                    ))

        # Clear this block's own references so it doesn't still point to neighbors
        try:
            self.prev_block = None
            self.next_block = None
            self.above_block = None
            self.below_block = None
            self.set_connected(False)
        except Exception:
            pass

        # Remove from scene and refresh linked sequence
        self.scene().removeItem(self)
        self.editor.update_linked_sequence()
        # Print debug snapshot after delete to help trace chain updates
        try:
            if self.editor:
                if debug_flag.DEBUG_MODE:
                    print("[DEBUG] Structure after delete:")
                    # Use the debug helper to print current structure
                    self.debug_print_structure()
        except Exception as e:
            if debug_flag.DEBUG_MODE:
                print(f"[DEBUG] Error printing structure after delete: {e}")

    def make_first(self):
        """Mark this action as the first in the sequence"""
        if self.editor:
            # Unmark any previous first action
            for block in self.editor.blocks:
                if block != self and block.is_first:
                    block.is_first = False
                    block.update_visual_style()
            
            # Mark this as first
            self.is_first = True
            self.update_visual_style()
            
            # Disconnect from previous block
            if self.prev_block:
                self.prev_block.next_block = None
            self.prev_block = None
            
            # Redraw to update the shape
            self.update()

    def move_chain(self, dx: float, dy: float):
        """Move the entire chain (both left and right) by dx, dy"""
        # Find the start of the chain (block with no prev_block)
        chain_start = self
        while chain_start.prev_block:
            chain_start = chain_start.prev_block
        
        # Move all blocks from chain_start onwards
        current = chain_start
        while current:
            pos = current.pos()
            current.setPos(pos.x() + dx, pos.y() + dy)
            current = current.next_block

    def open_editor(self):
        dialog = QDialog()
        dialog.setWindowTitle(self.action)
        dialog.setFixedWidth(350)
        layout = QFormLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        inputs = {}
        for key, value in self.params.items():
            field = QLineEdit(str(value))
            layout.addRow(key + ":", field)
            inputs[key] = field

        save = QPushButton("Save Changes")
        layout.addWidget(save)

        def apply():
            for k, field in inputs.items():
                self.params[k] = field.text()
            self.update_text()
            dialog.accept()

        save.clicked.connect(apply)
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
    """Chemical action block - green rectangle with 1/3 width"""
    def __init__(self, action, params, editor=None):
        # Call parent's parent __init__ to avoid Block.__init__
        QGraphicsRectItem.__init__(self, 0, 0, 115, 30)  # 1/3 width
        self.action = action
        self.params = params
        self.editor = editor
        self.next_block = None  # Horizontal links between action blocks (not used for chemicals)
        self.prev_block = None  # Horizontal links between action blocks (not used for chemicals)
        self.below_block = None  # Vertical link to chemical block below
        self.above_block = None  # Vertical link to block above (could be action or chemical)
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
    
    def update_text(self):
        """Update text to display the chemical name from params"""
        # Get the chemical name from params, default to action name if not available
        chemical_name = self.params.get("name", self.action) or self.action
        
        self.text.setPlainText(chemical_name)
        
        # Set modern font (smaller for chemical blocks)
        font = QFont("Segoe UI", 8)
        font.setBold(True)
        self.text.setFont(font)
        self.text.setDefaultTextColor(QColor(255, 255, 255))
        
        # Center the text in the block
        text_rect = self.text.boundingRect()
        block_rect = self.rect()
        
        # Calculate centered position
        x = (block_rect.width() - text_rect.width()) / 2
        y = (block_rect.height() - text_rect.height()) / 2
        
        self.text.setPos(x, y)