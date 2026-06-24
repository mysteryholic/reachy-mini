from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from reachy_robotis.robotis_interface.core.paths import project_path
from reachy_robotis.robotis_interface.core.action_catalog import ActionCatalog, ActionDefinition
from reachy_robotis.robotis_interface.core.recipe_catalog import CommandRecipe, RecipeCatalog
from reachy_robotis.robotis_interface.core.connection_registry import ConnectionRegistry
from reachy_robotis.robotis_interface.core.yaml_loader import dump_mapping, load_mapping


class ProductPresetCatalog:
    """Load ROBOTIS product defaults and generate runtime catalog entries."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or project_path("config", "robotis_product_presets.yaml")
        self._products: dict[str, dict[str, Any]] = {}
        self.reload()

    def reload(self) -> None:
        data = load_mapping(self.path)
        products = data.get("products") or {}
        if not isinstance(products, dict):
            raise ValueError("products must be a mapping")
        self._products = {str(product_id): dict(value or {}) for product_id, value in products.items()}

    def list_products(self) -> dict[str, dict[str, Any]]:
        return deepcopy(self._products)

    def get(self, product_id: str) -> dict[str, Any] | None:
        product = self._products.get(product_id)
        return deepcopy(product) if product is not None else None

    def public_products(self, connections: ConnectionRegistry | None = None) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for product_id, product in self._products.items():
            connection_id = str(product.get("connection_id") or product_id)
            profile = connections.get(connection_id) if connections is not None else None
            result.append(
                {
                    "product_id": product_id,
                    "display_name": str(product.get("display_name") or product_id),
                    "connection_id": connection_id,
                    "host": profile.host if profile else "",
                    "port": profile.port if profile else 22,
                    "user": profile.user if profile else str(product.get("default_user") or ""),
                    "auth_method": profile.auth_method if profile else "password",
                    "key_path": profile.key_path if profile else "",
                    "workflows": [
                        {
                            "workflow_id": workflow_id,
                            "display_name": str(workflow.get("display_name") or workflow_id),
                            "description": str(workflow.get("description") or ""),
                        }
                        for workflow_id, workflow in (product.get("workflows") or {}).items()
                    ],
                }
            )
        return result

    def connection_payload(
        self,
        product_id: str,
        *,
        host: str = "",
        port: int = 22,
        user: str = "",
        auth: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        product = self._require_product(product_id)
        docker = dict(product.get("docker") or {})
        ros = dict(product.get("ros") or {})
        container_names = list(docker.get("container_name_candidates") or [])
        helper_scripts = list(docker.get("helper_script_candidates") or [])
        connection_id = str(product.get("connection_id") or product_id)
        return connection_id, {
            "display_name": str(product.get("display_name") or product_id),
            "target": product_id,
            "transport": str(product.get("default_transport") or "ssh_docker"),
            "host": host,
            "fallback_hosts": [],
            "port": int(port or 22),
            "user": user or str(product.get("default_user") or ""),
            "auth": dict(auth or {"method": "password"}),
            "working_dir": str(product.get("default_working_dir") or ""),
            "container": {
                "mode": str(docker.get("mode") or "docker_exec"),
                "name": str(docker.get("container_name") or (container_names[0] if container_names else "")),
                "helper_script": str(docker.get("helper_script") or (helper_scripts[0] if helper_scripts else "")),
                "exec_shell": "bash -lc",
            },
            "ros": {
                "distro": str(ros.get("distro") or ""),
                "setup": list(ros.get("setup") or []),
                "env": dict(ros.get("env") or {}),
            },
        }

    def recipes(self) -> list[CommandRecipe]:
        recipes: list[CommandRecipe] = []
        for product_id, product in self._products.items():
            connection_id = str(product.get("connection_id") or product_id)
            for workflow_id, workflow in (product.get("workflows") or {}).items():
                data = dict(workflow or {})
                terminals = []
                for terminal in data.get("terminals") or []:
                    item = dict(terminal or {})
                    item.setdefault("display_name", item.get("terminal_id"))
                    item.setdefault("connection_id", connection_id)
                    item.setdefault("command_type", "container")
                    item.setdefault("required", True)
                    terminals.append(item)
                data["device"] = product_id
                data["terminals"] = terminals
                recipes.append(CommandRecipe.from_mapping(str(workflow_id), data))
        return recipes

    def actions(self) -> list[ActionDefinition]:
        return [
            ActionDefinition.from_mapping(
                {
                    "name": recipe.recipe_id,
                    "display_name": recipe.display_name,
                    "kind": "recipe",
                    "device": recipe.device,
                    "triggers": recipe.triggers,
                    "run": {"method": "start_recipe", "recipe_id": recipe.recipe_id},
                }
            )
            for recipe in self.recipes()
        ]

    def install(
        self,
        connections: ConnectionRegistry,
        recipes: RecipeCatalog,
        actions: ActionCatalog,
    ) -> None:
        """Overlay generated preset entries while preserving user host/auth data."""
        for product_id in self._products:
            connection_id, payload = self.connection_payload(product_id)
            connections.apply_preset(connection_id, payload)
        recipes.install_presets(self.recipes())
        actions.install_presets(self.actions())

    def update_workflow(self, product_id: str, workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Persist expert command edits back to the single preset source."""
        product = self._products.get(product_id)
        if product is None:
            raise KeyError(f"Unknown product preset: {product_id}")
        workflows = product.get("workflows") or {}
        if workflow_id not in workflows:
            raise KeyError(f"Unknown workflow preset: {workflow_id}")
        workflow = dict(workflows[workflow_id] or {})
        triggers = payload.get("triggers")
        if triggers is not None:
            if not isinstance(triggers, list):
                raise ValueError("Workflow triggers must be a list.")
            clean_triggers = [str(item).strip() for item in triggers if str(item).strip()]
            if not clean_triggers:
                raise ValueError("Preset workflow requires at least one trigger.")
            workflow["triggers"] = clean_triggers
        terminals = payload.get("terminals")
        if not isinstance(terminals, list) or not terminals:
            raise ValueError("Preset workflow requires at least one terminal.")
        workflow["terminals"] = [dict(item or {}) for item in terminals]
        workflows[workflow_id] = workflow
        product["workflows"] = workflows
        dump_mapping(self.path, {"products": self._products})
        self.reload()
        return deepcopy(workflow)

    def _require_product(self, product_id: str) -> dict[str, Any]:
        product = self.get(product_id)
        if product is None:
            raise KeyError(f"Unknown product preset: {product_id}")
        return product
