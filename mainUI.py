import sys
import random
import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QFrame, QProgressBar, 
                             QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QPen

# ==========================================
# 🎨 GOOGLE CLOUD THEME (PyQt Styles)
# ==========================================
STYLES = """
QMainWindow { background-color: #1e2026; }
QLabel { color: #b0b0b0; font-family: 'Consolas', 'Courier New'; }
QLabel#Header { color: #ffffff; font-size: 24px; font-weight: bold; }
QLabel#SubHeader { color: #4285F4; font-size: 14px; font-weight: bold; }
QLabel#BigValue { color: #ffffff; font-size: 36px; font-weight: bold; }
QFrame#Panel { background-color: rgba(255, 255, 255, 10); border-radius: 8px; }
QProgressBar { border: none; background-color: #333; height: 10px; border-radius: 5px; }
QProgressBar::chunk { background-color: #4285F4; border-radius: 5px; }
QTableWidget { background-color: transparent; color: white; gridline-color: #333; border: none; font-family: 'Consolas'; }
QHeaderView::section { background-color: #2d2d2d; color: #4285F4; padding: 4px; border: none; }
"""

# ==========================================
# 🏗️ SIMULATION VIEW (THE GRID)
# ==========================================
class WarehouseGrid(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(800, 800)
        self.grid_data = []
        self.robots = {}  # {'A': (x, y), 'B': (x, y)...}
        self.cell_size = 40
        self.cols = 20
        self.rows = 20

    def update_state(self):
        """Reads the layout file and repaints"""
        try:
            with open('warehouse_layout.txt', 'r') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
            
            if not lines: return
            
            self.grid_data = lines
            self.rows = len(lines)
            self.cols = len(lines[0])
            self.robots = {}

            # Parse for robots to draw them on top
            for y, row in enumerate(lines):
                for x, char in enumerate(row):
                    if char.isupper() and char not in ['X', 'T']:
                        self.robots[char] = (x, y)
            
            self.update() # Trigger paintEvent
        except: pass

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Calculate cell size to fit window
        w_scale = self.width() / max(1, self.cols)
        h_scale = self.height() / max(1, self.rows)
        sz = min(w_scale, h_scale) * 0.95
        
        # Draw Grid
        for y in range(self.rows):
            for x in range(self.cols):
                char = self.grid_data[y][x]
                
                # Base Floor
                painter.fillRect(int(x*sz), int(y*sz), int(sz), int(sz), QColor("#2d2d2d"))
                painter.setPen(QPen(QColor("#3d3d3d"), 1))
                painter.drawRect(int(x*sz), int(y*sz), int(sz), int(sz))
                
                # Draw Objects
                if char == 'X': # Shelf
                    painter.fillRect(int(x*sz+2), int(y*sz+2), int(sz-4), int(sz-4), QColor("#ffffff"))
                elif char == '#': # Charger
                    painter.fillRect(int(x*sz+5), int(y*sz+5), int(sz-10), int(sz-10), QColor("#0F9D58"))
                elif char == '$': # Pickup
                    painter.setBrush(QColor("#F4B400"))
                    painter.drawEllipse(int(x*sz+10), int(y*sz+10), int(sz-20), int(sz-20))
                elif char == '@': # Drop
                    painter.fillRect(int(x*sz+5), int(y*sz+5), int(sz-10), int(sz-10), QColor("#4285F4"))

        # Draw Robots (On Top)
        for rid, (rx, ry) in self.robots.items():
            painter.setBrush(QColor("#FF6D00")) # Orange
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(int(rx*sz+4), int(ry*sz+4), int(sz-8), int(sz-8), 5, 5)
            
            # Robot Label
            painter.setPen(QColor("black"))
            painter.setFont(QFont("Arial", int(sz/2.5), QFont.Weight.Bold))
            painter.drawText(int(rx*sz), int(ry*sz), int(sz), int(sz), Qt.AlignmentFlag.AlignCenter, rid)

# ==========================================
# 📊 DASHBOARD WIDGETS
# ==========================================
class KpiCard(QFrame):
    def __init__(self, title, value, unit, color_hex):
        super().__init__()
        self.setObjectName("Panel")
        layout = QVBoxLayout()
        
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: #888; font-size: 12px;")
        
        self.lbl_val = QLabel(value)
        self.lbl_val.setStyleSheet(f"color: {color_hex}; font-size: 28px; font-weight: bold;")
        
        lbl_unit = QLabel(unit)
        lbl_unit.setStyleSheet("color: #666; font-size: 10px;")
        
        layout.addWidget(lbl_title)
        layout.addWidget(self.lbl_val)
        layout.addWidget(lbl_unit)
        self.setLayout(layout)

class MissionControl(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AIPathfinder: PyQt6 Mission Control")
        self.resize(1280, 720)
        self.setStyleSheet(STYLES)

        # Main Layout: Split Screen (Sim Left | Dashboard Right)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. LEFT SIDE: 2D Grid
        self.grid_view = WarehouseGrid()
        main_layout.addWidget(self.grid_view, stretch=65)

        # 2. RIGHT SIDE: Dashboard Sidebar
        sidebar = QFrame()
        sidebar.setStyleSheet("background-color: #1e2026; border-left: 2px solid #4285F4;")
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(20, 30, 20, 20)
        side_layout.setSpacing(20)
        
        # --- HEADER ---
        header_layout = QVBoxLayout()
        title = QLabel("GOOGLE CLOUD OPS")
        title.setObjectName("Header")
        self.time_lbl = QLabel("00:00:00")
        self.time_lbl.setStyleSheet("color: #4285F4; font-size: 16px;")
        header_layout.addWidget(title)
        header_layout.addWidget(self.time_lbl)
        side_layout.addLayout(header_layout)

        # --- KPI GRID (2x2) ---
        kpi_grid = QGridLayout()
        self.card_workflow = KpiCard("WORKFLOW EFFICIENCY", "84%", "Global Score", "#0F9D58")
        self.card_energy = KpiCard("ENERGY USED", "142.5", "kWh Total", "#FFFFFF")
        self.card_conflicts = KpiCard("CONFLICTS", "3", "Hotspots", "#DB4437")
        self.card_util = KpiCard("FLEET UTILIZATION", "75%", "Active Time", "#F4B400")
        
        kpi_grid.addWidget(self.card_workflow, 0, 0)
        kpi_grid.addWidget(self.card_energy, 0, 1)
        kpi_grid.addWidget(self.card_conflicts, 1, 0)
        kpi_grid.addWidget(self.card_util, 1, 1)
        side_layout.addLayout(kpi_grid)

        # --- FLEET TABLE ---
        lbl_fleet = QLabel("LIVE FLEET HEARTBEAT")
        lbl_fleet.setObjectName("SubHeader")
        side_layout.addWidget(lbl_fleet)

        self.table = QTableWidget(4, 3)
        self.table.setHorizontalHeaderLabels(["ID", "STATE", "BATT %"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        side_layout.addWidget(self.table)

        # Fill table placeholders
        for i, rid in enumerate(['A', 'B', 'C', 'D']):
            self.table.setItem(i, 0, QTableWidgetItem(rid))
            self.table.setItem(i, 1, QTableWidgetItem("IDLE"))
            self.table.setItem(i, 2, QTableWidgetItem("100%"))

        # --- BOTTOM ALERTS ---
        self.alert_box = QFrame()
        self.alert_box.setObjectName("Panel")
        self.alert_box.setStyleSheet("background-color: rgba(219, 68, 55, 0.2); border: 1px solid #DB4437;")
        alert_layout = QHBoxLayout(self.alert_box)
        
        lbl_alert_icon = QLabel("🚨 ALERT:")
        lbl_alert_icon.setStyleSheet("color: #DB4437; font-weight: bold;")
        self.lbl_alert_msg = QLabel("System Nominal")
        self.lbl_alert_msg.setStyleSheet("color: white;")
        
        alert_layout.addWidget(lbl_alert_icon)
        alert_layout.addWidget(self.lbl_alert_msg)
        alert_layout.addStretch()
        side_layout.addWidget(self.alert_box)

        side_layout.addStretch() # Push everything up
        main_layout.addWidget(sidebar, stretch=35)

        # --- TIMER LOOP ---
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_loop)
        self.timer.start(100) # Update every 100ms (10 FPS)

    def update_loop(self):
        # 1. Update Clock
        self.time_lbl.setText(datetime.datetime.now().strftime("%H:%M:%S"))
        
        # 2. Update Grid Visualization
        self.grid_view.update_state()

        # 3. Simulate Data Updates (Connect your Real Data Here)
        if random.random() < 0.05:
            # Jitter Energy
            curr = float(self.card_energy.lbl_val.text())
            self.card_energy.lbl_val.setText(f"{curr + 0.1:.1f}")

            # Jitter Rows
            r = random.randint(0, 3)
            self.table.setItem(r, 1, QTableWidgetItem(random.choice(["MOVE", "PICK", "DROP"])))
            self.table.setItem(r, 2, QTableWidgetItem(f"{random.randint(20, 99)}%"))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MissionControl()
    window.show()
    sys.exit(app.exec())