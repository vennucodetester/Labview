import sys
from PyQt6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, QMainWindow, QVBoxLayout, QWidget, QGraphicsPathItem, QGraphicsTextItem, QGraphicsEllipseItem, QPushButton, QHBoxLayout, QLabel, QSpinBox, QComboBox
from PyQt6.QtGui import QBrush, QPen, QPainterPath, QColor
from PyQt6.QtCore import Qt, QPointF

# --- SIMPLE ISOLATED COMPONENTS ---

class SimpleBox(QGraphicsPathItem):
    def __init__(self, title, width=120, height=60, has_in=True, has_out=True):
        super().__init__()
        self.width = width
        self.height = height
        
        path = QPainterPath()
        path.addRect(0, 0, width, height)
        self.setPath(path)
        
        self.setBrush(QBrush(QColor('#222222')))
        self.setPen(QPen(QColor('#4DA6FF'), 2))
        
        self.text = QGraphicsTextItem(f'[{title}]', self)
        self.text.setDefaultTextColor(QColor('#FFFFFF'))
        self.text.setPos(10, 10)
        
        self.inlet_pos = QPointF(width/2, 0) if has_in else None
        self.outlet_pos = QPointF(width/2, height) if has_out else None
        
        if has_in:
            self.draw_port(self.inlet_pos, QColor('#FF5555'))
        if has_out:
            self.draw_port(self.outlet_pos, QColor('#55FF55'))

    def draw_port(self, pos, color):
        port = QGraphicsEllipseItem(-4, -4, 8, 8, self)
        port.setPos(pos)
        port.setBrush(QBrush(color))
        port.setPen(QPen(Qt.GlobalColor.white, 1))

class ColoredBox(QGraphicsPathItem):
    def __init__(self, title, width, height, bg_color):
        super().__init__()
        path = QPainterPath()
        path.addRect(0, 0, width, height)
        self.setPath(path)
        self.setBrush(QBrush(QColor(bg_color)))
        self.setPen(QPen(QColor('#000000'), 1))
        self.text = QGraphicsTextItem(f'{title}', self)
        self.text.setDefaultTextColor(QColor('#000000'))
        self.text.setPos(5, 5)

class SplitterManifold(QGraphicsPathItem):
    def __init__(self, num_splits=6, width=120, height=40, is_reversed=False):
        super().__init__()
        
        self.num_splits = num_splits
        self.is_reversed = is_reversed
        
        self.setBrush(QBrush(Qt.GlobalColor.transparent))
        self.setPen(QPen(Qt.GlobalColor.transparent))
        
        path = QPainterPath()
        
        if num_splits == 1:
            if not is_reversed:
                self.inlet_pos = QPointF(width/2, 0)
                self.outlet_positions = [QPointF(width/2, height + 15)]
                path.moveTo(width/2, 0)
                path.lineTo(width/2, height + 15)
                self.draw_port(self.inlet_pos, QColor('#FF5555'))
                self.draw_port(self.outlet_positions[0], QColor('#55FF55'))
            else:
                self.outlet_pos = QPointF(width/2, height + 15)
                self.inlet_positions = [QPointF(width/2, 0)]
                path.moveTo(width/2, 0)
                path.lineTo(width/2, height + 15)
                self.draw_port(self.inlet_positions[0], QColor('#FF5555'))
                self.draw_port(self.outlet_pos, QColor('#55FF55'))
        else:
            manifold_width = max(width, num_splits * 30)
            start_x = (width - manifold_width) / 2
            spacing = manifold_width / (num_splits - 1)
            
            if not is_reversed:
                self.inlet_pos = QPointF(width/2, 0)
                self.outlet_positions = []
                
                manifold_y = height
                path.moveTo(width/2, 0)
                path.lineTo(width/2, manifold_y)
                path.moveTo(start_x, manifold_y)
                path.lineTo(start_x + manifold_width, manifold_y)
                
                for i in range(num_splits):
                    px = start_x + i * spacing
                    path.moveTo(px, manifold_y)
                    path.lineTo(px, manifold_y + 15)
                    self.outlet_positions.append(QPointF(px, manifold_y + 15))
                    self.draw_port(QPointF(px, manifold_y + 15), QColor('#55FF55'))
                    
                self.draw_port(self.inlet_pos, QColor('#FF5555'))
            else:
                self.outlet_pos = QPointF(width/2, height + 15)
                self.inlet_positions = []
                
                manifold_y = 15
                path.moveTo(width/2, manifold_y)
                path.lineTo(width/2, height + 15)
                path.moveTo(start_x, manifold_y)
                path.lineTo(start_x + manifold_width, manifold_y)
                
                for i in range(num_splits):
                    px = start_x + i * spacing
                    path.moveTo(px, manifold_y)
                    path.lineTo(px, 0)
                    self.inlet_positions.append(QPointF(px, 0))
                    self.draw_port(QPointF(px, 0), QColor('#FF5555'))
                    
                self.draw_port(self.outlet_pos, QColor('#55FF55'))
            
        manifold_item = QGraphicsPathItem(path, self)
        manifold_item.setPen(QPen(QColor('#4DA6FF'), 2))

    def draw_port(self, pos, color):
        port = QGraphicsEllipseItem(-4, -4, 8, 8, self)
        port.setPos(pos)
        port.setBrush(QBrush(color))
        port.setPen(QPen(Qt.GlobalColor.white, 1))

