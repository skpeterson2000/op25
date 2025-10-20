import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QGroupBox, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView
from PyQt5.QtCore import QTimer, QThread, pyqtSignal
import utm
import maidenhead as mh
import mgrs
import json
import csv
from math import radians, sin, cos, sqrt, atan2, degrees
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
    gps_data_signal = pyqtSignal(float, float, float, float)  # Signal to send GPS data (latitude, longitude, altitude, speed)

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
                            
                            # Get speed (in m/s)
                            speed = data.get('speed', 0.0)
                            
                            # mode: 0=no fix, 1=no fix, 2=2D, 3=3D
                            if mode >= 2:
                                # Emit GPS data to main thread
                                self.gps_data_signal.emit(lat, lon, alt, speed)
                                
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

# Main Window Class
class GPSWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GPS Data and Tower Locator")
        self.setGeometry(100, 100, 800, 600)

        # Main layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Coordinates Group
        self.coords_group = QGroupBox("Coordinates")
        self.coords_layout = QVBoxLayout()
        self.label_lat = QLabel("Latitude: N/A")
        self.label_lon = QLabel("Longitude: N/A")
        self.coords_layout.addWidget(self.label_lat)
        self.coords_layout.addWidget(self.label_lon)
        self.coords_group.setLayout(self.coords_layout)
        self.layout.addWidget(self.coords_group)

        # Units Group
        self.units_group = QGroupBox("Units")
        self.units_layout = QVBoxLayout()
        self.label_elevation = QLabel("Elevation: N/A")
        self.label_speed = QLabel("Speed: N/A")
        self.units_layout.addWidget(self.label_elevation)
        self.units_layout.addWidget(self.label_speed)
        self.units_group.setLayout(self.units_layout)
        self.layout.addWidget(self.units_group)

        # Grid Systems Group
        self.grids_group = QGroupBox("Grid Systems")
        self.grids_layout = QVBoxLayout()
        self.label_utm = QLabel("UTM: N/A")
        self.label_maidenhead = QLabel("Maidenhead: N/A")
        self.label_mgrs_zone = QLabel("MGRS Zone: N/A")
        self.label_mgrs_grid = QLabel("MGRS Grid: N/A")
        self.label_mgrs_coords = QLabel("MGRS Easting/Northing: N/A")
        self.grids_layout.addWidget(self.label_utm)
        self.grids_layout.addWidget(self.label_maidenhead)
        self.grids_layout.addWidget(self.label_mgrs_zone)
        self.grids_layout.addWidget(self.label_mgrs_grid)
        self.grids_layout.addWidget(self.label_mgrs_coords)
        self.grids_group.setLayout(self.grids_layout)
        self.layout.addWidget(self.grids_group)

        # Table for Closest Towers
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Description", "County", "Distance (mi)", "Bearing (°)", "NAC", "Control Frequencies"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.layout.addWidget(self.table)

        # Path to the CSV file (using the trs_sites_3508.csv in current directory)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.csv_filepath = os.path.join(script_dir, "trs_sites_3508.csv")

        # Start the GPS worker thread
        self.gps_worker = GPSWorker()
        self.gps_worker.gps_data_signal.connect(self.update_gps_data)  # Connect signal to update_gps_data
        self.gps_worker.start()

    def closeEvent(self, event):
        """Clean up GPS worker thread when window closes"""
        if hasattr(self, 'gps_worker') and self.gps_worker.isRunning():
            print("Stopping GPS worker...")
            self.gps_worker.stop()
            self.gps_worker.wait(2000)  # Wait up to 2 seconds for thread to finish
        event.accept()

    def update_gps_data(self, latitude, longitude, altitude, speed):
        # Update Coordinates
        self.label_lat.setText(f"Latitude: {latitude:.6f}")
        self.label_lon.setText(f"Longitude: {longitude:.6f}")

        # Update Units
        self.label_elevation.setText(f"Elevation: {altitude:.2f} m ({altitude * M_TO_FEET:.2f} ft)")
        self.label_speed.setText(f"Speed: {speed:.2f} m/s ({speed * MPS_TO_MPH:.2f} mph, {speed * MPS_TO_KNOTS:.2f} knots)")

        # Update Grid Systems
        try:
            # UTM
            utm_result = utm.from_latlon(latitude, longitude)
            utm_str = f"Zone {utm_result[2]}{utm_result[3]} E:{utm_result[0]:.0f} N:{utm_result[1]:.0f}"
            self.label_utm.setText(f"UTM: {utm_str}")
            
            # Maidenhead
            mh_grid = mh.to_maiden(latitude, longitude)
            self.label_maidenhead.setText(f"Maidenhead: {mh_grid}")
            
            # MGRS
            m = mgrs.MGRS()
            mgrs_result = m.toMGRS(latitude, longitude)
            # Parse MGRS string: first 3 chars are zone, next 2 are grid square
            mgrs_zone = mgrs_result[:3]
            mgrs_grid = mgrs_result[3:5]
            mgrs_coords = mgrs_result[5:]
            self.label_mgrs_zone.setText(f"MGRS Zone: {mgrs_zone}")
            self.label_mgrs_grid.setText(f"MGRS Grid: {mgrs_grid}")
            self.label_mgrs_coords.setText(f"MGRS Easting/Northing: {mgrs_coords}")
        except Exception as e:
            print(f"Error calculating grid systems: {e}")

        # Update Closest Towers
        self.display_closest_sites(latitude, longitude)

    def display_closest_sites(self, latitude, longitude):
        closest_sites = find_closest_sites(self.csv_filepath, latitude, longitude)
        self.table.setRowCount(len(closest_sites))
        for row, (site, distance, bearing, control_frequencies, nac) in enumerate(closest_sites):
            self.table.setItem(row, 0, QTableWidgetItem(site["Description"]))
            self.table.setItem(row, 1, QTableWidgetItem(site["County Name"]))
            self.table.setItem(row, 2, QTableWidgetItem(f"{distance:.2f}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{bearing:.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(str(nac)))
            self.table.setItem(row, 5, QTableWidgetItem(", ".join(control_frequencies)))

# Main Application
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GPSWindow()
    window.show()
    sys.exit(app.exec_())