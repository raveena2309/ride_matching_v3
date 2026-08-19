"""
repositioning.py
==================
Demand-aware driver repositioning (Algorithm 2 from the original paper),
FIXED to check travel-time feasibility before moving a driver - this
prevents the "herding/oscillation" risk the reviewer flagged (Q5), where
a naive rule blindly sends drivers toward demand spikes they can't
realistically reach in time.
"""

import config
from distance_engine import get_distance_km


def _nearest_zone(x, y, zones):
    return min(zones, key=lambda z: get_distance_km(x, y, z.center[0], z.center[1], mode="haversine"))


def compute_zone_demand_scores(drivers, passengers, zones):
    """
    Returns {zone_id: demand_score} where demand_score = requests / max(1, drivers)
    for each zone - higher score means more request pressure relative to supply.
    """
    zone_requests = {z.id: 0 for z in zones}
    zone_drivers = {z.id: 0 for z in zones}

    for p in passengers:
        zone_requests[_nearest_zone(p.x, p.y, zones).id] += 1

    idle_drivers = [d for d in drivers if not d.current_passengers]
    for d in idle_drivers:
        zone_drivers[_nearest_zone(d.x, d.y, zones).id] += 1

    return {
        z.id: zone_requests[z.id] / max(1, zone_drivers[z.id])
        for z in zones
    }


def demand_aware_repositioning(drivers, passengers, zones,
                                max_travel_min=None, avg_speed_kmph=None,
                                distance_mode="haversine", verbose=False):
    """
    Moves idle drivers toward high-demand zones, but ONLY if they can
    realistically arrive within max_travel_min. Prevents oscillation/
    herding compared to a naive "always move nearest idle driver" rule.

    Returns a list of (driver_id, zone_id, travel_min) for moves made.
    """
    if max_travel_min is None:
        max_travel_min = config.MAX_REPOSITION_TRAVEL_MIN
    if avg_speed_kmph is None:
        avg_speed_kmph = config.AVG_CITY_SPEED_KMPH

    demand_scores = compute_zone_demand_scores(drivers, passengers, zones)
    ranked_zones = sorted(zones, key=lambda z: demand_scores[z.id], reverse=True)

    idle_drivers = [d for d in drivers if not d.current_passengers]
    moved_ids = set()
    moves = []

    for z in ranked_zones:
        if demand_scores[z.id] <= 1.0:
            # This zone isn't actually short on drivers relative to demand -
            # no repositioning needed here.
            continue

        remaining = [d for d in idle_drivers if d.id not in moved_ids]
        if not remaining:
            break

        nearest_driver = min(
            remaining,
            key=lambda d: get_distance_km(d.x, d.y, z.center[0], z.center[1], mode=distance_mode)
        )
        dist_km = get_distance_km(nearest_driver.x, nearest_driver.y,
                                   z.center[0], z.center[1], mode=distance_mode)
        travel_min = (dist_km / avg_speed_kmph) * 60

        if travel_min <= max_travel_min:
            nearest_driver.x, nearest_driver.y = z.center
            moved_ids.add(nearest_driver.id)
            moves.append((nearest_driver.id, z.id, round(travel_min, 1)))
            if verbose:
                print(f"  Repositioned Driver {nearest_driver.id} -> Zone {z.id} "
                      f"(demand_score={demand_scores[z.id]:.2f}, travel={travel_min:.1f}min)")
        else:
            if verbose:
                print(f"  SKIPPED repositioning to Zone {z.id}: nearest driver "
                      f"({nearest_driver.id}) would take {travel_min:.1f}min "
                      f"(exceeds {max_travel_min}min limit)")

    return moves


# ------------------------------------------------------------------
# QUICK TEST
# ------------------------------------------------------------------
if __name__ == "__main__":
    from geocoding import geocode
    from synthetic_data import generate_synthetic_drivers, generate_synthetic_passengers, generate_zones
    from matching_engine import match

    source_coords = geocode("Sitabuldi, Nagpur")

    drivers = generate_synthetic_drivers(n=30, center_lat=source_coords[0],
                                          center_lon=source_coords[1], radius_km=8.0, seed=42)
    passengers = generate_synthetic_passengers(n=20, center_lat=source_coords[0],
                                                center_lon=source_coords[1], radius_km=8.0,
                                                dest_radius_km=10.0, seed=42)
    zones = generate_zones(center_lat=source_coords[0], center_lon=source_coords[1],
                            grid_size=4, spacing_km=5.0)  # widened to stress-test travel feasibility

    print(f"Running matching first: {len(drivers)} drivers, {len(passengers)} passengers")
    matches = match(drivers, passengers)
    unmatched = [p for p in passengers if p.id not in [m[1] for m in matches]]
    print(f"Matched: {len(matches)}, Unmatched: {len(unmatched)}\n")

    print("Running demand-aware repositioning for idle drivers...")
    print("(Using ALL passenger requests as the zone demand signal, not just")
    print(" unmatched ones - matches the original paper's Algorithm 2 design,")
    print(" since repositioning anticipates future demand, not just past misses.)\n")

    idle_before = sum(1 for d in drivers if not d.current_passengers)
    print(f"Idle drivers before repositioning: {idle_before}\n")

    # Use a tighter feasibility window here to also demonstrate the SKIP case
    moves = demand_aware_repositioning(drivers, passengers, zones,
                                        max_travel_min=15, verbose=True)

    print(f"\nTotal repositioning moves made: {len(moves)}")