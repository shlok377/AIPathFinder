import sys
import random
import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QFrame, QProgressBar, 
                             QGridLayout, QSizePolicy)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QFont

# ==========================================
# 🎨 THEME: Google Cloud Dark Mode
# ==========================================
STYLES = """
QMainWindow { background-color: #1e2026; }
QLabel { color: #b0b0b0; font-family: 'Segoe UI', 'Roboto', 'Arial'; }

/* Headers */
QLabel#Header { color: #ffffff; font-size: 22px; font-weight: bold; letter-spacing: 0.5px; }
QLabel#SubHeader { color: #4285F4; font-size: 13px; font-weight: bold; text-transform: uppercase; margin-top: 15px; margin-bottom: 5px; }

/* KPI Cards */
QFrame#Card { background-color: rgba(255, 255, 255, 10); border-radius: 8px; border: 1px solid rgba(255,255,255,5); }
QLabel#KpiTitle { color: #888; font-size: 11px; }
QLabel#KpiValue { color: #fff; font-size: 24px; font-weight: bold; }
QLabel#KpiUnit { color: #666; font-size: 10px; }

/* System List Panel */
QFrame#SystemPanel { background-color: rgba(20, 20, 25, 150); border-radius: 12px; border: 1px solid #333; }
QLabel#SysLabel { color: #888; font-size: 12px; font-weight: 500; }
QLabel#SysValue { color: #fff; font-size: 13px; font-weight: bold; }

/* Robot Cards */
QFrame#RobotCard { background-color: rgba(30, 32, 40, 200); border-radius: 8px; border-left: 4px solid #555; }
QProgressBar { border: none; background-color: rgba(0,0,0,0.4); height: 6px; border-radius: 3px; }
QProgressBar::chunk { border-radius: 3px; }

/* Dock Cards */
QFrame#DockCard { background-color: rgba(255, 255, 255, 5); border-radius: 6px; border: 1px solid #333; }
QLabel#DockID { color: #fff; font-weight: bold; font-size: 11px; }
QLabel#DockStatus { font-size: 10px; font-weight: 600; }
"""

# ==========================================
# 🧩 CUSTOM WIDGETS
# ==========================================