class EvaporatorBox(QGraphicsPathItem):
    def __init__(self, title="Evaporator", num_circuits=6, width=120, height=60):
        super().__init__()
        
        path = QPainterPath()
        path.addRect(0, 0, width, height)
        self.setPath(path)
        
        self.setBrush(QBrush(QColor('#222222')))
        self.setPen(QPen(QColor('#4DA6FF'), 2))
        
        self.text = QGraphicsTextItem(f'[{title}]', self)
        self.text.setDefaultTextColor(QColor('#FFFFFF'))
        self.text.setPos(10, 10)
        
        self.inlet_positions = []
        self.outlet_positions = []
        
        if num_circuits == 1:
            px = width / 2
            in_pos = QPointF(px, 0)
            out_pos = QPointF(px, height)
            self.inlet_positions.append(in_pos)
            self.outlet_positions.append(out_pos)
            self.draw_port(in_pos, QColor('#FF5555'))
            self.draw_port(out_pos, QColor('#55FF55'))
        else:
            manifold_width = max(width, num_circuits * 30)
            start_x = (width - manifold_width) / 2
            spacing = manifold_width / (num_circuits - 1)
            
            for i in range(num_circuits):
                px = start_x + i * spacing
                in_pos = QPointF(px, 0)
                out_pos = QPointF(px, height)
                self.inlet_positions.append(in_pos)
                self.outlet_positions.append(out_pos)
                self.draw_port(in_pos, QColor('#FF5555'))
                self.draw_port(out_pos, QColor('#55FF55'))

    def draw_port(self, pos, color):
        port = QGraphicsEllipseItem(-4, -4, 8, 8, self)
        port.setPos(pos)
        port.setBrush(QBrush(color))
        port.setPen(QPen(Qt.GlobalColor.white, 1))

def draw_pipe(scene, start_pt, end_pt):
    path = QPainterPath()
    path.moveTo(start_pt)
    
    mid_y = (start_pt.y() + end_pt.y()) / 2
    path.lineTo(start_pt.x(), mid_y)
    path.lineTo(end_pt.x(), mid_y)
    path.lineTo(end_pt.x(), end_pt.y())
    
    pipe = QGraphicsPathItem(path)
    pipe.setPen(QPen(QColor('#888888'), 2))
    pipe.setZValue(-1)
    scene.addItem(pipe)

def draw_loopback_pipe(scene, start_pt, end_pt, leftmost_x):
    path = QPainterPath()
    path.moveTo(start_pt)
    
    path.lineTo(start_pt.x(), start_pt.y() + 30)
    path.lineTo(leftmost_x, start_pt.y() + 30)
    path.lineTo(leftmost_x, end_pt.y() - 30)
    path.lineTo(end_pt.x(), end_pt.y() - 30)
    path.lineTo(end_pt.x(), end_pt.y())
    
    pipe = QGraphicsPathItem(path)
    pipe.setPen(QPen(QColor('#888888'), 2))
    pipe.setZValue(-1)
    scene.addItem(pipe)

