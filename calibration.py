"""
calibration.py
================
Grid search over MATCH_WEIGHTS to find the combination that minimizes
average passenger waiting time, replacing hand-picked constants with a
data-driven, reproducible calibration process.

Uses a minimal greedy matching function here (nearest-by-score, one pass)
just for calibration speed. The full adaptive matching engine (Phase 7)
will be used for final evaluation.
"""

import statistics
import config
from scoring import match_score, priority_score
from synthetic_data import generate_synthetic_drivers, generate_synthetic_passengers
from geocoding import geocode
from distance_engine import get_distance_km


def _minimal_match(drivers, passengers, distance_mode="haversine"):
    """
    A simple greedy matcher: process passengers in priority order, assign
    each to their best-scoring available driver. Used only for calibration
    speed - the real matching_engine.py (Phase 7) adds adaptive radius,
    two-stage search, and pooling constraints on top of this core idea.
    """
    remaining = sorted(passengers, key=priority_score, reverse=True)
    matches = []

    for p in remaining:
        best_driver, best_score = None, float("inf")
        for d in drivers:
            if len(d.current_passengers) >= d.capacity:
                continue
            score = match_score(d, p, distance_mode=distance_mode)
            if score < best_score:
                best_score = score
                best_driver = d
        if best_driver:
            best_driver.current_passengers.append(p)
            matches.append((best_driver.id, p.id, best_score))

    return matches


def _run_single_trial(weights, center_lat, center_lon, seed, n_drivers=30, n_passengers=40):
    """Runs one simulation with a given weight combo and returns the average
    pickup distance across all matches - this DOES depend on which driver
    gets picked, unlike passenger.wait (which is fixed at generation time)."""
    config.MATCH_WEIGHTS = weights

    drivers = generate_synthetic_drivers(n=n_drivers, center_lat=center_lat,
                                          center_lon=center_lon, radius_km=8.0, seed=seed)
    passengers = generate_synthetic_passengers(n=n_passengers, center_lat=center_lat,
                                                center_lon=center_lon, radius_km=8.0,
                                                dest_radius_km=10.0, seed=seed)

    matches = _minimal_match(drivers, passengers, distance_mode="haversine")

    if not matches:
        return float("inf")

    driver_lookup = {d.id: d for d in drivers}
    passenger_lookup = {p.id: p for p in passengers}

    pickup_distances = []
    for driver_id, passenger_id, score in matches:
        d = driver_lookup[driver_id]
        p = passenger_lookup[passenger_id]
        dist_km = get_distance_km(d.x, d.y, p.x, p.y, mode="haversine")
        pickup_distances.append(dist_km)

    return sum(pickup_distances) / len(pickup_distances)


def calibrate_weights(weight_grid, center_lat, center_lon, seeds=5,
                       n_drivers=30, n_passengers=40):
    """
    Tests each weight combo in weight_grid across multiple seeds, returns
    the best combo (lowest mean wait time) and a full results table.
    """
    original_weights = dict(config.MATCH_WEIGHTS)  # save to restore after
    results_table = []
    best_combo, best_avg_wait = None, float("inf")

    for combo in weight_grid:
        waits = []
        for seed in range(seeds):
            avg_wait = _run_single_trial(combo, center_lat, center_lon, seed,
                                          n_drivers, n_passengers)
            waits.append(avg_wait)

        mean_wait = statistics.mean(waits)
        std_wait = statistics.pstdev(waits)
        results_table.append({"weights": combo, "mean_wait": round(mean_wait, 3),
                               "std_wait": round(std_wait, 3)})

        if mean_wait < best_avg_wait:
            best_avg_wait = mean_wait
            best_combo = combo

    config.MATCH_WEIGHTS = original_weights  # restore original
    return best_combo, best_avg_wait, results_table


# ------------------------------------------------------------------
# QUICK TEST
# ------------------------------------------------------------------
if __name__ == "__main__":
    source_coords = geocode("Sitabuldi, Nagpur")

    # Candidate weight combinations to test (must sum reasonably close to 1
    # for distance+wait+idle; pooling is a separate bonus term)
    weight_grid = [
        {"distance": 0.40, "wait": 0.30, "idle": 0.20, "pooling": 0.10},  # current default
        {"distance": 0.30, "wait": 0.40, "idle": 0.20, "pooling": 0.10},  # prioritize wait more
        {"distance": 0.50, "wait": 0.20, "idle": 0.20, "pooling": 0.10},  # prioritize distance more
        {"distance": 0.30, "wait": 0.30, "idle": 0.30, "pooling": 0.10},  # balanced
        {"distance": 0.35, "wait": 0.35, "idle": 0.15, "pooling": 0.15},  # higher pooling emphasis
    ]

    print("Running weight calibration (grid search across 5 seeds per combo)...")
    print("This may take a little while depending on driver/passenger count.\n")

    best_combo, best_wait, table = calibrate_weights(
        weight_grid, source_coords[0], source_coords[1], seeds=5,
        n_drivers=30, n_passengers=40
    )

    print("Results table:")
    for row in table:
        print(f"  {row['weights']} -> mean_wait={row['mean_wait']}  std={row['std_wait']}")

    print(f"\nBest weight combo: {best_combo}")
    print(f"Best avg pickup distance: {round(best_wait, 3)} km")
    print("\n--> Copy this combo into config.py's MATCH_WEIGHTS to use the calibrated values.")