"""
scoring.py
===========
Normalized priority, match, and pooling score formulas.

KEY FIX vs the original paper: every input (distance in km, wait in minutes,
idle in minutes, etc.) is normalized to [0,1] BEFORE being combined with
weights. This makes the weights meaningful (relative importance) instead of
accidentally performing unit conversion.
"""

from distance_engine import get_distance_km
import config


def normalize(x, x_min, x_max):
    """Scales x into [0,1] given expected bounds. Clamps out-of-range values."""
    if x_max - x_min == 0:
        return 0.0
    return max(0.0, min(1.0, (x - x_min) / (x_max - x_min)))


# ------------------------------------------------------------------
# PRIORITY SCORE (which passenger gets served first)
# ------------------------------------------------------------------
def priority_score(passenger):
    w = config.PRIORITY_WEIGHTS
    wait_n = normalize(passenger.wait, 0, config.MAX_WAIT_MIN)
    cancel_n = normalize(passenger.cancel_risk, 0, config.MAX_CANCEL_RISK)
    demand_n = normalize(passenger.demand, 0, config.MAX_DEMAND_SCORE)

    return (
        w["wait"] * wait_n
        + w["cancel"] * cancel_n
        + w["demand"] * demand_n
    )


# ------------------------------------------------------------------
# ROUTE SIMILARITY (used for pooling compatibility)
# ------------------------------------------------------------------
def route_similarity(p1, p2, distance_mode="haversine"):
    """
    Normalized similarity in [0,1]: 1.0 = identical route, 0.0 = combined
    pickup+destination distance exceeds POOLING_DETOUR_TOLERANCE_KM.
    Scale-aware fix - the old 1/(1+dist) formula only worked when
    passengers were bunched within a few hundred meters of each other.
    """
    pickup_dist = get_distance_km(p1.x, p1.y, p2.x, p2.y, mode=distance_mode)
    dest_dist = get_distance_km(p1.dest[0], p1.dest[1], p2.dest[0], p2.dest[1], mode=distance_mode)
    combined = pickup_dist + dest_dist

    similarity = max(0.0, 1 - (combined / config.POOLING_DETOUR_TOLERANCE_KM))
    return similarity


def can_pool(existing_passenger, new_passenger, distance_mode="haversine"):
    return route_similarity(existing_passenger, new_passenger, distance_mode) > config.POOLING_SIMILARITY_THRESHOLD


def pooling_gain(driver, new_passenger, distance_mode="haversine"):
    """Average route similarity between the new passenger and the driver's
    existing passengers. 0 if driver has none (no pooling benefit yet)."""
    if not driver.current_passengers:
        return 0.0
    sims = [route_similarity(existing, new_passenger, distance_mode) for existing in driver.current_passengers]
    return sum(sims) / len(sims)


# ------------------------------------------------------------------
# MATCH SCORE (lower is better - used to pick the best driver for a passenger)
# ------------------------------------------------------------------
def match_score(driver, passenger, distance_mode="haversine"):
    w = config.MATCH_WEIGHTS

    dist_km = get_distance_km(driver.x, driver.y, passenger.x, passenger.y, mode=distance_mode)
    dist_n = normalize(dist_km, 0, config.MAX_DISTANCE_KM)
    wait_n = normalize(passenger.wait, 0, config.MAX_WAIT_MIN)
    idle_n = normalize(driver.idle_time, 0, config.MAX_IDLE_MIN)
    pool_gain = pooling_gain(driver, passenger, distance_mode)  # already in [0,1]

    return (
        w["distance"] * dist_n
        + w["wait"] * wait_n
        + w["idle"] * idle_n
        - w["pooling"] * pool_gain   # subtract: higher pooling gain lowers (improves) score
    )


# ------------------------------------------------------------------
# QUICK TEST
# ------------------------------------------------------------------
if __name__ == "__main__":
    from geocoding import geocode
    from synthetic_data import generate_synthetic_drivers, generate_synthetic_passengers

    source_coords = geocode("Sitabuldi, Nagpur")

    drivers = generate_synthetic_drivers(n=10, center_lat=source_coords[0],
                                          center_lon=source_coords[1], radius_km=8.0, seed=42)
    passengers = generate_synthetic_passengers(n=5, center_lat=source_coords[0],
                                                center_lon=source_coords[1], radius_km=8.0,
                                                dest_radius_km=10.0, seed=42)

    print("Priority scores (higher = more urgent):")
    for p in sorted(passengers, key=priority_score, reverse=True):
        print(f"  Passenger {p.id}: priority = {priority_score(p):.3f}")

    print("\nMatch scores for Passenger", passengers[0].id, "(lower = better match):")
    scored = [(d.id, match_score(d, passengers[0])) for d in drivers]
    scored.sort(key=lambda t: t[1])
    for driver_id, score in scored[:5]:
        print(f"  Driver {driver_id}: match_score = {score:.3f}")