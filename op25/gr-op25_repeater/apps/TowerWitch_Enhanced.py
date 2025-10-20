import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, QHBoxLayout, 
                            QWidget, QGroupBox, QPushButton, QTableWidget, QTableWidgetItem, 
                            QHeaderView, QTabWidget, QFrame, QScrollArea, QGridLayout,
                            QSizePolicy, QSpacerItem)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt
from PyQt5.QtGui import QFont, QPalette, QColor
import utm
import maidenhead as mh
import mgrs
import json
import csv
from math import radians, sin, cos, sqrt, atan2, degrees
from datetime import datetime
import os
import subprocess
import time

# Conversion constants
M_TO_FEET = 3.28084
MPS_TO_MPH = 2.23694
MPS_TO_KNOTS = 1.94384

# Haversine formula to calculate distance
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Radius of the Earth in kilometers
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c * 0.621371  # Convert to miles

# Calculate bearing between two points
def calculate_bearing(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    x = sin(dlon) * cos(lat2)
    y = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
    return (degrees(atan2(x, y)) + 360) % 360

# Find closest sites from CSV
def find_closest_sites(csv_filepath, user_lat, user_lon, num_sites=5):
    try:
        with open(csv_filepath, "r", encoding="utf-8") as file:
            # Read raw CSV data to handle frequency columns correctly
            csv_reader = csv.reader(file)
            headers = next(csv_reader)  # Skip headers
            data = []
            
            for row in csv_reader:
                # Create site dictionary with proper column access
                site = {
                    "RFSS": row[0] if len(row) > 0 else "",
                    "Site Dec": row[1] if len(row) > 1 else "",
                    "Site Hex": row[2] if len(row) > 2 else "",
                    "Site NAC": row[3] if len(row) > 3 else "",
                    "Description": row[4] if len(row) > 4 else "",
                    "County Name": row[5] if len(row) > 5 else "",
                    "Lat": row[6] if len(row) > 6 else "",
                    "Lon": row[7] if len(row) > 7 else "",
                    "Range": row[8] if len(row) > 8 else "",
                }
                
                # Extract all frequencies from columns 9 onwards
                frequencies = []
                for i in range(9, len(row)):
                    value = row[i].strip() if row[i] else ""
                    if value:
                        frequencies.append(value)
                
                site["Frequencies"] = frequencies
                data.append(site)
                
    except FileNotFoundError:
        print(f"Error: CSV file not found at {csv_filepath}")
        return []

    distances = []
    for site in data:
        try:
            site_lat = float(site["Lat"])
            site_lon = float(site["Lon"])
            distance = haversine(user_lat, user_lon, site_lat, site_lon)
            bearing = calculate_bearing(user_lat, user_lon, site_lat, site_lon)
            
            # Find all control channels (those ending with 'c')
            control_frequencies = []
            for freq in site["Frequencies"]:
                if freq.endswith("c"):
                    control_frequencies.append(freq.replace("c", ""))
            
            # Get NAC (Network Access Code)
            nac = site.get("Site NAC", "N/A")
            
            if control_frequencies:
                distances.append((site, distance, bearing, control_frequencies, nac))
        except (KeyError, ValueError) as e:
            print(f"Error processing site {site.get('Description', 'Unknown')}: {e}")
            continue

    distances.sort(key=lambda x: x[1])
    return distances[:num_sites]

# GPS Worker Class using gpspipe
class GPSWorker(QThread):
    gps_data_signal = pyqtSignal(float, float, float, float, float)  # Added heading parameter

    def __init__(self, host='127.0.0.1', port=2947):
        super().__init__()
        self.host = host
        self.port = port
        self.running = True

    def run(self):
        try:
            # Start gpspipe process
            cmd = ['gpspipe', '-w']
            
            if self.host != '127.0.0.1' or self.port != 2947:
                env = os.environ.copy()
                env['GPSD_HOST'] = f"{self.host}:{self.port}"
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                          env=env, text=True)
            else:
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            print("✓ GPS Worker started - reading from gpspipe")
            
            # Read gpspipe output continuously
            for line in process.stdout:
                if not self.running:
                    break
                    
                try:
                    data = json.loads(line.strip())
                    msg_class = data.get('class', 'UNKNOWN')
                    
                    # Look for TPV (Time-Position-Velocity) messages
                    if msg_class == 'TPV':
                        if 'lat' in data and 'lon' in data and 'mode' in data:
                            lat = data['lat']
                            lon = data['lon']
                            alt = data.get('alt', 0.0)
                            mode = data['mode']
                            
                            # Get speed (in m/s) and track/heading
                            speed = data.get('speed', 0.0)
                            track = data.get('track', 0.0)  # Course over ground in degrees
                            
                            # mode: 0=no fix, 1=no fix, 2=2D, 3=3D
                            if mode >= 2:
                                # Emit GPS data to main thread (lat, lon, alt, speed, heading)
                                self.gps_data_signal.emit(lat, lon, alt, speed, track)
                                
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    print(f"Error parsing GPS message: {e}")
                    continue
            
            process.terminate()
            
        except FileNotFoundError:
            print("❌ Error: gpspipe not found. Install gpsd-clients package:")
            print("  sudo apt-get install gpsd-clients")
        except Exception as e:
            print(f"❌ Error in GPSWorker: {e}")
    
    def stop(self):
        self.running = False

