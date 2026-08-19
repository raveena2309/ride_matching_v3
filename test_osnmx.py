from distance_engine import get_distance_km

lat1, lon1 = 21.1450, 79.0880
lat2, lon2 = 21.1500, 79.0900

print("Downloading Nagpur road network (this may take 1-2 minutes)...")
d = get_distance_km(lat1, lon1, lat2, lon2, mode="osmnx")
print(f"OSMnx road distance: {d:.3f} km")