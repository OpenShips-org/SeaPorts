
#!/usr/bin/env python3

import json
import os
import sys
from pathlib import Path

from shapely.geometry import shape
from shapely.validation import explain_validity


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

PORTS_FILE = DATA_DIR / "ports.geojson"
POLYGONS_FILE = DATA_DIR / "port_polygons.geojson"

REPORT_PATH = Path(
    os.environ.get(
        "REPORT_PATH",
        "/tmp/seaports-validation-report.md"
    )
)

results = []
stats = {
    "ports": 0,
    "polygons": 0,
    "errors": 0,
    "warnings": 0,
}


def add_result(status, title, details=None):
    results.append({
        "status": status,
        "title": title,
        "details": details or [],
    })

    if status == "FAIL":
        stats["errors"] += 1
    elif status == "WARN":
        stats["warnings"] += 1


def read_geojson(path):
    if not path.exists():
        add_result(
            "FAIL",
            f"{path.name} exists",
            [f"File not found: `{path.relative_to(ROOT)}`"]
        )
        return None

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        add_result(
            "FAIL",
            f"{path.name} contains valid JSON",
            [str(error)]
        )
        return None

    if not isinstance(data, dict):
        add_result(
            "FAIL",
            f"{path.name} has a valid GeoJSON structure",
            ["The root element must be a JSON object."]
        )
        return None

    if data.get("type") != "FeatureCollection":
        add_result(
            "FAIL",
            f"{path.name} is a FeatureCollection",
            [f"Found type: `{data.get('type')}`"]
        )
        return None

    features = data.get("features")

    if not isinstance(features, list):
        add_result(
            "FAIL",
            f"{path.name} contains a feature list",
            ["The `features` property must be an array."]
        )
        return None

    # RFC 7946 GeoJSON uses WGS84 longitude/latitude by default.
    # The old optional "crs" member is checked if it is present.
    crs = data.get("crs")

    if crs is not None:
        crs_text = json.dumps(crs).upper()

        if "4326" not in crs_text and "CRS84" not in crs_text:
            add_result(
                "FAIL",
                f"{path.name} uses EPSG:4326",
                ["The declared CRS is not EPSG:4326 / CRS84."]
            )
        else:
            add_result(
                "PASS",
                f"{path.name} CRS",
                ["Declared CRS is compatible with WGS84."]
            )
    else:
        add_result(
            "PASS",
            f"{path.name} CRS",
            ["No CRS member declared; GeoJSON is interpreted as WGS84."]
        )

    return features


def get_property(properties, name):
    """Find a property without case sensitivity."""
    if not isinstance(properties, dict):
        return None

    for key, value in properties.items():
        if key.lower() == name.lower():
            return value

    return None


def normalize_id(value):
    if value is None:
        return None

    value = str(value).strip()

    return value if value else None


