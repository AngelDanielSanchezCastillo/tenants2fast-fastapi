"""Tests for the TENANT JSON route manifest loader/validator."""

from __future__ import annotations

import json

from tenant2fast_fastapi.services.route_manifest import (
    load_route_manifest,
    validate_route_manifest,
)


def _write(tmp_path, payload):
    path = tmp_path / "routes.json"
    path.write_text(json.dumps(payload))
    return path


def test_valid_manifest_loads_typed_specs(tmp_path):
    path = _write(tmp_path, [
        {"method": "GET", "path": "/orders", "permission": "orders:read", "roles": []},
        {"method": "put", "path": "/orders/{id}", "roles": ["Admin"], "profile": ["dev"]},
    ])
    specs = load_route_manifest(path)
    assert [s.method for s in specs] == ["GET", "PUT"]
    assert specs[0].permission == "orders:read"
    assert specs[1].profile == {"dev"}


def test_duplicate_routes_are_rejected(tmp_path):
    path = _write(tmp_path, [
        {"method": "GET", "path": "/x"},
        {"method": "GET", "path": "/x"},
    ])
    assert any("duplicate route" in e for e in validate_route_manifest(path))


def test_invalid_method_reported(tmp_path):
    path = _write(tmp_path, [{"method": "FETCH", "path": "/x"}])
    assert any("invalid method" in e for e in validate_route_manifest(path))
