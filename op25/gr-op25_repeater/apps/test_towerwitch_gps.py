#!/usr/bin/env python3
"""
Quick test script to verify TowerWitch GPS functionality without GUI
"""
import subprocess
import json
import time

def test_gpspipe():
    """Test if gpspipe is working"""
    print("=== Testing gpspipe GPS connectivity ===\n")
    
    try:
        cmd = ['gpspipe', '-w', '-n', '5']
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        print("Waiting for GPS data (5 messages)...\n")
        
        got_fix = False
        message_count = 0
        
        for line in process.stdout:
            message_count += 1
            try:
                data = json.loads(line.strip())
                msg_class = data.get('class', 'UNKNOWN')
                
                if msg_class == 'TPV':
                    lat = data.get('lat')
                    lon = data.get('lon')
                    alt = data.get('alt')
                    speed = data.get('speed', 0.0)
                    mode = data.get('mode', 0)
                    
                    if lat and lon and mode >= 2:
                        print(f"✓ GPS Fix Acquired!")
                        print(f"  Latitude:  {lat:.6f}")
                        print(f"  Longitude: {lon:.6f}")
                        print(f"  Altitude:  {alt:.1f} m" if alt else "  Altitude:  N/A")
                        print(f"  Speed:     {speed:.2f} m/s ({speed * 2.23694:.2f} mph)")
                        print(f"  Fix Mode:  {mode} ({'3D' if mode == 3 else '2D' if mode == 2 else 'No Fix'})")
                        got_fix = True
                        break
                    
            except json.JSONDecodeError:
                continue
        
        process.terminate()
        
        if not got_fix:
            print("⚠️  No GPS fix obtained after 5 messages")
            print("   GPS may still be acquiring satellites...")
            return False
        
        return True
        
    except FileNotFoundError:
        print("❌ Error: gpspipe not found!")
        print("   Install: sudo apt-get install gpsd-clients")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("TowerWitch GPS Test\n")
    print("This tests the GPS connectivity that TowerWitch.py will use.\n")
    
    if test_gpspipe():
        print("\n✓ GPS is working correctly!")
        print("  TowerWitch.py should receive GPS updates automatically.")
    else:
        print("\n⚠️  GPS may need more time to acquire satellites.")
        print("   Try running: cgps")
        print("   or: gpsmon")
