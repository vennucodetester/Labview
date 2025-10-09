from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QListWidget, QListWidgetItem, QLabel, QDialogButtonBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDrag, QColor

class MappingDialog(QDialog):
    """
    A dialog to allow the user to reconcile differences between sensors
    in a loaded config file and a newly loaded CSV file.
    """
    def __init__(self, orphaned_sensors, new_sensors, matched_sensors, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reconcile Sensor Changes")
        self.setMinimumSize(800, 600)
        
        self.user_mappings = {} # Dict to store {orphaned: new}

        main_layout = QVBoxLayout(self)

        # Instructions
        info_label = QLabel(
            "A new CSV has been loaded with different sensors than the configuration.\n"
            "Please map the 'Orphaned' sensors (from config) to the 'New' sensors (from CSV).\n"
            "Drag an orphaned sensor and drop it onto its new equivalent."
        )
        info_label.setStyleSheet("padding: 10px; background-color: #e3f2fd; border-radius: 5px;")
        main_layout.addWidget(info_label)

        # Lists Layout
        lists_layout = QHBoxLayout()
        main_layout.addLayout(lists_layout)
        
        # Orphaned Sensors Column
        orphaned_layout = QVBoxLayout()
        orphaned_layout.addWidget(QLabel("<h3>Orphaned Sensors (from Config)</h3>"))
        self.orphaned_list = QListWidget()
        self.orphaned_list.setDragEnabled(True)
        self.orphaned_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.orphaned_list.addItems(orphaned_sensors)
        orphaned_layout.addWidget(self.orphaned_list)
        lists_layout.addLayout(orphaned_layout)

        # New Sensors Column
        new_layout = QVBoxLayout()
        new_layout.addWidget(QLabel("<h3>New Sensors (from CSV)</h3>"))
        self.new_list = QListWidget()
        self.new_list.setAcceptDrops(True)
        self.new_list.setDropIndicatorShown(True)
        self.new_list.addItems(new_sensors)
        # Override drop event to handle mapping
        self.new_list.dropEvent = self.handle_drop_event
        self.new_list.dragEnterEvent = self.handle_drag_enter
        self.new_list.dragMoveEvent = self.handle_drag_move
        new_layout.addWidget(self.new_list)
        lists_layout.addLayout(new_layout)

        # Matched Sensors Column
        matched_layout = QVBoxLayout()
        matched_layout.addWidget(QLabel("<h3>Automatically Matched</h3>"))
        self.matched_list = QListWidget()
        self.matched_list.addItems(matched_sensors)
        matched_layout.addWidget(self.matched_list)
        lists_layout.addLayout(matched_layout)

        # --- Buttons ---
        button_layout = QHBoxLayout()
        auto_match_button = QPushButton("Auto-Match by Name")
        auto_match_button.clicked.connect(self.auto_match)
        button_layout.addWidget(auto_match_button)
        button_layout.addStretch()
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        button_layout.addWidget(self.button_box)
        main_layout.addLayout(button_layout)
        
    def handle_drag_enter(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def handle_drag_move(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def handle_drop_event(self, event):
        if not event.mimeData().hasText():
            return

        dragged_item_text = event.mimeData().text()
        target_item = self.new_list.itemAt(event.position().toPoint())

        if not target_item:
            return

        target_item_text = target_item.text()

        # Update our internal mapping
        # Check if the new sensor is already a target
        if target_item_text in self.user_mappings.values():
            # Find which orphan is mapped to it and unmap
            for orphan, new in self.user_mappings.items():
                if new == target_item_text:
                    del self.user_mappings[orphan]
                    break
        
        self.user_mappings[dragged_item_text] = target_item_text
        print(f"Mapped: {dragged_item_text} -> {target_item_text}")

        # Update UI to show the mapping
        self.update_list_styles()
        event.acceptProposedAction()


    def update_list_styles(self):
        """Update item backgrounds to show what's been mapped."""
        # Reset styles first
        for i in range(self.orphaned_list.count()):
            self.orphaned_list.item(i).setBackground(QColor("white"))
        for i in range(self.new_list.count()):
            self.new_list.item(i).setBackground(QColor("white"))

        # Highlight mapped items
        mapped_orphans = self.user_mappings.keys()
        mapped_news = self.user_mappings.values()

        for i in range(self.orphaned_list.count()):
            item = self.orphaned_list.item(i)
            if item.text() in mapped_orphans:
                item.setBackground(QColor("#d4edda")) # Light green
        
        for i in range(self.new_list.count()):
            item = self.new_list.item(i)
            if item.text() in mapped_news:
                item.setBackground(QColor("#d4edda"))

    def auto_match(self):
        """
        Attempts to automatically match orphaned sensors to new sensors
        based on a simple string similarity score.
        """
        # Levenshtein distance for similarity
        def levenshtein(s1, s2):
            if len(s1) < len(s2):
                return levenshtein(s2, s1)
            if len(s2) == 0:
                return len(s1)
            previous_row = range(len(s2) + 1)
            for i, c1 in enumerate(s1):
                current_row = [i + 1]
                for j, c2 in enumerate(s2):
                    insertions = previous_row[j + 1] + 1
                    deletions = current_row[j] + 1
                    substitutions = previous_row[j] + (c1 != c2)
                    current_row.append(min(insertions, deletions, substitutions))
                previous_row = current_row
            return previous_row[-1]

        unmapped_orphans = [self.orphaned_list.item(i).text() for i in range(self.orphaned_list.count()) if self.orphaned_list.item(i).text() not in self.user_mappings]
        unmapped_new = [self.new_list.item(i).text() for i in range(self.new_list.count()) if self.new_list.item(i).text() not in self.user_mappings.values()]

        for orphan in unmapped_orphans:
            best_match = None
            best_score = 0.5 # Require at least 50% similarity
            
            for new_sensor in unmapped_new:
                distance = levenshtein(orphan.lower(), new_sensor.lower())
                similarity = 1 - (distance / max(len(orphan), len(new_sensor)))
                if similarity > best_score:
                    best_score = similarity
                    best_match = new_sensor
            
            if best_match:
                self.user_mappings[orphan] = best_match
                # Remove the matched new sensor from the available pool for this iteration
                unmapped_new.remove(best_match)

        self.update_list_styles()

    def get_mappings(self):
        return self.user_mappings
