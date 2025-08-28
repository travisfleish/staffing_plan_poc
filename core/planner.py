from __future__ import annotations
import math
from typing import Dict, Any, Optional
import pandas as pd

from .features import extract_contract_features
from .constraints import get_utilization_target, min_team_by_project_type
from .calibration import calculate_calibrated_baseline


def _estimate_role_hours_from_total(total_hours: float, weights_cfg: Dict[str, Any], mix_override: Optional[Dict[str, float]] = None) -> Dict[str, float]:
	mix = mix_override if mix_override is not None else weights_cfg.get("role_mix", {"manager": 0.15, "senior": 0.45, "junior": 0.4})
	return {role: float(total_hours) * float(pct) for role, pct in mix.items()}


def _apply_constraints(role_hours: Dict[str, float], features: Dict[str, float], roles_cfg: Dict[str, Any], weights_cfg: Dict[str, Any], max_team_size: int) -> pd.DataFrame:
	project_type = features.get("project_type", weights_cfg.get("default_project_type", "project"))
	minimums = min_team_by_project_type(project_type, weights_cfg)
	rows = []
	duration_months = max(int(math.ceil(features.get("duration_months", 1) or 1)), 1)
	# Convert months to weeks: 1 month = 4.33 weeks (52 weeks / 12 months)
	weeks = max(int(duration_months * 4.33), 4)
	for role, hours in role_hours.items():
		util = get_utilization_target(role, roles_cfg)
		fte_weeks = hours / (util * 40.0) if util > 0 else 0
		num_people = max(1, int(math.ceil(fte_weeks / weeks)))
		num_people = max(num_people, int(minimums.get(role, 0)))
		# Use the actual role name instead of generic categorization
		seniority_level = "senior" if role in ("creative_director", "designer", "account_manager", "project_manager") else "junior"
		rows.append({
			"role": role,
			"planned_hours": round(hours),  # Round to whole numbers
			"fte": round(fte_weeks / weeks, 2),
			"start_week": 1,
			"end_week": weeks,
			"seniority_level": seniority_level,
			"num_people": num_people,
		})
	rows = sorted(rows, key=lambda r: -r["planned_hours"])[:max_team_size]
	return pd.DataFrame(rows)


