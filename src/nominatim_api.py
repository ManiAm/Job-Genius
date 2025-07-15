
import logging
import time
import inspect

from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

import models_redis

log = logging.getLogger(__name__)


def get_coordinates(city_name, max_retries=3, delay=2):

    frame = inspect.currentframe()
    cached = models_redis.get_from_cache(frame)
    if cached is not None:
        return True, cached

    geolocator = Nominatim(user_agent="city_distance_app")

    for attempt in range(1, max_retries + 1):

        try:

            location = geolocator.geocode(city_name)

            if location:
                loc = (location.latitude, location.longitude)
                models_redis.set_to_cache(frame, loc, ttl=86400)
                return True, loc

            return False, f"No match found for '{city_name}'"

        except (GeocoderTimedOut, GeocoderUnavailable) as e:

            if attempt == max_retries:
                return False, f"Geocoding failed after {max_retries} attempts: {e}"

            time.sleep(delay * attempt)  # Exponential backoff

    return False, f"Unexpected failure looking up: {city_name}"


def distance_between_cities(city1, city2, unit="miles"):
    """
        unit = meters, kilometers, feet, miles
    """

    status, output = get_coordinates(city1)
    if not status:
        return False, output

    coords_1 = output

    status, output = get_coordinates(city2)
    if not status:
        return False, output

    coords_2 = output

    return distance_between_coords(coords_1, coords_2, unit)


def distance_between_coords(coords_1, coords_2, unit="miles"):

    if unit == "meters":
        return geodesic(coords_1, coords_2).meters
    elif unit == "kilometers":
        return geodesic(coords_1, coords_2).kilometers
    elif unit == "feet":
        return geodesic(coords_1, coords_2).feet
    elif unit == "miles":
        return geodesic(coords_1, coords_2).miles
    else:
        return None
