"""
JSON manifest support for TENANT route seeding.

Apps declare their guarded routes as JSON instead of Python ``RouteSpec``
lists. ``load_route_manifest`` builds the typed specs; ``validate_route_manifest``
returns structural errors for CI (duplicate routes, invalid methods, ...).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .route_seeder import RouteSpec

VALID_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
VALID_PROFILES = {"dev", "prod", "staging", "test"}


def _read(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _entries(data: Any) -> list[Any]:
    if isinstance(data, dict):
        data = data.get("routes", [])
    return data if isinstance(data, list) else []


def validate_route_manifest(path: str | Path) -> list[str]:
    """Validate a GLOBAL route JSON manifest; returns a list of errors."""
    try:
        data = _read(path)
    except FileNotFoundError:
        return [f"route manifest not found: {path}"]
    except Exception as exc:  # noqa: BLE001 - surface parse errors
        return [f"invalid JSON: {exc}"]

    entries = _entries(data)
    if not entries:
        return ["route manifest has no routes"]

    errors: list[str] = []
    seen: set[tuple[str, str]] = set()

    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            errors.append(f"route[{index}] must be an object")
            continue
        method = str(item.get("method", "")).upper()
        route_path = item.get("path")
        if method not in VALID_METHODS:
            errors.append(f"route[{index}] invalid method {item.get('method')!r}")
        if not route_path or not isinstance(route_path, str):
            errors.append(f"route[{index}] missing 'path'")
        key = (method, str(route_path))
        if key in seen:
            errors.append(f"duplicate route {method} {route_path}")
        seen.add(key)

        permission = item.get("permission")
        if permission is not None and not isinstance(permission, str):
            errors.append(f"route[{index}] 'permission' must be a string or null")
        roles = item.get("roles", [])
        if not isinstance(roles, list) or any(not isinstance(r, str) for r in roles):
            errors.append(f"route[{index}] 'roles' must be a list of strings")
        profile = item.get("profile", ["dev", "prod"])
        if not isinstance(profile, list) or any(p not in VALID_PROFILES for p in profile):
            errors.append(f"route[{index}] invalid 'profile' {profile!r}")

    return errors


def load_route_manifest(
    path: str | Path,
    *,
    validate: bool = True,
) -> list[RouteSpec]:
    """Load a JSON route manifest into typed ``RouteSpec`` objects."""
    if validate:
        errors = validate_route_manifest(path)
        if errors:
            raise ValueError(
                f"Invalid route manifest '{path}': " + "; ".join(errors)
            )

    entries = _entries(_read(path))
    specs: list[RouteSpec] = []
    for item in entries:
        specs.append(
            RouteSpec(
                method=str(item["method"]).upper(),
                path=str(item["path"]),
                permission=item.get("permission"),
                roles=list(item.get("roles", [])),
                profile=set(item.get("profile", ["dev", "prod"])),
            )
        )
    return specs


__all__ = [
    "VALID_METHODS",
    "VALID_PROFILES",
    "load_route_manifest",
    "validate_route_manifest",
]
