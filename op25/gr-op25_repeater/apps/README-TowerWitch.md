# TowerWitch GUI - GPS Tower Locator

## Overview

TowerWitch is a PyQt5 GUI application that displays real-time GPS information and automatically finds the nearest P25 radio towers. It's the graphical companion to the command-line `tower_witch.py` tool.

## Features

### Real-Time GPS Display
- **Coordinates**: Latitude/Longitude with 6 decimal precision
- **Elevation**: Displayed in both meters and feet
- **Speed**: Shown in m/s, mph, and knots
- **Live Updates**: Continuously updates as you move

### Multiple Grid Systems
- **UTM** (Universal Transverse Mercator): Zone, Easting, Northing
- **Maidenhead**: Ham radio grid locator system
- **MGRS** (Military Grid Reference System): Zone, Grid Square, Coordinates

### Tower Information
- **Distance**: Shows distance to nearest towers in miles
- **Bearing**: Displays compass direction to each tower
- **Control Frequencies**: Lists control channels for P25 scanning
- **Auto-Sort**: Towers automatically sorted by distance

## Recent Updates (October 2025)

### Migrated from python-gps to gpspipe

**Why the change?**
- More reliable GPS data acquisition
- Better error handling
- Consistent with `tower_witch.py` implementation
- No dependency on python-gps library issues

**Technical Details:**
- Now uses `gpspipe -w` to read JSON GPS data
- Runs in background QThread for non-blocking updates
- Handles TPV (Time-Position-Velocity) messages
- Graceful degradation if GPS unavailable

## Requirements

### System Packages
```bash
# GPS daemon and tools
sudo apt-get install gpsd gpsd-clients

# PyQt5 dependencies (if not using venv)
sudo apt-get install python3-pyqt5
```

### Python Packages
```bash
# Using virtual environment (recommended)
source /home/pc/op25/op25/gr-op25_repeater/apps/.venv/bin/activate
pip install PyQt5 utm maidenhead mgrs packaging
```

Or install to system Python:
```bash
pip3 install PyQt5 utm maidenhead mgrs packaging
```

## Configuration

### GPS Setup
1. **Connect GPS device** (e.g., U-Blox 7 on /dev/ttyACM0)
2. **Configure gpsd** in `/etc/default/gpsd`:
   ```
   DEVICES="/dev/ttyACM0"
   GPSD_OPTIONS="-n -b"
   START_DAEMON="true"
   USBAUTO="true"
   ```
3. **Start gpsd**:
   ```bash
   sudo systemctl restart gpsd
   ```
4. **Verify GPS**:
   ```bash
   cgps        # Visual GPS status
   gpsmon      # Detailed GPS monitor
   ```

### Tower Data
- Uses `crow_wing_sites_and_frequencies.json` in the same directory
- Fallback: Can be adapted for other JSON formats
- Expected format:
  ```json
  [
    {
      "Description": "Tower Name",
      "County Name": "County",
      "Lat": 46.123456,
      "Lon": -94.123456,
      "Frequencies": ["852.975000c", "858.262500c", ...]
    }
  ]
  ```
- Frequencies ending in 'c' are control channels

## Running TowerWitch

### Using Virtual Environment (Recommended)
```bash
cd /home/pc/op25/op25/gr-op25_repeater/apps
source .venv/bin/activate
python TowerWitch.py
```

### Direct Execution
```bash
/home/pc/op25/op25/gr-op25_repeater/apps/.venv/bin/python TowerWitch.py
```

### Background Mode
```bash
/home/pc/op25/op25/gr-op25_repeater/apps/.venv/bin/python TowerWitch.py &
```

## Testing

### Test GPS Connectivity
```bash
python test_towerwitch_gps.py
```

This will verify:
- gpspipe is accessible
- GPS has valid fix
- Coordinates are being received
- Speed data is available

### Expected Output
```
✓ GPS Fix Acquired!
  Latitude:  46.598475
  Longitude: -94.315385
  Altitude:  402.9 m
  Speed:     0.12 m/s (0.27 mph)
  Fix Mode:  3 (3D)
```

## Comparison: TowerWitch.py vs tower_witch.py

| Feature | TowerWitch.py (GUI) | tower_witch.py (CLI) |
|---------|---------------------|----------------------|
| **Interface** | PyQt5 GUI | Command-line |
| **Updates** | Real-time continuous | One-shot execution |
| **GPS Method** | gpspipe (reliable) | gpspipe (reliable) |
| **Data Format** | JSON | CSV (trs_sites_3508.csv) |
| **Grid Systems** | UTM, MGRS, Maidenhead | Lat/Lon only |
| **Bearing** | Yes ✓ | No ✗ |
| **Distance Units** | Miles only | mi/km/nm selectable |
| **Tower Display** | Top 5 in table | Configurable range |
| **Best For** | Desktop monitoring | Headless/automation |
| **OP25 Integration** | Visual reference | Direct integration |

## Use Cases

### Desktop Monitoring
- Run TowerWitch.py for visual GPS tracking
- See nearest towers update in real-time
- Useful for mobile operations

### Scanner Setup
- Identify nearest tower and control frequencies
- Use bearing information for antenna pointing
- Reference grid systems for location reporting

### Ham Radio
- Maidenhead grid for QSO reporting
- UTM/MGRS for field operations
- Speed tracking for mobile operations

## Troubleshooting

### GPS Not Working
```bash
# Check GPS device
lsusb | grep -i gps
ls -la /dev/tty{USB,ACM}*

# Check gpsd status
sudo systemctl status gpsd

# Test GPS directly
gpspipe -w -n 5

# Restart gpsd
sudo systemctl restart gpsd
sudo killall gpsd
sudo gpsd /dev/ttyACM0 -n -N -D 2
```

### No Tower Data
- Verify `crow_wing_sites_and_frequencies.json` exists
- Check JSON format is valid
- Look for console error messages

### GUI Won't Start
```bash
# Check if display is available
echo $DISPLAY

# Test PyQt5
python3 -c "from PyQt5.QtWidgets import QApplication; print('OK')"

# Check virtual environment
source .venv/bin/activate
pip list | grep PyQt5
```

## Development Notes

### GPS Worker Thread
- Runs continuously in background
- Emits signals on GPS updates (lat, lon, alt, speed)
- Non-blocking for GUI responsiveness
- Clean shutdown on window close

### Distance Calculation
- Uses Haversine formula for great-circle distance
- Accurate for distances up to several hundred miles
- Results in statute miles

### Bearing Calculation
- True bearing (not magnetic)
- Range: 0-360 degrees (0=North, 90=East, 180=South, 270=West)

## Future Enhancements

### Possible Features
- [ ] Selectable distance units (km, nm)
- [ ] Configurable tower count (not fixed to 5)
- [ ] CSV support (trs_sites_3508.csv compatibility)
- [ ] Frequency tuning integration with OP25
- [ ] Tower range circles on map
- [ ] Path loss calculations
- [ ] Magnetic declination for bearing
- [ ] Save/load favorite locations

## Credits

- Original concept: KC9SP (6 months ago)
- Updated implementation: October 2025
- GPS integration: Migrated to gpspipe method
- Uses Minnesota ARMER P25 tower database

## License

Part of the OP25 project. See main repository for license details.

## See Also

- `tower_witch.py` - Command-line version
- `README-tower-witch.md` - CLI tool documentation
- `DEBUGGING-GPS.md` - GPS troubleshooting guide
- `trs_sites_3508.csv` - Full Minnesota tower database
