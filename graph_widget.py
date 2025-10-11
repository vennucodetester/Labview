import pyqtgraph as pg
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QFrame, 
                             QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
import pandas as pd
from datetime import datetime

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
        
        # Custom range selection state
        self.range_selection_mode = False
        self.range_region = None

        self.setupUi()
        self.connect_signals()

    def setupUi(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        
        # --- Control Bar ---
        control_bar = QFrame()
        control_bar.setStyleSheet("background-color: #f0f0f0; border-bottom: 1px solid #ddd;")
        control_layout = QHBoxLayout(control_bar)
        
        self.reset_zoom_btn = QPushButton("Reset Zoom")
        self.select_range_btn = QPushButton("📅 Select Custom Range")
        self.select_range_btn.setCheckable(True)
        self.select_range_btn.setToolTip("Click to enable range selection, then drag on the graph to select a custom time range")
        self.apply_range_btn = QPushButton("Apply Range")
        self.apply_range_btn.setEnabled(False)
        self.apply_range_btn.setToolTip("Apply the selected time range")
        self.export_btn = QPushButton("Export")
        
        control_layout.addWidget(self.reset_zoom_btn)
        control_layout.addWidget(self.select_range_btn)
        control_layout.addWidget(self.apply_range_btn)
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
        main_layout.addWidget(self.plot_widget, 4) # Give plot more space

        # --- Custom Legend/Stats Table ---
        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(6)
        self.stats_table.setHorizontalHeaderLabels(["Sensor Name", "Color", "Avg", "Min", "Max", "Delta"])
        self.stats_table.verticalHeader().setVisible(False)
        self.stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.stats_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.stats_table.setMaximumHeight(250)
        main_layout.addWidget(self.stats_table, 1) # Give table minimal space

    def connect_signals(self):
        self.reset_zoom_btn.clicked.connect(self.plot_widget.autoRange)
        self.select_range_btn.toggled.connect(self.toggle_range_selection)
        self.apply_range_btn.clicked.connect(self.apply_custom_range)
        self.export_btn.clicked.connect(self.export_graph)

    def update_ui(self):
        """Redraws the graph and stats table based on the DataManager's state."""
        self.plot_widget.clear()
        self.stats_table.setRowCount(0)

        # Use filtered data based on time range
        df = self.data_manager.get_filtered_data()
        sensors_to_plot = self.data_manager.graph_sensors

        if df is None or not sensors_to_plot or df.empty:
            return
            

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
                # Faster rendering: thinner pens, disable antialias via pen if desired
                pen = pg.mkPen(color=colors[i % len(colors)], width=1.5)
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
    
    def toggle_range_selection(self, checked):
        """Toggle custom range selection mode."""
        self.range_selection_mode = checked
        
        if checked:
            # Enable range selection mode
            self.select_range_btn.setStyleSheet("background-color: #4CAF50; color: white;")
            self.select_range_btn.setText("📅 Drag to Select Range")
            
            # Remove existing range region if any
            if self.range_region:
                self.plot_widget.removeItem(self.range_region)
            
            # Create a new linear region item for selection
            self.range_region = pg.LinearRegionItem(
                values=[0, 1],
                brush=pg.mkBrush(QColor(100, 149, 237, 80)),  # Semi-transparent blue
                movable=True,
                pen=pg.mkPen(color=QColor(30, 144, 255), width=3),  # Bright blue edges
                hoverPen=pg.mkPen(color=QColor(255, 165, 0), width=5)  # Orange on hover
            )
            self.plot_widget.addItem(self.range_region)
            
            # Enable apply button
            self.apply_range_btn.setEnabled(True)
            
            # Position the region in the middle of the view by default
            view_range = self.plot_widget.viewRange()[0]
            mid_point = (view_range[0] + view_range[1]) / 2
            width = (view_range[1] - view_range[0]) * 0.3
            self.range_region.setRegion([mid_point - width/2, mid_point + width/2])
        else:
            # Disable range selection mode
            self.select_range_btn.setStyleSheet("")
            self.select_range_btn.setText("📅 Select Custom Range")
            
            # Remove the range region
            if self.range_region:
                self.plot_widget.removeItem(self.range_region)
                self.range_region = None
            
            # Disable apply button
            self.apply_range_btn.setEnabled(False)
    
    def apply_custom_range(self):
        """Apply the selected time range as the custom range."""
        if not self.range_region:
            return
        
        # Get the selected range (in Unix timestamp format)
        start_unix, end_unix = self.range_region.getRegion()
        
        # Convert Unix timestamps to datetime
        start_dt = datetime.fromtimestamp(start_unix)
        end_dt = datetime.fromtimestamp(end_unix)
        
        # Set the custom time range in data manager
        self.data_manager.set_custom_time_range(start_dt, end_dt)
        
        # Disable selection mode
        self.select_range_btn.setChecked(False)
        
        # Show confirmation message
        QMessageBox.information(
            self,
            "Custom Range Applied",
            f"Custom time range set:\n\n"
            f"From: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"To: {end_dt.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"The time range selector has been set to 'Custom'."
        )
        
        print(f"Custom range applied: {start_dt} to {end_dt}")
