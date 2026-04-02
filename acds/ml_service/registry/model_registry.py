"""
model_registry.py — File-based model versioning and lifecycle management.

Stores metadata in a JSON registry file. Each version tracks model paths,
metrics, timestamps, and active/inactive status.
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

log = logging.getLogger("ml_service.registry.model_registry")

DEFAULT_REGISTRY_PATH = os.path.join(
    os.path.dirname(__file__), "model_registry.json"
)


class ModelRegistry:
    """JSON-backed model registry with versioning and activation control."""

    def __init__(self, registry_path: Optional[str] = None):
        self.registry_path = registry_path or DEFAULT_REGISTRY_PATH
        self._registry: Dict[str, Any] = self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(
        self,
        version: str,
        model_paths: Dict[str, str],
        metrics: Optional[Dict[str, float]] = None,
        description: str = "",
        set_active: bool = False,
    ) -> Dict[str, Any]:
        """
        Register a new model version.

        Parameters
        ----------
        version      : e.g. "v1.0", "v2.1"
        model_paths  : dict mapping model_name -> file path
        metrics      : dict of evaluation metrics
        description  : human-readable description
        set_active   : if True, make this the active version
        """
        entry = {
            "version": version,
            "model_paths": model_paths,
            "metrics": metrics or {},
            "description": description,
            "registered_at": time.time(),
            "is_active": False,
        }

        self._registry["versions"][version] = entry

        if set_active:
            self._set_active(version)

        self._save()
        log.info("Registered model version %s", version)
        return entry

    def get_active(self) -> Optional[Dict[str, Any]]:
        """Return the currently active model version entry, or None."""
        active_version = self._registry.get("active_version")
        if active_version and active_version in self._registry["versions"]:
            return self._registry["versions"][active_version]
        return None

    def get_active_version(self) -> Optional[str]:
        """Return the active version string, or None."""
        return self._registry.get("active_version")

    def switch_active(self, version: str) -> Dict[str, Any]:
        """Set a different version as active."""
        if version not in self._registry["versions"]:
            raise KeyError(f"Version '{version}' not found in registry.")
        self._set_active(version)
        self._save()
        log.info("Switched active model to %s", version)
        return self._registry["versions"][version]

    def get_version(self, version: str) -> Optional[Dict[str, Any]]:
        """Get a specific version entry."""
        return self._registry["versions"].get(version)

    def list_versions(self) -> List[Dict[str, Any]]:
        """Return all registered versions, sorted by registration time."""
        versions = list(self._registry["versions"].values())
        versions.sort(key=lambda v: v.get("registered_at", 0))
        return versions

    def remove_version(self, version: str) -> bool:
        """Remove a version from the registry. Cannot remove the active version."""
        if version == self._registry.get("active_version"):
            raise ValueError("Cannot remove the active model version. Switch first.")
        if version in self._registry["versions"]:
            del self._registry["versions"][version]
            self._save()
            log.info("Removed model version %s", version)
            return True
        return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _set_active(self, version: str) -> None:
        # Deactivate all
        for v in self._registry["versions"].values():
            v["is_active"] = False
        self._registry["versions"][version]["is_active"] = True
        self._registry["active_version"] = version

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, "r") as f:
                    data = json.load(f)
                log.info("Loaded model registry from %s", self.registry_path)
                return data
            except (json.JSONDecodeError, IOError) as e:
                log.warning("Failed to load registry (%s), starting fresh.", e)
        return {"active_version": None, "versions": {}}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.registry_path), exist_ok=True)
        with open(self.registry_path, "w") as f:
            json.dump(self._registry, f, indent=2)
