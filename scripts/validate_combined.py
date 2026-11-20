
#!/usr/bin/env python3

import json
import os
import sys

from pathlib import Path
from shapely.geometry import shape
from shapely.validation import explain_validity


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data/processed"

COMBINED_FILE = DATA_DIR / "ports_combined.geojson"

REPORT_PATH = Path(
    os.environ.get(
        "REPORT_PATH",
        "/tmp/seaports-validation-report.md"
    )
)

results = []

stats = {
    "ports": 0,
    "with_polygon": 0,
    "without_polygon": 0,
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
            [f"File not found: `{path}`"]
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

    crs = data.get("crs")

    if crs is not None:
        crs_text = json.dumps(crs).upper()

        if "4326" not in crs_text and "CRS84" not in crs_text:
            add_result(
                "FAIL",
                f"{path.name} CRS",
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


def validate_geometry(geometry_data, label, expected_types):
    try:
        geometry = shape(geometry_data)

    except Exception as error:
        return [
            f"{label}: could not read geometry ({error})."
        ]

    errors = []

    if geometry.is_empty:
        errors.append(f"{label}: geometry is empty.")
        return errors

    if geometry.geom_type not in expected_types:
        errors.append(
            f"{label}: found {geometry.geom_type}, "
            f"expected {', '.join(expected_types)}."
        )

    if not geometry.is_valid:
        errors.append(
            f"{label}: {explain_validity(geometry)}"
        )

    min_x, min_y, max_x, max_y = geometry.bounds

    if (
        min_x < -180
        or max_x > 180
        or min_y < -90
        or max_y > 90
    ):
        errors.append(
            f"{label}: bounds "
            f"({min_x}, {min_y}, {max_x}, {max_y}) "
            "are outside WGS84 longitude/latitude limits."
        )

    return errors


def validate_features(features):
    valid_ids = set()
    duplicate_ids = set()

    missing_ids = []
    invalid_features = []
    invalid_geometries = []
    invalid_properties = []

    for index, feature in enumerate(features):
        if not isinstance(feature, dict):
            invalid_features.append(
                f"Feature {index}: feature is not a JSON object."
            )
            continue

        properties = feature.get("properties") or {}

        port_id = normalize_id(
            get_property(properties, "id")
        )

        if port_id is None:
            missing_ids.append(f"Feature {index}")

        elif port_id in valid_ids:
            duplicate_ids.add(port_id)

        else:
            valid_ids.add(port_id)

        geometry_data = feature.get("geometry")

        if not isinstance(geometry_data, dict):
            invalid_features.append(
                f"Feature {index}: missing or invalid geometry."
            )
            continue

        if geometry_data.get("type") != "GeometryCollection":
            invalid_features.append(
                f"Feature {index}: expected GeometryCollection, "
                f"found {geometry_data.get('type')}."
            )
            continue

        geometries = geometry_data.get("geometries")

        if not isinstance(geometries, list):
            invalid_features.append(
                f"Feature {index}: geometries must be an array."
            )
            continue

        points = []
        polygons = []

        for geometry_index, geometry in enumerate(geometries):
            if not isinstance(geometry, dict):
                invalid_geometries.append(
                    f"Feature {index}, geometry {geometry_index}: "
                    "invalid geometry object."
                )
                continue

            geometry_type = geometry.get("type")

            if geometry_type == "Point":
                points.append(geometry)

            elif geometry_type in ("Polygon", "MultiPolygon"):
                polygons.append(geometry)

            else:
                invalid_geometries.append(
                    f"Feature {index}: unexpected geometry type "
                    f"{geometry_type}."
                )
                continue

            errors = validate_geometry(
                geometry,
                f"Feature {index}, {geometry_type}",
                {"Point"} if geometry_type == "Point"
                else {"Polygon", "MultiPolygon"}
            )

            invalid_geometries.extend(errors)

        if len(points) != 1:
            invalid_features.append(
                f"Feature {index}: expected exactly one Point, "
                f"found {len(points)}."
            )

        if len(polygons) > 1:
            invalid_features.append(
                f"Feature {index}: expected at most one Polygon, "
                f"found {len(polygons)}."
            )

        if polygons:
            stats["with_polygon"] += 1
        else:
            stats["without_polygon"] += 1

        area_id = get_property(properties, "area_id")
        area_name = get_property(properties, "area_name")

        if polygons:
            if not normalize_id(area_id):
                invalid_properties.append(
                    f"Feature {index}: polygon exists but area_id is missing."
                )

            if not normalize_id(area_name):
                invalid_properties.append(
                    f"Feature {index}: polygon exists but area_name is missing."
                )
        else:
            if area_id is not None or area_name is not None:
                invalid_properties.append(
                    f"Feature {index}: no polygon exists, "
                    "but area_id or area_name is set."
                )

    stats["ports"] = len(features)

    if missing_ids:
        add_result(
            "FAIL",
            "Required port IDs",
            missing_ids[:20]
        )
    else:
        add_result(
            "PASS",
            "Required port IDs",
            [f"All {len(features)} features have an ID."]
        )

    if duplicate_ids:
        add_result(
            "FAIL",
            "Duplicate port IDs",
            sorted(duplicate_ids)[:20]
        )
    else:
        add_result(
            "PASS",
            "Unique port IDs",
            [f"Checked {len(valid_ids)} unique IDs."]
        )

    if invalid_features:
        add_result(
            "FAIL",
            "Feature structure",
            invalid_features[:20]
        )
    else:
        add_result(
            "PASS",
            "Feature structure",
            ["All features have the expected structure."]
        )

    if invalid_geometries:
        add_result(
            "FAIL",
            "Geometry validity and coordinates",
            invalid_geometries[:20]
        )
    else:
        add_result(
            "PASS",
            "Geometry validity and coordinates",
            ["All geometries are valid and within WGS84 limits."]
        )

    if invalid_properties:
        add_result(
            "FAIL",
            "Polygon properties",
            invalid_properties[:20]
        )
    else:
        add_result(
            "PASS",
            "Polygon properties",
            ["Polygon properties match their geometries."]
        )


def create_report():
    failed = stats["errors"] > 0

    status_text = "FAILED" if failed else "PASSED"
    status_emoji = "❌" if failed else "✅"

    lines = [
        "# SeaPorts – Combined Data Validation Report",
        "",
        f"**Overall result:** {status_emoji} {status_text}",
        "",
        "## Summary",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Ports checked | {stats['ports']} |",
        f"| Ports with polygon | {stats['with_polygon']} |",
        f"| Ports without polygon | {stats['without_polygon']} |",
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

    REPORT_PATH.write_text(
        "\n".join(lines),
        encoding="utf-8"
    )

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")

    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as file:
            file.write("\n".join(lines))
            file.write("\n")


def main():
    features = read_geojson(COMBINED_FILE)

    if features is not None:
        validate_features(features)

    create_report()

    print(f"Ports: {stats['ports']}")
    print(f"With polygon: {stats['with_polygon']}")
    print(f"Without polygon: {stats['without_polygon']}")
    print(f"Errors: {stats['errors']}")
    print(f"Warnings: {stats['warnings']}")

    if stats["errors"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
