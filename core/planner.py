from __future__ import annotations
import math
from typing import Dict, Any, Optional
import pandas as pd

from .features import extract_contract_features
from .constraints import get_utilization_target, min_team_by_project_type
from .calibration import calculate_calibrated_baseline


def _estimate_role_hours_from_total(total_hours: float, weights_cfg: Dict[str, Any]) -> Dict[str, float]:
	mix = weights_cfg.get("role_mix", {"manager": 0.15, "senior": 0.45, "junior": 0.4})
	return {role: float(total_hours) * pct for role, pct in mix.items()}


def _apply_constraints(role_hours: Dict[str, float], features: Dict[str, float], roles_cfg: Dict[str, Any], weights_cfg: Dict[str, Any], max_team_size: int) -> pd.DataFrame:
	project_type = weights_cfg.get("default_project_type", "project")
	minimums = min_team_by_project_type(project_type, weights_cfg)
	rows = []
	duration_months = max(int(math.ceil(features.get("duration_months", 1) or 1)), 1)
	weeks = max(duration_months * 4, 4)
	for role, hours in role_hours.items():
		util = get_utilization_target(role, roles_cfg)
		fte_weeks = hours / (util * 40.0) if util > 0 else 0
		num_people = max(1, int(math.ceil(fte_weeks / weeks)))
		num_people = max(num_people, int(minimums.get(role, 0)))
		rows.append({
			"role": role,
			"planned_hours": round(hours, 1),
			"fte": round(fte_weeks / weeks, 2),
			"start_week": 1,
			"end_week": weeks,
			"seniority_level": "senior" if role in ("senior", "manager", "partner") else "junior",
			"num_people": num_people,
		})
	rows = sorted(rows, key=lambda r: -r["planned_hours"])[:max_team_size]
	return pd.DataFrame(rows)


def generate_staffing_plan(
	contract_id: str,
	sow_df: pd.DataFrame,
	roles_cfg: Dict[str, Any],
	weights_cfg: Dict[str, Any],
	duration_multiplier: float = 1.0,
	scope_multiplier: float = 1.0,
	max_team_size: int = 8,
	features_override: Optional[Dict[str, float]] = None,
	historical_data: Optional[pd.DataFrame] = None,
	similar_neighbors: Optional[pd.DataFrame] = None,
	ai_total_estimate: Optional[float] = None,
) -> pd.DataFrame:
	if features_override is not None:
		features = dict(features_override)
	else:
		contract_sow = sow_df[sow_df["contract_id"] == contract_id]
		features = extract_contract_features(contract_sow)
	features["estimated_hours"] = max(features.get("estimated_hours", 0.0), 0.0) * max(scope_multiplier, 0.1)
	features["duration_months"] = max(features.get("duration_months", 1.0), 0.1) * max(duration_multiplier, 0.1)

	cal_cfg = (weights_cfg or {}).get("calibration", {})
	ai_guess = float(ai_total_estimate) if ai_total_estimate is not None else float(features.get("estimated_hours", 0.0))
	cal = calculate_calibrated_baseline(
		features,
		similar_neighbors if similar_neighbors is not None else pd.DataFrame(),
		ai_guess,
		historical_data if historical_data is not None else pd.DataFrame(),
		ai_confidence=float(cal_cfg.get("ai_confidence", 0.3)),
		historical_confidence=float(cal_cfg.get("historical_confidence", 0.7)),
		min_similar_contracts=int(cal_cfg.get("min_similar_contracts", 2)),
		similarity_threshold=float(cal_cfg.get("similarity_threshold", 0.8)),
		fallback_strategy=str(cal_cfg.get("fallback_strategy", "conservative")),
	)
	baseline_total = max(cal.get("blended_baseline", ai_guess), 0.0)

	role_hours = _estimate_role_hours_from_total(baseline_total, weights_cfg)
	plan = _apply_constraints(role_hours, features, roles_cfg, weights_cfg, max_team_size)
	plan.insert(0, "contract_id", contract_id)
	plan._calibration_debug = cal  # type: ignore
	return plan


def compare_plan_vs_actual(plan_df: pd.DataFrame, hours_df: pd.DataFrame) -> pd.DataFrame:
	if plan_df.empty or hours_df.empty:
		return pd.DataFrame()
	actuals = hours_df.groupby(["contract_id", "role"], dropna=False)["actual_hours"].sum().reset_index()
	plan_sum = plan_df.groupby(["contract_id", "role"], dropna=False)["planned_hours"].sum().reset_index()
	merged = plan_sum.merge(actuals, on=["contract_id", "role"], how="left").fillna({"actual_hours": 0})
	merged["variance_hours"] = merged["planned_hours"] - merged["actual_hours"]
	merged["variance_pct"] = merged.apply(lambda r: (r["variance_hours"] / r["actual_hours"]) * 100 if r["actual_hours"] > 0 else 100.0, axis=1)
	return merged