def validate_features(path, features, expected_types, id_field):
    valid_ids = set()
    duplicate_ids = set()
    invalid_geometries = []
    invalid_coordinates = []
    wrong_types = []
    missing_ids = []

    for index, feature in enumerate(features):
        if not isinstance(feature, dict):
            invalid_geometries.append(
                f"Feature {index}: feature is not a JSON object."
            )
            continue

        properties = feature.get("properties") or {}

        feature_id = normalize_id(
            get_property(properties, id_field)
        )

        if feature_id is None:
            missing_ids.append(f"Feature {index}")
        elif feature_id in valid_ids:
            duplicate_ids.add(feature_id)
        else:
            valid_ids.add(feature_id)

        geometry_data = feature.get("geometry")

        if not isinstance(geometry_data, dict):
            invalid_geometries.append(
                f"Feature {index}: missing or invalid geometry."
            )
            continue

        try:
            geometry = shape(geometry_data)
        except Exception as error:
            invalid_geometries.append(
                f"Feature {index}: could not read geometry ({error})."
            )
            continue

        if geometry.is_empty:
            invalid_geometries.append(
                f"Feature {index}: geometry is empty."
            )
            continue

        if geometry.geom_type not in expected_types:
            wrong_types.append(
                f"Feature {index}: found {geometry.geom_type}, "
                f"expected {', '.join(expected_types)}."
            )

        if not geometry.is_valid:
            invalid_geometries.append(
                f"Feature {index}: {explain_validity(geometry)}"
            )

        min_x, min_y, max_x, max_y = geometry.bounds

        if (
            min_x < -180
            or max_x > 180
            or min_y < -90
            or max_y > 90
        ):
            invalid_coordinates.append(
                f"Feature {index}: bounds "
                f"({min_x}, {min_y}, {max_x}, {max_y}) "
                "are outside WGS84 longitude/latitude limits."
            )

    stats_key = "ports" if id_field.lower() == "id" and path.name == "ports.geojson" else "polygons"
    stats[stats_key] = len(features)

    if missing_ids:
        add_result(
            "FAIL",
            f"{path.name}: required `{id_field}` values",
            missing_ids[:20]
        )
    else:
        add_result(
            "PASS",
            f"{path.name}: required `{id_field}` values",
            [f"All {len(features)} features have an ID."]
        )

    if duplicate_ids:
        add_result(
            "FAIL",
            f"{path.name}: duplicate IDs",
            sorted(duplicate_ids)[:20]
        )
    else:
        add_result(
            "PASS",
            f"{path.name}: unique IDs",
            [f"Checked {len(valid_ids)} unique IDs."]
        )

    if wrong_types:
        add_result(
            "FAIL",
            f"{path.name}: geometry types",
            wrong_types[:20]
        )
    else:
        add_result(
            "PASS",
            f"{path.name}: geometry types",
            [f"All features use the expected geometry types."]
        )

    if invalid_geometries:
        add_result(
            "FAIL",
            f"{path.name}: geometry validity",
            invalid_geometries[:20]
        )
    else:
        add_result(
            "PASS",
            f"{path.name}: geometry validity",
            [f"All {len(features)} geometries are valid and non-empty."]
        )

    if invalid_coordinates:
        add_result(
            "FAIL",
            f"{path.name}: coordinate ranges",
            invalid_coordinates[:20]
        )
    else:
        add_result(
            "PASS",
            f"{path.name}: coordinate ranges",
            ["All geometry bounds are within WGS84 limits."]
        )

    return valid_ids


def validate_polygon_references(port_ids, polygon_features):
    missing_references = []

    for index, feature in enumerate(polygon_features):
        properties = feature.get("properties") or {}

        point_id = normalize_id(
            get_property(properties, "point_id")
        )

        if point_id is None:
            missing_references.append(
                f"Polygon feature {index}: missing `point_id`."
            )
        elif point_id not in port_ids:
            missing_references.append(
                f"Polygon feature {index}: "
                f"`point_id` `{point_id}` does not exist in ports.geojson."
            )

    if missing_references:
        add_result(
            "FAIL",
            "Polygon references",
            missing_references[:20]
        )
    else:
        add_result(
            "PASS",
            "Polygon references",
            [
                f"All {len(polygon_features)} polygons reference "
                "an existing port."
            ]
        )



def create_report():
    failed = stats["errors"] > 0

    status_text = "FAILED" if failed else "PASSED"
    status_emoji = "❌" if failed else "✅"

    lines = [
        "# SeaPorts – Data Validation Report",
        "",
        f"**Overall result:** {status_emoji} {status_text}",
        "",
        "## Summary",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Ports checked | {stats['ports']} |",
        f"| Polygons checked | {stats['polygons']} |",
        f"| Errors | {stats['errors']} |",
        f"| Warnings | {stats['warnings']} |",
        "",
        "## Validation Results",
        "",
        "| Check | Result | Details |",
        "|---|---|---|",
    ]

    for result in results:
        if result["status"] == "PASS":
            status = "✅ Passed"
        elif result["status"] == "WARN":
            status = "⚠️ Warning"
        else:
            status = "❌ Failed"

        details = "<br>".join(
            detail.replace("|", "\\|")
            for detail in result["details"]
        )

        lines.append(
            f"| {result['title']} | {status} | {details} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "<sub>Automated report · SeaPorts Data Validator</sub>",
    ])

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")

    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as file:
            file.write("\n".join(lines))
            file.write("\n")



def main():
    ports = read_geojson(PORTS_FILE)
    polygons = read_geojson(POLYGONS_FILE)

    port_ids = set()

    if ports is not None:
        port_ids = validate_features(
            PORTS_FILE,
            ports,
            expected_types={"Point"},
            id_field="id",
        )

    if polygons is not None:
        validate_features(
            POLYGONS_FILE,
            polygons,
            expected_types={"Polygon", "MultiPolygon"},
            id_field="id",
        )

        if ports is not None:
            validate_polygon_references(port_ids, polygons)

    create_report()

    print(f"Ports: {stats['ports']}")
    print(f"Polygons: {stats['polygons']}")
    print(f"Errors: {stats['errors']}")
    print(f"Warnings: {stats['warnings']}")

    if stats["errors"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