def _compute_dynamic_role_mix(similar_neighbors: Optional[pd.DataFrame], historical_data: Optional[pd.DataFrame], *, similarity_threshold: float, min_similar_contracts: int) -> Optional[Dict[str, float]]:
	if similar_neighbors is None or historical_data is None or similar_neighbors.empty or historical_data.empty:
		print(f"DEBUG: Early return - neighbors: {similar_neighbors is not None and not similar_neighbors.empty}, historical: {historical_data is not None and not historical_data.empty}")
		return None
	neighbors = similar_neighbors.copy()
	if "distance" not in neighbors.columns:
		print("DEBUG: No distance column in neighbors")
		return None
	
	print(f"DEBUG: Initial neighbors count: {len(neighbors)}")
	print(f"DEBUG: Similarity threshold: {similarity_threshold}")
	print(f"DEBUG: Min similar contracts: {min_similar_contracts}")
	
	# Compute similarity and filter
	neighbors = neighbors.assign(sim=lambda d: 1.0 / (1.0 + d["distance"].astype(float)))
	print(f"DEBUG: Similarity scores: {neighbors['sim'].tolist()}")
	
	if similarity_threshold is not None and similarity_threshold > 0:
		neighbors = neighbors.loc[neighbors["sim"] >= float(similarity_threshold)].copy()
		print(f"DEBUG: After similarity filtering: {len(neighbors)} neighbors")
	
	if neighbors.empty:
		print("DEBUG: No neighbors after similarity filtering")
		return None
		
	# Aggregate historical hours by contract and role
	hist = historical_data.copy()
	if not {"contract_id", "role", "actual_hours"}.issubset(set(hist.columns)):
		print(f"DEBUG: Missing columns in historical data: {set(hist.columns)}")
		return None
		
	# Use the hardcoded mapping from app.py instead of regex extraction
	HIST_SOW_TO_CONTRACT = {
		"[SOW-X-300] Delta Airlines Integrated Retainer (C-300)": "C-300",
		"[SOW-X-301] Global Beverage Brand Integrated Retainer (C-301)": "C-301",
		"[SOW-X-302] Telecom Co. Integrated Retainer (C-302)": "C-302",
		"[SOW-X-303] Consumer Electronics Integrated Retainer (C-303)": "C-303",
		"[SOW-X-304] Financial Services Integrated Retainer (C-304)": "C-304",
		"[SOW-X-305] Streaming Platform Integrated Retainer (C-305)": "C-305",
		"[SOW-X-306] National Retailer Integrated Retainer (C-306)": "C-306",
		"[SOW-X-307] Airline Alliance Integrated Retainer (C-307)": "C-307",
		"[SOW-X-308] Automotive Brand Integrated Retainer (C-308)": "C-308",
		"[SOW-X-309] Apparel Brand Integrated Retainer (C-309)": "C-309",
		"[SOW-X-310] Tech Manufacturer Integrated Retainer (C-310)": "C-310",
	}
	
	neighbors["contract_id"] = neighbors["id"].astype(str).apply(lambda x: HIST_SOW_TO_CONTRACT.get(x.strip(), x.strip()))
	
	# Debug: print what we extracted
	print(f"DEBUG: Extracted contract IDs: {neighbors['contract_id'].tolist()}")
	print(f"DEBUG: Available historical contract IDs: {hist['contract_id'].unique().tolist()}")
	
	weights = neighbors.groupby("contract_id", dropna=False)["sim"].max().reset_index()
	print(f"DEBUG: Contract weights: {weights.to_dict('records')}")
	
	# Join hours with weights
	merged = hist.merge(weights, how="inner", on="contract_id")
	print(f"DEBUG: After merge with historical data: {len(merged)} rows")
	
	if merged.empty:
		print("DEBUG: No data after merging with historical data")
		return None
		
	# Compute total hours per contract and weighted role hours
	contract_totals = merged.groupby("contract_id", dropna=False)["actual_hours"].sum().rename("total_hours").reset_index()
	merged = merged.merge(contract_totals, on="contract_id", how="left")
	
	# Weighted role shares contributed by each contract
	merged["weighted_role_hours"] = merged["actual_hours"].astype(float) * merged["sim"].astype(float)
	merged["weighted_total_hours"] = merged["total_hours"].astype(float) * merged["sim"].astype(float)
	
	# Ensure sufficient distinct contracts
	distinct_contracts = merged["contract_id"].nunique()
	print(f"DEBUG: Distinct contracts found: {distinct_contracts}")
	
	if distinct_contracts < int(min_similar_contracts):
		print(f"DEBUG: Not enough distinct contracts: {distinct_contracts} < {min_similar_contracts}")
		return None
		
	# Aggregate across contracts
	role_hours = merged.groupby("role", dropna=False)["weighted_role_hours"].sum()
	total_hours = float(merged["weighted_total_hours"].sum())
	print(f"DEBUG: Role hours: {role_hours.to_dict()}")
	print(f"DEBUG: Total hours: {total_hours}")
	
	if total_hours <= 0:
		print("DEBUG: Total hours <= 0")
		return None
		
	mix = (role_hours / total_hours).fillna(0.0).to_dict()
	# Normalize to sum to 1.0 and drop zero/negative
	mix = {str(r).strip(): float(p) for r, p in mix.items() if float(p) > 0}
	s = sum(mix.values())
	if s <= 0:
		print("DEBUG: Mix sum <= 0")
		return None
	mix = {r: p / s for r, p in mix.items()}
	print(f"DEBUG: Final role mix: {mix}")
	return mix if mix else None


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
		min_similar_contracts=int(cal_cfg.get("min_similar_contracts", 1)),
		similarity_threshold=float(cal_cfg.get("similarity_threshold", 0.3)),
		fallback_strategy=str(cal_cfg.get("fallback_strategy", "conservative")),
	)
	baseline_total = max(cal.get("blended_baseline", ai_guess), 0.0)

	# Dynamic role mix from similar historical contracts (fallback to configured mix)
	dyn_mix = _compute_dynamic_role_mix(
		similar_neighbors,
		historical_data,
		similarity_threshold=float(cal_cfg.get("similarity_threshold", 0.3)),
		min_similar_contracts=int(cal_cfg.get("min_similar_contracts", 1)),
	)
	role_hours = _estimate_role_hours_from_total(baseline_total, weights_cfg, mix_override=dyn_mix)
	plan = _apply_constraints(role_hours, features, roles_cfg, weights_cfg, max_team_size)
	plan.insert(0, "contract_id", contract_id)
	# Attach calibration and role mix debug info
	cal_debug = dict(cal)
	# Round role mix percentages to 2 decimal places for cleaner display
	if dyn_mix is not None:
		rounded_mix = {role: round(percentage, 2) for role, percentage in dyn_mix.items()}
		cal_debug["role_mix_used"] = rounded_mix
	else:
		# Round configured role mix as well
		config_mix = weights_cfg.get("role_mix", {})
		rounded_config_mix = {role: round(percentage, 2) for role, percentage in config_mix.items()}
		cal_debug["role_mix_used"] = rounded_config_mix
	plan._calibration_debug = cal_debug  # type: ignore
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
