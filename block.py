import sys
from PySide6.QtWidgets import (
    QApplication, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsLineItem,
    QDialog, QFormLayout, QLineEdit, QPushButton, QMenu
)
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import QPen, QColor, QFont
import json

class Block(QGraphicsRectItem):
    def __init__(self, action, params, editor=None):
        super().__init__(0, 0, 140, 60)
        self.action = action
        self.params = params
        self.editor = editor
        self.next_block = None  # Reference to the next block in the sequence
        self.prev_block = None  # Reference to the previous block
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

    def mousePressEvent(self, event):
        """Handle mouse press events including right-click and Ctrl+click"""
        if event.button() == Qt.RightButton:
            self.show_context_menu(event)
        elif event.modifiers() == Qt.ControlModifier:
            # Ctrl+click: enable chain drag mode
            self.chain_drag_mode = True
            super().mousePressEvent(event)
        else:
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
            # Notify editor to check for side-touch linking
            if self.editor:
                self.editor.check_and_link_horizontal_blocks(self)

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
        """Delete this block from the scene"""
        if self.editor:
            # Remove from editor's blocks list
            if self in self.editor.blocks:
                self.editor.blocks.remove(self)
            
            # Update chain connections
            if self.prev_block:
                self.prev_block.next_block = self.next_block
            if self.next_block:
                self.next_block.prev_block = self.prev_block
            
            # Remove from scene
            self.scene().removeItem(self)
            
            # Update linked sequence
            self.editor.update_linked_sequence()

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
        self.next_block = None
        self.prev_block = None
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