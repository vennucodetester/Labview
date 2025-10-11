import pandas as pd
from pandas.api.types import is_datetime64_any_dtype
import json
import base64
import os
import uuid
from PyQt6.QtCore import QObject, pyqtSignal, QPointF
from PyQt6.QtGui import QPixmap
from mapping_dialog import MappingDialog

# --- NEW: Import the component schemas ---
from component_schemas import SCHEMAS

class DataManager(QObject):
    """
    Centralized class to manage all application data.
    NOW MANAGES THE INTERACTIVE DIAGRAM MODEL.
    """
    data_changed = pyqtSignal()
    # --- NEW: Signal for when the diagram model itself is loaded/changed ---
    diagram_model_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self._reset_state()

    def _get_default_diagram_model(self):
        """Returns the default structure for a new diagram model."""
        return {
            "properties": {"refrigerant": "R410A"},
            "components": {},
            "pipes": {},
            "sensor_roles": {}
        }

    def _reset_state(self):
        """Resets all data to initial state."""
        self.csv_data = None
        
        # --- MODIFIED: The diagram model is now the core data structure ---
        self.diagram_model = self._get_default_diagram_model()
        
        self.selected_sensors = set()
        self.graph_sensors = set()
        self.sensor_groups = {}
        self.group_states = {}
        self.config_path = None
        self.current_mode = 'mapping'
        self.config_sensor_list = []
        self.time_range = 'All Data'
        self.value_aggregation = 'Average'
        self.custom_time_range = None

    def load_csv(self, file_path):
        """
        Loads a CSV. If a config is already loaded, it triggers
        the reconciliation process.
        NOTE: This part is unchanged for now, but will eventually interact
        with the new system analyzer.
        """
        try:
            new_csv_data = pd.read_csv(file_path)
            if 'Timestamp' in new_csv_data.columns:
                try:
                    new_csv_data['Timestamp'] = pd.to_datetime(new_csv_data['Timestamp'], errors='coerce')
                except Exception:
                    pass
            new_sensor_list = new_csv_data.columns.tolist()[1:] 

            if self.config_path and self.config_sensor_list:
                self.reconcile_csv(new_csv_data, new_sensor_list)
            else:
                self.csv_data = new_csv_data
                self.data_changed.emit()
            return True
        except Exception as e:
            print(f"Error loading CSV file: {e}")
            return False

    def reconcile_csv(self, new_csv_data, new_sensor_list):
        """
        Compares the new CSV against the loaded config and opens a dialog
        for the user to map sensor name changes.
        """
        orphaned = sorted([s for s in self.config_sensor_list if s not in new_sensor_list])
        new = sorted([s for s in new_sensor_list if s not in self.config_sensor_list])
        matched = sorted([s for s in self.config_sensor_list if s in new_sensor_list])

        if not orphaned and not new:
            self.csv_data = new_csv_data
            self.data_changed.emit()
            return

        # NOTE: The old 'mappings' dict is now part of the diagram_model's sensor_roles.
        # This reconciliation logic will need to be updated in a later phase to work
        # with the new sensor role mapping system.
        dialog = MappingDialog(orphaned, new, matched, parent=self.parent)
        if dialog.exec():
            # This part needs refactoring later.
            self.csv_data = new_csv_data
            self.data_changed.emit()

    # --- MAJOR OVERHAUL: Load session now loads the diagram model ---
    def load_session(self, file_path):
        """Loads a .json session file, prioritizing the new diagramModel structure."""
        try:
            self._reset_state()
            self.config_path = file_path
            with open(file_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            # --- NEW: Load the intelligent diagram model ---
            if 'diagramModel' in session_data:
                self.diagram_model = session_data['diagramModel']
                print("Loaded intelligent diagram model from session file.")
            else:
                # Legacy support: try to load old format (this will be phased out)
                print("Legacy session file found. No diagram model present.")
                # We could potentially try to convert old mappings to new roles here in the future
                pass

            # Sensor groups and other UI states can still be loaded
            self.sensor_groups = session_data.get('sensorGroups', {})
            
            self.diagram_model_changed.emit() # Signal that the whole diagram needs to be redrawn
            self.data_changed.emit()
            return True
        except Exception as e:
            print(f"Error loading session file: {e}")
            self.diagram_model_changed.emit() # Emit even on error to clear the view
            return False

    # --- MAJOR OVERHAUL: Save session now saves the diagram model ---
    def save_session(self, file_path):
        """Saves the current session, including the full diagramModel."""
        try:
            from datetime import datetime
            
            session_data = {
                "name": os.path.splitext(os.path.basename(file_path))[0],
                "timestamp": datetime.now().isoformat() + "Z",
                
                # --- NEW: Save the entire diagram model ---
                "diagramModel": self.diagram_model,
                
                # These are kept for now for UI state, but could be integrated
                # into the diagram model later.
                "sensorGroups": self.sensor_groups,
                "groupStates": {}, # This can be implemented later
                "ui": {
                    "selectedSensors": list(self.selected_sensors),
                    "currentMode": self.current_mode,
                    "selectedTimeRange": self.time_range
                }
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            
            print(f"Session saved successfully to: {file_path}")
            return True
            
        except Exception as e:
            print(f"Error saving session: {e}")
            return False
            
    # --- NEW METHODS for manipulating the diagram model ---
    def add_component_to_model(self, component_type, position):
        """Adds a new component to the diagram model."""
        schema = SCHEMAS.get(component_type, {})
        new_id = f"{component_type.lower()}_{uuid.uuid4().hex[:6]}"
        
        # Populate with default properties from schema
        properties = {}
        for prop_name, prop_data in schema.get('properties', {}).items():
            properties[prop_name] = prop_data.get('default')

        self.diagram_model['components'][new_id] = {
            "type": component_type,
            "position": [position.x(), position.y()],
            "properties": properties
        }
        self.diagram_model_changed.emit()
        return new_id

    def remove_components_from_model(self, component_ids):
        """Removes components and any connected pipes from the model."""
        for comp_id in component_ids:
            if comp_id in self.diagram_model['components']:
                del self.diagram_model['components'][comp_id]
        
        # Remove pipes connected to the deleted components
        pipes_to_delete = []
        for pipe_id, pipe_data in self.diagram_model['pipes'].items():
            if pipe_data['start_component_id'] in component_ids or pipe_data['end_component_id'] in component_ids:
                pipes_to_delete.append(pipe_id)
        
        for pipe_id in pipes_to_delete:
            del self.diagram_model['pipes'][pipe_id]
            
        self.diagram_model_changed.emit()

    def update_component_position(self, component_id, position):
        """Updates a component's position in the model."""
        if component_id in self.diagram_model['components']:
            self.diagram_model['components'][component_id]['position'] = position
            # This is a frequent update, so we might want a different signal
            # to avoid full redraws, but for now this is fine.
            self.data_changed.emit()
    
    def add_pipe_to_model(self, start_comp_id, start_port, end_comp_id, end_port, fluid_state='any'):
        """Adds a new pipe connection to the diagram model."""
        pipe_id = f"pipe_{uuid.uuid4().hex[:6]}"
        
        self.diagram_model['pipes'][pipe_id] = {
            "start_component_id": start_comp_id,
            "start_port": start_port,
            "end_component_id": end_comp_id,
            "end_port": end_port,
            "fluid_state": fluid_state
        }
        
        self.diagram_model_changed.emit()
        return pipe_id
    
    def remove_pipes_from_model(self, pipe_ids):
        """Removes pipes from the model."""
        for pipe_id in pipe_ids:
            if pipe_id in self.diagram_model['pipes']:
                del self.diagram_model['pipes'][pipe_id]
        
        self.diagram_model_changed.emit()

    def get_port_scene_position(self, component_id, port_name):
        # This is a helper for the UI to know where to draw pipes.
        # It needs access to the scene items, so it might be better placed
        # in the DiagramWidget or passed the scene as an argument.
        # For now, it's a placeholder.
        return None

    # --- Existing methods (some may need refactoring later) ---
    def create_group(self, group_name, sensor_names):
        if group_name not in self.sensor_groups:
            self.sensor_groups[group_name] = []
        for name in sensor_names:
            for g_name, g_list in self.sensor_groups.items():
                if name in g_list:
                    g_list.remove(name)
        self.sensor_groups[group_name].extend(sensor_names)
        self.data_changed.emit()

    def rename_group(self, old_name, new_name):
        if old_name in self.sensor_groups and new_name not in self.sensor_groups:
            self.sensor_groups[new_name] = self.sensor_groups.pop(old_name)
            self.data_changed.emit()
    
    def delete_group(self, group_name):
        if group_name in self.sensor_groups:
            del self.sensor_groups[group_name]
            self.data_changed.emit()
            
    # --- The methods below are largely unchanged for this phase ---
    # ... (set_sensor_ranges, get_sensor_value, etc.) ...
    def get_sensor_list(self):
        if self.csv_data is not None:
            return self.csv_data.columns.tolist()[1:]
        elif self.config_sensor_list:
            return self.config_sensor_list
        return []

    # --- Stubs for methods that were removed from the original but are referenced ---
    @property
    def mappings(self):
        # Legacy property, can be removed later
        return self.diagram_model.get('sensor_roles', {})

