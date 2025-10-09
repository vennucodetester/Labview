import pandas as pd
import json
import base64
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QPixmap
from mapping_dialog import MappingDialog

class DataManager(QObject):
    """
    Centralized class to manage all application data, including sensor groups.
    """
    data_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self._reset_state()

    def _reset_state(self):
        """Resets all data to initial state."""
        self.csv_data = None
        self.mappings = {}
        self.selected_sensors = set()
        self.graph_sensors = set()
        self.sensor_groups = {}
        self.image_path = None
        self.image_pixmap = None
        self.config_path = None
        self.current_mode = 'mapping'
        self.config_sensor_list = [] 

    # --- load_csv and reconcile_csv are unchanged ---
    def load_csv(self, file_path):
        """
        Loads a CSV. If a config is already loaded, it triggers
        the reconciliation process.
        """
        try:
            new_csv_data = pd.read_csv(file_path)
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

        dialog = MappingDialog(orphaned, new, matched, parent=self.parent)
        if dialog.exec():
            user_mappings = dialog.get_mappings()
            new_mappings_dict = {}
            for old_sensor, mapping_data in self.mappings.items():
                if old_sensor in matched:
                    new_mappings_dict[old_sensor] = mapping_data
                elif old_sensor in user_mappings:
                    new_sensor_name = user_mappings[old_sensor]
                    new_mappings_dict[new_sensor_name] = mapping_data
            self.mappings = new_mappings_dict
            self.csv_data = new_csv_data
            self.config_sensor_list = new_sensor_list
            self.data_changed.emit()

    def load_session(self, file_path):
        """Loads a .json session file with specified UTF-8 encoding."""
        try:
            self._reset_state()
            self.config_path = file_path
            with open(file_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            self.mappings = session_data.get('mappings', {})
            # --- UPDATED: Now loads sensor groups from the config file ---
            self.sensor_groups = session_data.get('sensorGroups', {})

            csv_data_obj = session_data.get('csvData')
            if csv_data_obj and 'headers' in csv_data_obj:
                self.config_sensor_list = csv_data_obj.get('headers', [])
            else:
                self.config_sensor_list = session_data.get('csvHeaders', [])

            if self.config_sensor_list:
                self.config_sensor_list = self.config_sensor_list[1:]

            image_data_base64 = session_data.get('imageData')
            if image_data_base64:
                try:
                    header, encoded = image_data_base64.split(",", 1)
                    image_bytes = base64.b64decode(encoded)
                    pixmap = QPixmap()
                    pixmap.loadFromData(image_bytes)
                    self.image_pixmap = pixmap
                except Exception as e:
                    print(f"Error decoding base64 image data: {e}")

            if self.config_sensor_list and not session_data.get('csvPath'):
                self.csv_data = pd.DataFrame(columns=['Timestamp'] + self.config_sensor_list)

            self.data_changed.emit()
            return True
        except Exception as e:
            print(f"Error loading session file: {e}")
            return False

    # --- NEW METHODS FOR GROUP MANAGEMENT ---
    def create_group(self, group_name, sensor_names):
        """Creates a new group or adds sensors to an existing one."""
        if group_name not in self.sensor_groups:
            self.sensor_groups[group_name] = []
        
        # Remove sensors from any other group they might be in
        for name in sensor_names:
            for g_name, g_list in self.sensor_groups.items():
                if name in g_list:
                    g_list.remove(name)

        # Add sensors to the new group
        self.sensor_groups[group_name].extend(sensor_names)
        self.data_changed.emit()

    def rename_group(self, old_name, new_name):
        """Renames an existing sensor group."""
        if old_name in self.sensor_groups and new_name not in self.sensor_groups:
            self.sensor_groups[new_name] = self.sensor_groups.pop(old_name)
            self.data_changed.emit()

    def move_sensors_to_group(self, target_group_name, sensor_names):
        """Moves a list of sensors to a specified group."""
        # Remove sensors from their old groups
        for name in sensor_names:
            for g_list in self.sensor_groups.values():
                if name in g_list:
                    g_list.remove(name)
        
        # Add them to the new group
        if target_group_name in self.sensor_groups:
            self.sensor_groups[target_group_name].extend(sensor_names)
        
        self.data_changed.emit()


    # --- Unchanged methods below ---
    def load_image_from_path(self, file_path):
        self.image_path = file_path
        self.image_pixmap = QPixmap(file_path)
        self.data_changed.emit()

    def update_mapping(self, sensor_name, x, y):
        if sensor_name not in self.mappings:
            self.mappings[sensor_name] = {}
        self.mappings[sensor_name]['x'] = x
        self.mappings[sensor_name]['y'] = y
    
    def update_mapping_and_notify(self, sensor_name, x, y):
        self.update_mapping(sensor_name, x, y)
        self.data_changed.emit()

    def toggle_sensor_selection(self, sensor_name):
        if sensor_name in self.selected_sensors:
            self.selected_sensors.clear()
        else:
            self.selected_sensors.clear()
            self.selected_sensors.add(sensor_name)
        self.data_changed.emit()

    def set_sensor_selected(self, sensor_name, is_selected):
        if is_selected:
            self.selected_sensors.clear()
            self.selected_sensors.add(sensor_name)
        else:
            self.selected_sensors.discard(sensor_name)

    def set_sensor_graphed(self, sensor_name, is_graphed):
        if is_graphed:
            self.graph_sensors.add(sensor_name)
        else:
            self.graph_sensors.discard(sensor_name)

    def get_sensor_list(self):
        if self.csv_data is not None:
            return self.csv_data.columns.tolist()[1:]
        elif self.config_sensor_list:
            return self.config_sensor_list
        return []

