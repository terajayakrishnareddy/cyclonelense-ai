"""Constant-motion great-circle extrapolation.

This is a geometric baseline, NOT a trained model and NOT a forecast: it ignores
steering flow, storm physics, land interaction and uncertainty.
"""
import math

EARTH_RADIUS_KM = 6371.0
RESEARCH_DISCLAIMER = ("Research baseline only. Not an official forecast and not an ML model. "
                       "Not for warning, navigation, evacuation or any safety decision.")


def project(lat: float, lon: float, bearing_deg: float, distance_km: float) -> tuple[float, float]:
    lat1, lon1, brg = math.radians(lat), math.radians(lon), math.radians(bearing_deg)
    ang = distance_km / EARTH_RADIUS_KM
    lat2 = math.asin(math.sin(lat1) * math.cos(ang) + math.cos(lat1) * math.sin(ang) * math.cos(brg))
    lon2 = lon1 + math.atan2(math.sin(brg) * math.sin(ang) * math.cos(lat1),
                             math.cos(ang) - math.sin(lat1) * math.sin(lat2))
    return round(math.degrees(lat2), 4), round((math.degrees(lon2) + 540) % 360 - 180, 4)


def constant_motion_track(lat: float, lon: float, bearing_deg: float, speed_kmh: float, hours: int, step_hours: int = 6):
    """Projected positions every ``step_hours`` (and at the final hour)."""
    marks = sorted({*range(step_hours, hours + 1, step_hours), hours})
    return [{"hours_ahead": h, **dict(zip(("latitude", "longitude"), project(lat, lon, bearing_deg, speed_kmh * h)))}
            for h in marks]
