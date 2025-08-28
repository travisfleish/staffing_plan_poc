from __future__ import annotations
from pathlib import Path
from typing import Dict, Any
import yaml

ROLE_HIERARCHY = ["junior", "senior", "manager", "partner"]


def load_yaml(path: Path) -> Dict[str, Any]:
	with path.open("r") as f:
		return yaml.safe_load(f) or {}


def load_configs(roles_path: Path, weights_path: Path):
	roles_cfg = load_yaml(roles_path)
	weights_cfg = load_yaml(weights_path)
	return roles_cfg, weights_cfg


def get_utilization_target(role: str, roles_cfg: Dict[str, Any]) -> float:
	return float(roles_cfg.get("utilization_targets", {}).get(role.lower(), 0.8))


def get_rate(role: str, seniority: str, roles_cfg: Dict[str, Any]) -> float:
	return float(roles_cfg.get("rates", {}).get(role.lower(), {}).get(seniority.lower(), roles_cfg.get("default_rate", 200)))


def min_team_by_project_type(project_type: str, weights_cfg: Dict[str, Any]) -> Dict[str, int]:
	return weights_cfg.get("min_team_composition", {}).get(project_type.lower(), {"manager": 1, "senior": 1})
