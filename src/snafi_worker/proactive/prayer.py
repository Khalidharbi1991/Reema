"""Prayer times by the Umm al-Qura method, the same way the Snafi app computes them.

A line-by-line port of the parts of the adhan library (4.4.6, MIT) that the app uses for Jeddah:
the sun's position (Meeus, Astronomical Algorithms), Fajr at 18.5 degrees, Dhuhr at transit, Asr
at one shadow length (Shafi'i), Maghrib at sunset, Isha 90 minutes after Maghrib (120 in Ramadan),
every time rounded to the nearest minute. No network, no package.

tests/fixtures/snafi_prayer_times.json holds times from the app's own adhan code; both test suites
check against it (the web suite that adhan still gives those times, this suite that this port does),
so the worker's quiet times and the Today screen never disagree.

Ramadan comes from RAMADAN below (Umm al-Qura, from the built-in calendar the app uses); the web
suite checks the table against that calendar.
"""

import math
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Tuple

ORDER = ("fajr", "dhuhr", "asr", "maghrib", "isha")

# Umm al-Qura Ramadan, first and last day (Gregorian), from Intl "islamic-umalqura".
RAMADAN: Tuple[Tuple[str, str], ...] = (
    ("2026-02-18", "2026-03-19"), ("2027-02-08", "2027-03-08"), ("2028-01-28", "2028-02-25"),
    ("2029-01-16", "2029-02-13"), ("2030-01-05", "2030-02-03"), ("2030-12-26", "2031-01-23"),
    ("2031-12-16", "2032-01-13"), ("2032-12-04", "2033-01-02"), ("2033-11-23", "2033-12-22"),
    ("2034-11-12", "2034-12-11"), ("2035-11-01", "2035-11-30"),
)
FAJR_ANGLE = 18.5
ISHA_MINUTES = 90
RAMADAN_EXTRA = 30


def in_ramadan(day: date) -> bool:
    iso = day.isoformat()
    return any(first <= iso <= last for first, last in RAMADAN)


# ---------- adhan MathUtils ----------
def _rad(d: float) -> float:
    return d * math.pi / 180.0


def _deg(r: float) -> float:
    return r * 180.0 / math.pi


def _scale(num: float, top: float) -> float:
    return num - top * math.floor(num / top)


def _unwind(angle: float) -> float:
    return _scale(angle, 360.0)


def _quadrant(angle: float) -> float:
    if -180 <= angle <= 180:
        return angle
    return angle - 360 * _js_round(angle / 360)


def _js_round(x: float) -> int:
    return math.floor(x + 0.5)  # JavaScript Math.round


# ---------- adhan Astronomical ----------
def _mean_solar_longitude(t):
    return _unwind(280.4664567 + 36000.76983 * t + 0.0003032 * t ** 2)


def _mean_lunar_longitude(t):
    return _unwind(218.3165 + 481267.8813 * t)


def _ascending_node(t):
    return _unwind(125.04452 - 1934.136261 * t + 0.0020708 * t ** 2 + t ** 3 / 450000)


def _mean_anomaly(t):
    return _unwind(357.52911 + 35999.05029 * t - 0.0001537 * t ** 2)


def _equation_of_center(t, m):
    mr = _rad(m)
    return ((1.914602 - 0.004817 * t - 0.000014 * t ** 2) * math.sin(mr)
            + (0.019993 - 0.000101 * t) * math.sin(2 * mr) + 0.000289 * math.sin(3 * mr))


def _apparent_longitude(t, l0):
    longitude = l0 + _equation_of_center(t, _mean_anomaly(t))
    omega = 125.04 - 1934.136 * t
    return _unwind(longitude - 0.00569 - 0.00478 * math.sin(_rad(omega)))


def _mean_obliquity(t):
    return 23.439291 - 0.013004167 * t - 0.0000001639 * t ** 2 + 0.0000005036 * t ** 3


