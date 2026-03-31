#!/usr/bin/env python3
import json
import math
import os
import sys
import urllib.request

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(REPO_ROOT, "data")
GEOJSON_PATH = os.path.join(DATA_DIR, "ne_50m_admin_0_countries.geojson")
OUT_SVG_PATH = os.path.join(REPO_ROOT, "images", "americas-political.svg")

GEOJSON_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
    "ne_50m_admin_0_countries.geojson"
)


def fetch_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "PanAmBlog SVG generator",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode("utf-8")


def ensure_geojson() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(GEOJSON_PATH) and os.path.getsize(GEOJSON_PATH) > 0:
        return
    body = fetch_text(GEOJSON_URL)
    with open(GEOJSON_PATH, "w", encoding="utf-8") as f:
        f.write(body)


def escape_attr(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def stable_id(props: dict) -> str:
    iso2 = (props.get("ISO_A2") or "").strip()
    if iso2 and iso2 != "-99":
        return iso2.upper()
    iso3 = (props.get("ISO_A3") or "").strip()
    if iso3 and iso3 != "-99":
        return iso3.upper()

    name = (props.get("NAME") or props.get("ADMIN") or "UNKNOWN").strip()
    out = []
    last_us = False
    for ch in name.upper():
        ok = ("A" <= ch <= "Z") or ("0" <= ch <= "9")
        if ok:
            out.append(ch)
            last_us = False
        elif not last_us:
            out.append("_")
            last_us = True
    slug = "".join(out).strip("_")
    return slug or "UNKNOWN"


def is_americas_feature(feature: dict) -> bool:
    props = feature.get("properties") or {}
    continent = (props.get("CONTINENT") or "").strip().lower()
    return continent in ("north america", "south america")


def rad(deg: float) -> float:
    return deg * math.pi / 180.0


def lambert_azimuthal_equal_area(lon_deg, lat_deg, lon0_deg, lat0_deg):
    lon = rad(lon_deg)
    lat = rad(lat_deg)
    lon0 = rad(lon0_deg)
    lat0 = rad(lat0_deg)

    sin_lat = math.sin(lat)
    cos_lat = math.cos(lat)
    sin_lat0 = math.sin(lat0)
    cos_lat0 = math.cos(lat0)
    dlon = lon - lon0

    cos_c = sin_lat0 * sin_lat + cos_lat0 * cos_lat * math.cos(dlon)
    cos_c = max(-1.0, min(1.0, cos_c))  # numeric safety
    k = math.sqrt(2.0 / (1.0 + cos_c))
    x = k * cos_lat * math.sin(dlon)
    y = k * (cos_lat0 * sin_lat - sin_lat0 * cos_lat * math.cos(dlon))
    return x, y


def project_coords(coords, lon0, lat0):
    points = []
    for lon, lat in coords:
        x, y = lambert_azimuthal_equal_area(lon, lat, lon0, lat0)
        points.append((x, y))
    return points


def iter_rings(geometry: dict):
    gtype = geometry.get("type")
    if gtype == "Polygon":
        for ring in geometry.get("coordinates", []):
            yield ring
        return
    if gtype == "MultiPolygon":
        for poly in geometry.get("coordinates", []):
            for ring in poly:
                yield ring


def iter_polygons(geometry: dict):
    """
    Yield polygons as list-of-rings from GeoJSON Polygon / MultiPolygon.
    """
    gtype = geometry.get("type")
    if gtype == "Polygon":
        yield geometry.get("coordinates", [])
        return
    if gtype == "MultiPolygon":
        for poly in geometry.get("coordinates", []):
            yield poly


def normalize_lon(lon: float) -> float:
    out = lon
    while out > 180:
        out -= 360
    while out < -180:
        out += 360
    return out


def ring_center_lon_lat(ring):
    if not ring:
        return 0.0, 0.0
    lons = [normalize_lon(pt[0]) for pt in ring]
    lats = [pt[1] for pt in ring]
    return (sum(lons) / len(lons), sum(lats) / len(lats))


def is_caribbean_props(props: dict) -> bool:
    """Match logic in generate-caribbean-svg.py for hotspot + detail map."""
    sub = (props.get("SUBREGION") or "").strip().lower()
    if sub == "caribbean":
        return True
    iso3 = (props.get("ISO_A3") or "").strip().upper()
    if iso3 in {
        "PRI",
        "VIR",
        "CUW",
        "ABW",
        "BES",
        "SXM",
        "MSR",
        "BLM",
        "MAF",
    }:
        return True
    return False


# Hotspot shape: exclude mainland wedges that overlap Central America / Nicaragua on this projection.
HOTSPOT_EXCLUDE_ISO3 = frozenset({"BLZ", "NIC"})  # Belize, Nicaragua (Caribbean coast inflates the hull)
HOTSPOT_MIN_LON_DEG = -87.5  # drop points west of this (Belize ~-89; Cuba west ~-85)
HOTSPOT_MAX_POINTS = 3500  # subsample before convex hull (performance)
HOTSPOT_HULL_SHRINK = 0.97  # pull hull slightly toward centroid (looser = more islands inside outline)


def convex_hull_2d(points: list) -> list:
    """Monotone chain; points are (x, y). Returns hull vertices in CCW order."""
    if len(points) < 3:
        return list(points)
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def shrink_polygon_toward_centroid(vertices: list, factor: float) -> list:
    if not vertices or factor <= 0:
        return vertices
    cx = sum(p[0] for p in vertices) / len(vertices)
    cy = sum(p[1] for p in vertices) / len(vertices)
    return [(cx + (x - cx) * factor, cy + (y - cy) * factor) for x, y in vertices]


def svg_path_from_closed_poly(vertices: list) -> str:
    if len(vertices) < 3:
        return ""
    parts = [f"M {vertices[0][0]:.2f},{vertices[0][1]:.2f}"]
    for x, y in vertices[1:]:
        parts.append(f"L {x:.2f},{y:.2f}")
    parts.append("Z")
    return " ".join(parts)


def classify_us_polygon(poly_rings):
    """
    Return one of: 'alaska', 'hawaii', 'contiguous'
    """
    if not poly_rings:
        return "contiguous"
    lon, lat = ring_center_lon_lat(poly_rings[0])

    # Hawaii island chain.
    if 17.0 <= lat <= 24.0 and -162.5 <= lon <= -153.0:
        return "hawaii"

    # Alaska + Aleutians.
    if lat >= 50.0 and (lon <= -130.0 or lon >= 160.0):
        return "alaska"

    return "contiguous"


def svg_path_from_rings(rings_xy):
    parts = []
    for ring in rings_xy:
        if not ring:
            continue
        x0, y0 = ring[0]
        parts.append(f"M {x0:.2f},{y0:.2f}")
        for x, y in ring[1:]:
            parts.append(f"L {x:.2f},{y:.2f}")
        parts.append("Z")
    return " ".join(parts)


def main() -> None:
    ensure_geojson()
    with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
        geo = json.load(f)

    features = [ft for ft in (geo.get("features") or []) if is_americas_feature(ft)]
    if not features:
        raise RuntimeError("No Americas features found in GeoJSON.")

    # Projection center for Americas.
    lon0, lat0 = -95.0, 15.0

    all_xy = []
    feature_rings_xy = []
    for feature in features:
        geom = feature.get("geometry") or {}
        rings = list(iter_rings(geom))
        rings_xy = []
        for ring in rings:
            pts = project_coords(ring, lon0, lat0)
            rings_xy.append(pts)
            all_xy.extend(pts)
        feature_rings_xy.append(rings_xy)

    xs = [p[0] for p in all_xy]
    ys = [p[1] for p in all_xy]
    if not xs or not ys:
        raise RuntimeError("Projected bounds are empty.")

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    width, height = 1100.0, 900.0
    pad = 20.0

    span_x = max_x - min_x
    span_y = max_y - min_y
    if span_x <= 0 or span_y <= 0:
        raise RuntimeError("Invalid bounds span.")
    scale = min((width - 2 * pad) / span_x, (height - 2 * pad) / span_y)

    def to_svg_xy(x, y):
        sx = (x - min_x) * scale + pad
        sy = (max_y - y) * scale + pad  # flip y so north is up
        return sx, sy

    paths = []
    for feature, rings_xy in zip(features, feature_rings_xy):
        props = feature.get("properties") or {}
        cid = stable_id(props)
        name = (props.get("NAME") or props.get("ADMIN") or cid).strip()
        admin = (props.get("ADMIN") or "").strip().lower()

        # Split USA into separate map elements for contiguous 48, Alaska, Hawaii.
        if admin == "united states of america":
            geom = feature.get("geometry") or {}
            buckets = {"contiguous": [], "alaska": [], "hawaii": []}
            for poly in iter_polygons(geom):
                region = classify_us_polygon(poly)
                buckets[region].append(poly)

            region_specs = [
                ("contiguous", "US_CONTIGUOUS", "United States (Contiguous 48)"),
                ("alaska", "US_ALASKA", "United States (Alaska)"),
                ("hawaii", "US_HAWAII", "United States (Hawaii)"),
            ]

            for key, rid, rname in region_specs:
                poly_group = buckets.get(key) or []
                if not poly_group:
                    continue

                rings_svg = []
                for poly in poly_group:
                    for ring in poly:
                        projected_ring = project_coords(ring, lon0, lat0)
                        rings_svg.append([to_svg_xy(x, y) for x, y in projected_ring])
                d = svg_path_from_rings(rings_svg)
                if not d:
                    continue
                paths.append(
                    f'<path class="country country-us-subregion" id="{escape_attr(rid)}" '
                    f'data-name="{escape_attr(rname)}" data-country="US" data-subregion="{escape_attr(key)}" d="{d}"></path>'
                )
            continue

        rings_svg = [[to_svg_xy(x, y) for x, y in ring] for ring in rings_xy]
        d = svg_path_from_rings(rings_svg)
        if not d:
            continue
        paths.append(
            f'<path class="country" id="{escape_attr(cid)}" '
            f'data-name="{escape_attr(name)}" d="{d}"></path>'
        )

    hotspot_el = ""
    hotspot_pts = []
    for feature, rings_xy in zip(features, feature_rings_xy):
        props = feature.get("properties") or {}
        if not is_caribbean_props(props):
            continue
        iso3 = (props.get("ISO_A3") or "").strip().upper()
        if iso3 in HOTSPOT_EXCLUDE_ISO3:
            continue
        geom = feature.get("geometry") or {}
        for ring in iter_rings(geom):
            for lon, lat in ring:
                if normalize_lon(lon) < HOTSPOT_MIN_LON_DEG:
                    continue
                x, y = lambert_azimuthal_equal_area(lon, lat, lon0, lat0)
                hotspot_pts.append(to_svg_xy(x, y))

    if hotspot_pts:
        if len(hotspot_pts) > HOTSPOT_MAX_POINTS:
            step = max(1, len(hotspot_pts) // HOTSPOT_MAX_POINTS)
            hotspot_pts = hotspot_pts[::step]
        hull = convex_hull_2d(hotspot_pts)
        hull = shrink_polygon_toward_centroid(hull, HOTSPOT_HULL_SHRINK)
        d_hot = svg_path_from_closed_poly(hull)
        if d_hot:
            hotspot_el = f"""  <g id="hotspots" pointer-events="all">
    <title>Caribbean — click to zoom</title>
    <path id="caribbean-hotspot" class="map-hotspot" d="{d_hot}" pointer-events="all"></path>
  </g>
"""
        else:
            hxs = [p[0] for p in hotspot_pts]
            hys = [p[1] for p in hotspot_pts]
            hpad = 4.0
            hx = min(hxs) - hpad
            hy = min(hys) - hpad
            hw = max(hxs) - min(hxs) + 2 * hpad
            hh = max(hys) - min(hys) + 2 * hpad
            cx = hx + hw / 2
            cy = hy + hh / 2
            rx = hw / 2 * 0.92
            ry = hh / 2 * 0.92
            hotspot_el = f"""  <g id="hotspots" pointer-events="all">
    <title>Caribbean — click to zoom</title>
    <ellipse id="caribbean-hotspot" class="map-hotspot" cx="{cx:.2f}" cy="{cy:.2f}" rx="{rx:.2f}" ry="{ry:.2f}" pointer-events="all"></ellipse>
  </g>
"""

    svg = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" width="{width:.0f}" height="{height:.0f}"
     role="img" aria-label="Americas map (Lambert azimuthal equal-area)">
  <defs>
    <style type="text/css"><![CDATA[
      .ocean {{ fill: #ffffff; }}
      .country {{ fill: #b9b9b9; stroke: #ffffff; stroke-width: 0.75; vector-effect: non-scaling-stroke; }}
      .map-hotspot {{
        fill: rgba(30, 120, 200, 0.12);
        stroke: rgba(25, 95, 175, 0.85);
        stroke-width: 1.75;
        cursor: pointer;
        vector-effect: non-scaling-stroke;
      }}
      .map-hotspot:hover {{ fill: rgba(30, 120, 200, 0.2); stroke: rgba(15, 70, 140, 0.95); }}
    ]]></style>
  </defs>
  <rect class="ocean" x="0" y="0" width="{width:.0f}" height="{height:.0f}"></rect>
  <g id="countries">
    {"\n    ".join(paths)}
  </g>
{hotspot_el}</svg>
"""

    os.makedirs(os.path.dirname(OUT_SVG_PATH), exist_ok=True)
    with open(OUT_SVG_PATH, "w", encoding="utf-8") as f:
        f.write(svg)

    sys.stdout.write(
        f"Wrote {OUT_SVG_PATH}\nCountries: {len(paths)}\nGeoJSON cache: {GEOJSON_PATH}\n"
    )


if __name__ == "__main__":
    main()
