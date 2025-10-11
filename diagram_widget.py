"""
diagram_widget.py (Heavily Modified)

This widget is now an interactive editor for building the refrigeration cycle diagram.
It replaces the old static image viewer.

Key changes:
- It no longer loads a QPixmap. It builds a scene from QGraphicsItems.
- It has a `build_scene_from_model` method to render the diagram from the DataManager.
- It includes a `PropertyEditor` dock widget to change component properties.
- It handles adding, moving, and deleting components.
- It has the logic for the "smart sensor drop" functionality.
"""
import uuid
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QFileDialog, QFrame, QGraphicsView,
                             QGraphicsScene, QMessageBox, QComboBox, QToolBar,
                             QDockWidget, QFormLayout, QLineEdit, QSpinBox)
from PyQt6.QtGui import QPainter, QColor, QPen, QAction
from PyQt6.QtCore import Qt, pyqtSignal, QPointF

# --- NEW: Import the visual components and schemas ---
from component_schemas import SCHEMAS
from diagram_components import BaseComponentItem, PipeItem, PortItem

# --- NEW: Property Editor Panel ---
class PropertyEditor(QWidget):
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.current_item_id = None
        
        self.layout = QFormLayout(self)
        self.setLayout(self.layout)
        self.layout.addWidget(QLabel("Select a component to see its properties."))

    def show_properties(self, item):
        self.clear_layout()
        if not item or not isinstance(item, BaseComponentItem):
            self.current_item_id = None
            self.layout.addWidget(QLabel("Select a component to see its properties."))
            return
            
        self.current_item_id = item.component_id
        component_data = item.component_data
        schema = item.schema
        
        self.layout.addRow(QLabel(f"<b>Properties for {component_data['type']}</b>"))
        
        for prop_name, prop_schema in schema.get('properties', {}).items():
            prop_type = prop_schema['type']
            current_value = component_data.get('properties', {}).get(prop_name)
            
            if prop_type == 'integer':
                editor = QSpinBox()
                editor.setValue(current_value or prop_schema.get('default', 0))
                # editor.valueChanged.connect(lambda val, p=prop_name: self.update_property(p, val))
                self.layout.addRow(QLabel(prop_name), editor)
            elif prop_type == 'string':
                editor = QLineEdit()
                editor.setText(current_value or prop_schema.get('default', ''))
                self.layout.addRow(QLabel(prop_name), editor)
            elif prop_type == 'enum':
                editor = QComboBox()
                editor.addItems(prop_schema.get('options', []))
                if current_value:
                    editor.setCurrentText(current_value)
                self.layout.addRow(QLabel(prop_name), editor)

    def clear_layout(self):
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

