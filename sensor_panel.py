from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLineEdit, QCheckBox, QTreeWidget, QTreeWidgetItem, 
                             QLabel, QGroupBox, QFrame, QTreeWidgetItemIterator,
                             QAbstractItemView, QMenu, QInputDialog)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QAction

class SensorPanel(QWidget):
    """
    Manages the sensor list UI with a full-featured right-click context menu
    for grouping, renaming, and moving sensors.
    """
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.clipboard = [] # Simple clipboard for cut/paste
        self.setupUi()
        self.connect_signals()

    def setupUi(self):
        """Creates and arranges all the widgets for this panel."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #2196F3; color: white; padding: 10px; border: none;")
        header_layout = QHBoxLayout(header_frame)
        header_layout.addWidget(QLabel("<h3>Sensor Panel</h3>"))
        main_layout.addWidget(header_frame)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        main_layout.addWidget(content_widget)

        file_ops_group = QGroupBox("File Operations")
        file_ops_layout = QHBoxLayout(file_ops_group)
        self.load_config_button = QPushButton("Load Config")
        self.load_csv_button = QPushButton("Load CSV")
        self.save_config_button = QPushButton("Save Config")
        file_ops_layout.addWidget(self.load_config_button)
        file_ops_layout.addWidget(self.load_csv_button)
        file_ops_layout.addWidget(self.save_config_button)
        content_layout.addWidget(file_ops_group)
        
        controls_group = QGroupBox("Controls")
        controls_layout = QVBoxLayout(controls_group)
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search sensors...")
        controls_layout.addWidget(self.search_bar)
        
        self.select_all_graph_checkbox = QCheckBox("Select All for Graph")
        controls_layout.addWidget(self.select_all_graph_checkbox)
        content_layout.addWidget(controls_group)
        
        self.sensor_tree = QTreeWidget()
        self.sensor_tree.setHeaderLabels(["Sensor", "Value", "Graph"])
        self.sensor_tree.setColumnWidth(0, 200)
        self.sensor_tree.setColumnWidth(1, 60)
        # --- NEW: Enable multi-selection with Ctrl and Shift keys ---
        self.sensor_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        # --- NEW: Enable the custom context menu ---
        self.sensor_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        content_layout.addWidget(self.sensor_tree, 1)

        self.stats_label = QLabel("Sensors: 0 | Mapped: 0 | Selected: 0")
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stats_label.setStyleSheet("background-color: #f0f0f0; padding: 8px; border-top: 1px solid #ddd;")
        main_layout.addWidget(self.stats_label)

    def connect_signals(self):
        self.sensor_tree.itemClicked.connect(self.on_item_clicked)
        self.search_bar.textChanged.connect(self.filter_tree_and_select)
        self.sensor_tree.customContextMenuRequested.connect(self.show_context_menu)

    def on_item_clicked(self, item, column):
        """Handles clicks on tree items."""
        if item.childCount() > 0: # Is a group
            return

        sensor_name = item.text(0)
        if column == 2:
            is_checked = item.checkState(2) == Qt.CheckState.Checked
            self.data_manager.set_sensor_graphed(sensor_name, is_checked)
            self.data_manager.data_changed.emit()
        else:
            # Single-clicking a sensor still highlights it for placement
            self.data_manager.toggle_sensor_selection(sensor_name)

    def show_context_menu(self, position):
        """Creates and displays the right-click menu."""
        menu = QMenu()
        selected_items = self.sensor_tree.selectedItems()
        item_under_cursor = self.sensor_tree.itemAt(position)

        if not selected_items:
            return

        # --- Menu actions for SENSOR items ---
        if all(item.childCount() == 0 for item in selected_items):
            group_action = QAction("Group Selected Sensors", self)
            group_action.triggered.connect(self.group_selected_sensors)
            menu.addAction(group_action)

            cut_action = QAction("Cut", self)
            cut_action.triggered.connect(self.cut_sensors)
            menu.addAction(cut_action)

        # --- Menu actions for GROUP items ---
        if item_under_cursor and item_under_cursor.childCount() > 0:
            rename_action = QAction("Rename Group", self)
            rename_action.triggered.connect(lambda: self.rename_group(item_under_cursor))
            menu.addAction(rename_action)

            if self.clipboard:
                paste_action = QAction(f"Paste {len(self.clipboard)} sensor(s)", self)
                paste_action.triggered.connect(lambda: self.paste_sensors(item_under_cursor))
                menu.addAction(paste_action)

        if menu.actions():
            menu.exec(self.sensor_tree.viewport().mapToGlobal(position))

    def group_selected_sensors(self):
        """Prompts for a group name and tells the DataManager to group selected sensors."""
        selected_sensors = [item.text(0) for item in self.sensor_tree.selectedItems() if item.childCount() == 0]
        if not selected_sensors:
            return

        text, ok = QInputDialog.getText(self, 'Create Group', 'Enter group name:')
        if ok and text:
            self.data_manager.create_group(text, selected_sensors)

    def rename_group(self, group_item):
        """Prompts for a new name and renames the group in the DataManager."""
        old_name = group_item.text(0)
        new_name, ok = QInputDialog.getText(self, 'Rename Group', 'Enter new name:', text=old_name)
        if ok and new_name and new_name != old_name:
            self.data_manager.rename_group(old_name, new_name)

    def cut_sensors(self):
        """Copies selected sensor names to the internal clipboard."""
        self.clipboard = [item.text(0) for item in self.sensor_tree.selectedItems() if item.childCount() == 0]
        print(f"Cut {len(self.clipboard)} sensors to clipboard.")

    def paste_sensors(self, target_group_item):
        """Moves sensors from the clipboard to the target group in the DataManager."""
        if not self.clipboard:
            return
        
        target_group_name = target_group_item.text(0)
        self.data_manager.move_sensors_to_group(target_group_name, self.clipboard)
        self.clipboard.clear()

    def update_ui(self):
        """Redraws the sensor list with groups based on the DataManager's state."""
        self.sensor_tree.clear()
        
        all_sensors = set(self.data_manager.get_sensor_list())
        grouped_sensors = set()

        # Create items for each group and its sensors
        for group_name, sensor_list in sorted(self.data_manager.sensor_groups.items()):
            group_item = QTreeWidgetItem(self.sensor_tree, [group_name])
            group_item.setExpanded(True)
            for sensor_name in sorted(sensor_list):
                if sensor_name in all_sensors:
                    self.create_sensor_item(sensor_name, group_item)
                    grouped_sensors.add(sensor_name)
        
        # Create "Ungrouped" for any remaining sensors
        ungrouped_list = sorted(list(all_sensors - grouped_sensors))
        if ungrouped_list:
            ungrouped_item = QTreeWidgetItem(self.sensor_tree, ["Ungrouped"])
            ungrouped_item.setExpanded(True)
            for sensor_name in ungrouped_list:
                self.create_sensor_item(sensor_name, ungrouped_item)

        self.update_stats()
    
    def create_sensor_item(self, sensor_name, parent_item):
        """Helper function to create and configure a single sensor item."""
        sensor_item = QTreeWidgetItem(parent_item)
        sensor_item.setText(0, sensor_name)
        
        if sensor_name in self.data_manager.selected_sensors:
            sensor_item.setBackground(0, QColor("#ffc107"))
        
        sensor_item.setText(1, "N/A")
        sensor_item.setFlags(sensor_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        if sensor_name in self.data_manager.graph_sensors:
             sensor_item.setCheckState(2, Qt.CheckState.Checked)
        else:
             sensor_item.setCheckState(2, Qt.CheckState.Unchecked)

    def filter_tree_and_select(self, text):
        """Filters the tree and auto-selects all visible items."""
        self.sensor_tree.clearSelection()
        iterator = QTreeWidgetItemIterator(self.sensor_tree)
        is_hidden = text.lower() != ""
        
        while iterator.value():
            item = iterator.value()
            if item.childCount() == 0: # Is a sensor item
                matches = text.lower() in item.text(0).lower()
                item.setHidden(is_hidden and not matches)
                if not item.isHidden():
                    item.setSelected(True)
            iterator += 1

    def update_stats(self):
        total = len(self.data_manager.get_sensor_list())
        mapped = len(self.data_manager.mappings)
        selected = len(self.sensor_tree.selectedItems())
        self.stats_label.setText(f"Sensors: {total} | Mapped: {mapped} | Selected: {selected}")

