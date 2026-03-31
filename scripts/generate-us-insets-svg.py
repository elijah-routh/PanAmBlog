#!/usr/bin/env python3
import json
import math
import os
import sys
import urllib.request

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(REPO_ROOT, "data")
GEOJSON_PATH = os.path.join(DATA_DIR, "ne_50m_admin_0_countries.geojson")
OUT_ALASKA = os.path.join(REPO_ROOT, "images", "alaska.svg")
OUT_HAWAII = os.path.join(REPO_ROOT, "images", "hawaii.svg")

GEOJSON_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
    "ne_50m_admin_0_countries.geojson"
)


def fetch_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "PanAmBlog US inset SVG generator",
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


def rad(deg: float) -> float:
    return deg * math.pi / 180.0


def laea(lon_deg: float, lat_deg: float, lon0_deg: float, lat0_deg: float):
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
    cos_c = max(-1.0, min(1.0, cos_c))
    k = math.sqrt(2.0 / (1.0 + cos_c))
    x = k * cos_lat * math.sin(dlon)
    y = k * (cos_lat0 * sin_lat - sin_lat0 * cos_lat * math.cos(dlon))
    return x, y


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


def classify_us_polygon(poly_rings):
    if not poly_rings:
        return None
    lon, lat = ring_center_lon_lat(poly_rings[0])

    # Hawaii islands cluster.
    if 17.0 <= lat <= 24.0 and -162.5 <= lon <= -153.0:
        return "hawaii"

    # Alaska and Aleutians.
    if lat >= 50.0 and (lon <= -130.0 or lon >= 160.0):
        return "alaska"

    return None


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


def build_region_svg(poly_groups, lon0, lat0, width, height, out_path, label):
    if not poly_groups:
        raise RuntimeError(f"No geometry found for {label}.")

    projected = []
    all_xy = []
    for poly in poly_groups:
        rings_xy = []
        for ring in poly:
            pts = [laea(lon, lat, lon0, lat0) for lon, lat in ring]
            rings_xy.append(pts)
            all_xy.extend(pts)
        projected.append(rings_xy)

    xs = [p[0] for p in all_xy]
    ys = [p[1] for p in all_xy]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    pad = 20.0
    scale = min((width - 2 * pad) / (max_x - min_x), (height - 2 * pad) / (max_y - min_y))

    def to_svg_xy(x, y):
        sx = (x - min_x) * scale + pad
        sy = (max_y - y) * scale + pad
        return sx, sy

    paths = []
    for rings in projected:
        rings_svg = [[to_svg_xy(x, y) for x, y in ring] for ring in rings]
        d = svg_path_from_rings(rings_svg)
        if d:
            paths.append(f'<path class="region" d="{d}"></path>')

    svg = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" width="{width:.0f}" height="{height:.0f}"
     role="img" aria-label="{label} map inset">
  <defs>
    <style type="text/css"><![CDATA[
      .ocean {{ fill: #ffffff; }}
      .region {{ fill: #b9b9b9; stroke: #ffffff; stroke-width: 0.75; vector-effect: non-scaling-stroke; }}
    ]]></style>
  </defs>
  <rect class="ocean" x="0" y="0" width="{width:.0f}" height="{height:.0f}"></rect>
  <g id="{label.lower()}">
    {"\n    ".join(paths)}
  </g>
</svg>
"""

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)


def main():
    ensure_geojson()
    with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
        geo = json.load(f)

    features = geo.get("features") or []
    usa = None
    for ft in features:
        props = ft.get("properties") or {}
        if (props.get("ADMIN") or "").strip().lower() == "united states of america":
            usa = ft
            break

    if not usa:
        raise RuntimeError("USA geometry not found in GeoJSON.")

    geom = usa.get("geometry") or {}
    if geom.get("type") != "MultiPolygon":
        raise RuntimeError("Expected USA geometry to be MultiPolygon.")

    alaska_polys = []
    hawaii_polys = []

    for poly in geom.get("coordinates", []):
        region = classify_us_polygon(poly)
        if region == "alaska":
            alaska_polys.append(poly)
        elif region == "hawaii":
            hawaii_polys.append(poly)

    build_region_svg(
        alaska_polys,
        lon0=-154.0,
        lat0=64.5,
        width=900.0,
        height=600.0,
        out_path=OUT_ALASKA,
        label="Alaska",
    )
    build_region_svg(
        hawaii_polys,
        lon0=-157.5,
        lat0=20.5,
        width=900.0,
        height=600.0,
        out_path=OUT_HAWAII,
        label="Hawaii",
    )

    sys.stdout.write(
        f"Wrote {OUT_ALASKA} ({len(alaska_polys)} polygons)\n"
        f"Wrote {OUT_HAWAII} ({len(hawaii_polys)} polygons)\n"
        f"GeoJSON cache: {GEOJSON_PATH}\n"
    )


if __name__ == "__main__":
    main()