def draw_sensor_line(scene, txv, head):
    txv_left = txv.scenePos() + QPointF(0, txv.height / 2)
    attach_pt = head.scenePos() + head.outlet_pos + QPointF(0, 20)
    
    path = QPainterPath()
    path.moveTo(txv_left)
    
    clearance_x = txv_left.x() - 80
    
    path.lineTo(clearance_x, txv_left.y())
    path.lineTo(clearance_x, attach_pt.y())
    path.lineTo(attach_pt.x(), attach_pt.y())
    
    pipe = QGraphicsPathItem(path)
    pipe.setPen(QPen(QColor('#9932CC'), 2))
    pipe.setZValue(-1)
    scene.addItem(pipe)

def _draw_branch_pipe(scene, start_pt, end_pt, branch_y):
    """start_pt → down to branch_y → horizontal to end_pt.x → down/up to end_pt.y"""
    path = QPainterPath()
    path.moveTo(start_pt)
    path.lineTo(start_pt.x(), branch_y)
    path.lineTo(end_pt.x(), branch_y)
    path.lineTo(end_pt)
    pipe = QGraphicsPathItem(path)
    pipe.setPen(QPen(QColor('#888888'), 2))
    pipe.setZValue(-1)
    scene.addItem(pipe)

def _draw_up_arrow(scene, x, y_bottom, y_top):
    path = QPainterPath()
    path.moveTo(x, y_bottom)
    path.lineTo(x, y_top)
    # arrow head
    path.lineTo(x - 5, y_top + 5)
    path.moveTo(x, y_top)
    path.lineTo(x + 5, y_top + 5)
    
    arrow = QGraphicsPathItem(path)
    arrow.setPen(QPen(QColor('#555555'), 2))
    scene.addItem(arrow)

