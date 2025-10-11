from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QDialogButtonBox, QLineEdit, QMessageBox,
                             QScrollArea, QWidget, QFrame)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QDoubleValidator


class RangeDialog(QDialog):
    """Dialog to set min/max ranges for sensors and groups."""
    
    def __init__(self, sensor_groups, current_ranges, all_sensors, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Sensor Ranges")
        self.setMinimumSize(900, 700)
        
        # Store sensor groups and current ranges
        self.sensor_groups = sensor_groups
        self.all_sensors = all_sensors
        self.ranges = dict(current_ranges)  # Copy to avoid modifying original
        
        # Store references to input widgets for easy access
        self.sensor_inputs = {}  # {sensor_name: {'min': QLineEdit, 'max': QLineEdit}}
        self.group_inputs = {}   # {group_name: {'min': QLineEdit, 'max': QLineEdit}}
        
        self.setup_ui()
        self.populate_sensors()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Instructions
        info = QLabel(
            "<b>Set Sensor Ranges (Min/Max)</b><br>"
            "• Enter min/max values directly next to each sensor<br>"
            "• Enter values next to a group header and click 'Apply to All' to set for entire group<br>"
            "• Leave fields empty for no limit • Values auto-save when you type"
        )
        info.setWordWrap(True)
        info.setStyleSheet(
            "padding: 10px; background-color: #e3f2fd; "
            "border-radius: 4px; border: 1px solid #90caf9;"
        )
        layout.addWidget(info)
        
        # Create scrollable area for sensors
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Container widget for all sensor/group rows
        self.container_widget = QWidget()
        self.container_layout = QVBoxLayout(self.container_widget)
        self.container_layout.setContentsMargins(5, 5, 5, 5)
        self.container_layout.setSpacing(2)
        
        scroll_area.setWidget(self.container_widget)
        layout.addWidget(scroll_area, 1)
        
        # Bottom action buttons
        button_layout = QHBoxLayout()
        
        clear_all_btn = QPushButton("Clear All Ranges")
        clear_all_btn.clicked.connect(self.clear_all_ranges)
        button_layout.addWidget(clear_all_btn)
        
        button_layout.addStretch()
        
        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        button_layout.addWidget(buttons)
        
        layout.addLayout(button_layout)
    
    def populate_sensors(self):
        """Populate the scrollable area with groups and sensors."""
        # Clear existing widgets
        while self.container_layout.count():
            child = self.container_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        self.sensor_inputs.clear()
        self.group_inputs.clear()
        
        # Find ungrouped sensors
        all_grouped_sensors = set()
        for sensors in self.sensor_groups.values():
            all_grouped_sensors.update(sensors)
        
        ungrouped_sensors = [s for s in self.all_sensors if s not in all_grouped_sensors]
        
        # Create a combined list: regular groups + ungrouped
        groups_to_display = list(sorted(self.sensor_groups.items()))
        if ungrouped_sensors:
            groups_to_display.append(("Ungrouped", ungrouped_sensors))
        
        # Iterate through groups and create UI elements
        for group_name, sensors in groups_to_display:
            if not sensors:
                continue
            
            # Create group header frame
            group_frame = QFrame()
            group_frame.setStyleSheet("background-color: #e0e0e0; padding: 5px; border-radius: 3px;")
            group_layout = QHBoxLayout(group_frame)
            group_layout.setContentsMargins(10, 5, 10, 5)
            
            # Group name label
            group_label = QLabel(f"<b>{group_name}</b> ({len(sensors)} sensors)")
            group_label.setMinimumWidth(300)
            group_layout.addWidget(group_label)
            
            # Group min input
            group_min = QLineEdit()
            group_min.setPlaceholderText("Min")
            group_min.setValidator(QDoubleValidator())
            group_min.setFixedWidth(100)
            group_layout.addWidget(QLabel("Min:"))
            group_layout.addWidget(group_min)
            
            # Group max input
            group_max = QLineEdit()
            group_max.setPlaceholderText("Max")
            group_max.setValidator(QDoubleValidator())
            group_max.setFixedWidth(100)
            group_layout.addWidget(QLabel("Max:"))
            group_layout.addWidget(group_max)
            
            # Apply to all button
            apply_btn = QPushButton("Apply to All")
            apply_btn.setFixedWidth(100)
            apply_btn.clicked.connect(lambda checked, g=group_name: self.apply_group_range(g))
            group_layout.addWidget(apply_btn)
            
            # Clear all button
            clear_btn = QPushButton("Clear All")
            clear_btn.setFixedWidth(100)
            clear_btn.clicked.connect(lambda checked, g=group_name: self.clear_group_ranges(g))
            group_layout.addWidget(clear_btn)
            
            group_layout.addStretch()
            
            # Store references to group inputs
            self.group_inputs[group_name] = {'min': group_min, 'max': group_max}
            
            self.container_layout.addWidget(group_frame)
            
            # Add sensors in this group
            for sensor_name in sorted(sensors):
                sensor_frame = QFrame()
                sensor_frame.setStyleSheet("background-color: #ffffff; padding: 3px; border-bottom: 1px solid #e0e0e0;")
                sensor_layout = QHBoxLayout(sensor_frame)
                sensor_layout.setContentsMargins(30, 3, 10, 3)
                
                # Sensor name label
                sensor_label = QLabel(sensor_name)
                sensor_label.setMinimumWidth(300)
                sensor_layout.addWidget(sensor_label)
                
                # Sensor min input
                sensor_min = QLineEdit()
                sensor_min.setPlaceholderText("Min")
                sensor_min.setValidator(QDoubleValidator())
                sensor_min.setFixedWidth(100)
                sensor_min.textChanged.connect(lambda text, s=sensor_name: self.on_sensor_range_changed(s))
                sensor_layout.addWidget(QLabel("Min:"))
                sensor_layout.addWidget(sensor_min)
                
                # Sensor max input
                sensor_max = QLineEdit()
                sensor_max.setPlaceholderText("Max")
                sensor_max.setValidator(QDoubleValidator())
                sensor_max.setFixedWidth(100)
                sensor_max.textChanged.connect(lambda text, s=sensor_name: self.on_sensor_range_changed(s))
                sensor_layout.addWidget(QLabel("Max:"))
                sensor_layout.addWidget(sensor_max)
                
                # Clear button for individual sensor
                clear_sensor_btn = QPushButton("Clear")
                clear_sensor_btn.setFixedWidth(100)
                clear_sensor_btn.clicked.connect(lambda checked, s=sensor_name: self.clear_sensor_range(s))
                sensor_layout.addWidget(clear_sensor_btn)
                
                sensor_layout.addStretch()
                
                # Populate with existing values if any
                if sensor_name in self.ranges:
                    range_data = self.ranges[sensor_name]
                    if 'min' in range_data and range_data['min'] is not None:
                        sensor_min.setText(str(range_data['min']))
                    if 'max' in range_data and range_data['max'] is not None:
                        sensor_max.setText(str(range_data['max']))
                    # Highlight sensor with existing range
                    sensor_frame.setStyleSheet("background-color: #c8e6c9; padding: 3px; border-bottom: 1px solid #e0e0e0;")
                
                # Store references to sensor inputs
                self.sensor_inputs[sensor_name] = {'min': sensor_min, 'max': sensor_max, 'frame': sensor_frame}
                
                self.container_layout.addWidget(sensor_frame)
        
        # Add stretch at the end to push everything to the top
        self.container_layout.addStretch()
    
    def on_sensor_range_changed(self, sensor_name):
        """Auto-save when sensor range inputs change."""
        if sensor_name not in self.sensor_inputs:
            return
        
        inputs = self.sensor_inputs[sensor_name]
        min_val = inputs['min'].text().strip()
        max_val = inputs['max'].text().strip()
        
        # If both are empty, remove the range
        if not min_val and not max_val:
            if sensor_name in self.ranges:
                del self.ranges[sensor_name]
                inputs['frame'].setStyleSheet("background-color: #ffffff; padding: 3px; border-bottom: 1px solid #e0e0e0;")
            return
        
        # Store range
        range_data = {}
        
        if min_val:
            try:
                range_data['min'] = float(min_val)
            except ValueError:
                return  # Invalid input, just ignore
        else:
            range_data['min'] = None
        
        if max_val:
            try:
                range_data['max'] = float(max_val)
            except ValueError:
                return  # Invalid input, just ignore
        else:
            range_data['max'] = None
        
        # Validate min < max if both provided
        if range_data['min'] is not None and range_data['max'] is not None:
            if range_data['min'] >= range_data['max']:
                return  # Invalid range, just ignore
        
        self.ranges[sensor_name] = range_data
        # Highlight sensor with range
        inputs['frame'].setStyleSheet("background-color: #c8e6c9; padding: 3px; border-bottom: 1px solid #e0e0e0;")
    
    def clear_sensor_range(self, sensor_name):
        """Clear the range for a specific sensor."""
        if sensor_name in self.sensor_inputs:
            self.sensor_inputs[sensor_name]['min'].clear()
            self.sensor_inputs[sensor_name]['max'].clear()
        
        if sensor_name in self.ranges:
            del self.ranges[sensor_name]
    
    def clear_all_ranges(self):
        """Clear all ranges."""
        reply = QMessageBox.question(self, 'Clear All Ranges',
                                     'Are you sure you want to clear all sensor ranges?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.ranges.clear()
            # Clear all input fields
            for inputs in self.sensor_inputs.values():
                inputs['min'].clear()
                inputs['max'].clear()
            for inputs in self.group_inputs.values():
                inputs['min'].clear()
                inputs['max'].clear()
    
    def apply_group_range(self, group_name):
        """Apply the group's input values to all sensors in that group."""
        if group_name not in self.group_inputs:
            return
        
        group_inputs = self.group_inputs[group_name]
        min_val = group_inputs['min'].text().strip()
        max_val = group_inputs['max'].text().strip()
        
        if not min_val and not max_val:
            QMessageBox.warning(self, "No Range", "Please enter min and/or max values in the group fields first.")
            return
        
        # Get sensors in group (handle "Ungrouped" specially)
        if group_name == "Ungrouped":
            all_grouped_sensors = set()
            for sensors in self.sensor_groups.values():
                all_grouped_sensors.update(sensors)
            sensors = [s for s in self.all_sensors if s not in all_grouped_sensors]
        else:
            sensors = self.sensor_groups.get(group_name, [])
        
        if not sensors:
            return
        
        # Parse values
        range_data = {}
        if min_val:
            try:
                range_data['min'] = float(min_val)
            except ValueError:
                QMessageBox.warning(self, "Invalid Input", "Min value must be a number.")
                return
        else:
            range_data['min'] = None
        
        if max_val:
            try:
                range_data['max'] = float(max_val)
            except ValueError:
                QMessageBox.warning(self, "Invalid Input", "Max value must be a number.")
                return
        else:
            range_data['max'] = None
        
        # Validate min < max if both provided
        if range_data['min'] is not None and range_data['max'] is not None:
            if range_data['min'] >= range_data['max']:
                QMessageBox.warning(self, "Invalid Range", "Min value must be less than Max value.")
                return
        
        # Apply to all sensors in group
        for sensor_name in sensors:
            self.ranges[sensor_name] = dict(range_data)
            # Update the sensor input fields
            if sensor_name in self.sensor_inputs:
                inputs = self.sensor_inputs[sensor_name]
                if range_data['min'] is not None:
                    inputs['min'].setText(str(range_data['min']))
                else:
                    inputs['min'].clear()
                if range_data['max'] is not None:
                    inputs['max'].setText(str(range_data['max']))
                else:
                    inputs['max'].clear()
                # Highlight
                inputs['frame'].setStyleSheet("background-color: #c8e6c9; padding: 3px; border-bottom: 1px solid #e0e0e0;")
        
        QMessageBox.information(self, "Success", 
                               f"Applied range to {len(sensors)} sensors in group '{group_name}'.")
    
    def clear_group_ranges(self, group_name):
        """Clear ranges for all sensors in a group."""
        # Get sensors in group (handle "Ungrouped" specially)
        if group_name == "Ungrouped":
            all_grouped_sensors = set()
            for sensors in self.sensor_groups.values():
                all_grouped_sensors.update(sensors)
            sensors = [s for s in self.all_sensors if s not in all_grouped_sensors]
        else:
            sensors = self.sensor_groups.get(group_name, [])
        
        if not sensors:
            return
        
        for sensor_name in sensors:
            if sensor_name in self.ranges:
                del self.ranges[sensor_name]
            # Clear the sensor input fields
            if sensor_name in self.sensor_inputs:
                self.sensor_inputs[sensor_name]['min'].clear()
                self.sensor_inputs[sensor_name]['max'].clear()
                self.sensor_inputs[sensor_name]['frame'].setStyleSheet("background-color: #ffffff; padding: 3px; border-bottom: 1px solid #e0e0e0;")
    
    def get_ranges(self):
        """Return the configured ranges."""
        return self.ranges

