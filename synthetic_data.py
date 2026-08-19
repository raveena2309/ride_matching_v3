"""
synthetic_data.py
====================
Generates a synthetic driver fleet and passenger set scattered realistically
around a real geocoded center point, plus a zone grid for repositioning.

Key design choice: locations are synthetic (we don't have real fleet data),
but they're generated RELATIVE TO a real geocoded location, so the whole
simulation stays grounded in an actual place rather than floating in
arbitrary coordinate space.
"""

import random
import math
from entities import Driver, Passenger, Zone

# Rough conversion: 1 degree latitude ~= 111 km (good enough for city-scale simulation)
KM_PER_DEGREE = 111.0


# ------------------------------------------------------------------
# HELPER: random point within a radius (proper polar scatter, not just
# adding a random number to lat/lon, so the radius corresponds to a real km value)
# ------------------------------------------------------------------
def _random_offset_km(radius_km):
    """Returns a random (delta_lat, delta_lon) within radius_km of a center point."""
    angle = random.uniform(0, 2 * math.pi)
    distance_km = random.uniform(0, radius_km)

    delta_lat = (distance_km * math.cos(angle)) / KM_PER_DEGREE
    delta_lon = (distance_km * math.sin(angle)) / KM_PER_DEGREE
    return delta_lat, delta_lon


# ------------------------------------------------------------------
# DRIVER GENERATION
# ------------------------------------------------------------------
def generate_synthetic_drivers(n, center_lat, center_lon, radius_km=4.0,
                                seed=None, capacity_range=(2, 4), idle_range=(0, 10)):
    """
    Generates n drivers scattered within radius_km of (center_lat, center_lon).
    seed: pass an int for reproducible generation (important for multi-seed evaluation).
    """
    if seed is not None:
        random.seed(seed)

    drivers = []
    for i in range(1, n + 1):
        d_lat, d_lon = _random_offset_km(radius_km)
        x = center_lat + d_lat
        y = center_lon + d_lon
        idle_time = random.randint(*idle_range)
        capacity = random.randint(*capacity_range)
        drivers.append(Driver(id=i, x=x, y=y, idle_time=idle_time, capacity=capacity))

    return drivers


# ------------------------------------------------------------------
# PASSENGER GENERATION (scaled up: many passengers, wide radius)
# ------------------------------------------------------------------
def generate_synthetic_passengers(n, center_lat, center_lon, radius_km=6.0,
                                   dest_radius_km=8.0, seed=None,
                                   wait_range=(0, 15), demand_range=(1, 5),
                                   cancel_range=(1, 5)):
    """
    Generates n passengers scattered within radius_km of the center point,
    each with a randomly generated destination within dest_radius_km of
    their own pickup point (simulating varied trip lengths).
    """
    if seed is not None:
        random.seed(seed)

    passengers = []
    for i in range(1, n + 1):
        # pickup location, scattered around the city center
        p_lat_off, p_lon_off = _random_offset_km(radius_km)
        pickup_lat = center_lat + p_lat_off
        pickup_lon = center_lon + p_lon_off

        # destination, scattered around the pickup point (own trip radius)
        d_lat_off, d_lon_off = _random_offset_km(dest_radius_km)
        dest_lat = pickup_lat + d_lat_off
        dest_lon = pickup_lon + d_lon_off

        wait = random.randint(*wait_range)
        demand = random.randint(*demand_range)
        cancel_risk = random.randint(*cancel_range)

        passengers.append(Passenger(
            id=100 + i, x=pickup_lat, y=pickup_lon,
            dest=(dest_lat, dest_lon), wait=wait,
            demand=demand, cancel_risk=cancel_risk
        ))

    return passengers


# ------------------------------------------------------------------
# SINGLE PASSENGER FROM REAL USER INPUT (source/destination typed by user)
# ------------------------------------------------------------------
def build_passenger_from_input(source_coords, dest_coords, passenger_id=1,
                                wait=0, demand=1, cancel_risk=1):
    """
    Builds a single Passenger object from real geocoded source/destination
    coordinates (output of geocoding.geocode()). Use this for the actual
    real-time single-request flow; use generate_synthetic_passengers() for
    bulk simulation/evaluation runs.
    """
    lat, lon = source_coords
    dest = dest_coords  # already a (lat, lon) tuple
    return Passenger(id=passenger_id, x=lat, y=lon, dest=dest,
                      wait=wait, demand=demand, cancel_risk=cancel_risk)


# ------------------------------------------------------------------
# ZONE GENERATION (grid of zones covering the service area, used by
# the repositioning module later)
# ------------------------------------------------------------------
def generate_zones(center_lat, center_lon, grid_size=3, spacing_km=2.0):
    """
    Generates a grid_size x grid_size set of Zones centered on
    (center_lat, center_lon), spaced spacing_km apart.
    """
    zones = []
    zone_id = 1
    offset = (grid_size - 1) / 2.0

    for i in range(grid_size):
        for j in range(grid_size):
            d_lat = ((i - offset) * spacing_km) / KM_PER_DEGREE
            d_lon = ((j - offset) * spacing_km) / KM_PER_DEGREE
            zones.append(Zone(id=zone_id, center_x=center_lat + d_lat, center_y=center_lon + d_lon))
            zone_id += 1

    return zones


# ------------------------------------------------------------------
# QUICK TEST — scaled-up scenario (more passengers, wider radius)
# ------------------------------------------------------------------
if __name__ == "__main__":
    from geocoding import geocode
    from distance_engine import get_distance_km

    source_text = "Sitabuldi, Nagpur"
    source_coords = geocode(source_text)
    print(f"Center point '{source_text}' -> {source_coords}")

    # Scaled-up scenario: more drivers, more passengers, wider radius
    drivers = generate_synthetic_drivers(
        n=50, center_lat=source_coords[0], center_lon=source_coords[1],
        radius_km=8.0, seed=42
    )
    passengers = generate_synthetic_passengers(
        n=80, center_lat=source_coords[0], center_lon=source_coords[1],
        radius_km=8.0, dest_radius_km=10.0, seed=42
    )

    print(f"\nGenerated {len(drivers)} drivers within 8km radius:")
    for d in drivers[:5]:
        print(f"  {d}")
    print("  ...")

    print(f"\nGenerated {len(passengers)} passengers within 8km radius:")
    for p in passengers[:5]:
        print(f"  {p}")
    print("  ...")

    # Sanity check: confirm the scatter actually spans a real distance range
    farthest_driver = max(
        get_distance_km(source_coords[0], source_coords[1], d.x, d.y, mode="haversine")
        for d in drivers
    )
    farthest_passenger = max(
        get_distance_km(source_coords[0], source_coords[1], p.x, p.y, mode="haversine")
        for p in passengers
    )
    print(f"\nFarthest driver from center: {farthest_driver:.2f} km (should be <= 8.0 km)")
    print(f"Farthest passenger from center: {farthest_passenger:.2f} km (should be <= 8.0 km)")

    zones = generate_zones(center_lat=source_coords[0], center_lon=source_coords[1],
                            grid_size=4, spacing_km=3.0)
    print(f"\nGenerated {len(zones)} zones covering the wider area")

    # Also demonstrate the single-real-input passenger builder
    dest_text = "VNIT Nagpur"
    dest_coords = geocode(dest_text)
    real_passenger = build_passenger_from_input(source_coords, dest_coords, wait=5, demand=3, cancel_risk=1)
    print(f"\nSingle real-input passenger (Sitabuldi -> VNIT Nagpur): {real_passenger}")