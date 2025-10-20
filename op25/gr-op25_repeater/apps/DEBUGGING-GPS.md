# Tower Witch GPS Debugging Guide

## Quick Start

### 1. Start gpsd with your GPS device
```bash
./start_gpsd.sh
# Or manually:
sudo gpsd /dev/ttyACM0 -n -N -D 2
```

### 2. Run tower_witch with debug enabled
```bash
# With real GPS
python3 tower_witch.py --debug

# Or with manual coordinates for testing
python3 tower_witch.py --lat 44.9778 --lon -93.2650 --debug
```

### 3. Check the log file
```bash
tail -f tower_witch.log
# Or view all:
cat tower_witch.log
```

## Command Line Options

```
--debug              Enable debug output to console and detailed log file
--log-file FILE      Specify log file path (default: tower_witch.log)
--timeout SECONDS    GPS timeout in seconds (default: 10)
--lat LAT            Manual latitude for testing
--lon LON            Manual longitude for testing
--unit {km,mi,nm}    Distance unit (default: mi)
--range RANGE        Search range (default: 30)
--csv FILE           Tower CSV file (default: trs_sites_3508.csv)
```

## Troubleshooting

### Check if GPS device is connected
```bash
lsusb | grep -i ublox
# Should show: Bus 003 Device 004: ID 1546:01a7 U-Blox AG [u-blox 7]

ls -la /dev/ttyACM0
# Should show the device
```

### Check if you have permissions
```bash
groups | grep dialout
# If not in dialout group:
sudo usermod -a -G dialout $USER
# Then log out and back in
```

### Test GPS directly
```bash
# Read raw GPS data
cat /dev/ttyACM0

# Read JSON GPS data from gpsd
gpspipe -w -n 10

# Look for TPV messages with lat and lon
```

### Common Issues

**"gpspipe not found"**
```bash
sudo apt-get install gpsd-clients
```

**"Cannot connect to gpsd"**
```bash
# Make sure gpsd is running
sudo systemctl status gpsd

# Or start manually
sudo gpsd /dev/ttyACM0 -n -N
```

**"No fix" or mode=0/1**
- GPS needs clear view of sky
- Wait 30-60 seconds for initial fix
- Check antenna connection
- Move near window or outside

**"Permission denied on /dev/ttyACM0"**
```bash
sudo usermod -a -G dialout $USER
# Log out and back in
```

## Debug Log Analysis

The log file (`tower_witch.log`) contains detailed information:

- **GPS messages received** - Each JSON message from gpsd
- **Parse attempts** - Shows what data was found in each message  
- **Fix status** - Mode 0/1=no fix, 2=2D, 3=3D
- **Errors and warnings** - Connection issues, timeouts, etc.

Look for patterns like:
```
INFO: Got position: lat=44.977800, lon=-93.265000, alt=265.5, mode=3
INFO: ✓ Valid GPS fix obtained (mode 3)
```

Or problems like:
```
WARNING: GPS position available but no fix (mode 1)
ERROR: No GPS position obtained after 10 messages
```

## Example Sessions

### Normal operation with GPS
```bash
$ python3 tower_witch.py --debug
INFO: Tower Witch started at 2025-10-18 19:43:01
✓ Loaded 290 towers from trs_sites_3508.csv

=== Getting GPS Position ===
🛰️  Reading from GPS device via gpsd...
INFO: Waiting up to 10s for GPS fix...
INFO: gpsd version: 3.25
INFO: GPS device: /dev/ttyACM0 - u-blox
INFO: Got position: lat=44.977800, lon=-93.265000, alt=265.5, mode=3
INFO: ✓ Valid GPS fix obtained (mode 3)
✓ GPS Position: 44.977800, -93.265000
  Altitude: 265.5 m
  Fix Quality: 3D fix

=== Using miles ===
Nearest tower:
Tower: Minneapolis City Center Simulcast
...
```

### Testing with manual coordinates
```bash
$ python3 tower_witch.py --lat 44.9778 --lon -93.2650 --range 5
✓ Loaded 290 towers from trs_sites_3508.csv

=== Getting GPS Position ===
📍 Using manual coordinates (testing mode)
✓ GPS Position: 44.977800, -93.265000

Found 3 towers within 5.0 mi
...
```

### Troubleshooting mode
```bash
$ python3 tower_witch.py --debug --timeout 30
# Longer timeout, full debug output
# Check tower_witch.log for details
```

## Integration with OP25

Once GPS is working, you can integrate tower_witch into your OP25 workflow:

```python
from tower_witch import get_gps_position_gpsd, find_nearest_tower, load_towers_from_csv

# In your OP25 script:
towers = load_towers_from_csv('trs_sites_3508.csv')
gps = get_gps_position_gpsd(timeout=10)

if gps:
    lat, lon, alt, mode = gps
    nearest = find_nearest_tower(lat, lon, towers, unit='mi')
    print(f"Nearest tower: {nearest['description']} at {nearest['distance']:.2f} miles")
    print(f"Frequencies: {nearest['frequencies']}")
```

## Files

- `tower_witch.py` - Main script
- `tower_witch.log` - Debug log file (auto-created)
- `trs_sites_3508.csv` - Tower database
- `start_gpsd.sh` - Helper to start gpsd
- `README-tower-witch.md` - Full documentation

## Getting Help

1. Enable debug mode: `--debug`
2. Check log file: `tail -f tower_witch.log`
3. Test GPS directly: `gpspipe -w -n 10`
4. Verify device: `lsusb | grep -i ublox`
5. Check permissions: `groups | grep dialout`