def _apparent_obliquity(t, e0):
    return e0 + 0.00256 * math.cos(_rad(125.04 - 1934.136 * t))


def _mean_sidereal(t):
    jd = t * 36525 + 2451545.0
    return _unwind(280.46061837 + 360.98564736629 * (jd - 2451545) + 0.000387933 * t ** 2 - t ** 3 / 38710000)


def _nutation_longitude(l0, lp, omega):
    return (-17.2 / 3600 * math.sin(_rad(omega)) - 1.32 / 3600 * math.sin(2 * _rad(l0))
            - 0.23 / 3600 * math.sin(2 * _rad(lp)) + 0.21 / 3600 * math.sin(2 * _rad(omega)))


def _nutation_obliquity(l0, lp, omega):
    return (9.2 / 3600 * math.cos(_rad(omega)) + 0.57 / 3600 * math.cos(2 * _rad(l0))
            + 0.1 / 3600 * math.cos(2 * _rad(lp)) - 0.09 / 3600 * math.cos(2 * _rad(omega)))


def _altitude(lat, dec, h):
    return _deg(math.asin(math.sin(_rad(lat)) * math.sin(_rad(dec))
                          + math.cos(_rad(lat)) * math.cos(_rad(dec)) * math.cos(_rad(h))))


def _interpolate(y2, y1, y3, n):
    a, b = y2 - y1, y3 - y2
    return y2 + n / 2 * (a + b + n * (b - a))


def _interpolate_angles(y2, y1, y3, n):
    a, b = _unwind(y2 - y1), _unwind(y3 - y2)
    return y2 + n / 2 * (a + b + n * (b - a))


def _julian_day(year, month, day):
    y = year if month > 2 else year - 1
    m = month if month > 2 else month + 12
    a = math.trunc(y / 100)
    b = math.trunc(2 - a + math.trunc(a / 4))
    return math.trunc(365.25 * (y + 4716)) + math.trunc(30.6001 * (m + 1)) + day + b - 1524.5


class _Solar:
    def __init__(self, jd):
        t = (jd - 2451545.0) / 36525
        l0, lp, omega = _mean_solar_longitude(t), _mean_lunar_longitude(t), _ascending_node(t)
        lam = _rad(_apparent_longitude(t, l0))
        theta0 = _mean_sidereal(t)
        dpsi, deps = _nutation_longitude(l0, lp, omega), _nutation_obliquity(l0, lp, omega)
        e0 = _mean_obliquity(t)
        eps = _rad(_apparent_obliquity(t, e0))
        self.declination = _deg(math.asin(math.sin(eps) * math.sin(lam)))
        self.right_ascension = _unwind(_deg(math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))))
        self.sidereal = theta0 + dpsi * 3600 * math.cos(_rad(e0 + deps)) / 3600


