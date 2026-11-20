
#!/usr/bin/env python3

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data/source"
OUTPUT_DIR = ROOT / "data/processed"

PORTS_FILE = DATA_DIR / "ports.geojson"
POLYGONS_FILE = DATA_DIR / "port_polygons.geojson"
OUTPUT_FILE = OUTPUT_DIR / "ports_combined.geojson"


def load_geojson(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def main():
    ports = load_geojson(PORTS_FILE)
    polygons = load_geojson(POLYGONS_FILE)

    # Index polygons by their referenced port ID
    polygon_index = {
        feature["properties"]["point_id"]: feature
        for feature in polygons["features"]
        if feature.get("properties", {}).get("point_id")
    }

    combined_features = []
    matched = 0

    for port in ports["features"]:
        port_id = port["properties"].get("id")
        polygon = polygon_index.get(port_id)

        geometries = [port["geometry"]]

        area_id = None
        area_name = None

        if polygon:
            geometries.append(polygon["geometry"])
            area_id = polygon["properties"].get("id")
            area_name = polygon["properties"].get("Name")
            matched += 1

        combined_features.append({
            "type": "Feature",
            "properties": {
                **port["properties"],
                "area_id": area_id,
                "area_name": area_name,
            },
            "geometry": {
                "type": "GeometryCollection",
                "geometries": geometries,
            },
        })

    result = {
        "type": "FeatureCollection",
        "name": "ports_combined",
        "features": combined_features,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)

    print(f"Ports: {len(ports['features'])}")
    print(f"Polygons: {len(polygons['features'])}")
    print(f"Matched: {matched}")
    print(f"Without polygon: {len(ports['features']) - matched}")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
