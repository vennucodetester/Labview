import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTabWidget, QLabel, QFrame, QPushButton,
                             QFileDialog, QDockWidget)
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt

# Import our component classes
from data_manager import DataManager
from sensor_panel import SensorPanel
from graph_widget import GraphWidget
from comparison_widget import ComparisonWidget
# --- MODIFIED: Import the new, interactive DiagramWidget ---
from diagram_widget import DiagramWidget, PropertyEditor
# --- NEW: Import system analyzer (not used in UI yet, but good practice) ---
import system_analyzer


class MainWindow(QMainWindow):
    """The main application window, orchestrating all other components."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HVAC System Analyzer (Intelligent Modeler)")
        self.setGeometry(100, 100, 1800, 1000) # Increased size
        self.set_light_theme()

        self.data_manager = DataManager(self) 

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- Instantiate UI Components ---
        self.sensor_panel = SensorPanel(self.data_manager)
        # --- MODIFIED: DiagramWidget is now the new interactive version ---
        self.diagram_widget = DiagramWidget(self.data_manager)
        self.graph_widget = GraphWidget(self.data_manager)
        self.comparison_widget = ComparisonWidget(self.data_manager)

        # --- Assemble Layout ---
        self.sensor_panel.setFixedWidth(350) 
        main_layout.addWidget(self.sensor_panel)
        
        # The tab widget is now the main central area
        right_panel = self.setup_tabs()
        main_layout.addWidget(right_panel)
        
        # --- NEW: Add the Property Editor as a Dock Widget ---
        self.property_editor_dock = QDockWidget("Properties", self)
        self.property_editor_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self.property_editor = PropertyEditor(self.data_manager)
        self.property_editor_dock.setWidget(self.property_editor)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.property_editor_dock)
        
        # --- Connect Signals and Slots ---
        self.connect_signals()

    def setup_tabs(self):
        """Creates the tab widget and populates it with our custom widgets."""
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        # Placeholder for diagnostics tab
        self.diagnostics_tab = QLabel("Diagnostics View will go here.")

        # --- MODIFIED: The main tab is now the interactive diagram ---
        self.tabs.addTab(self.diagram_widget, "Diagram Modeler")
        self.tabs.addTab(self.graph_widget, "Graph")
        self.tabs.addTab(self.comparison_widget, "Comparison")
        self.tabs.addTab(self.diagnostics_tab, "Case Diagnostics")
        
        return self.tabs

    def connect_signals(self):
        """Central place to connect all component signals to controller slots."""
        self.sensor_panel.load_csv_button.clicked.connect(self.open_csv_file_dialog)
        self.sensor_panel.load_config_button.clicked.connect(self.open_session_file_dialog)
        self.sensor_panel.save_config_button.clicked.connect(self.save_session_file_dialog)
        
        self.data_manager.data_changed.connect(self.update_active_tab)

    def open_csv_file_dialog(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open CSV File", "", "CSV Files (*.csv)")
        if file_name:
            self.data_manager.load_csv(file_name) 

    def open_session_file_dialog(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Session File", "", "JSON Files (*.json)")
        if file_name:
            self.data_manager.load_session(file_name)
    
    def save_session_file_dialog(self):
        file_name, _ = QFileDialog.getSaveFileName(self, "Save Session File", "", "JSON Files (*.json)")
        if file_name:
            self.data_manager.save_session(file_name) 
    
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts, passing Delete to the diagram widget."""
        # --- NEW: Forward delete key press to the diagram widget ---
        if event.key() == Qt.Key.Key_Delete:
            if self.tabs.currentWidget() == self.diagram_widget:
                self.diagram_widget.keyPressEvent(event)
                return

        if event.key() == Qt.Key.Key_Escape:
            self.data_manager.selected_sensors.clear()
            self.data_manager.data_changed.emit()
        else:
            super().keyPressEvent(event)

    def on_tab_changed(self, index):
        self.update_active_tab()

    def update_active_tab(self):
        try:
            self.sensor_panel.update_ui()
        except Exception as e:
            print(f"Error updating sensor panel: {e}")

        current_widget = self.tabs.currentWidget()
        try:
            # The diagram widget now has its own update logic connected via signals
            if hasattr(current_widget, 'update_ui'):
                 current_widget.update_ui()
        except Exception as e:
            print(f"Error updating active tab: {e}")

    def set_light_theme(self):
        """Sets a professional light theme for the application."""
        app = QApplication.instance()
        app.setStyle("Fusion")
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
        palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
        # ... rest of the theme code
        app.setPalette(palette)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

