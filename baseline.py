"""
baseline.py
=============
Hungarian-algorithm (linear sum assignment) optimization baseline.

Addresses the reviewer's repeated complaint that FCFS/Nearest/Static-Radius
are all weak, non-optimization baselines. This finds the mathematically
optimal one-to-one driver-passenger assignment (minimizing total match
score), giving a real upper bound to compare our adaptive heuristic against.

Note: one-to-one only (no pooling) - a fair, stated limitation when
comparing against our system's pooled results.
"""

import numpy as np
from scipy.optimize import linear_sum_assignment
from scoring import match_score

INFEASIBLE_COST = 1e6  # large cost representing "this pair cannot be assigned"


import config

def hungarian_baseline(drivers, passengers, distance_mode="haversine", max_distance_km=None):
    """
    Returns a list of (driver_id, passenger_id, cost) for the optimal
    one-to-one assignment, respecting the same max_distance_km feasibility
    limit our adaptive engine implicitly applies via its search radius -
    this makes the comparison fair (same feasible pair set for both).
    """
    if max_distance_km is None:
        max_distance_km = config.MAX_DISTANCE_KM

    n_d, n_p = len(drivers), len(passengers)
    cost_matrix = np.full((n_d, n_p), INFEASIBLE_COST)

    from distance_engine import get_distance_km

    for i, d in enumerate(drivers):
        for j, p in enumerate(passengers):
            dist_km = get_distance_km(d.x, d.y, p.x, p.y, mode=distance_mode)
            if dist_km <= max_distance_km:
                cost_matrix[i, j] = match_score(d, p, distance_mode=distance_mode)

    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    assignments = []
    total_cost = 0.0
    for r, c in zip(row_ind, col_ind):
        cost = cost_matrix[r, c]
        if cost < INFEASIBLE_COST:
            assignments.append((drivers[r].id, passengers[c].id, round(cost, 3)))
            total_cost += cost

    return assignments, total_cost


# ------------------------------------------------------------------
# QUICK TEST + COMPARISON AGAINST OUR ADAPTIVE MATCHING ENGINE
# ------------------------------------------------------------------
if __name__ == "__main__":
    from geocoding import geocode
    from synthetic_data import generate_synthetic_drivers, generate_synthetic_passengers
    from matching_engine import match

    source_coords = geocode("Sitabuldi, Nagpur")

    # Fresh driver/passenger sets for a fair side-by-side (same seed = same data)
    drivers_hungarian = generate_synthetic_drivers(n=20, center_lat=source_coords[0],
                                                     center_lon=source_coords[1], radius_km=8.0, seed=42)
    passengers_hungarian = generate_synthetic_passengers(n=20, center_lat=source_coords[0],
                                                           center_lon=source_coords[1], radius_km=8.0,
                                                           dest_radius_km=10.0, seed=42)

    drivers_ours = generate_synthetic_drivers(n=20, center_lat=source_coords[0],
                                               center_lon=source_coords[1], radius_km=8.0, seed=42)
    passengers_ours = generate_synthetic_passengers(n=20, center_lat=source_coords[0],
                                                      center_lon=source_coords[1], radius_km=8.0,
                                                      dest_radius_km=10.0, seed=42)


    print("=" * 60)
    print("HUNGARIAN ALGORITHM (optimal one-to-one assignment)")
    print("=" * 60)
    hungarian_matches, hungarian_total_cost = hungarian_baseline(drivers_hungarian, passengers_hungarian)
    print(f"Matches: {len(hungarian_matches)} / {len(passengers_hungarian)}")
    print(f"Total assignment cost: {hungarian_total_cost:.3f}")
    print(f"Average cost per match: {hungarian_total_cost / max(1, len(hungarian_matches)):.3f}")

    print("\n" + "=" * 60)
    print("OUR ADAPTIVE MATCHING ENGINE (two-stage, priority-queue based)")
    print("=" * 60)
    our_matches = match(drivers_ours, passengers_ours)
    our_total_cost = sum(score for _, _, score in our_matches)
    print(f"Matches: {len(our_matches)} / {len(passengers_ours)}")
    print(f"Total assignment cost: {our_total_cost:.3f}")
    print(f"Average cost per match: {our_total_cost / max(1, len(our_matches)):.3f}")

    print("\n" + "=" * 60)
    print("COMPARISON (fair: both constrained to the same max distance)")
    print("=" * 60)
    print(f"Hungarian: {len(hungarian_matches)}/{len(passengers_hungarian)} matched, "
          f"avg cost/match = {hungarian_total_cost/max(1,len(hungarian_matches)):.3f}")
    print(f"Ours:      {len(our_matches)}/{len(passengers_ours)} matched, "
          f"avg cost/match = {our_total_cost/max(1,len(our_matches)):.3f}")

    if len(our_matches) < len(hungarian_matches):
        print(f"\nNote: comparing average cost directly is misleading here - Hungarian "
              f"matched {len(hungarian_matches)} (including harder cases), ours matched "
              f"only {len(our_matches)} (likely skipping harder cases), so ours has an "
              f"easier average by comparison. Success rate is the fairer headline metric.")