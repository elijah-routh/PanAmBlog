#!/usr/bin/env python3
"""
Generate a zoomed Caribbean political map (same styling as americas-political.svg).
Run after data/ne_50m_admin_0_countries.geojson exists (via generate-americas-svg.py fetch).
"""
import json
import math
import os
import sys
import urllib.request

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(REPO_ROOT, "data")
GEOJSON_PATH = os.path.join(DATA_DIR, "ne_50m_admin_0_countries.geojson")
GEOJSON_MAP_UNITS_PATH = os.path.join(DATA_DIR, "ne_50m_admin_0_map_units.geojson")
OUT_SVG_PATH = os.path.join(REPO_ROOT, "images", "SVG", "caribbean-political.svg")

GEOJSON_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
    "ne_50m_admin_0_countries.geojson"
)
GEOJSON_MAP_UNITS_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
    "ne_50m_admin_0_map_units.geojson"
)


def fetch_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "PanAmBlog Caribbean SVG generator",
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


def ensure_map_units_geojson() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(GEOJSON_MAP_UNITS_PATH) and os.path.getsize(GEOJSON_MAP_UNITS_PATH) > 0:
        return
    body = fetch_text(GEOJSON_MAP_UNITS_URL)
    with open(GEOJSON_MAP_UNITS_PATH, "w", encoding="utf-8") as f:
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
    if len(iso2) == 2 and iso2.isalpha() and iso2 != "-99":
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


def is_caribbean_feature(feature: dict) -> bool:
    props = feature.get("properties") or {}
    sub = (props.get("SUBREGION") or "").strip().lower()
    if sub == "caribbean":
        return True
    iso3 = (props.get("ISO_A3") or "").strip().upper()
    # Territories often tagged separately
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


EXTRA_CARIBBEAN_MAP_UNITS_ISO3 = frozenset({"GLP", "MTQ", "BES"})


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
    cos_c = max(-1.0, min(1.0, cos_c))
    k = math.sqrt(2.0 / (1.0 + cos_c))
    x = k * cos_lat * math.sin(dlon)
    y = k * (cos_lat0 * sin_lat - sin_lat0 * cos_lat * math.cos(dlon))
    return x, y


def project_coords(coords, lon0, lat0):
    return [lambert_azimuthal_equal_area(lon, lat, lon0, lat0) for lon, lat in coords]


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
    ensure_map_units_geojson()
    with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
        geo = json.load(f)

    features = [ft for ft in (geo.get("features") or []) if is_caribbean_feature(ft)]

    # Add select Caribbean territories that may be missing from admin_0_countries at 50m scale.
    with open(GEOJSON_MAP_UNITS_PATH, "r", encoding="utf-8") as f:
        mu = json.load(f)
    for ft in (mu.get("features") or []):
        props = ft.get("properties") or {}
        iso3 = (props.get("ISO_A3") or "").strip().upper()
        if iso3 not in EXTRA_CARIBBEAN_MAP_UNITS_ISO3:
            continue
        if not is_caribbean_feature(ft):
            continue
        features.append(ft)
    if not features:
        raise RuntimeError("No Caribbean features found in GeoJSON.")

    # Center on the Caribbean basin for a readable inset.
    lon0, lat0 = -72.0, 18.0

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

    width, height = 900.0, 700.0
    pad = 24.0

    span_x = max_x - min_x
    span_y = max_y - min_y
    if span_x <= 0 or span_y <= 0:
        raise RuntimeError("Invalid bounds span.")
    scale = min((width - 2 * pad) / span_x, (height - 2 * pad) / span_y)

    def to_svg_xy(x, y):
        sx = (x - min_x) * scale + pad
        sy = (max_y - y) * scale + pad
        return sx, sy

    paths = []
    for feature, rings_xy in zip(features, feature_rings_xy):
        props = feature.get("properties") or {}
        cid = stable_id(props)
        name = (props.get("NAME") or props.get("ADMIN") or cid).strip()
        rings_svg = [[to_svg_xy(x, y) for x, y in ring] for ring in rings_xy]
        d = svg_path_from_rings(rings_svg)
        if not d:
            continue
        paths.append(
            f'<path class="country" id="{escape_attr(cid)}" '
            f'data-name="{escape_attr(name)}" d="{d}"></path>'
        )

    svg = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" width="{width:.0f}" height="{height:.0f}"
     role="img" aria-label="Caribbean map (Lambert azimuthal equal-area)">
  <defs>
    <style type="text/css"><![CDATA[
      .ocean {{ fill: #ffffff; }}
      .country {{ fill: #b9b9b9; stroke: #ffffff; stroke-width: 0.75; vector-effect: non-scaling-stroke; }}
    ]]></style>
  </defs>
  <rect class="ocean" x="0" y="0" width="{width:.0f}" height="{height:.0f}"></rect>
  <g id="countries">
    {"\n    ".join(paths)}
  </g>
</svg>
"""

    os.makedirs(os.path.dirname(OUT_SVG_PATH), exist_ok=True)
    with open(OUT_SVG_PATH, "w", encoding="utf-8") as f:
        f.write(svg)

    sys.stdout.write(
        f"Wrote {OUT_SVG_PATH}\nCountries: {len(paths)}\nGeoJSON cache: {GEOJSON_PATH}\n"
    )


if __name__ == "__main__":
    main()
