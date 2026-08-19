"""
matching_engine.py
=====================
The real two-stage adaptive matching engine (replaces the minimal matcher
used only for calibration speed in Phase 6).

Fixes vs the original paper:
  - Search radius EXPANDS when drivers are scarce (was inverted in v1)
  - All scoring is normalized + calibrated (Phase 5/6), not raw ad-hoc sums
  - Passengers processed in priority order via a proper priority queue
"""

import heapq
import config
from scoring import match_score, priority_score, can_pool
from distance_engine import get_distance_km


# ------------------------------------------------------------------
# ADAPTIVE SEARCH RADIUS
# FIX: expands under scarcity (requests > available drivers), instead of
# shrinking as the original paper's Eq. 6-7 incorrectly specified.
# ------------------------------------------------------------------
def adaptive_radius(num_requests, num_available_drivers, base_radius=None):
    if base_radius is None:
        base_radius = config.BASE_SEARCH_RADIUS_KM

    if num_available_drivers == 0:
        return base_radius * 2.0  # no drivers at all -> search as wide as possible

    ratio = num_requests / num_available_drivers

    if ratio > 1:
        # Demand exceeds supply -> WIDEN the search to avoid rejections
        return base_radius * min(2.0, 1 + 0.3 * (ratio - 1))
    else:
        # Supply exceeds demand -> can afford a tighter, more efficient search
        return base_radius * max(0.6, 1 - 0.2 * (1 - ratio))


# ------------------------------------------------------------------
# TWO-STAGE DRIVER SEARCH
# Stage 1: distance-threshold filter. Stage 2: K-nearest selection.
# ------------------------------------------------------------------
def two_stage_driver_search(drivers, passenger, radius_km, k=None, distance_mode="haversine"):
    if k is None:
        k = config.K_NEAREST

    candidates = []
    for d in drivers:
        if len(d.current_passengers) >= d.capacity:
            continue  # driver is full
        dist_km = get_distance_km(d.x, d.y, passenger.x, passenger.y, mode=distance_mode)
        if dist_km <= radius_km:
            candidates.append((dist_km, d))

    candidates.sort(key=lambda t: t[0])
    return [d for _, d in candidates[:k]]


# ------------------------------------------------------------------
# MAIN MATCHING ENGINE
# ------------------------------------------------------------------
def match(drivers, passengers, distance_mode="haversine", verbose=False):
    pq = [(-priority_score(p), p.id, p) for p in passengers]
    heapq.heapify(pq)

    matches = []

    while pq:
        _, _, passenger = heapq.heappop(pq)

        num_available = sum(1 for d in drivers if len(d.current_passengers) < d.capacity)
        num_remaining_requests = len(pq) + 1
        radius = adaptive_radius(num_remaining_requests, num_available)

        candidates = two_stage_driver_search(drivers, passenger, radius, distance_mode=distance_mode)

        best_driver, best_score = None, float("inf")
        rejected_for_pooling = 0

        for d in candidates:
            if d.current_passengers:
                if not all(can_pool(existing, passenger, distance_mode) for existing in d.current_passengers):
                    rejected_for_pooling += 1
                    continue

            score = match_score(d, passenger, distance_mode=distance_mode)
            if score < best_score:
                best_score = score
                best_driver = d

        if best_driver:
            best_driver.current_passengers.append(passenger)
            matches.append((best_driver.id, passenger.id, best_score))
            if verbose:
                print(f"  Matched Driver {best_driver.id} -> Passenger {passenger.id} "
                      f"(score={best_score:.3f}, radius_used={radius:.2f}km)")
        else:
            if verbose:
                if len(candidates) == 0:
                    print(f"  UNMATCHED Passenger {passenger.id}: no driver within {radius:.2f}km radius")
                else:
                    print(f"  UNMATCHED Passenger {passenger.id}: {len(candidates)} driver(s) in range, "
                          f"but all {rejected_for_pooling} rejected on pooling compatibility")

    return matches


# ------------------------------------------------------------------
# QUICK TEST
# ------------------------------------------------------------------
if __name__ == "__main__":
    from geocoding import geocode
    from synthetic_data import generate_synthetic_drivers, generate_synthetic_passengers

    source_coords = geocode("Sitabuldi, Nagpur")

    # Reduced driver count relative to passengers -> forces scarcity,
    # which should trigger pooling (unlike the oversupplied 30-driver case)
    drivers = generate_synthetic_drivers(n=12, center_lat=source_coords[0],
                                          center_lon=source_coords[1], radius_km=8.0, seed=42)
    passengers = generate_synthetic_passengers(n=40, center_lat=source_coords[0],
                                                center_lon=source_coords[1], radius_km=8.0,
                                                dest_radius_km=10.0, seed=42)

    print(f"Running matching engine: {len(drivers)} drivers, {len(passengers)} passengers\n")
    matches = match(drivers, passengers, verbose=True)

    print(f"\nTotal matches: {len(matches)} / {len(passengers)} passengers")
    print(f"Success rate: {len(matches) / len(passengers):.2%}")

    used_drivers = sum(1 for d in drivers if d.current_passengers)
    print(f"Drivers used: {used_drivers} / {len(drivers)} (utilization: {used_drivers/len(drivers):.2%})")

    pooled = sum(1 for d in drivers if len(d.current_passengers) > 1)
    print(f"Drivers with pooled rides: {pooled}")

    # Show capacity of each used driver to see multi-passenger assignments
    print("\nDriver load breakdown:")
    for d in drivers:
        if d.current_passengers:
            print(f"  Driver {d.id} (capacity {d.capacity}): {len(d.current_passengers)} passenger(s)")
            
                # Diagnostic: check actual similarity values between passenger pairs
    from scoring import route_similarity
    print("\nSample route similarities (for tuning POOLING_DETOUR_TOLERANCE_KM):")
    sims = []
    for i in range(len(passengers)):
        for j in range(i + 1, len(passengers)):
            sim = route_similarity(passengers[i], passengers[j])
            sims.append(sim)

    import statistics
    print(f"  Total pairs checked: {len(sims)}")
    print(f"  Mean similarity: {statistics.mean(sims):.3f}")
    print(f"  Max similarity: {max(sims):.3f}")
    print(f"  Pairs above 0.5 threshold: {sum(1 for s in sims if s > 0.5)}")
    print(f"  Pairs above 0.3 threshold: {sum(1 for s in sims if s > 0.3)}")
    print(f"  Pairs above 0.1 threshold: {sum(1 for s in sims if s > 0.1)}")