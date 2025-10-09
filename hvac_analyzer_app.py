import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTabWidget, QLabel, QFrame, QPushButton,
                             QFileDialog)
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt

# Import our component classes
from data_manager import DataManager
from sensor_panel import SensorPanel
from diagram_widget import DiagramWidget
from graph_widget import GraphWidget
from mapping_dialog import MappingDialog

class MainWindow(QMainWindow):
    """The main application window, orchestrating all other components."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HVAC System Analyzer (Python Edition)")
        self.setGeometry(100, 100, 1600, 900)
        self.set_light_theme()

        self.data_manager = DataManager(self) 

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Instantiate UI Components ---
        self.sensor_panel = SensorPanel(self.data_manager)
        self.diagram_widget = DiagramWidget(self.data_manager)
        self.graph_widget = GraphWidget(self.data_manager)

        # --- Assemble Layout ---
        self.sensor_panel.setFixedWidth(350) 
        main_layout.addWidget(self.sensor_panel)
        
        right_panel = self.setup_tabs()
        main_layout.addWidget(right_panel)
        
        # --- Connect Signals and Slots ---
        self.connect_signals()

    def setup_tabs(self):
        """Creates the tab widget and populates it with our custom widgets."""
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        
        self.tabs = QTabWidget()
        
        self.comparison_tab = QLabel("Comparison View will go here.")
        self.diagnostics_tab = QLabel("Diagnostics View will go here.")

        self.tabs.addTab(self.diagram_widget, "Diagram")
        self.tabs.addTab(self.graph_widget, "Graph")
        self.tabs.addTab(self.comparison_tab, "Comparison")
        self.tabs.addTab(self.diagnostics_tab, "Case Diagnostics")
        
        right_layout.addWidget(self.tabs)
        return right_panel

    def connect_signals(self):
        """Central place to connect all component signals to controller slots."""
        self.sensor_panel.load_csv_button.clicked.connect(self.open_csv_file_dialog)
        self.sensor_panel.load_config_button.clicked.connect(self.open_session_file_dialog)
        
        # The single data_changed signal now drives all UI updates.
        self.data_manager.data_changed.connect(self.sensor_panel.update_ui)
        self.data_manager.data_changed.connect(self.diagram_widget.update_ui)
        self.data_manager.data_changed.connect(self.graph_widget.update_ui)

        # --- FIX: Removed connection to the non-existent signal ---
        # self.sensor_panel.graph_sensor_toggled.connect(self.on_graph_sensor_toggled)
        
    def open_csv_file_dialog(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open CSV File", "", "CSV Files (*.csv)")
        if file_name:
            self.data_manager.load_csv(file_name) 

    def open_session_file_dialog(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Session File", "", "JSON Files (*.json)")
        if file_name:
            self.data_manager.load_session(file_name) 
    
    # --- FIX: Removed the unused slot method ---
    # def on_graph_sensor_toggled(self, sensor_name, is_selected_for_graph):
    #     self.data_manager.set_sensor_graphed(sensor_name, is_selected_for_graph)
    #     self.data_manager.data_changed.emit()

    def set_light_theme(self):
        """Sets a professional light theme for the application."""
        app = QApplication.instance()
        app.setStyle("Fusion")
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
        palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
        palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.black)
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
        palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
        app.setPalette(palette)
        self.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #c4c4c4; background: #ffffff; }
            QTabBar::tab { 
                background: #e1e1e1; color: #333; padding: 10px 25px; 
                font-weight: bold; border: 1px solid #c4c4c4; border-bottom: none;
                border-top-left-radius: 4px; border-top-right-radius: 4px;
            }
            QTabBar::tab:selected { 
                background: #ffffff; color: #007bff; border-bottom: 2px solid #007bff;
            }
        """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

