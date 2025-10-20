# Tower Witch - GPS Tower Locator

Tower Witch helps you find the nearest P25 radio towers based on your GPS location.

## Features

- Multiple distance units: miles (mi), kilometers (km), nautical miles (nm)
- Multiple GPS sources: gpsd, NMEA serial GPS, file, or manual coordinates
- Find nearest tower or all towers within a specified range
- Distance conversion utilities
- Save/load GPS positions to/from file

## Quick Start

### Using Manual GPS Coordinates
```bash
python3 tower_witch.py --gps manual --lat 44.9778 --lon -93.2650
```

### Save GPS Position for Later Use
```bash
python3 tower_witch.py --gps manual --lat 44.9778 --lon -93.2650 --save-gps
```

### Use Saved GPS Position
```bash
python3 tower_witch.py --gps file
```

### Using gpsd (if you have a GPS device connected)
```bash
# Make sure gpsd is running first:
# sudo systemctl start gpsd

python3 tower_witch.py --gps gpsd
```

### Auto-detect GPS Source
```bash
python3 tower_witch.py --gps auto
```

## Distance Units

Change units with `--unit`:

```bash
# Miles (default)
python3 tower_witch.py --gps file --unit mi --range 30

# Kilometers
python3 tower_witch.py --gps file --unit km --range 50

# Nautical miles
python3 tower_witch.py --gps file --unit nm --range 25
```

## Search Range

Find towers within a specific distance:

```bash
# Find all towers within 50 miles
python3 tower_witch.py --gps file --range 50

# Find all towers within 100 km
python3 tower_witch.py --gps file --unit km --range 100
```

## GPS Sources

### Method 1: Manual Coordinates
Best for: Testing, fixed locations

```bash
python3 tower_witch.py --gps manual --lat 44.9778 --lon -93.2650
```

### Method 2: GPS File
Best for: Saving a position for repeated use

Create `gps_position.txt` with:
```json
{"latitude": 44.9778, "longitude": -93.2650}
```

Or save automatically:
```bash
python3 tower_witch.py --gps manual --lat 44.9778 --lon -93.2650 --save-gps
```

Then use it:
```bash
python3 tower_witch.py --gps file
```

### Method 3: gpsd (GPS Daemon)
Best for: Live GPS tracking with a connected GPS device

Requirements:
```bash
sudo apt-get install gpsd gpsd-clients
```

Start gpsd with your GPS device:
```bash
# For USB GPS (adjust device as needed)
sudo gpsd /dev/ttyUSB0 -F /var/run/gpsd.sock

# Or use systemd
sudo systemctl start gpsd
```

Use with tower_witch:
```bash
python3 tower_witch.py --gps gpsd
```

### Method 4: NMEA Serial GPS
Best for: Direct serial GPS without gpsd

```bash
python3 tower_witch.py --gps nmea --gps-device /dev/ttyUSB0
```

### Method 5: Auto-detect
Tries gpsd first, then falls back to file:

```bash
python3 tower_witch.py --gps auto
```

## All Command Line Options

```
usage: tower_witch.py [-h] [--csv CSV] [--unit {km,mi,nm}] [--range RANGE]
                      [--gps {auto,gpsd,nmea,file,manual}] [--lat LAT] [--lon LON]
                      [--gps-device GPS_DEVICE] [--gps-file GPS_FILE] [--save-gps]

Tower Witch - Find nearest P25 towers

options:
  -h, --help            show this help message and exit
  --csv CSV             CSV file with tower data (default: trs_sites_3508.csv)
  --unit {km,mi,nm}     Distance unit (default: mi)
  --range RANGE         Search range (default: 30)
  --gps {auto,gpsd,nmea,file,manual}
                        GPS source method (default: auto)
  --lat LAT             Manual latitude
  --lon LON             Manual longitude
  --gps-device GPS_DEVICE
                        NMEA GPS device (default: /dev/ttyUSB0)
  --gps-file GPS_FILE   GPS position file (default: gps_position.txt)
  --save-gps            Save GPS position to file
```

## Output Format

The script shows:
- Your GPS position
- Nearest tower with full details (RFSS, Site, NAC, frequencies)
- List of all towers within range, sorted by distance
- Distance in your chosen unit (with all units shown for nearest tower)

Example output:
```
Loaded 290 towers from trs_sites_3508.csv

=== Getting GPS Position (method: file) ===
GPS Position: 44.977800, -93.265000

=== Using miles ===

Nearest tower:
Tower: Minneapolis City Center Simulcast
County: Hennepin
Location: 44.9799654, -93.2638361
RFSS: 1, Site: 1 (0x1)
NAC: 400
Range: 40 km
Distance: 0.16 mi (0.26 km, 0.16 mi, 0.14 nm)
Frequencies: 856.2375, 856.2625, 856.7625, ...

Found 13 towers within 30.0 mi

Top 10 nearest towers:
 1.   0.16 mi - Minneapolis City Center Simulcast        (Hennepin)
 2.   0.16 mi - Minneapolis N - S Simulcast              (Hennepin)
 3.   4.71 mi - Hennepin Co. East Simulcast              (Hennepin)
 ...
```

## Using in Your Own Scripts

You can import tower_witch as a module:

```python
from tower_witch import load_towers_from_csv, find_nearest_tower, get_gps_position

# Load towers
towers = load_towers_from_csv('trs_sites_3508.csv')

# Get GPS position
gps = get_gps_position('file')
if gps:
    lat, lon, alt, fix = gps
    
    # Find nearest tower
    nearest = find_nearest_tower(lat, lon, towers, unit='mi')
    print(f"Nearest: {nearest['description']} at {nearest['distance']:.2f} miles")
```

## Troubleshooting

### gpsd not working
```bash
# Check if gpsd is running
systemctl status gpsd

# Check for GPS data
gpspipe -w -n 5

# Restart gpsd
sudo systemctl restart gpsd
```

### No GPS device found
```bash
# List USB serial devices
ls -l /dev/ttyUSB* /dev/ttyACM*

# Check dmesg for GPS device
dmesg | grep -i gps
dmesg | grep -i tty
```

### Permission denied on GPS device
```bash
# Add your user to dialout group
sudo usermod -a -G dialout $USER

# Log out and back in for changes to take effect
```

## Requirements

- Python 3.6+
- For gpsd: `gpsd`, `gpsd-clients` packages
- For NMEA serial: `pyserial` (pip install pyserial)
- CSV file with tower data (included: trs_sites_3508.csv)