class KpiCard(QFrame):
    def __init__(self, title, value, unit, color="#fff"):
        super().__init__()
        self.setObjectName("Card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        l = QVBoxLayout()
        l.setContentsMargins(12, 10, 12, 10)
        l.setSpacing(2)
        
        t = QLabel(title)
        t.setObjectName("KpiTitle")
        self.v = QLabel(value)
        self.v.setObjectName("KpiValue")
        self.v.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: bold;")
        u = QLabel(unit)
        u.setObjectName("KpiUnit")
        
        l.addWidget(t)
        l.addWidget(self.v)
        l.addWidget(u)
        self.setLayout(l)
        
    def set_value(self, val):
        self.v.setText(str(val))

class SystemRow(QWidget):
    def __init__(self, label, value, color="#fff"):
        super().__init__()
        l = QHBoxLayout()
        l.setContentsMargins(0, 4, 0, 4)
        
        lbl = QLabel(label)
        lbl.setObjectName("SysLabel")
        
        self.val = QLabel(value)
        self.val.setObjectName("SysValue")
        self.val.setStyleSheet(f"color: {color}; font-weight: bold;")
        
        l.addWidget(lbl)
        l.addStretch()
        l.addWidget(self.val)
        self.setLayout(l)

    def set_value(self, text, color=None):
        self.val.setText(text)
        if color:
            self.val.setStyleSheet(f"color: {color}; font-weight: bold;")

class CircularGauge(QWidget):
    def __init__(self, title, color_hex):
        super().__init__()
        self.value = 0
        self.title = title
        self.color = QColor(color_hex)
        self.setMinimumSize(130, 130)

    def set_value(self, val):
        self.value = val
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        rect_size = min(w, h) - 15
        rect = (w-rect_size)//2, (h-rect_size)//2, rect_size, rect_size
        
        p.setPen(QPen(QColor("#2d2d2d"), 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(*rect, 0, 360 * 16)
        
        p.setPen(QPen(self.color, 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        span = int(-self.value * 3.6 * 16)
        p.drawArc(*rect, 90 * 16, span)
        
        p.setPen(QColor("white"))
        p.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        p.drawText(0, -8, w, h, Qt.AlignmentFlag.AlignCenter, f"{int(self.value)}%")
        
        p.setPen(QColor("#888"))
        p.setFont(QFont("Arial", 10))
        p.drawText(0, 22, w, h, Qt.AlignmentFlag.AlignCenter, self.title)

class RobotCard(QFrame):
    def __init__(self, rid):
        super().__init__()
        self.setObjectName("RobotCard")
        self.setFixedHeight(85)
        
        l = QVBoxLayout()
        l.setContentsMargins(12, 8, 12, 8)
        l.setSpacing(4)
        
        r1 = QHBoxLayout()
        self.lid = QLabel(f"ROBOT {rid}")
        self.lid.setStyleSheet("color: white; font-weight: bold; font-size: 12px;")
        self.lst = QLabel("IDLE")
        self.lst.setStyleSheet("color: #aaa; font-size: 10px; font-weight: 600;")
        r1.addWidget(self.lid)
        r1.addStretch()
        r1.addWidget(self.lst)
        
        self.bar = QProgressBar()
        self.bar.setValue(100)
        self.bar.setTextVisible(False)
        
        r2 = QHBoxLayout()
        self.ltask = QLabel("TASK: -")
        self.ltask.setStyleSheet("color: #4285F4; font-size: 10px;")
        self.leta = QLabel("ETA: --")
        self.leta.setStyleSheet("color: #666; font-size: 10px;")
        r2.addWidget(self.ltask)
        r2.addStretch()
        r2.addWidget(self.leta)

        l.addLayout(r1)
        l.addWidget(self.bar)
        l.addLayout(r2)
        self.setLayout(l)

    def update_data(self, state, batt, task, eta):
        self.lst.setText(state.upper())
        self.bar.setValue(int(batt))
        
        col = "#0F9D58"
        if state.upper() == "CHARGING": col = "#4285F4"
        elif batt < 20: col = "#DB4437"
        elif batt < 50: col = "#F4B400"
        
        self.bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {col}; }}")
        self.setStyleSheet(f"#RobotCard {{ border-left: 4px solid {col}; background-color: rgba(30, 32, 40, 200); border-radius: 8px; }}")
        self.ltask.setText(f"TASK: {task}")
        self.leta.setText(f"ETA: {eta}s")

class DockCard(QFrame):
    def __init__(self, dock_id):
        super().__init__()
        self.setObjectName("DockCard")
        self.setFixedHeight(60)
        
        l = QVBoxLayout()
        l.setContentsMargins(10, 5, 10, 5)
        l.setSpacing(2)
        
        self.lid = QLabel(f"DOCK {dock_id}")
        self.lid.setObjectName("DockID")
        
        self.lstatus = QLabel("IDLE")
        self.lstatus.setObjectName("DockStatus")
        self.lstatus.setStyleSheet("color: #888;")
        
        l.addWidget(self.lid)
        l.addWidget(self.lstatus)
        self.setLayout(l)
        
    def update_status(self, status):
        self.lstatus.setText(status.upper())
        
        if status.upper() == "CHARGING":
            self.setStyleSheet("#DockCard { border: 1px solid #4285F4; background-color: rgba(66, 133, 244, 0.1); }")
            self.lstatus.setStyleSheet("color: #4285F4;")
        elif status.upper() == "ARRIVING":
            self.setStyleSheet("#DockCard { border: 1px solid #F4B400; background-color: rgba(244, 180, 0, 0.1); }")
            self.lstatus.setStyleSheet("color: #F4B400;")
        else:
            self.setStyleSheet("#DockCard { border: 1px solid #333; background-color: rgba(255, 255, 255, 5); }")
            self.lstatus.setStyleSheet("color: #888;")

# ==========================================
# 🚀 MAIN WINDOW
# ==========================================
class MissionControl(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Warehouse Analytics")
        self.resize(1000, 900)
        self.setStyleSheet(STYLES)

        central = QWidget()
        self.setCentralWidget(central)
        
        main_l = QVBoxLayout(central)
        main_l.setContentsMargins(20, 15, 20, 15)
        main_l.setSpacing(10)

        # 1. HEADER
        header = QHBoxLayout()
        t = QLabel("WAREHOUSE ANALYTICS")
        t.setObjectName("Header")
        self.time = QLabel("00:00:00")
        self.time.setStyleSheet("color: #4285F4; font-size: 16px; font-weight: bold;")
        header.addWidget(t)
        header.addStretch()
        header.addWidget(self.time)
        main_l.addLayout(header)

        # 2. TOP SECTION
        top_h = QHBoxLayout()
        
        # Left: Gauges
        gauge_l = QHBoxLayout()
        self.g_work = CircularGauge("Workflow", "#0F9D58")
        self.g_util = CircularGauge("Utilization", "#4285F4")
        gauge_l.addWidget(self.g_work)
        gauge_l.addWidget(self.g_util)
        
        # Right: System Health List
        sys_panel = QFrame()
        sys_panel.setObjectName("SystemPanel")
        sys_l = QVBoxLayout(sys_panel)
        sys_l.setContentsMargins(20, 15, 20, 15)
        sys_l.setSpacing(5)

        sys_l.addWidget(QLabel("SYSTEM HEALTH", objectName="KpiTitle"))
        
        self.row_queue = SystemRow("Queue Load", "12 Tasks", "#F4B400")
        self.row_th = SystemRow("Throughput", "45/min", "#4285F4")
        self.row_spawn = SystemRow("Spawner", "Active (95%)", "#0F9D58")
        self.row_lat = SystemRow("Latency (Avg/Max)", "24s / 55s", "#ccc")
        self.row_bottle = SystemRow("Bottlenecks", "None", "#0F9D58")

        sys_l.addWidget(self.row_queue)
        sys_l.addWidget(self.row_th)
        sys_l.addWidget(self.row_spawn)
        sys_l.addWidget(self.row_lat)
        sys_l.addWidget(self.row_bottle)
        
        top_h.addLayout(gauge_l)
        top_h.addSpacing(20)
        top_h.addWidget(sys_panel)
        main_l.addLayout(top_h)

        # 3. KPI STRIP
        main_l.addWidget(QLabel("PERFORMANCE METRICS", objectName="SubHeader"))
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(10)
        
        self.k_near = KpiCard("Near Misses", "0", "Events", "#F4B400")
        self.k_conf = KpiCard("Conflicts", "0", "Hotspots", "#DB4437")
        self.k_nrg = KpiCard("Energy", "0.0", "kWh", "#fff")
        self.k_eff = KpiCard("Efficiency", "0.00", "kWh/Job", "#0F9D58")
        
        kpi_row.addWidget(self.k_near)
        kpi_row.addWidget(self.k_conf)
        kpi_row.addWidget(self.k_nrg)
        kpi_row.addWidget(self.k_eff)
        main_l.addLayout(kpi_row)

        # 4. FLEET GRID (2x2)
        main_l.addWidget(QLabel("REAL-TIME FLEET", objectName="SubHeader"))
        fleet_grid = QGridLayout()
        fleet_grid.setSpacing(10)
        
        self.robots = {}
        ids = ['A', 'B', 'C', 'D']
        for i, rid in enumerate(ids):
            card = RobotCard(rid)
            self.robots[rid] = card
            fleet_grid.addWidget(card, i//2, i%2)
            
        main_l.addLayout(fleet_grid)
        
        # 5. DOCKING STATUS (New 2x2 Grid)
        main_l.addWidget(QLabel("DOCKING STATION STATUS", objectName="SubHeader"))
        dock_grid = QGridLayout()
        dock_grid.setSpacing(10)
        
        self.docks = []
        for i in range(4): # 0 to 3
            d = DockCard(i+1) # ID 1-4
            self.docks.append(d)
            dock_grid.addWidget(d, i//2, i%2) # 0,0 | 0,1 | 1,0 | 1,1
            
        main_l.addLayout(dock_grid)
        main_l.addStretch() 

        # Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(100)

    def tick(self):
        self.time.setText(datetime.datetime.now().strftime("%H:%M:%S"))
        
        if random.random() < 0.05:
            # Gauges
            self.g_work.set_value(random.randint(80, 99))
            self.g_util.set_value(random.randint(50, 90))
            
            # System Rows
            self.row_queue.set_value(f"{random.randint(5, 20)} Tasks")
            self.row_th.set_value(f"{random.randint(40, 60)}/min")
            
            b_count = 0
            if random.random() < 0.1: b_count = random.randint(1, 3)
            col = "#DB4437" if b_count > 0 else "#0F9D58"
            txt = f"{b_count} Alerts" if b_count > 0 else "None"
            self.row_bottle.set_value(txt, col)

            # KPIs
            en = float(self.k_nrg.v.text()) + 0.05
            self.k_nrg.set_value(f"{en:.2f}")
            
            # Robots
            rid = random.choice(['A', 'B', 'C', 'D'])
            st = random.choice(["MOVING", "PICKUP", "CHARGING", "IDLE"])
            bat = random.randint(10, 100)
            if st == "CHARGING": bat = random.randint(20, 80)
            self.robots[rid].update_data(st, bat, random.choice(['T-202', 'A-105', '-']), random.randint(10, 90))
            
            # Docks
            d = random.choice(self.docks)
            d.update_status(random.choice(["IDLE", "IDLE", "ARRIVING", "CHARGING"]))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MissionControl()
    window.show()
    sys.exit(app.exec())