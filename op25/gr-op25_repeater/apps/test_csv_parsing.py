#!/usr/bin/env python3
"""
Test script to verify CSV parsing for TowerWitch
"""
import csv
import os

def test_csv_parsing():
    csv_filepath = "trs_sites_3508.csv"
    
    if not os.path.exists(csv_filepath):
        print(f"❌ CSV file not found: {csv_filepath}")
        return
    
    print(f"✓ Testing CSV file: {csv_filepath}")
    
    with open(csv_filepath, "r", encoding="utf-8") as file:
        # Read raw CSV data
        csv_reader = csv.reader(file)
        headers = next(csv_reader)  # Get headers
        print(f"Total columns: {len(headers)}")
        
        count = 0
        for row in csv_reader:
            count += 1
            if count <= 3:  # Show first 3 rows as examples
                print(f"\n--- Row {count} ---")
                print(f"Description: {row[4]}")  # Description is column 4
                print(f"County: {row[5]}")      # County Name is column 5
                print(f"NAC: {row[3]}")         # Site NAC is column 3
                print(f"Lat/Lon: {row[6]}, {row[7]}")  # Lat/Lon are columns 6,7
                
                # Extract all frequencies from columns 9 onwards (starting with "Frequencies")
                frequencies = []
                control_frequencies = []
                
                for i in range(9, len(row)):  # Start from column 9 (Frequencies)
                    value = row[i].strip() if i < len(row) and row[i] else ""
                    if value:
                        frequencies.append(value)
                        if value.endswith("c"):
                            control_frequencies.append(value.replace("c", ""))
                
                print(f"Total frequencies: {len(frequencies)}")
                print(f"Control frequencies: {control_frequencies}")
                print(f"First 10 frequencies: {frequencies[:10]}")
        
        print(f"\n✓ Total sites in CSV: {count}")

if __name__ == "__main__":
    test_csv_parsing()