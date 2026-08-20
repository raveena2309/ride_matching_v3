"""
map_visualizer.py
====================
Live folium map rendering: drivers, passengers, and TWO distinct routes
for the real user request:
  1. Driver -> Pickup  (red solid line)  - the driver traveling to reach you
  2. Pickup -> Destination (dark blue dashed line) - your actual ride/trip

These are two separate legs of the journey and were previously conflated -
only the driver->pickup leg was ever drawn, with no destination marker at
all, which made it look like the route was "going nowhere near" the stated
destination. Both legs are now drawn using real road-network geometry.
"""

import folium
from folium import FeatureGroup, LayerControl
from distance_engine import get_route_geometry


def show_map(drivers, passengers, matches, save_path="outputs/live_map.html",
             route_mode="osmnx"):
    """
    route_mode: "osmnx" (offline, real roads, default) or "live_osrm"
    (real-time, needs internet). Real route geometry is only fetched for
    YOUR request (passenger id=999) to avoid slow calls for every match.
    """
    if not drivers:
        print("No drivers to show on map.")
        return

    center_lat = sum(d.x for d in drivers) / len(drivers)
    center_lon = sum(d.y for d in drivers) / len(drivers)

    m = folium.Map(location=[center_lat, center_lon], zoom_start=13)

    drivers_layer = FeatureGroup(name="Drivers")
    passengers_layer = FeatureGroup(name="Background Passengers")
    matches_layer = FeatureGroup(name="Background Matches")
    your_layer = FeatureGroup(name="YOUR Request + Routes", show=True)

    driver_lookup = {d.id: d for d in drivers}
    passenger_lookup = {p.id: p for p in passengers}

    # ------------------------------------------------------------------
    # Driver markers
    # ------------------------------------------------------------------
    for d in drivers:
        folium.Marker(
            [d.x, d.y],
            popup=f"Driver {d.id} | Capacity {d.capacity} | Idle {d.idle_time}m",
            icon=folium.Icon(color="blue", icon="car", prefix="fa")
        ).add_to(drivers_layer)

    # ------------------------------------------------------------------
    # Passenger markers (+ destination marker for the real user)
    # ------------------------------------------------------------------
    all_route_points = []  # collects every point across both of your routes, for auto-zoom

    for p in passengers:
        if p.id == 999:
            folium.Marker(
                [p.x, p.y],
                popup="YOUR pickup location",
                icon=folium.Icon(color="red", icon="star", prefix="fa")
            ).add_to(your_layer)

            dest_lat, dest_lon = p.dest
            folium.Marker(
                [dest_lat, dest_lon],
                popup="YOUR destination",
                icon=folium.Icon(color="darkred", icon="flag-checkered", prefix="fa")
            ).add_to(your_layer)

            # Trip route: pickup -> destination (your actual ride)
            print("Fetching your trip route (pickup -> destination)...")
            trip_route = get_route_geometry(p.x, p.y, dest_lat, dest_lon, mode=route_mode)
            print(f"  Trip route has {len(trip_route)} points "
                  f"({'real road path' if len(trip_route) > 2 else 'straight-line fallback'})")

            folium.PolyLine(
                trip_route, color="darkblue", weight=5, opacity=0.9, dash_array="10,10",
                tooltip="YOUR TRIP: pickup -> destination"
            ).add_to(your_layer)

            all_route_points.extend(trip_route)
        else:
            folium.Marker(
                [p.x, p.y],
                popup=f"Passenger {p.id}",
                icon=folium.Icon(color="gray", icon="user", prefix="fa")
            ).add_to(passengers_layer)

    # ------------------------------------------------------------------
    # Match lines
    # ------------------------------------------------------------------
    for d_id, p_id, score in matches:
        d = driver_lookup[d_id]
        p = passenger_lookup[p_id]

        if p_id == 999:
            # Driver -> Pickup leg (the driver traveling to reach you)
            print("Fetching driver-to-pickup route...")
            pickup_route = get_route_geometry(d.x, d.y, p.x, p.y, mode=route_mode)
            print(f"  Pickup route has {len(pickup_route)} points "
                  f"({'real road path' if len(pickup_route) > 2 else 'straight-line fallback'})")

            folium.PolyLine(
                pickup_route, color="red", weight=5, opacity=1.0,
                tooltip=f"Driver {d_id} coming to pick you up"
            ).add_to(your_layer)

            all_route_points.extend(pickup_route)
        else:
            # Background matches - straight lines only, for speed
            folium.PolyLine(
                [(d.x, d.y), (p.x, p.y)],
                color="lightgray", weight=1, opacity=0.4,
                tooltip=f"Driver {d_id} -> Passenger {p_id} (approx.)"
            ).add_to(matches_layer)

    # ------------------------------------------------------------------
    # Assemble layers
    # ------------------------------------------------------------------
    drivers_layer.add_to(m)
    passengers_layer.add_to(m)
    matches_layer.add_to(m)
    your_layer.add_to(m)
    LayerControl(collapsed=False).add_to(m)

    # ------------------------------------------------------------------
    # Smart zoom: fit to BOTH of your route legs if they exist,
    # else fall back to fitting the whole simulation
    # ------------------------------------------------------------------
    if all_route_points:
        m.fit_bounds(all_route_points, padding=(50, 50))
    else:
        all_points = [(d.x, d.y) for d in drivers] + [(p.x, p.y) for p in passengers]
        if all_points:
            m.fit_bounds(all_points)

    # ------------------------------------------------------------------
    # Legend
    # ------------------------------------------------------------------
    legend_html = """
    <div style="position: fixed; bottom: 30px; left: 30px; z-index:9999;
                background: white; padding: 10px; border: 2px solid gray;
                border-radius: 5px; font-size: 13px; line-height: 1.6;">
    <b>Legend</b><br>
    🔵 Driver &nbsp; ⚪ Background Passenger<br>
    ⭐ Your pickup &nbsp; 🏁 Your destination<br>
    <span style="color:red;">━━</span> Driver coming to pick you up<br>
    <span style="color:darkblue;">┅┅</span> Your trip (pickup &rarr; destination)<br>
    <span style="color:lightgray;">─</span> Background matches (approx.)
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    m.save(save_path)
    print(f"\nMap saved: {save_path}")
    print("(Use the layer control panel top-right to toggle background traffic on/off.)")


# ------------------------------------------------------------------
# QUICK STANDALONE TEST
# ------------------------------------------------------------------
if __name__ == "__main__":
    from geocoding import geocode
    from synthetic_data import generate_synthetic_drivers, generate_synthetic_passengers, \
                                build_passenger_from_input
    from matching_engine import match

    source_coords = geocode("VNIT Nagpur")
    dest_coords = geocode("Sitabuldi, Nagpur")

    drivers = generate_synthetic_drivers(n=15, center_lat=source_coords[0],
                                          center_lon=source_coords[1], radius_km=8.0, seed=1)
    background_passengers = generate_synthetic_passengers(n=10, center_lat=source_coords[0],
                                                            center_lon=source_coords[1],
                                                            radius_km=8.0, dest_radius_km=10.0, seed=1)
    real_passenger = build_passenger_from_input(source_coords, dest_coords, passenger_id=999,
                                                 wait=0, demand=5, cancel_risk=1)

    all_passengers = background_passengers + [real_passenger]
    matches = match(drivers, all_passengers)

    show_map(drivers, all_passengers, matches, save_path="outputs/test_map.html", route_mode="osmnx")