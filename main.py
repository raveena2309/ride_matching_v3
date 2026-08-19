"""
main.py
========
Real-time entry point: takes source + destination input from the user,
geocodes it, generates a synthetic driver fleet around that real location,
runs matching + repositioning, and shows results + a live map.
"""

import sys
from geocoding import geocode, reverse_geocode
from synthetic_data import generate_synthetic_drivers, generate_synthetic_passengers, \
                            generate_zones, build_passenger_from_input
from matching_engine import match
from repositioning import demand_aware_repositioning
from map_visualizer import show_map  # built in the next step


def get_user_input():
    """Prompts for source and destination text. Falls back to defaults if run non-interactively."""
    try:
        source_text = input("Enter pickup location (e.g. 'Sitabuldi, Nagpur'): ").strip()
        dest_text = input("Enter destination (e.g. 'VNIT Nagpur'): ").strip()
    except EOFError:
        # Non-interactive environment fallback
        source_text, dest_text = "Sitabuldi, Nagpur", "VNIT Nagpur"

    if not source_text:
        source_text = "Sitabuldi, Nagpur"
    if not dest_text:
        dest_text = "VNIT Nagpur"

    return source_text, dest_text


def run_pipeline(source_text, dest_text, n_synthetic_drivers=25, n_background_passengers=15):
    print(f"\nGeocoding '{source_text}'...")
    source_coords = geocode(source_text)
    if source_coords is None:
        print(f"ERROR: Could not find location '{source_text}'. Please check spelling and try again.")
        sys.exit(1)

    print(f"Geocoding '{dest_text}'...")
    dest_coords = geocode(dest_text)
    if dest_coords is None:
        print(f"ERROR: Could not find location '{dest_text}'. Please check spelling and try again.")
        sys.exit(1)

    print(f"  Source: {source_coords}")
    print(f"  Destination: {dest_coords}\n")

    # Generate synthetic fleet + background demand around the real source point
    drivers = generate_synthetic_drivers(n=n_synthetic_drivers, center_lat=source_coords[0],
                                          center_lon=source_coords[1], radius_km=8.0, seed=None)

    background_passengers = generate_synthetic_passengers(
        n=n_background_passengers, center_lat=source_coords[0], center_lon=source_coords[1],
        radius_km=8.0, dest_radius_km=10.0, seed=None
    )

    # The real user's request, built from actual geocoded input
    real_passenger = build_passenger_from_input(source_coords, dest_coords, passenger_id=999,
                                                 wait=0, demand=5, cancel_risk=1)

    all_passengers = background_passengers + [real_passenger]

    print(f"Simulating {len(drivers)} drivers and {len(all_passengers)} total requests "
          f"({len(background_passengers)} background + your request)...\n")

    matches = match(drivers, all_passengers, verbose=False)

    # Check specifically whether the real user's request got matched
    user_match = next((m for m in matches if m[1] == real_passenger.id), None)
    if user_match:
        driver_id, _, score = user_match
        matched_driver = next(d for d in drivers if d.id == driver_id)
        print(f"✅ YOUR REQUEST MATCHED: Driver {driver_id} is on the way "
              f"(match score={score:.3f})")
    else:
        print(f"⚠️  YOUR REQUEST COULD NOT BE MATCHED right now (no driver in range).")

    # Repositioning for whoever's left idle
    zones = generate_zones(center_lat=source_coords[0], center_lon=source_coords[1],
                            grid_size=4, spacing_km=3.0)
    moves = demand_aware_repositioning(drivers, all_passengers, zones, verbose=False)

    print(f"\nOverall stats:")
    print(f"  Total matched: {len(matches)} / {len(all_passengers)}")
    print(f"  Drivers repositioned: {len(moves)}")

    # Generate live map
    show_map(drivers, all_passengers, matches, save_path="outputs/live_map.html")

    return matches, drivers, all_passengers


if __name__ == "__main__":
    source_text, dest_text = get_user_input()
    run_pipeline(source_text, dest_text)