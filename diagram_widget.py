from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QFileDialog, QFrame, QGraphicsView,
                             QGraphicsScene, QGraphicsPixmapItem, QGraphicsEllipseItem,
                             QMessageBox)
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QCursor
from PyQt6.QtCore import Qt, pyqtSignal, QPointF

class SensorDotItem(QGraphicsEllipseItem):
    """
    A custom QGraphicsEllipseItem that represents a sensor dot.
    Clicking the dot now uses the DataManager to toggle its selection state.
    """
    def __init__(self, sensor_name, x_pos, y_pos, size, data_manager):
        super().__init__(0, 0, size, size)
        self.setPos(x_pos - size/2, y_pos - size/2)
        
        self.sensor_name = sensor_name
        self.data_manager = data_manager
        
        self.setToolTip(sensor_name)
        self.setAcceptHoverEvents(True)
        self.setZValue(1)

    def hoverEnterEvent(self, event):
        """Change cursor to open hand when hovering in mapping mode."""
        if self.data_manager.current_mode == 'mapping':
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)) # Pointing hand in analysis mode
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """Reset cursor when not hovering."""
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        """
        On left click, toggle the selection state via the DataManager.
        This allows for highlighting and linking with the sensor panel.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.data_manager.toggle_sensor_selection(self.sensor_name)
        
        # This part handles the visual feedback for dragging
        if self.data_manager.current_mode == 'mapping':
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle dragging the dot in mapping mode."""
        if self.data_manager.current_mode == 'mapping':
            orig_pos = event.lastScenePos()
            new_pos = event.scenePos()
            delta = new_pos - orig_pos
            self.moveBy(delta.x(), delta.y())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """
        On release, calculate the new percentage and call the DataManager directly.
        """
        if self.data_manager.current_mode == 'mapping':
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            
            parent = self.parentItem()
            if parent:
                dot_center = self.scenePos() - parent.scenePos()
                
                pixmap_width = parent.pixmap().width()
                pixmap_height = parent.pixmap().height()

                if pixmap_width > 0 and pixmap_height > 0:
                    new_x_percent = (dot_center.x() / pixmap_width) * 100
                    new_y_percent = (dot_center.y() / pixmap_height) * 100
                    
                    self.data_manager.update_mapping_and_notify(self.sensor_name, new_x_percent, new_y_percent)
        
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Show sensor information on double-click."""
        value = "N/A"
        if self.data_manager.csv_data is not None and self.sensor_name in self.data_manager.csv_data.columns:
            if not self.data_manager.csv_data[self.sensor_name].dropna().empty:
                last_value = self.data_manager.csv_data[self.sensor_name].dropna().iloc[-1]
                value = f"{last_value:.2f}"
            
        mapping_data = self.data_manager.mappings.get(self.sensor_name, {})
        min_range = mapping_data.get('range', {}).get('min', 'Not Set')
        max_range = mapping_data.get('range', {}).get('max', 'Not Set')

        info_text = (
            f"<b>Sensor:</b> {self.sensor_name}<br>"
            f"<b>Current Value:</b> {value}<br>"
            f"<b>Min Range:</b> {min_range}<br>"
            f"<b>Max Range:</b> {max_range}"
        )
        
        QMessageBox.information(self.scene().views()[0], "Sensor Information", info_text)
        super().mouseDoubleClickEvent(event)


class DiagramWidget(QWidget):
    """
    Handles displaying the diagram and sensor dots.
    Places a new dot when a sensor is selected and the view is clicked.
    """
    
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.current_pixmap = None 
        self.pixmap_item = None
        self.sensor_dot_items = {} 

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Control Bar
        control_bar = QFrame()
        control_bar.setStyleSheet("background-color: #f0f0f0; border-bottom: 1px solid #ddd;")
        control_layout = QHBoxLayout(control_bar)
        
        self.load_image_btn = QPushButton("Load Image")
        self.mode_btn = QPushButton("Mode: Mapping")
        self.mode_btn.setCheckable(True)
        self.mode_btn.toggled.connect(self.toggle_mode)
        
        fit_width_btn = QPushButton("Fit Width")

        control_layout.addWidget(self.load_image_btn)
        control_layout.addWidget(QPushButton("Set Range"))
        control_layout.addWidget(QPushButton("Delete Selected"))
        control_layout.addWidget(QPushButton("Export PDF"))
        control_layout.addStretch()
        control_layout.addWidget(fit_width_btn)
        control_layout.addWidget(self.mode_btn)
        main_layout.addWidget(control_bar)

        # Diagram Area
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)

        # Connect signals
        self.load_image_btn.clicked.connect(self.load_image_from_file)
        fit_width_btn.clicked.connect(self.fit_to_width)
        
        self.view.mousePressEvent = self.view_mouse_press_event
        
        main_layout.addWidget(self.view)

    def load_image_from_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if file_name:
            self.data_manager.load_image_from_path(file_name)

    def view_mouse_press_event(self, event):
        """
        Handles mouse press on the view. If a sensor is selected in the panel,
        this will place a new dot for it. Otherwise, it lets the dot handle the click.
        """
        if self.data_manager.current_mode == 'analysis':
             super().mousePressEvent(event)
             return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        # If click is on an existing dot, let the dot's event handler manage it.
        item = self.view.itemAt(event.pos())
        if isinstance(item, QGraphicsEllipseItem):
            QGraphicsView.mousePressEvent(self.view, event)
            return

        # If a sensor is selected, place it.
        if len(self.data_manager.selected_sensors) == 1 and self.pixmap_item:
            sensor_to_place = list(self.data_manager.selected_sensors)[0]
            scene_pos = self.view.mapToScene(event.pos())
            item_pos = self.pixmap_item.mapFromScene(scene_pos)

            pixmap_width = self.pixmap_item.pixmap().width()
            pixmap_height = self.pixmap_item.pixmap().height()

            if 0 <= item_pos.x() < pixmap_width and 0 <= item_pos.y() < pixmap_height:
                x_percent = (item_pos.x() / pixmap_width) * 100
                y_percent = (item_pos.y() / pixmap_height) * 100
                
                # Update mapping and deselect sensor to prevent multiple placements
                self.data_manager.update_mapping_and_notify(sensor_to_place, x_percent, y_percent)
                self.data_manager.set_sensor_selected(sensor_to_place, False)
                self.data_manager.data_changed.emit()
        
    def fit_to_width(self):
        if not self.pixmap_item:
            return
        
        self.view.resetTransform()
        view_width = self.view.viewport().width() - 2
        pixmap_width = self.pixmap_item.pixmap().width()

        if pixmap_width > 0:
            scale = view_width / pixmap_width
            self.view.scale(scale, scale)

    def update_sensor_dots(self):
        """Clears and redraws sensor dots, highlighting the selected one."""
        for item in self.sensor_dot_items.values():
            if item.scene():
                self.scene.removeItem(item)
        self.sensor_dot_items.clear()
        
        if not self.pixmap_item:
            return

        mappings = self.data_manager.mappings
        pixmap_width = self.pixmap_item.pixmap().width()
        pixmap_height = self.pixmap_item.pixmap().height()

        for sensor_name, mapping_data in mappings.items():
            if 'x' in mapping_data and 'y' in mapping_data:
                x_pos = pixmap_width * (mapping_data['x'] / 100)
                y_pos = pixmap_height * (mapping_data['y'] / 100)
                
                dot_size = 16
                dot = SensorDotItem(sensor_name, x_pos, y_pos, dot_size, self.data_manager)
                dot.setParentItem(self.pixmap_item)

                pen = QPen(QColor("#555"), 2)
                dot.setPen(pen)

                # --- NEW: Highlight the dot if it's selected in the DataManager ---
                if sensor_name in self.data_manager.selected_sensors:
                    dot.setBrush(QBrush(QColor("#ffc107"))) # Yellow highlight
                    pen.setColor(QColor("#e65100")) # Darker orange border
                    dot.setPen(pen)
                    dot.setZValue(2)
                else:
                    dot.setBrush(QBrush(QColor("#9e9e9e"))) 
                    dot.setZValue(1)

                self.sensor_dot_items[sensor_name] = dot

    def toggle_mode(self, checked):
        if checked:
            self.mode_btn.setText("Mode: Analysis")
            self.data_manager.current_mode = 'analysis'
        else:
            self.mode_btn.setText("Mode: Mapping")
            self.data_manager.current_mode = 'mapping'

        print(f"Mode changed to: {self.data_manager.current_mode}")
        
        for dot in self.sensor_dot_items.values():
            dot.hoverEnterEvent(None)

    def update_ui(self):
        """Updates the diagram image and redraws the sensor dots."""
        # print("DiagramWidget: Updating UI based on data change.")
        
        if self.current_pixmap is not self.data_manager.image_pixmap:
            self.current_pixmap = self.data_manager.image_pixmap
            
            self.scene.clear()
            self.pixmap_item = None
            self.sensor_dot_items.clear()

            if self.current_pixmap:
                self.pixmap_item = self.scene.addPixmap(self.current_pixmap)
                self.scene.setSceneRect(self.pixmap_item.boundingRect())
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, self.fit_to_width)
            else:
                placeholder_text = self.scene.addText("Please load a diagram image or a config file.")
                placeholder_text.setDefaultTextColor(QColor("grey"))
                self.view.resetTransform()
        
        self.update_sensor_dots()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self.fit_to_width)

