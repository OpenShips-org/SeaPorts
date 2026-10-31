
# Contributing to SeaPorts

Thank you for your interest in contributing to SeaPorts!

SeaPorts is an open-source geospatial dataset that aims to collect and maintain information about ports and their geographic boundaries.

Contributions of all kinds are welcome, including missing ports, data corrections, polygon improvements, and documentation.

## How to Contribute

There are two main ways to contribute:

- Open an issue to report incorrect or missing data.
- Submit a pull request with your proposed changes.

Please check existing issues before opening a new one to avoid duplicates.

## Development Workflow

1. Fork the repository.
2. Create a new branch from `main`.
3. Make your changes.
4. Validate your data.
5. Commit your changes.
6. Open a pull request against `main`.

## Data Guidelines

All contributions must follow these guidelines:

- Use GeoJSON as the data format.
- Use EPSG:4326 (WGS84) for geographic coordinates.
- Keep port IDs unique and consistent.
- Ensure polygon geometries are valid.
- Every polygon must reference an existing port through `point_id`.
- Do not introduce duplicate ports or polygons.
- Preserve the existing attribute structure.

## Data Sources

Contributions should be based on reliable and verifiable sources.

Please include source links in your pull request whenever possible.

Do not submit data that cannot legally be redistributed under the project's licensing terms.

## Validation

Pull requests that modify files in `data/` are automatically checked using GitHub Actions.

Please make sure your changes pass all validation checks before requesting a review.

## Pull Requests

When submitting a pull request:

- Use the provided pull request template.
- Clearly describe your changes.
- List all affected ports.
- Include relevant data sources.
- Explain any unusual geometry changes.

All contributions are subject to review before being merged.

## Questions

If you have questions or are unsure how to contribute, feel free to open an issue.

Thank you for helping improve SeaPorts!
