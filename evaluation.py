"""
evaluation.py
===============
Multi-seed statistical evaluation of our adaptive matching engine vs the
Hungarian baseline. Addresses reviewer's "no statistical robustness"
complaint by reporting mean +/- std across multiple random seeds instead
of single-run numbers.
"""

import statistics
from geocoding import geocode
from synthetic_data import generate_synthetic_drivers, generate_synthetic_passengers, generate_zones
from matching_engine import match
from baseline import hungarian_baseline
from repositioning import demand_aware_repositioning


def compute_metrics(matches, drivers, passengers):
    """
    Computes metrics purely from the matches list + total driver/passenger
    counts - works correctly whether or not the matching function mutated
    driver.current_passengers (our engine does; Hungarian baseline doesn't).
    """
    success_rate = len(matches) / len(passengers)

    matched_driver_ids = [m[0] for m in matches]
    unique_drivers_used = len(set(matched_driver_ids))
    utilization = unique_drivers_used / len(drivers)

    # Pooling: a driver appearing more than once in the matches list means
    # they picked up multiple passengers (pooled ride)
    from collections import Counter
    driver_counts = Counter(matched_driver_ids)
    pooled_drivers = sum(1 for count in driver_counts.values() if count > 1)
    pooling_rate = pooled_drivers / len(drivers)

    idle_times = [d.idle_time for d in drivers]
    mean_idle = sum(idle_times) / len(idle_times)
    variance = sum((x - mean_idle) ** 2 for x in idle_times) / len(idle_times)

    avg_match_cost = sum(s for _, _, s in matches) / max(1, len(matches))

    return {
        "success_rate": success_rate,
        "utilization": utilization,
        "idle_variance": variance,
        "pooling_rate": pooling_rate,
        "avg_match_cost": avg_match_cost,
    }

def run_multi_seed_evaluation(num_seeds=10, n_drivers=20, n_passengers=20,
                               center_lat=None, center_lon=None,
                               radius_km=8.0, dest_radius_km=10.0):
    """Runs both our engine and Hungarian across num_seeds, returns summary stats for each."""
    our_results, hungarian_results = [], []

    for seed in range(num_seeds):
        drivers_ours = generate_synthetic_drivers(n=n_drivers, center_lat=center_lat,
                                                    center_lon=center_lon, radius_km=radius_km, seed=seed)
        passengers_ours = generate_synthetic_passengers(n=n_passengers, center_lat=center_lat,
                                                          center_lon=center_lon, radius_km=radius_km,
                                                          dest_radius_km=dest_radius_km, seed=seed)
        matches_ours = match(drivers_ours, passengers_ours)
        our_results.append(compute_metrics(matches_ours, drivers_ours, passengers_ours))

        drivers_h = generate_synthetic_drivers(n=n_drivers, center_lat=center_lat,
                                                 center_lon=center_lon, radius_km=radius_km, seed=seed)
        passengers_h = generate_synthetic_passengers(n=n_passengers, center_lat=center_lat,
                                                       center_lon=center_lon, radius_km=radius_km,
                                                       dest_radius_km=dest_radius_km, seed=seed)
        hungarian_matches, _ = hungarian_baseline(drivers_h, passengers_h)
        hungarian_results.append(compute_metrics(hungarian_matches, drivers_h, passengers_h))

    def summarize(results_list):
        summary = {}
        for key in results_list[0]:
            values = [r[key] for r in results_list]
            summary[key] = (statistics.mean(values), statistics.pstdev(values))
        return summary

    return summarize(our_results), summarize(hungarian_results)


def print_summary(name, summary):
    print(f"\n{name}")
    print("-" * 50)
    for key, (mean, std) in summary.items():
        print(f"  {key}: {mean:.3f} +/- {std:.3f}")


# ------------------------------------------------------------------
# MAIN EVALUATION
# ------------------------------------------------------------------
if __name__ == "__main__":
    source_coords = geocode("Sitabuldi, Nagpur")

    print(f"Running multi-seed evaluation (10 seeds, 20 drivers, 20 passengers)...")
    print("This may take a little while.\n")

    our_summary, hungarian_summary = run_multi_seed_evaluation(
        num_seeds=10, n_drivers=20, n_passengers=20,
        center_lat=source_coords[0], center_lon=source_coords[1]
    )

    print_summary("OUR ADAPTIVE ENGINE (mean +/- std across 10 seeds)", our_summary)
    print_summary("HUNGARIAN BASELINE (mean +/- std across 10 seeds)", hungarian_summary)