class _SolarTime:
    def __init__(self, day: date, lat: float, lon: float):
        jd = _julian_day(day.year, day.month, day.day)
        self.lat, self.lon = lat, lon
        self.s, self.p, self.n = _Solar(jd), _Solar(jd - 1), _Solar(jd + 1)
        lw = -lon
        m0 = _scale((self.s.right_ascension + lw - self.s.sidereal) / 360, 1)
        expected = _scale((12.0 - lon / 15.0) / 24.0, 1)
        if m0 - expected > 0.5:
            m0 -= 1.0
        elif expected - m0 > 0.5:
            m0 += 1.0
        self.m0 = m0
        theta = _unwind(self.s.sidereal + 360.985647 * m0)
        a = _unwind(_interpolate_angles(self.s.right_ascension, self.p.right_ascension, self.n.right_ascension, m0))
        h = _quadrant(theta - lw - a)
        self.transit = (m0 + h / -360) * 24
        self.sunrise = self.hour_angle(-50.0 / 60.0, False)
        self.sunset = self.hour_angle(-50.0 / 60.0, True)

    def hour_angle(self, h0: float, after: bool) -> float:
        s, p, n, lat = self.s, self.p, self.n, self.lat
        lw = -self.lon
        term = ((math.sin(_rad(h0)) - math.sin(_rad(lat)) * math.sin(_rad(s.declination)))
                / (math.cos(_rad(lat)) * math.cos(_rad(s.declination))))
        if not -1 <= term <= 1:
            return float("nan")
        big_h0 = _deg(math.acos(term))
        m = self.m0 + big_h0 / 360 if after else self.m0 - big_h0 / 360
        theta = _unwind(s.sidereal + 360.985647 * m)
        a = _unwind(_interpolate_angles(s.right_ascension, p.right_ascension, n.right_ascension, m))
        delta = _interpolate(s.declination, p.declination, n.declination, m)
        h = theta - lw - a
        alt = _altitude(lat, delta, h)
        dm = (alt - h0) / (360 * math.cos(_rad(delta)) * math.cos(_rad(lat)) * math.sin(_rad(h)))
        return (m + dm) * 24

    def afternoon(self, shadow: float) -> float:
        tangent = abs(self.lat - self.s.declination)
        angle = _deg(math.atan(1.0 / (shadow + math.tan(_rad(tangent)))))
        return self.hour_angle(angle, True)


def _utc(day: date, hours: float) -> datetime:
    h = math.floor(hours)
    m = math.floor((hours - h) * 60)
    s = math.floor((hours - (h + m / 60)) * 3600)
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(hours=h, minutes=m, seconds=s)


def _rounded(when: datetime) -> datetime:
    seconds = when.second
    offset = 60 - seconds if seconds >= 30 else -seconds
    return (when + timedelta(seconds=offset)).replace(microsecond=0)


def prayer_times(day: date, latitude: float, longitude: float) -> Dict[str, datetime]:
    """The five prayers on the city's calendar day `day`, as UTC datetimes rounded to the minute."""
    solar = _SolarTime(day, latitude, longitude)
    tomorrow = day + timedelta(days=1)
    dhuhr, sunrise, sunset = _utc(day, solar.transit), _utc(day, solar.sunrise), _utc(day, solar.sunset)
    asr = _utc(day, solar.afternoon(1))
    tomorrow_sunrise = _utc(tomorrow, _SolarTime(tomorrow, latitude, longitude).sunrise)
    night = (tomorrow_sunrise - sunset).total_seconds()
    fajr_hours = solar.hour_angle(-FAJR_ANGLE, False)
    safe_fajr = sunrise - timedelta(seconds=night / 2)  # MiddleOfTheNight, adhan's default
    fajr = safe_fajr if math.isnan(fajr_hours) or safe_fajr > _utc(day, fajr_hours) else _utc(day, fajr_hours)
    isha = sunset + timedelta(minutes=ISHA_MINUTES + (RAMADAN_EXTRA if in_ramadan(day) else 0))
    return {"fajr": _rounded(fajr), "dhuhr": _rounded(dhuhr), "asr": _rounded(asr), "maghrib": _rounded(sunset),
            "isha": _rounded(isha)}


def quiet_windows(now: datetime, latitude: float, longitude: float, tz, minutes: int) -> List[Tuple[datetime, datetime]]:
    """Each adhan from yesterday to tomorrow (city calendar days) and the end of its quiet time."""
    local_day = now.astimezone(tz).date()
    windows = []
    for delta in (-1, 0, 1):
        for when in prayer_times(local_day + timedelta(days=delta), latitude, longitude).values():
            windows.append((when, when + timedelta(minutes=minutes)))
    return sorted(windows)


def quiet_until(now: datetime, latitude: float, longitude: float, tz, minutes: int):
    """When the current prayer quiet time ends, or None if it is not quiet now."""
    for start, end in quiet_windows(now, latitude, longitude, tz, minutes):
        if start <= now < end:
            return end
    return None