class DiagramWidget(QWidget):
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        # --- NEW: Store references to scene items for easy access ---
        self.component_items = {}
        self.pipe_items = {}
        
        self.current_tool = None # For adding components
        self.pipe_mode = False  # For drawing pipes
        self.pipe_start_port = None  # Track pipe drawing state
        self.temp_pipe_line = None  # Temporary visual feedback while drawing
        
        self.setupUi()
        self.connect_signals()

    def setupUi(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # --- NEW: Component Palette Toolbar ---
        self.toolbar = QToolBar("Component Palette")
        main_layout.addWidget(self.toolbar)
        self.populate_toolbar()
        
        # --- MODIFIED: The scene is now the primary view ---
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        
        main_layout.addWidget(self.view)
        
        # --- NEW: Enable drops for sensors ---
        self.setAcceptDrops(True)

    def populate_toolbar(self):
        """Populates the toolbar with actions for each component in the schema."""
        for comp_type in SCHEMAS.keys():
            action = QAction(comp_type, self)
            action.setCheckable(True)
            action.triggered.connect(lambda checked, t=comp_type: self.set_tool(t if checked else None))
            self.toolbar.addAction(action)
        
        self.toolbar.addSeparator()
        
        # Add pipe connection tool
        pipe_action = QAction("🔗 Connect Pipe", self)
        pipe_action.setCheckable(True)
        pipe_action.triggered.connect(self.toggle_pipe_mode)
        self.toolbar.addAction(pipe_action)
        self.pipe_action = pipe_action
        
    def set_tool(self, tool_name):
        """Sets the active tool for adding components."""
        self.current_tool = tool_name
        # Disable pipe mode if switching tools
        if tool_name and self.pipe_mode:
            self.pipe_mode = False
            self.pipe_action.setChecked(False)
        # Uncheck other toolbar actions
        for action in self.toolbar.actions():
            if action.text() != tool_name and action.isCheckable() and action != self.pipe_action:
                action.setChecked(False)
    
    def toggle_pipe_mode(self, checked):
        """Toggle pipe connection mode."""
        self.pipe_mode = checked
        if checked:
            # Disable component placement tools
            self.current_tool = None
            for action in self.toolbar.actions():
                if action.isCheckable() and action != self.pipe_action:
                    action.setChecked(False)
            print("Pipe mode enabled: Click on a port to start, then click another port to connect")
        else:
            self.pipe_start_port = None
            if self.temp_pipe_line and self.temp_pipe_line.scene():
                self.scene.removeItem(self.temp_pipe_line)
            self.temp_pipe_line = None
            print("Pipe mode disabled")

    def connect_signals(self):
        # Connect to the new signal from DataManager
        self.data_manager.diagram_model_changed.connect(self.build_scene_from_model)
        
        # Connect scene selection changes to the property editor
        self.scene.selectionChanged.connect(self.on_scene_selection_changed)
        
        # --- NEW: Override mouse press for adding components ---
        self.view.mousePressEvent = self.view_mouse_press_event

    # --- MAJOR NEW METHOD: Renders the diagram from the data model ---
    def build_scene_from_model(self):
        """Clears the scene and rebuilds it based on the DataManager's diagram_model."""
        self.scene.clear()
        self.component_items.clear()
        self.pipe_items.clear()
        
        model = self.data_manager.diagram_model
        
        # 1. Create Component Items
        for comp_id, comp_data in model.get('components', {}).items():
            item = BaseComponentItem(comp_id, comp_data, self.data_manager)
            self.scene.addItem(item)
            self.component_items[comp_id] = item
            
        # 2. Create Pipe Items
        for pipe_id, pipe_data in model.get('pipes', {}).items():
            # Find the port items
            start_comp = self.component_items.get(pipe_data['start_component_id'])
            end_comp = self.component_items.get(pipe_data['end_component_id'])
            
            if start_comp and end_comp:
                start_port = start_comp.ports.get(pipe_data['start_port'])
                end_port = end_comp.ports.get(pipe_data['end_port'])
                
                if start_port and end_port:
                    pipe_item = PipeItem(pipe_id, pipe_data, start_port, end_port)
                    self.scene.addItem(pipe_item)
                    self.pipe_items[pipe_id] = pipe_item
        
        self.scene.update()
        
    def on_scene_selection_changed(self):
        """Updates the property editor when the scene selection changes."""
        selected_items = self.scene.selectedItems()
        # In a real app, find the property editor dock and call a method on it.
        # For now, we print to the console.
        if len(selected_items) == 1:
            item = selected_items[0]
            if isinstance(item, BaseComponentItem):
                print(f"Selected: {item.component_data['type']} ({item.component_id})")
                # This is where you would tell the PropertyEditor to show properties for 'item'
                if hasattr(self.parent(), 'property_editor_dock'):
                    self.parent().property_editor_dock.widget().show_properties(item)
        else:
            if hasattr(self.parent(), 'property_editor_dock'):
                self.parent().property_editor_dock.widget().show_properties(None)


    def view_mouse_press_event(self, event):
        """Handles mouse press on the view for adding components or drawing pipes."""
        scene_pos = self.view.mapToScene(event.pos())
        
        # Handle component placement
        if self.current_tool and event.button() == Qt.MouseButton.LeftButton:
            # Add the component to the data model
            self.data_manager.add_component_to_model(self.current_tool, scene_pos)
            
            # De-select the tool after placing
            self.set_tool(None)
            return
        
        # Handle pipe drawing
        if self.pipe_mode and event.button() == Qt.MouseButton.LeftButton:
            # Find if we clicked on a port
            items_at_pos = self.scene.items(scene_pos)
            port_item = None
            for item in items_at_pos:
                if isinstance(item, PortItem):
                    port_item = item
                    break
            
            if port_item:
                if self.pipe_start_port is None:
                    # Start drawing a pipe
                    self.pipe_start_port = port_item
                    port_item.setBrush(QBrush(QColor("#00FF00")))  # Highlight start port
                    print(f"Pipe start: {port_item.port_data['name']}")
                else:
                    # Complete the pipe
                    self.create_pipe(self.pipe_start_port, port_item)
                    # Reset
                    self.pipe_start_port._update_style()  # Restore original color
                    self.pipe_start_port = None
                    if self.temp_pipe_line and self.temp_pipe_line.scene():
                        self.scene.removeItem(self.temp_pipe_line)
                    self.temp_pipe_line = None
            return
        
        # Call the original event handler for selection/panning
        super(QGraphicsView, self.view).mousePressEvent(event)

    def create_pipe(self, start_port_item, end_port_item):
        """Create a pipe connection between two ports with validation."""
        start_port_data = start_port_item.port_data
        end_port_data = end_port_item.port_data
        
        # Validation 1: Can't connect a port to itself
        if start_port_item == end_port_item:
            QMessageBox.warning(self, "Invalid Connection", "Cannot connect a port to itself!")
            return False
        
        # Validation 2: Can't connect two ports on the same component
        if start_port_item.parent_component == end_port_item.parent_component:
            QMessageBox.warning(self, "Invalid Connection", "Cannot connect ports on the same component!")
            return False
        
        # Validation 3: Must be out-to-in or in-to-out (or sensor)
        start_type = start_port_data['type']
        end_type = end_port_data['type']
        
        if start_type == 'sensor' or end_type == 'sensor':
            # Sensor ports can't be connected via pipes
            QMessageBox.warning(self, "Invalid Connection", "Sensor ports cannot be connected with pipes!")
            return False
        
        # Ensure we have out -> in direction
        if start_type == 'in' and end_type == 'out':
            # Swap them
            start_port_item, end_port_item = end_port_item, start_port_item
            start_port_data, end_port_data = end_port_data, start_port_data
            start_type, end_type = end_type, start_type
        
        if not (start_type == 'out' and end_type == 'in'):
            QMessageBox.warning(self, "Invalid Connection", 
                              f"Invalid connection: {start_type} -> {end_type}. Must connect outlet to inlet!")
            return False
        
        # Validation 4: Fluid state compatibility
        start_fluid = start_port_data.get('fluid_state', 'any')
        end_fluid = end_port_data.get('fluid_state', 'any')
        
        if not self.validate_fluid_compatibility(start_fluid, end_fluid):
            QMessageBox.warning(self, "Fluid State Mismatch",
                              f"Cannot connect {start_fluid} outlet to {end_fluid} inlet!\n"
                              f"Fluid states must be compatible.")
            return False
        
        # All validations passed - create the pipe
        start_comp_id = start_port_item.parent_component.component_id
        end_comp_id = end_port_item.parent_component.component_id
        start_port_name = start_port_data['name']
        end_port_name = end_port_data['name']
        
        # Determine fluid state for the pipe (use the more specific one)
        pipe_fluid = start_fluid if start_fluid != 'any' else end_fluid
        
        self.data_manager.add_pipe_to_model(
            start_comp_id, start_port_name,
            end_comp_id, end_port_name,
            pipe_fluid
        )
        
        print(f"Pipe created: {start_comp_id}.{start_port_name} -> {end_comp_id}.{end_port_name} ({pipe_fluid})")
        return True
    
    def validate_fluid_compatibility(self, fluid1, fluid2):
        """Check if two fluid states are compatible for connection."""
        if fluid1 == 'any' or fluid2 == 'any':
            return True
        if fluid1 == fluid2:
            return True
        # Add more nuanced rules if needed (e.g., two-phase can accept liquid in some cases)
        return False
    
    def keyPressEvent(self, event):
        """Handle key presses for deleting items."""
        if event.key() == Qt.Key.Key_Delete:
            selected_ids = [item.component_id for item in self.scene.selectedItems() if isinstance(item, BaseComponentItem)]
            if selected_ids:
                self.data_manager.remove_components_from_model(selected_ids)
            
            # Also delete selected pipes
            selected_pipe_ids = [item.pipe_id for item in self.scene.selectedItems() if isinstance(item, PipeItem)]
            if selected_pipe_ids:
                self.data_manager.remove_pipes_from_model(selected_pipe_ids)
        
        super().keyPressEvent(event)
        
    # --- SMART SENSOR DROP LOGIC (Phase 3) ---
    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        sensor_name = event.mimeData().text()
        scene_pos = self.view.mapToScene(event.pos())
        item_at_pos = self.scene.itemAt(scene_pos, self.view.transform())

        if isinstance(item_at_pos, BaseComponentItem):
            # This is where the contextual analysis will go.
            # For now, we'll just print what we know.
            component_type = item_at_pos.component_data['type']
            component_id = item_at_pos.component_id
            print(f"Dropped sensor '{sensor_name}' on component '{component_type}' ({component_id})")
            
            # In a full implementation, you would analyze the drop position against
            # port/zone hotspots and then call a method on the data_manager to
            # set the sensor's role.
            # e.g., self.data_manager.set_sensor_role(sensor_name, role, component_id)

    def update_ui(self):
        """This method is now triggered by data_changed, but the heavy lifting is done by build_scene_from_model."""
        # This can be used for lighter-weight updates that don't require a full rebuild.
        self.scene.update()

