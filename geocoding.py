"""
geocoding.py
=============
Converts human-readable address text into (lat, lon) coordinates.
Uses Nominatim (OpenStreetMap's free geocoding service) via geopy.
"""

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

# Nominatim requires a unique "user_agent" string identifying your app
# (their usage policy, not optional) — customize this if you like.
_geolocator = Nominatim(user_agent="daa_ride_matching_project")


def geocode(address_text, timeout=10, city_context="Nagpur, India"):
    """
    Converts an address string into (lat, lon).
    If the initial query fails, retries once with city_context appended,
    since short/ambiguous place names often fail without it.
    Returns None if the address could not be found after both attempts.
    """
    try:
        location = _geolocator.geocode(address_text, timeout=timeout)
        if location is not None:
            return (location.latitude, location.longitude)

        # Retry with city context appended, in case the bare name was ambiguous
        if city_context and city_context.lower() not in address_text.lower():
            print(f"[geocoding] '{address_text}' not found directly, retrying with context...")
            location = _geolocator.geocode(f"{address_text}, {city_context}", timeout=timeout)
            if location is not None:
                return (location.latitude, location.longitude)

        print(f"[geocoding] Could not find location for: '{address_text}'")
        return None
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"[geocoding] Geocoding service error: {e}")
        return None


def reverse_geocode(lat, lon, timeout=10):
    """
    Converts (lat, lon) back into a human-readable address.
    Useful for displaying results to the user.
    """
    try:
        location = _geolocator.reverse((lat, lon), timeout=timeout)
        if location is None:
            return None
        return location.address
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"[geocoding] Reverse geocoding error: {e}")
        return None


# ------------------------------------------------------------------
# QUICK TEST
# ------------------------------------------------------------------
if __name__ == "__main__":
    test_address = "Sitabuldi, Nagpur"

    print(f"Geocoding: '{test_address}'")
    coords = geocode(test_address)
    print(f"  Coordinates: {coords}")

    if coords:
        print(f"\nReverse geocoding {coords}:")
        address = reverse_geocode(*coords)
        print(f"  Address: {address}")