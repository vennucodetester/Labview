"""
diagram_components.py (New File)

This file contains the visual building blocks (QGraphicsItems) for the diagram editor.
Each class here is responsible for rendering a component from the data model,
handling user interactions like moving, selecting, and deleting, and providing
"hotspots" for pipe connections and sensor drops.

This modularizes the visual representation, separating it from the core data
and the main widget logic.
"""
import uuid
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsTextItem, QGraphicsPathItem, QGraphicsItem
from PyQt6.QtGui import QPen, QBrush, QColor, QPainterPath
from PyQt6.QtCore import Qt, QRectF, QPointF

from component_schemas import SCHEMAS

# --- Component Visual Item ---
class BaseComponentItem(QGraphicsRectItem):
    def __init__(self, component_id, component_data, data_manager):
        super().__init__(0, 0, 100, 60) # Default size
        self.component_id = component_id
        self.component_data = component_data
        self.data_manager = data_manager
        
        self.schema = SCHEMAS.get(component_data['type'], {})
        
        # Make item selectable and movable
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        
        # Style
        self.setBrush(QBrush(QColor("#e3f2fd")))
        self.setPen(QPen(QColor("#90caf9"), 2))
        
        self.setPos(QPointF(*component_data.get('position', [0, 0])))
        
        # Label
        self.label = QGraphicsTextItem(component_data['type'], self)
        self.label.setDefaultTextColor(Qt.GlobalColor.black)
        self.label.setPos(5, 5)

        self.ports = {}
        self._create_ports()

    def _create_ports(self):
        # Create static ports
        for port_data in self.schema.get('ports', []):
            port_item = PortItem(self, port_data)
            self.ports[port_data['name']] = port_item
        
        # Create dynamic ports (e.g., for distributors)
        dynamic_port_schema = self.schema.get('dynamic_ports')
        if dynamic_port_schema:
            count = self.component_data.get('properties', {}).get(dynamic_port_schema['count_property'], 1)
            for i in range(count):
                port_name = f"{dynamic_port_schema['prefix']}{i+1}"
                port_data = dynamic_port_schema['port_details'].copy()
                port_data['name'] = port_name
                # Simple positioning for now, can be improved
                port_data['position'] = [1, (i + 1) / (count + 1)]
                
                port_item = PortItem(self, port_data)
                self.ports[port_name] = port_item

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Update the position in the central data model
            new_pos = [value.x(), value.y()]
            self.data_manager.update_component_position(self.component_id, new_pos)
            
            # Update all connected pipes
            self.update_connected_pipes()
            
        return super().itemChange(change, value)
    
    def update_connected_pipes(self):
        """Update all pipes connected to this component's ports."""
        for port_item in self.ports.values():
            for pipe_item in port_item.connected_pipes:
                pipe_item.update_path()