def _draw_boundary(scene, label_text, x, y, w, h):
    from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsTextItem
    from PyQt6.QtGui import QPen, QBrush, QColor
    from PyQt6.QtCore import Qt
    
    rect = QGraphicsRectItem(x, y, w, h)
    pen = QPen(QColor('#AAAAAA'), 2)
    pen.setStyle(Qt.PenStyle.DashLine)
    rect.setPen(pen)
    rect.setBrush(QBrush(Qt.BrushStyle.NoBrush))
    rect.setZValue(-10)
    scene.addItem(rect)
    
    label = QGraphicsTextItem(label_text)
    label.setDefaultTextColor(QColor('#888888'))
    label.setPos(x + 5, y + 5)
    scene.addItem(label)

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Isolated Loop Test - Variations")
        self.resize(1200, 950)
        
        self.current_mode = 'modular'
        self.current_count = 3
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Toolbar 1: Modular
        btn_layout_mod = QHBoxLayout()
        btn_layout_mod.addWidget(QLabel("Modular:"))
        for i in range(1, 4):
            btn = QPushButton(f"{i} Module{'s' if i>1 else ''}")
            btn.clicked.connect(lambda checked, n=i: self.set_mode('modular', n))
            btn_layout_mod.addWidget(btn)
        btn_layout_mod.addStretch()

        # Toolbar 2: Non-Modular (Doors)
        btn_layout_door = QHBoxLayout()
        btn_layout_door.addWidget(QLabel("Non-Modular (Doors):"))
        for i in range(1, 6):
            btn = QPushButton(f"{i}Dr")
            btn.clicked.connect(lambda checked, n=i: self.set_mode('door', n))
            btn_layout_door.addWidget(btn)
        
        btn_layout_door.addSpacing(40)
        btn_layout_door.addWidget(QLabel("Circuits:"))
        
        self.circuit_spin = QSpinBox()
        self.circuit_spin.setRange(1, 8)
        self.circuit_spin.setValue(6)
        self.circuit_spin.valueChanged.connect(self.update_diagram)
        btn_layout_door.addWidget(self.circuit_spin)
        
        btn_layout_door.addSpacing(40)
        btn_layout_door.addWidget(QLabel("Shelf Rows:"))
        self.shelf_spin = QSpinBox()
        self.shelf_spin.setRange(3, 8)
        self.shelf_spin.setValue(5)
        self.shelf_spin.valueChanged.connect(self.update_diagram)
        btn_layout_door.addWidget(self.shelf_spin)
        
        btn_layout_door.addSpacing(40)
        btn_layout_door.addWidget(QLabel("Case Type:"))
        self.case_combo = QComboBox()
        self.case_combo.addItems(["Doored", "Open"])
        self.case_combo.currentTextChanged.connect(self.update_diagram)
        btn_layout_door.addWidget(self.case_combo)
        
        btn_layout_door.addStretch()
        
        layout.addLayout(btn_layout_mod)
        layout.addLayout(btn_layout_door)
        
        self.view = QGraphicsView()
        self.scene = QGraphicsScene()
        self.scene.setBackgroundBrush(QBrush(QColor('#EEEEEE')))
        self.view.setScene(self.scene)
        layout.addWidget(self.view)
        
        self.update_diagram()

    def set_mode(self, mode, count):
        self.current_mode = mode
        self.current_count = count
        self.update_diagram()

    def update_diagram(self):
        self.scene.clear()

        num_modules = self.current_count if self.current_mode == 'modular' else 1
        CENTER_X = 600
        MOD_SPACING = 300

        # ── Fixed y positions ────────────────────────────────────────────────
        Y_COMP  = 100   # compressor top
        Y_COND  = 200   # condenser top
        Y_TXV   = 330   # TXV top  (one per module)
        Y_EVAP  = 445   # Evaporator top (one per module)
        EVAP_H  = 80
        COMP_W  = 120;  COMP_H  = 60
        COND_W  = 120;  COND_H  = 60
        TXV_W   = 120;  TXV_H   = 60
        EVAP_W  = 240
        if self.current_mode == 'door':
            EVAP_W = 240 * self.current_count

        # module x-centres
        if num_modules == 1:
            mod_xs  = [CENTER_X]
            mod_lbs = [""]
        elif num_modules == 2:
            mod_xs  = [CENTER_X - MOD_SPACING // 2, CENTER_X + MOD_SPACING // 2]
            mod_lbs = ["LH", "RH"]
        else:
            mod_xs  = [CENTER_X - MOD_SPACING, CENTER_X, CENTER_X + MOD_SPACING]
            mod_lbs = ["LH", "CTR", "RH"]

        LEFTMOST = mod_xs[0] - (EVAP_W // 2) - 100   # loopback clearance lane

        # ── Shared boxes ─────────────────────────────────────────────────────
        comp = SimpleBox("Compressor", width=COMP_W, height=COMP_H)
        comp.setPos(CENTER_X - COMP_W // 2, Y_COMP)
        self.scene.addItem(comp)

        cond = SimpleBox("Condenser", width=COND_W, height=COND_H)
        cond.setPos(CENTER_X - COND_W // 2, Y_COND)
        self.scene.addItem(cond)

        # comp → cond  (straight vertical)
        draw_pipe(self.scene,
                  comp.scenePos() + comp.outlet_pos,
                  cond.scenePos() + cond.inlet_pos)

        # cond outlet scene point
        cond_out = cond.scenePos() + cond.outlet_pos   # (CENTER_X, Y_COND+COND_H)

        num_circuits = self.circuit_spin.value()

        # branch / merge levels (where multi-module pipes fan out / collect)
        BRANCH_Y   = Y_COND + COND_H + 30      # module fan-out below condenser
        MERGE_Y    = Y_EVAP + EVAP_H + 85      # module collection before loopback

        # ── Per-module columns ───────────────────────────────────────────────
        mod_evap_outlets = []

        for mod_x, lb in zip(mod_xs, mod_lbs):
            lp = f"{lb} " if lb else ""

            txv = SimpleBox(f"{lp}TXV", width=TXV_W, height=TXV_H)
            txv.setPos(mod_x - TXV_W // 2, Y_TXV)
            self.scene.addItem(txv)

            evap = EvaporatorBox(f"{lp}Evaporator",
                                 num_circuits=num_circuits,
                                 width=EVAP_W, height=EVAP_H)
            evap.setPos(mod_x - EVAP_W // 2, Y_EVAP)
            self.scene.addItem(evap)

            dist_h = 40
            dist = SplitterManifold(num_splits=num_circuits, width=EVAP_W, height=dist_h, is_reversed=False)
            dist.setPos(mod_x - EVAP_W // 2, Y_EVAP - dist_h - 15)
            self.scene.addItem(dist)

            head_h = 40
            head = SplitterManifold(num_splits=num_circuits, width=EVAP_W, height=head_h, is_reversed=True)
            head.setPos(mod_x - EVAP_W // 2, Y_EVAP + EVAP_H)
            self.scene.addItem(head)

            txv_in  = txv.scenePos() + txv.inlet_pos
            txv_out = txv.scenePos() + txv.outlet_pos

            # cond → TXV  (branch at BRANCH_Y then drop to module x)
            _draw_branch_pipe(self.scene, cond_out, txv_in, BRANCH_Y)

            # bottom header outlet → module merge point
            head_out = head.scenePos() + head.outlet_pos
            mod_evap_outlets.append(head_out)

        # ── Collect module outlets and loopback ──────────────────────────────
        merge_pt = QPointF(CENTER_X, MERGE_Y)

        for evap_out in mod_evap_outlets:
            _draw_branch_pipe(self.scene, evap_out, merge_pt, MERGE_Y)

        draw_loopback_pipe(self.scene,
                           merge_pt,
                           comp.scenePos() + comp.inlet_pos,
                           LEFTMOST)

        # ── Air Distribution & Fans ──────────────────────────────────────────
        left_edge = mod_xs[0] - EVAP_W / 2
        right_edge = mod_xs[-1] + EVAP_W / 2
        combined_w = right_edge - left_edge

        # Y positions (MERGE_Y is where the loopback starts)
        base_y = MERGE_Y + 100
        
        # Primary Discharge Air (Coldest)
        pri_air = ColoredBox("Primary Discharge Air", width=combined_w, height=30, bg_color="#B3E5FC") # Light Blue
        pri_air.setPos(left_edge, base_y)
        self.scene.addItem(pri_air)
        
        # Secondary Discharge Air (Warmish)
        sec_air = ColoredBox("Secondary Discharge Air", width=combined_w, height=30, bg_color="#FFF9C4") # Light Yellow
        sec_air.setPos(left_edge, base_y + 40)
        self.scene.addItem(sec_air)
        
        # Fans
        fan_y = base_y + 80
        fan_size = 60
        if self.current_mode == 'modular':
            for mx, label in zip(mod_xs, mod_lbs):
                fan_label = f"Fan {label}".strip() if label else "Fan"
                fan = ColoredBox(fan_label, width=fan_size, height=fan_size, bg_color="#E0E0E0")
                fan.setPos(mx - fan_size / 2, fan_y)
                self.scene.addItem(fan)
                
                # Airflow arrows
                _draw_up_arrow(self.scene, mx, fan_y + fan_size + 10, fan_y + fan_size)
                _draw_up_arrow(self.scene, mx, fan_y, fan_y - 10)
        else: # door mode
            # Place `current_count` fans evenly spaced
            slice_w = combined_w / self.current_count
            for i in range(self.current_count):
                fx = left_edge + (slice_w / 2) + (i * slice_w)
                fan = ColoredBox(f"Fan Dr {i+1}", width=fan_size, height=fan_size, bg_color="#E0E0E0")
                fan.setPos(fx - fan_size / 2, fan_y)
                self.scene.addItem(fan)
                
                # Airflow arrows
                _draw_up_arrow(self.scene, fx, fan_y + fan_size + 10, fan_y + fan_size)
                _draw_up_arrow(self.scene, fx, fan_y, fan_y - 10)
                
        # Return Air (Warmest)
        ret_air_y = fan_y + fan_size + 10
        ret_air = ColoredBox("Return Air", width=combined_w, height=30, bg_color="#FFCDD2") # Light Red
        ret_air.setPos(left_edge, ret_air_y)
        self.scene.addItem(ret_air)

        # ── Grouping Boundaries ──────────────────────────────────────────────
        process_x = LEFTMOST - 40
        process_w = (right_edge + 40) - process_x
        process_y = Y_COMP - 80
        process_h = MERGE_Y + 40 - process_y
        _draw_boundary(self.scene, "Refrigeration Process", process_x, process_y, process_w, process_h)

        air_y = base_y - 40
        air_h = (ret_air_y + 30 + 40) - air_y
        _draw_boundary(self.scene, "Airflow Diagram", process_x, air_y, process_w, air_h)

        # ── Shelving Diagram ──────────────────────────────────────────────────
        shelf_base_y = ret_air_y + 30 + 100
        num_rows = self.shelf_spin.value()
        shelf_height = 30
        shelf_gap = 10
        shelf_total_h = num_rows * (shelf_height + shelf_gap)
        
        if self.current_mode == 'modular':
            col_w = EVAP_W
            col_xs = [mx - EVAP_W / 2 for mx in mod_xs]
        else: # door mode
            col_w = combined_w / self.current_count
            col_xs = [left_edge + i * col_w for i in range(self.current_count)]
            
        for cx in col_xs:
            for r in range(num_rows):
                sy = shelf_base_y + r * (shelf_height + shelf_gap)
                # Adding a small horizontal gap so columns don't perfectly touch
                shelf = ColoredBox(f"Shelf {r+1}", width=col_w - 6, height=shelf_height, bg_color="#F0F0F0") 
                shelf.setPos(cx + 3, sy)
                self.scene.addItem(shelf)
                
        shelf_bound_h = shelf_total_h + 60
        _draw_boundary(self.scene, "Shelving Diagram", process_x, shelf_base_y - 40, process_w, shelf_bound_h)

        # ── Doors Diagram ─────────────────────────────────────────────────────
        if self.case_combo.currentText() == "Doored":
            door_base_y = shelf_base_y + shelf_total_h + 80
            door_height = 240
            
            mullion_w = 16
            
            if self.current_mode == 'modular':
                M = len(mod_xs)
                # LH End Mullion
                lh_mullion = ColoredBox("", width=mullion_w, height=door_height, bg_color="#B0BEC5")
                lh_mullion.setPos(left_edge - mullion_w - 10, door_base_y)
                self.scene.addItem(lh_mullion)
                
                # RH End Mullion
                rh_mullion = ColoredBox("", width=mullion_w, height=door_height, bg_color="#B0BEC5")
                rh_mullion.setPos(right_edge + 10, door_base_y)
                self.scene.addItem(rh_mullion)
                
                # Doors and CTR Mullions
                door_w = EVAP_W / 2 - 2
                for m, mx in enumerate(mod_xs):
                    door1 = ColoredBox(f"Door {2*m+1}", width=door_w, height=door_height, bg_color="#E1F5FE")
                    door1.setPos(mx - EVAP_W/2, door_base_y)
                    self.scene.addItem(door1)
                    
                    door2 = ColoredBox(f"Door {2*m+2}", width=door_w, height=door_height, bg_color="#E1F5FE")
                    door2.setPos(mx + 2, door_base_y)
                    self.scene.addItem(door2)
                    
                    if m < M - 1:
                        ctr_x = (mod_xs[m] + mod_xs[m+1]) / 2
                        ctr_mullion = ColoredBox("", width=mullion_w, height=door_height, bg_color="#B0BEC5")
                        ctr_mullion.setPos(ctr_x - mullion_w / 2, door_base_y)
                        self.scene.addItem(ctr_mullion)
            else: # door mode
                N = self.current_count
                gap = 4
                total_mullion_w = (N + 1) * mullion_w
                total_gap_w = (2 * N) * gap
                door_w = (combined_w - total_mullion_w - total_gap_w) / N
                
                current_x = left_edge
                
                # LH End Mullion
                lh_mullion = ColoredBox("", width=mullion_w, height=door_height, bg_color="#B0BEC5")
                lh_mullion.setPos(current_x, door_base_y)
                self.scene.addItem(lh_mullion)
                current_x += mullion_w + gap
                
                for i in range(N):
                    door = ColoredBox(f"Door {i+1}", width=door_w, height=door_height, bg_color="#E1F5FE")
                    door.setPos(current_x, door_base_y)
                    self.scene.addItem(door)
                    current_x += door_w + gap
                    
                    if i < N - 1:
                        ctr_mullion = ColoredBox("", width=mullion_w, height=door_height, bg_color="#B0BEC5")
                        ctr_mullion.setPos(current_x, door_base_y)
                        self.scene.addItem(ctr_mullion)
                        current_x += mullion_w + gap
                
                # RH End Mullion
                rh_mullion = ColoredBox("", width=mullion_w, height=door_height, bg_color="#B0BEC5")
                rh_mullion.setPos(current_x, door_base_y)
                self.scene.addItem(rh_mullion)
                    
            door_bound_h = door_height + 60
            _draw_boundary(self.scene, "Doors Diagram", process_x, door_base_y - 40, process_w, door_bound_h)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = TestWindow()
    w.show()
    sys.exit(app.exec())
