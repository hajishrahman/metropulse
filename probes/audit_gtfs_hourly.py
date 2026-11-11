
import csv
from pathlib import Path
from collections import defaultdict

RAW = Path("data/raw")

def read_csv(name):
    with open(RAW / name, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

trips = read_csv("trips.txt")
stop_times = read_csv("stop_times.txt")

stops_by_trip = defaultdict(list)

for row in stop_times:
    stops_by_trip[row["trip_id"]].append(row)

for trip_id in stops_by_trip:
    stops_by_trip[trip_id].sort(
        key=lambda x: int(x["stop_sequence"])
    )

print("\n========== PARTIAL TRIP AUDIT ==========\n")

count = 0

for trip in trips:
    if trip["service_id"] != "WK":
        continue

    trip_id = trip["trip_id"]
    records = stops_by_trip.get(trip_id, [])

    if not records:
        continue

    first = records[0]
    last = records[-1]

    hour = int(first["departure_time"].split(":")[0])

    if not 6 <= hour < 23:
        continue

    complete = (
        (first["stop_id"] == "ALVA" and last["stop_id"] == "TPHT")
        or
        (first["stop_id"] == "TPHT" and last["stop_id"] == "ALVA")
    )

    if not complete:
        count += 1
        print(
            f"Trip: {trip_id} | "
            f"Direction ID: {trip.get('direction_id')} | "
            f"Departure: {first['departure_time']} | "
            f"First: {first['stop_id']} | "
            f"Last: {last['stop_id']} | "
            f"Stops: {len(records)}"
        )

print(f"\nTotal partial trips: {count}")