# Enhanced Main Window Class
class EnhancedGPSWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TowerWitch - Enhanced GPS Tower Locator")
        
        # Optimize for 10" touchscreen (1024x600 typical resolution)
        self.setGeometry(0, 0, 1024, 600)
        self.setMinimumSize(800, 600)
        
        # Set up styling for touch interface
        self.setup_styling()
        
        # Create main widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setSpacing(10)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Create header with title and status
        self.create_header()
        
        # Create tabbed interface
        self.create_tabs()
        
        # Create control buttons
        self.create_control_buttons()
        
        # Path to the CSV file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.csv_filepath = os.path.join(script_dir, "trs_sites_3508.csv")
        
        # Start GPS worker
        self.gps_worker = GPSWorker()
        self.gps_worker.gps_data_signal.connect(self.update_gps_data)
        self.gps_worker.start()
        
        # Initialize with demo data if no GPS
        self.last_lat = 44.9778  # Minneapolis default
        self.last_lon = -93.2650

    def setup_styling(self):
        """Set up fonts and colors for touch interface"""
        # Balanced fonts - larger for important data, reasonable for coordinates
        self.header_font = QFont("Arial", 18, QFont.Bold)
        self.label_font = QFont("Arial", 14, QFont.Bold)
        self.data_font = QFont("Arial", 12)  # Smaller for coordinate data
        self.coordinate_font = QFont("Arial", 11)  # Even smaller for coordinates
        self.button_font = QFont("Arial", 14, QFont.Bold)
        self.table_font = QFont("Arial", 13)
        
        # Color scheme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 2px solid #555555;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 12px;
                background-color: #3b3b3b;
                color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px 0 10px;
                color: #00ff00;
                font-size: 14px;
            }
            QLabel {
                color: #ffffff;
                padding: 6px;
                font-size: 12px;
            }
            QPushButton {
                background-color: #4a90e2;
                border: none;
                border-radius: 8px;
                padding: 15px;
                font-weight: bold;
                color: white;
                min-height: 45px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QPushButton:pressed {
                background-color: #2968a3;
            }
            QTableWidget {
                background-color: #3b3b3b;
                border: 1px solid #555555;
                border-radius: 5px;
                gridline-color: #555555;
                font-size: 13px;
                color: #ffffff;
            }
            QTableWidget::item {
                padding: 12px;
                border-bottom: 1px solid #555555;
                color: #ffffff;
                font-size: 13px;
            }
            QTableWidget::item:alternate {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QTableWidget::item:selected {
                background-color: #4a90e2;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #4a90e2;
                color: #ffffff;
                padding: 12px;
                border: 1px solid #555555;
                font-weight: bold;
                font-size: 14px;
            }
            QTabWidget::pane {
                border: 1px solid #555555;
                background-color: #3b3b3b;
            }
            QTabBar::tab {
                background-color: #2b2b2b;
                color: #ffffff;
                padding: 15px 25px;
                margin-right: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                min-width: 120px;
                font-size: 14px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #4a90e2;
            }
        """)

    def create_header(self):
        """Create header with title, date/time, and GPS status"""
        header_frame = QFrame()
        header_layout = QHBoxLayout(header_frame)
        
        # Title
        title_label = QLabel("🗼 TowerWitch")
        title_label.setFont(self.header_font)
        title_label.setStyleSheet("color: #00ff00; padding: 10px;")
        
        # Date and Time in center
        self.datetime_label = QLabel()
        self.datetime_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.datetime_label.setStyleSheet("color: #ffffff; padding: 10px;")
        self.datetime_label.setAlignment(Qt.AlignCenter)
        self.update_datetime()
        
        # GPS Status indicator (right side)
        self.gps_status = QLabel("GPS: Searching...")
        self.gps_status.setFont(self.label_font)
        self.gps_status.setStyleSheet("color: #ffaa00; padding: 6px; font-size: 14px;")
        self.gps_status.setAlignment(Qt.AlignRight)
        
        header_layout.addWidget(title_label, 1)
        header_layout.addWidget(self.datetime_label, 2)
        header_layout.addWidget(self.gps_status, 1)
        
        self.main_layout.addWidget(header_frame)
        
        # Timer for updating date/time every second
        self.datetime_timer = QTimer()
        self.datetime_timer.timeout.connect(self.update_datetime)
        self.datetime_timer.start(1000)  # Update every second

    def create_tabs(self):
        """Create tabbed interface for different information views"""
        self.tabs = QTabWidget()
        
        # GPS Data Tab
        self.gps_tab = self.create_gps_tab()
        self.tabs.addTab(self.gps_tab, "📍 GPS Data")
        
        # Tower Data Tab
        self.tower_tab = self.create_tower_tab()
        self.tabs.addTab(self.tower_tab, "🗼 Towers")
        
        # Grid Systems Tab
        self.grid_tab = self.create_grid_tab()
        self.tabs.addTab(self.grid_tab, "🗺️ Grids")
        
        self.main_layout.addWidget(self.tabs)

    def create_gps_tab(self):
        """Create GPS data display tab with table format"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Create a table for GPS data
        self.gps_table = QTableWidget()
        self.gps_table.setColumnCount(2)
        self.gps_table.setHorizontalHeaderLabels(["MEASUREMENT", "VALUE"])
        self.gps_table.setRowCount(8)  # 8 different measurements (added heading and vector speed)
        
        # Set up table appearance
        self.gps_table.setAlternatingRowColors(True)
        self.gps_table.verticalHeader().setVisible(False)
        self.gps_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.gps_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # Set column widths
        header = self.gps_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Measurement name column
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Value column expands
        
        # Set row height for better readability
        self.gps_table.verticalHeader().setDefaultSectionSize(45)
        
        # Style the GPS table specifically
        self.gps_table.setStyleSheet("""
            QTableWidget {
                background-color: #3b3b3b;
                border: 1px solid #555555;
                border-radius: 5px;
                gridline-color: #555555;
                font-size: 12px;
                color: #ffffff;
            }
            QTableWidget::item {
                padding: 10px;
                border-bottom: 1px solid #555555;
                color: #ffffff;
            }
            QTableWidget::item:alternate {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QTableWidget::item:selected {
                background-color: #4a90e2;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #4a90e2;
                color: #ffffff;
                padding: 12px;
                border: 1px solid #555555;
                font-weight: bold;
                font-size: 13px;
            }
        """)
        
        # Initialize GPS labels for updating
        self.gps_items = {}
        
        # Row 0: Latitude
        self.gps_items['lat_item'] = QTableWidgetItem("📍 LATITUDE")
        self.gps_items['lat_item'].setFont(QFont("Arial", 12, QFont.Bold))
        self.gps_items['lat_value'] = QTableWidgetItem("Waiting for GPS...")
        self.gps_items['lat_value'].setFont(QFont("Arial", 12))
        
        # Row 1: Longitude  
        self.gps_items['lon_item'] = QTableWidgetItem("� LONGITUDE")
        self.gps_items['lon_item'].setFont(QFont("Arial", 12, QFont.Bold))
        self.gps_items['lon_value'] = QTableWidgetItem("Waiting for GPS...")
        self.gps_items['lon_value'].setFont(QFont("Arial", 12))
        
        # Row 2: Altitude
        self.gps_items['alt_item'] = QTableWidgetItem("⛰️ ALTITUDE")
        self.gps_items['alt_item'].setFont(QFont("Arial", 12, QFont.Bold))
        self.gps_items['alt_value'] = QTableWidgetItem("N/A")
        self.gps_items['alt_value'].setFont(QFont("Arial", 12))
        
        # Row 3: Speed
        self.gps_items['speed_item'] = QTableWidgetItem("🚗 SPEED")
        self.gps_items['speed_item'].setFont(QFont("Arial", 12, QFont.Bold))
        self.gps_items['speed_value'] = QTableWidgetItem("N/A")
        self.gps_items['speed_value'].setFont(QFont("Arial", 12))
        
        # Row 4: Heading/Direction
        self.gps_items['heading_item'] = QTableWidgetItem("🧭 HEADING")
        self.gps_items['heading_item'].setFont(QFont("Arial", 12, QFont.Bold))
        self.gps_items['heading_value'] = QTableWidgetItem("N/A")
        self.gps_items['heading_value'].setFont(QFont("Arial", 12))
        
        # Row 5: Vector Speed (speed + direction)
        self.gps_items['vector_item'] = QTableWidgetItem("🏃 VECTOR SPEED")
        self.gps_items['vector_item'].setFont(QFont("Arial", 12, QFont.Bold))
        self.gps_items['vector_value'] = QTableWidgetItem("N/A")
        self.gps_items['vector_value'].setFont(QFont("Arial", 12))
        
        # Row 6: GPS Status
        self.gps_items['status_item'] = QTableWidgetItem("🛰️ GPS STATUS")
        self.gps_items['status_item'].setFont(QFont("Arial", 12, QFont.Bold))
        self.gps_items['status_value'] = QTableWidgetItem("Searching...")
        self.gps_items['status_value'].setFont(QFont("Arial", 12))
        
        # Row 7: Fix Quality
        self.gps_items['fix_item'] = QTableWidgetItem("📡 FIX QUALITY")
        self.gps_items['fix_item'].setFont(QFont("Arial", 12, QFont.Bold))
        self.gps_items['fix_value'] = QTableWidgetItem("No Fix")
        self.gps_items['fix_value'].setFont(QFont("Arial", 12))
        
        # Add items to table
        self.gps_table.setItem(0, 0, self.gps_items['lat_item'])
        self.gps_table.setItem(0, 1, self.gps_items['lat_value'])
        self.gps_table.setItem(1, 0, self.gps_items['lon_item'])
        self.gps_table.setItem(1, 1, self.gps_items['lon_value'])
        self.gps_table.setItem(2, 0, self.gps_items['alt_item'])
        self.gps_table.setItem(2, 1, self.gps_items['alt_value'])
        self.gps_table.setItem(3, 0, self.gps_items['speed_item'])
        self.gps_table.setItem(3, 1, self.gps_items['speed_value'])
        self.gps_table.setItem(4, 0, self.gps_items['heading_item'])
        self.gps_table.setItem(4, 1, self.gps_items['heading_value'])
        self.gps_table.setItem(5, 0, self.gps_items['vector_item'])
        self.gps_table.setItem(5, 1, self.gps_items['vector_value'])
        self.gps_table.setItem(6, 0, self.gps_items['status_item'])
        self.gps_table.setItem(6, 1, self.gps_items['status_value'])
        self.gps_table.setItem(7, 0, self.gps_items['fix_item'])
        self.gps_table.setItem(7, 1, self.gps_items['fix_value'])
        
        layout.addWidget(self.gps_table)
        
        return tab

    def create_tower_tab(self):
        """Create tower information display tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Tower table with enhanced formatting
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Site Name", "County", "Distance", "Bearing", "NAC", "Control Channels"])
        
        # Set column widths for better touch interface
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Site name can expand
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # County
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Distance
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Bearing
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # NAC
        header.setSectionResizeMode(5, QHeaderView.Stretch)  # Control frequencies can expand
        
        # Make table touch-friendly with larger fonts and spacing
        self.table.setMinimumHeight(450)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(50)  # Even taller rows for better readability
        self.table.setFont(self.table_font)
        
        layout.addWidget(self.table)
        
        return tab

    def create_grid_tab(self):
        """Create grid systems display tab with table format"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Create a table for grid systems
        self.grid_table = QTableWidget()
        self.grid_table.setColumnCount(2)
        self.grid_table.setHorizontalHeaderLabels(["GRID SYSTEM", "COORDINATES"])
        self.grid_table.setRowCount(6)  # 6 different coordinate systems
        
        # Set up table appearance
        self.grid_table.setAlternatingRowColors(True)
        self.grid_table.verticalHeader().setVisible(False)
        self.grid_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.grid_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # Set column widths
        header = self.grid_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # System name column
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Coordinates column expands
        
        # Set row height for better readability
        self.grid_table.verticalHeader().setDefaultSectionSize(45)
        
        # Style the grid table specifically
        self.grid_table.setStyleSheet("""
            QTableWidget {
                background-color: #3b3b3b;
                border: 1px solid #555555;
                border-radius: 5px;
                gridline-color: #555555;
                font-size: 12px;
                color: #ffffff;
            }
            QTableWidget::item {
                padding: 10px;
                border-bottom: 1px solid #555555;
                color: #ffffff;
            }
            QTableWidget::item:alternate {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QTableWidget::item:selected {
                background-color: #4a90e2;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #4a90e2;
                color: #ffffff;
                padding: 12px;
                border: 1px solid #555555;
                font-weight: bold;
                font-size: 13px;
            }
        """)
        
        # Initialize grid labels for updating
        self.grid_items = {}
        
        # Row 0: Decimal Degrees
        self.grid_items['lat_item'] = QTableWidgetItem("📍 LATITUDE")
        self.grid_items['lat_item'].setFont(QFont("Arial", 12, QFont.Bold))
        self.grid_items['lat_value'] = QTableWidgetItem("Waiting for GPS...")
        self.grid_items['lat_value'].setFont(QFont("Arial", 12))
        
        # Row 1: Longitude
        self.grid_items['lon_item'] = QTableWidgetItem("📍 LONGITUDE")
        self.grid_items['lon_item'].setFont(QFont("Arial", 12, QFont.Bold))
        self.grid_items['lon_value'] = QTableWidgetItem("Waiting for GPS...")
        self.grid_items['lon_value'].setFont(QFont("Arial", 12))
        
        # Row 2: UTM
        self.grid_items['utm_item'] = QTableWidgetItem("🗺️ UTM")
        self.grid_items['utm_item'].setFont(QFont("Arial", 12, QFont.Bold))
        self.grid_items['utm_value'] = QTableWidgetItem("N/A")
        self.grid_items['utm_value'].setFont(QFont("Arial", 12))
        
        # Row 3: Maidenhead
        self.grid_items['mh_item'] = QTableWidgetItem("📡 MAIDENHEAD")
        self.grid_items['mh_item'].setFont(QFont("Arial", 12, QFont.Bold))
        self.grid_items['mh_value'] = QTableWidgetItem("N/A")
        self.grid_items['mh_value'].setFont(QFont("Arial", 12))
        
        # Row 4: MGRS Zone/Grid
        self.grid_items['mgrs_zone_item'] = QTableWidgetItem("🪖 MGRS ZONE/GRID")
        self.grid_items['mgrs_zone_item'].setFont(QFont("Arial", 12, QFont.Bold))
        self.grid_items['mgrs_zone_value'] = QTableWidgetItem("N/A")
        self.grid_items['mgrs_zone_value'].setFont(QFont("Arial", 12))
        
        # Row 5: MGRS Coordinates
        self.grid_items['mgrs_coords_item'] = QTableWidgetItem("🔢 MGRS EASTING/NORTHING")
        self.grid_items['mgrs_coords_item'].setFont(QFont("Arial", 12, QFont.Bold))
        self.grid_items['mgrs_coords_value'] = QTableWidgetItem("N/A")
        self.grid_items['mgrs_coords_value'].setFont(QFont("Arial", 12))
        
        # Add items to table
        self.grid_table.setItem(0, 0, self.grid_items['lat_item'])
        self.grid_table.setItem(0, 1, self.grid_items['lat_value'])
        self.grid_table.setItem(1, 0, self.grid_items['lon_item'])
        self.grid_table.setItem(1, 1, self.grid_items['lon_value'])
        self.grid_table.setItem(2, 0, self.grid_items['utm_item'])
        self.grid_table.setItem(2, 1, self.grid_items['utm_value'])
        self.grid_table.setItem(3, 0, self.grid_items['mh_item'])
        self.grid_table.setItem(3, 1, self.grid_items['mh_value'])
        self.grid_table.setItem(4, 0, self.grid_items['mgrs_zone_item'])
        self.grid_table.setItem(4, 1, self.grid_items['mgrs_zone_value'])
        self.grid_table.setItem(5, 0, self.grid_items['mgrs_coords_item'])
        self.grid_table.setItem(5, 1, self.grid_items['mgrs_coords_value'])
        
        layout.addWidget(self.grid_table)
        
        return tab

    def create_control_buttons(self):
        """Create touch-friendly control buttons"""
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh Towers")
        refresh_btn.setFont(self.button_font)
        refresh_btn.clicked.connect(self.refresh_towers)
        
        # Export button  
        export_btn = QPushButton("💾 Export Data")
        export_btn.setFont(self.button_font)
        export_btn.clicked.connect(self.export_data)
        
        # Night Mode toggle button
        self.night_mode_btn = QPushButton("🌙 Night Mode")
        self.night_mode_btn.setFont(self.button_font)
        self.night_mode_btn.clicked.connect(self.toggle_night_mode_button)
        self.night_mode_active = False  # Track night mode state
        
        button_layout.addWidget(refresh_btn)
        button_layout.addWidget(export_btn)
        button_layout.addWidget(self.night_mode_btn)
        
        self.main_layout.addWidget(button_frame)

    def refresh_towers(self):
        """Manually refresh tower data"""
        if hasattr(self, 'last_lat') and hasattr(self, 'last_lon'):
            self.display_closest_sites(self.last_lat, self.last_lon)

    def export_data(self):
        """Export current tower data"""
        # Placeholder for export functionality
        print("Export functionality - could save to file or copy to clipboard")

    def show_settings(self):
        """Show settings dialog"""
        # Placeholder for settings dialog
        print("Settings dialog - could configure GPS host, number of sites, etc.")

    def update_datetime(self):
        """Update date and time display"""
        now = datetime.now()
        # Format: "Mon Oct 20, 2025  14:35:27"
        day_name = now.strftime("%a")  # Mon, Tue, etc.
        date_str = now.strftime("%b %d, %Y")
        time_str = now.strftime("%H:%M:%S")
        self.datetime_label.setText(f"{day_name} {date_str}  {time_str}")

    def toggle_night_mode_button(self):
        """Toggle night mode when button is clicked"""
        self.night_mode_active = not self.night_mode_active
        self.toggle_night_mode(self.night_mode_active)
        
        # Update button text to reflect current state
        if self.night_mode_active:
            self.night_mode_btn.setText("☀️ Day Mode")
        else:
            self.night_mode_btn.setText("🌙 Night Mode")

    def update_table_colors_for_mode(self, night_mode_on):
        """Update table item colors based on current mode"""
        if night_mode_on:
            # Night mode colors - red theme
            active_color = QColor(255, 102, 102)      # Light red for active status
            warning_color = QColor(255, 153, 102)     # Orange-red for warnings  
            text_color = QColor(255, 102, 102)        # Red for regular text
        else:
            # Day mode colors - original theme
            active_color = QColor(0, 255, 0)          # Green for active status
            warning_color = QColor(255, 255, 0)       # Yellow for warnings
            text_color = QColor(255, 255, 255)        # White for regular text
        
        # Update GPS status colors if they exist
        if hasattr(self, 'gps_items'):
            if 'status_value' in self.gps_items:
                self.gps_items['status_value'].setForeground(active_color)
            if 'fix_value' in self.gps_items:
                # Check current fix text to determine appropriate color
                fix_text = self.gps_items['fix_value'].text()
                if "Moving" in fix_text:
                    self.gps_items['fix_value'].setForeground(active_color)
                else:
                    self.gps_items['fix_value'].setForeground(warning_color)
        
        # Update tower table colors if it exists
        if hasattr(self, 'tower_table'):
            for row in range(self.tower_table.rowCount()):
                for col in range(self.tower_table.columnCount()):
                    item = self.tower_table.item(row, col)
                    if item:
                        item.setForeground(text_color)

    def toggle_night_mode(self, night_mode_on):
        """Toggle between day and night mode for better night vision"""
        if night_mode_on:
            # Night mode - red theme for preserving night vision
            night_style = """
            QMainWindow {
                background-color: #1a0000;
                color: #ff6666;
            }
            QTabWidget::pane {
                border: 2px solid #330000;
                background-color: #1a0000;
            }
            QTabBar::tab {
                background-color: #220000;
                color: #ff6666;
                padding: 15px 25px;
                margin-right: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                min-width: 120px;
                font-size: 14px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #660000;
            }
            QTableWidget {
                background-color: #1a0000;
                alternate-background-color: #220000;
                color: #ff6666;
                gridline-color: #330000;
                border: 1px solid #330000;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #330000;
            }
            QHeaderView::section {
                background-color: #330000;
                color: #ff6666;
                font-weight: bold;
                font-size: 14px;
                padding: 8px;
                border: 1px solid #550000;
            }
            QLabel {
                color: #ff6666;
            }
            QPushButton {
                background-color: #660000;
                border: none;
                border-radius: 8px;
                padding: 15px;
                font-weight: bold;
                color: #ff6666;
                min-height: 45px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #880000;
            }

            """
            self.setStyleSheet(night_style)
            # Update header colors for night mode
            self.gps_status.setStyleSheet("color: #ff6666; padding: 6px; font-size: 14px;")
            self.datetime_label.setStyleSheet("color: #ff6666; padding: 10px;")
        else:
            # Day mode - restore original dark theme
            self.setup_styling()
            self.gps_status.setStyleSheet("color: #00ff00; padding: 6px; font-size: 14px;")
            self.datetime_label.setStyleSheet("color: #ffffff; padding: 10px;")
        
        # Update all table item colors to match the new theme
        self.update_table_colors_for_mode(night_mode_on)

    def update_gps_data(self, latitude, longitude, altitude, speed, heading):
        """Update all GPS-related displays"""
        self.last_lat = latitude
        self.last_lon = longitude
        
        # Update GPS status in header
        self.gps_status.setText("GPS: Active 🟢")
        self.gps_status.setStyleSheet("color: #00ff00; padding: 12px; font-size: 14px;")
        
        # Update GPS table
        self.gps_items['lat_value'].setText(f"{latitude:.6f}°")
        self.gps_items['lon_value'].setText(f"{longitude:.6f}°")
        
        # Update altitude with both metric and imperial
        self.gps_items['alt_value'].setText(f"{altitude:.1f} m ({altitude * M_TO_FEET:.1f} ft)")
        
        # Update speed with multiple units (with minimum threshold)
        # GPS noise threshold - ignore speeds below 0.5 m/s (~1.1 mph, walking speed)
        MIN_SPEED_THRESHOLD = 0.5  # meters per second
        
        if speed >= MIN_SPEED_THRESHOLD:
            speed_mph = speed * MPS_TO_MPH
            speed_knots = speed * MPS_TO_KNOTS
            self.gps_items['speed_value'].setText(f"{speed:.1f} m/s ({speed_mph:.1f} mph, {speed_knots:.1f} kt)")
            is_moving = True
        else:
            # Below threshold - consider stationary
            self.gps_items['speed_value'].setText("0.0 m/s (0.0 mph, 0.0 kt)")
            is_moving = False
        
        # Update heading with cardinal direction (only when moving)
        if heading is not None and heading >= 0 and is_moving:
            # Convert bearing to cardinal direction
            directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                         'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
            index = int((heading + 11.25) / 22.5) % 16
            cardinal = directions[index]
            self.gps_items['heading_value'].setText(f"{heading:.0f}° ({cardinal})")
        else:
            self.gps_items['heading_value'].setText("--° (--)")
        
        # Update vector speed (speed + direction combined)
        if is_moving and heading is not None and heading >= 0:
            # Convert bearing to cardinal direction for vector
            directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                         'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
            index = int((heading + 11.25) / 22.5) % 16
            cardinal = directions[index]
            speed_mph = speed * MPS_TO_MPH
            self.gps_items['vector_value'].setText(f"{speed_mph:.1f} mph {cardinal}")
        else:
            self.gps_items['vector_value'].setText("Stationary")
        
        # Update GPS status and fix quality
        self.gps_items['status_value'].setText("🟢 ACTIVE")
        self.gps_items['status_value'].setForeground(QColor(0, 255, 0))  # Green text
        
        # Determine fix quality based on speed accuracy (rough estimate)
        if speed > 0.1:  # Moving
            self.gps_items['fix_value'].setText("🟢 3D FIX (Moving)")
            self.gps_items['fix_value'].setForeground(QColor(0, 255, 0))
        else:  # Stationary
            self.gps_items['fix_value'].setText("🟡 3D FIX (Stationary)")
            self.gps_items['fix_value'].setForeground(QColor(255, 255, 0))

        # Update Grid Systems in table format
        try:
            # Update coordinates in grid table
            self.grid_items['lat_value'].setText(f"{latitude:.6f}°")
            self.grid_items['lon_value'].setText(f"{longitude:.6f}°")
            
            # UTM
            utm_result = utm.from_latlon(latitude, longitude)
            utm_str = f"Zone {utm_result[2]}{utm_result[3]} E:{utm_result[0]:.0f} N:{utm_result[1]:.0f}"
            self.grid_items['utm_value'].setText(utm_str)
            
            # Maidenhead
            mh_grid = mh.to_maiden(latitude, longitude)
            self.grid_items['mh_value'].setText(mh_grid)
            
            # MGRS
            m = mgrs.MGRS()
            mgrs_result = m.toMGRS(latitude, longitude)
            mgrs_zone = mgrs_result[:3]
            mgrs_grid = mgrs_result[3:5]
            mgrs_coords = mgrs_result[5:]
            
            # Split MGRS coordinates into easting and northing for better readability
            if len(mgrs_coords) >= 6:
                mid_point = len(mgrs_coords) // 2
                easting = mgrs_coords[:mid_point]
                northing = mgrs_coords[mid_point:]
                formatted_coords = f"{easting} {northing}"
            else:
                formatted_coords = mgrs_coords
                
            self.grid_items['mgrs_zone_value'].setText(f"{mgrs_zone} {mgrs_grid}")
            self.grid_items['mgrs_coords_value'].setText(formatted_coords)
            
        except Exception as e:
            print(f"Error calculating grid systems: {e}")

        # Update Closest Towers
        self.display_closest_sites(latitude, longitude)

    def display_closest_sites(self, latitude, longitude):
        """Display closest tower sites in enhanced table"""
        closest_sites = find_closest_sites(self.csv_filepath, latitude, longitude)
        self.table.setRowCount(len(closest_sites))
        
        for row, (site, distance, bearing, control_frequencies, nac) in enumerate(closest_sites):
            # Site name with color coding by distance
            site_item = QTableWidgetItem(site["Description"])
            if distance < 5:
                site_item.setBackground(QColor(0, 120, 0))  # Darker green for better contrast
                site_item.setForeground(QColor(255, 255, 255))  # White text
            elif distance < 15:
                site_item.setBackground(QColor(140, 140, 0))  # Darker yellow for better contrast
                site_item.setForeground(QColor(255, 255, 255))  # White text
            else:
                site_item.setBackground(QColor(120, 0, 0))  # Darker red for better contrast
                site_item.setForeground(QColor(255, 255, 255))  # White text
            
            # Create other items with white text
            county_item = QTableWidgetItem(site["County Name"])
            county_item.setForeground(QColor(255, 255, 255))
            
            distance_item = QTableWidgetItem(f"{distance:.1f} mi")
            distance_item.setForeground(QColor(255, 255, 255))
            
            bearing_item = QTableWidgetItem(f"{bearing:.0f}°")
            bearing_item.setForeground(QColor(255, 255, 255))
            
            nac_item = QTableWidgetItem(str(nac))
            nac_item.setForeground(QColor(255, 255, 255))
            
            # Format control frequencies nicely
            freq_text = ", ".join(control_frequencies) if control_frequencies else "N/A"
            freq_item = QTableWidgetItem(freq_text)
            freq_item.setForeground(QColor(255, 255, 255))
            
            self.table.setItem(row, 0, site_item)
            self.table.setItem(row, 1, county_item)
            self.table.setItem(row, 2, distance_item)
            self.table.setItem(row, 3, bearing_item)
            self.table.setItem(row, 4, nac_item)
            self.table.setItem(row, 5, freq_item)

    def closeEvent(self, event):
        """Clean up GPS worker thread when window closes"""
        if hasattr(self, 'gps_worker') and self.gps_worker.isRunning():
            print("Stopping GPS worker...")
            self.gps_worker.stop()
            self.gps_worker.wait(2000)
        event.accept()

# Main Application
if __name__ == "__main__":
    # Enable high DPI scaling BEFORE creating QApplication
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    
    window = EnhancedGPSWindow()
    window.show()
    
    sys.exit(app.exec_())