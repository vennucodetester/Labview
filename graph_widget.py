import pyqtgraph as pg
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QFrame, 
                             QLabel, QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import Qt
import pandas as pd

class GraphWidget(QWidget):
    """
    Python translation of 'tab-graph.html'.
    Uses pyqtgraph for high-performance plotting and includes a detailed stats legend.
    """
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')

        self.setupUi()
        self.connect_signals()

    def setupUi(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Header ---
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #34495e; color: white; padding: 10px; border: none;")
        header_layout = QHBoxLayout(header_frame)
        self.header_label = QLabel("<h3>Sensor Graphs</h3>")
        header_layout.addWidget(self.header_label)
        header_layout.addStretch()
        main_layout.addWidget(header_frame)
        
        # --- Control Bar ---
        control_bar = QFrame()
        control_bar.setStyleSheet("background-color: #f0f0f0; border-bottom: 1px solid #ddd;")
        control_layout = QHBoxLayout(control_bar)
        self.reset_zoom_btn = QPushButton("Reset Zoom")
        self.export_btn = QPushButton("Export")
        control_layout.addWidget(self.reset_zoom_btn)
        control_layout.addWidget(self.export_btn)
        control_layout.addStretch()
        main_layout.addWidget(control_bar)

        # --- Plot Widget ---
        self.plot_widget = pg.PlotWidget(axisItems={'bottom': pg.DateAxisItem()})
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.getAxis('left').setLabel('Sensor Value')
        self.plot_widget.getAxis('bottom').setLabel('Time')
        # We are using a custom legend table, so the built-in one is not needed.
        # self.legend = self.plot_widget.addLegend() 
        main_layout.addWidget(self.plot_widget, 3) # Give plot more space

        # --- Custom Legend/Stats Table ---
        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(6)
        self.stats_table.setHorizontalHeaderLabels(["Sensor Name", "Color", "Avg", "Min", "Max", "Delta"])
        self.stats_table.verticalHeader().setVisible(False)
        self.stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.stats_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.stats_table.setMaximumHeight(250)
        main_layout.addWidget(self.stats_table, 1) # Give table space

    def connect_signals(self):
        self.reset_zoom_btn.clicked.connect(self.plot_widget.autoRange)
        self.export_btn.clicked.connect(self.export_graph)

    def update_ui(self):
        """Redraws the graph and stats table based on the DataManager's state."""
        print("GraphWidget: Updating UI based on data change.")
        self.plot_widget.clear()
        self.stats_table.setRowCount(0)

        df = self.data_manager.csv_data
        sensors_to_plot = self.data_manager.graph_sensors

        if df is None or not sensors_to_plot or df.empty:
            self.header_label.setText("<h3>Sensor Graphs (No data selected)</h3>")
            return
            
        self.header_label.setText(f"<h3>Sensor Graphs ({len(sensors_to_plot)} selected)</h3>")

        colors = ['#E74C3C', '#3498DB', '#2ECC71', '#F39C12', '#9B59B6', '#1ABC9C']
        
        timestamps = None
        has_timestamps = False
        if 'Timestamp' in df.columns:
            try:
                # Convert timestamp strings to Unix timestamps for plotting
                timestamps = pd.to_datetime(df['Timestamp']).astype('int64') // 10**9
                has_timestamps = True
            except Exception as e:
                print(f"Timestamp conversion failed: {e}. Plotting by index.")
        
        self.stats_table.setRowCount(len(sensors_to_plot))
        
        for i, sensor_name in enumerate(sensors_to_plot):
            if sensor_name in df.columns:
                pen = pg.mkPen(color=colors[i % len(colors)], width=2)
                y_data = df[sensor_name].to_numpy()

                # Plotting
                if has_timestamps:
                    self.plot_widget.plot(x=timestamps.to_numpy(), y=y_data, pen=pen, name=sensor_name)
                else:
                    self.plot_widget.plot(y_data, pen=pen, name=sensor_name)

                # --- Update Stats Table ---
                self.stats_table.setItem(i, 0, QTableWidgetItem(sensor_name))
                
                # Color swatch
                color_item = QTableWidgetItem()
                color_item.setBackground(pg.mkColor(colors[i % len(colors)]))
                self.stats_table.setItem(i, 1, color_item)
                
                # Calculate stats
                valid_data = df[sensor_name].dropna()
                if not valid_data.empty:
                    avg_val = valid_data.mean()
                    min_val = valid_data.min()
                    max_val = valid_data.max()
                    delta_val = max_val - min_val

                    self.stats_table.setItem(i, 2, QTableWidgetItem(f"{avg_val:.2f}"))
                    self.stats_table.setItem(i, 3, QTableWidgetItem(f"{min_val:.2f}"))
                    self.stats_table.setItem(i, 4, QTableWidgetItem(f"{max_val:.2f}"))
                    self.stats_table.setItem(i, 5, QTableWidgetItem(f"{delta_val:.2f}"))
                else:
                    for j in range(2, 6):
                        self.stats_table.setItem(i, j, QTableWidgetItem("N/A"))

    def export_graph(self):
        """Exports the current graph view to an image file."""
        exporter = pg.exporters.ImageExporter(self.plot_widget.plotItem)
        # In a real app, you would use a QFileDialog here to ask for a path
        exporter.export('graph_export.png')
        print("Graph exported to graph_export.png")