# --- Port Visual Item ---
class PortItem(QGraphicsRectItem):
    def __init__(self, parent, port_data):
        super().__init__(-6, -6, 12, 12, parent)  # Larger, more visible
        self.port_data = port_data
        self.parent_component = parent
        self.connected_pipes = []  # Track connected pipes
        
        # Positioning based on percentage (0,0 to 1,1)
        parent_rect = parent.rect()
        pos_x = parent_rect.x() + parent_rect.width() * port_data['position'][0]
        pos_y = parent_rect.y() + parent_rect.height() * port_data['position'][1]
        self.setPos(pos_x, pos_y)
        
        # Enhanced style based on port type and fluid state
        self._update_style()
        
        # Make port interactive
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setZValue(10)  # Draw ports on top
        
        # Tooltip with detailed info
        port_type = port_data['type'].upper()
        fluid = port_data.get('fluid_state', 'unknown')
        self.setToolTip(f"{port_data['name']}\nType: {port_type}\nFluid: {fluid}")
    
    def _update_style(self):
        """Apply color coding based on port type and fluid state."""
        port_type = self.port_data['type']
        fluid_state = self.port_data.get('fluid_state', 'any')
        
        # Color by port type
        if port_type == 'in':
            base_color = QColor("#4CAF50")  # Green for inlet
        elif port_type == 'out':
            base_color = QColor("#F44336")  # Red for outlet
        elif port_type == 'sensor':
            base_color = QColor("#FFC107")  # Yellow for sensor ports
        else:
            base_color = QColor("#9E9E9E")  # Gray for other
        
        # Adjust shade based on fluid state
        if fluid_state == 'liquid':
            base_color = base_color.darker(110)
        elif fluid_state == 'gas':
            base_color = base_color.lighter(110)
        elif fluid_state == 'two-phase':
            # Use gradient or pattern for two-phase (simplified for now)
            base_color = base_color
        
        self.setBrush(QBrush(base_color))
        self.setPen(QPen(Qt.GlobalColor.black, 2))
    
    def hoverEnterEvent(self, event):
        """Highlight port on hover."""
        self.setBrush(QBrush(QColor("#FFEB3B")))  # Bright yellow
        self.setPen(QPen(QColor("#FF9800"), 3))
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Restore normal appearance."""
        self._update_style()
        super().hoverLeaveEvent(event)
    
    def get_scene_position(self):
        """Get the center position of this port in scene coordinates."""
        return self.mapToScene(self.rect().center())
    
    def add_connected_pipe(self, pipe_item):
        """Register a pipe connected to this port."""
        if pipe_item not in self.connected_pipes:
            self.connected_pipes.append(pipe_item)
    
    def remove_connected_pipe(self, pipe_item):
        """Unregister a pipe from this port."""
        if pipe_item in self.connected_pipes:
            self.connected_pipes.remove(pipe_item)

# --- Pipe Visual Item ---
class PipeItem(QGraphicsPathItem):
    def __init__(self, pipe_id, pipe_data, start_port_item, end_port_item):
        super().__init__()
        self.pipe_id = pipe_id
        self.pipe_data = pipe_data
        self.start_port_item = start_port_item
        self.end_port_item = end_port_item
        
        # Register with ports
        if start_port_item:
            start_port_item.add_connected_pipe(self)
        if end_port_item:
            end_port_item.add_connected_pipe(self)
        
        # Get fluid state for styling
        fluid_state = pipe_data.get('fluid_state', 'any')
        
        # Style based on fluid state
        pen_color, pen_width, pen_style = self._get_pen_style(fluid_state)
        self.setPen(QPen(pen_color, pen_width, pen_style))
        
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setZValue(1)  # Draw pipes below ports but above components
        
        # Tooltip
        self.setToolTip(f"Pipe: {pipe_data.get('fluid_state', 'unknown')}\n"
                       f"From: {pipe_data['start_port']}\n"
                       f"To: {pipe_data['end_port']}")
        
        self.update_path()
    
    def _get_pen_style(self, fluid_state):
        """Return pen color, width, and style based on fluid state."""
        if fluid_state == 'liquid':
            return QColor("#2196F3"), 3, Qt.PenStyle.SolidLine  # Blue solid for liquid
        elif fluid_state == 'gas':
            return QColor("#F44336"), 3, Qt.PenStyle.SolidLine  # Red solid for gas
        elif fluid_state == 'two-phase':
            return QColor("#9C27B0"), 3, Qt.PenStyle.DashLine  # Purple dashed for two-phase
        elif fluid_state == 'air':
            return QColor("#00BCD4"), 2, Qt.PenStyle.DotLine  # Cyan dotted for air
        else:
            return QColor("#607D8B"), 2, Qt.PenStyle.SolidLine  # Gray for unknown
    
    def update_path(self):
        """Redraw the pipe path based on current port positions."""
        if not self.start_port_item or not self.end_port_item:
            return
        
        start_pos = self.start_port_item.get_scene_position()
        end_pos = self.end_port_item.get_scene_position()
        
        if start_pos and end_pos:
            path = QPainterPath()
            path.moveTo(start_pos)
            
            # Create a smooth curved path (Bezier curve)
            dx = end_pos.x() - start_pos.x()
            dy = end_pos.y() - start_pos.y()
            
            # Control points for smooth curve
            ctrl1 = QPointF(start_pos.x() + dx * 0.5, start_pos.y())
            ctrl2 = QPointF(start_pos.x() + dx * 0.5, end_pos.y())
            
            # Use cubic bezier for smooth pipes
            path.cubicTo(ctrl1, ctrl2, end_pos)
            
            self.setPath(path)
    
    def mousePressEvent(self, event):
        """Handle pipe selection."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.setSelected(True)
            # Change appearance when selected
            current_pen = self.pen()
            current_pen.setWidth(current_pen.width() + 2)
            self.setPen(current_pen)
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Restore normal appearance."""
        if not self.isSelected():
            fluid_state = self.pipe_data.get('fluid_state', 'any')
            pen_color, pen_width, pen_style = self._get_pen_style(fluid_state)
            self.setPen(QPen(pen_color, pen_width, pen_style))
        super().mouseReleaseEvent(event)

