"""
map_visualizer.py
====================
Live folium map rendering: drivers, passengers, and match lines.
"""

import folium


import folium
from folium import FeatureGroup, LayerControl
from folium.plugins import MarkerCluster

def show_map(drivers, passengers, matches, save_path="outputs/live_map.html"):
    if not drivers:
        print("No drivers to show on map.")
        return

    center_lat = sum(d.x for d in drivers) / len(drivers)
    center_lon = sum(d.y for d in drivers) / len(drivers)

    m = folium.Map(location=[center_lat, center_lon], zoom_start=13)

    drivers_layer = FeatureGroup(name="Drivers")
    passengers_layer = FeatureGroup(name="Background Passengers")
    matches_layer = FeatureGroup(name="Background Matches")
    your_layer = FeatureGroup(name="YOUR Request + Match", show=True)

    for d in drivers:
        folium.Marker(
            [d.x, d.y],
            popup=f"Driver {d.id} | Capacity {d.capacity} | Idle {d.idle_time}m",
            icon=folium.Icon(color="blue", icon="car", prefix="fa")
        ).add_to(drivers_layer)

    driver_lookup = {d.id: d for d in drivers}
    passenger_lookup = {p.id: p for p in passengers}

    for p in passengers:
        if p.id == 999:
            folium.Marker(
                [p.x, p.y],
                popup="YOUR pickup location",
                icon=folium.Icon(color="red", icon="star", prefix="fa")
            ).add_to(your_layer)
        else:
            folium.Marker(
                [p.x, p.y],
                popup=f"Passenger {p.id}",
                icon=folium.Icon(color="gray", icon="user", prefix="fa")
            ).add_to(passengers_layer)

    for d_id, p_id, score in matches:
        d = driver_lookup[d_id]
        p = passenger_lookup[p_id]
        if p_id == 999:
            folium.PolyLine(
                [(d.x, d.y), (p.x, p.y)],
                color="red", weight=5, opacity=0.9,
                tooltip=f"YOUR MATCH: Driver {d_id}",
                popup=f"Your match score = {round(score, 3)}"
            ).add_to(your_layer)
        else:
            folium.PolyLine(
                [(d.x, d.y), (p.x, p.y)],
                color="lightgray", weight=1, opacity=0.4,
                tooltip=f"Driver {d_id} -> Passenger {p_id}"
            ).add_to(matches_layer)

    drivers_layer.add_to(m)
    passengers_layer.add_to(m)
    matches_layer.add_to(m)
    your_layer.add_to(m)
    LayerControl(collapsed=False).add_to(m)

    # Legend
    legend_html = """
    <div style="position: fixed; bottom: 30px; left: 30px; z-index:9999;
                background: white; padding: 10px; border: 2px solid gray; border-radius: 5px;">
    <b>Legend</b><br>
    🔵 Driver &nbsp; ⚪ Background Passenger &nbsp; ⭐ You<br>
    <span style="color:red;">━━</span> Your match &nbsp;
    <span style="color:lightgray;">─</span> Background matches
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    m.save(save_path)
    print(f"\nMap saved: {save_path}")
    print("(Use the layer control panel top-right to toggle background traffic on/off.)")