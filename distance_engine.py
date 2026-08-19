"""
distance_engine.py
====================
Computes distance between two lat/lon points using one of three methods:
  - haversine   : fast, offline, mathematically correct straight-line distance
  - osmnx       : real road-network distance (offline after one-time graph download)
  - live_osrm   : real-time road distance via public OSRM routing API

Falls back automatically to haversine if a live/network method fails.
Includes simple caching so repeated distance queries in a single run are free.
"""

import math
import requests

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
OSRM_BASE_URL = "http://router.project-osrm.org/route/v1/driving"

# Cache: maps (lat1, lon1, lat2, lon2, mode) -> distance_km
_distance_cache = {}

# OSMnx graph is loaded lazily (only when first needed) since it's a
# heavier one-time operation (downloads city road network).
_osmnx_graph = None


# ------------------------------------------------------------------
# METHOD 1: HAVERSINE (always available, offline, correct)
# ------------------------------------------------------------------
def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km between two lat/lon points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ------------------------------------------------------------------
# METHOD 2: OSMNX (real road network, offline after first download)
# ------------------------------------------------------------------
def _load_osmnx_graph(place_name="Nagpur, India"):
    """Loads (and caches) the road network graph for a place. Only runs once."""
    global _osmnx_graph
    if _osmnx_graph is None:
        import osmnx as ox
        print(f"[distance_engine] Downloading road network for '{place_name}' (one-time)...")
        _osmnx_graph = ox.graph_from_place(place_name, network_type="drive")
        print("[distance_engine] Road network loaded.")
    return _osmnx_graph


def osmnx_road_distance_km(lat1, lon1, lat2, lon2, place_name="Nagpur, India"):
    """Real road-network shortest-path distance using OSMnx + NetworkX."""
    import osmnx as ox
    import networkx as nx

    G = _load_osmnx_graph(place_name)
    node1 = ox.distance.nearest_nodes(G, lon1, lat1)
    node2 = ox.distance.nearest_nodes(G, lon2, lat2)
    meters = nx.shortest_path_length(G, node1, node2, weight="length")
    return meters / 1000.0


# ------------------------------------------------------------------
# METHOD 3: LIVE OSRM ROUTING (real-time, needs internet)
# ------------------------------------------------------------------
def live_osrm_distance_km(lat1, lon1, lat2, lon2, timeout=5):
    """
    Real-time road distance via OSRM's public demo server.
    Falls back to haversine if the request fails.
    """
    try:
        url = f"{OSRM_BASE_URL}/{lon1},{lat1};{lon2},{lat2}?overview=false"
        resp = requests.get(url, timeout=timeout)
        data = resp.json()
        meters = data["routes"][0]["distance"]
        return meters / 1000.0
    except Exception as e:
        print(f"[distance_engine] Live routing failed ({e}), falling back to haversine.")
        return haversine_km(lat1, lon1, lat2, lon2)


# ------------------------------------------------------------------
# MAIN ENTRY POINT (what every other module should call)
# ------------------------------------------------------------------
def get_distance_km(lat1, lon1, lat2, lon2, mode="haversine"):
    """
    mode: "haversine" | "osmnx" | "live_osrm"
    Cached so repeated calls with the same inputs+mode don't recompute.
    """
    key = (round(lat1, 6), round(lon1, 6), round(lat2, 6), round(lon2, 6), mode)
    if key in _distance_cache:
        return _distance_cache[key]

    if mode == "haversine":
        result = haversine_km(lat1, lon1, lat2, lon2)
    elif mode == "osmnx":
        try:
            result = osmnx_road_distance_km(lat1, lon1, lat2, lon2)
        except Exception as e:
            print(f"[distance_engine] OSMnx failed ({e}), falling back to haversine.")
            result = haversine_km(lat1, lon1, lat2, lon2)
    elif mode == "live_osrm":
        result = live_osrm_distance_km(lat1, lon1, lat2, lon2)
    else:
        raise ValueError(f"Unknown mode: {mode}")

    _distance_cache[key] = result
    return result


# ------------------------------------------------------------------
# QUICK TEST
# ------------------------------------------------------------------
if __name__ == "__main__":
    lat1, lon1 = 21.1450, 79.0880   # point A, Nagpur
    lat2, lon2 = 21.1500, 79.0900   # point B, Nagpur

    print("Testing haversine (should always work):")
    d1 = get_distance_km(lat1, lon1, lat2, lon2, mode="haversine")
    print(f"  Haversine distance: {d1:.3f} km")

    print("\nTesting live OSRM (needs internet):")
    d2 = get_distance_km(lat1, lon1, lat2, lon2, mode="live_osrm")
    print(f"  Live road distance: {d2:.3f} km")

    print(f"\nDifference (real road vs straight-line): {d2 - d1:.3f} km")
    print("(If this is 0.000, live routing likely failed and fell back to haversine — check internet.)")