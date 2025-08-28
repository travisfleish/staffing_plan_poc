from __future__ import annotations
import logging
from typing import Dict, Optional
import pandas as pd

logger = logging.getLogger(__name__)


def get_actual_hours_for_contract(contract_id: str, historical_data: pd.DataFrame) -> float:
	try:
		if historical_data is None or historical_data.empty:
			return 0.0
		return float(historical_data.loc[historical_data["contract_id"] == contract_id, "actual_hours"].sum())
	except Exception as exc:
		logger.exception("Historical aggregation failed: %s", exc)
		return 0.0


def _weighted_historical_baseline(similar_contracts: pd.DataFrame, historical_data: pd.DataFrame) -> Optional[float]:
	if similar_contracts is None or similar_contracts.empty or historical_data is None or historical_data.empty:
		return None
	
	# Use the same contract ID mapping as in planner.py
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
	
	usable = []
	for _, row in similar_contracts.iterrows():
		sow_id = str(row.get("id", "")).strip()
		dist = float(row.get("distance", 0.0) or 0.0)
		if not sow_id:
			continue
		
		# Extract contract ID from SOW ID
		contract_id = HIST_SOW_TO_CONTRACT.get(sow_id, sow_id)
		
		actual = get_actual_hours_for_contract(contract_id, historical_data)
		if actual <= 0:
			continue
		w = 1.0 / (1.0 + dist)
		usable.append((actual, w))
	if not usable:
		return None
	numer = sum(a * w for a, w in usable)
	denom = sum(w for _, w in usable)
	return float(numer / denom) if denom else None


def calculate_ai_bias_correction(similar_contracts: pd.DataFrame, historical_data: pd.DataFrame) -> float:
	return 1.0


def calculate_calibrated_baseline(
	features: Dict,
	similar_contracts: pd.DataFrame,
	ai_estimate: float,
	historical_data: pd.DataFrame,
	*,
	ai_confidence: float = 0.3,
	historical_confidence: float = 0.7,
	min_similar_contracts: int = 2,
	similarity_threshold: float = 0.3,
	fallback_strategy: str = "conservative",
) -> Dict[str, float]:
	ai_estimate = float(ai_estimate or 0.0)
	neighbors = similar_contracts.copy() if similar_contracts is not None else pd.DataFrame()
	if not neighbors.empty and "distance" in neighbors.columns and similarity_threshold is not None:
		neighbors = neighbors.assign(sim=lambda d: 1.0 / (1.0 + d["distance"].astype(float)))
		neighbors = neighbors.loc[neighbors["sim"] >= similarity_threshold].copy() if similarity_threshold > 0 else neighbors
	baseline_hist = _weighted_historical_baseline(neighbors if not neighbors.empty else similar_contracts, historical_data)
	bias = calculate_ai_bias_correction(neighbors if not neighbors.empty else similar_contracts, historical_data)
	corrected_ai = ai_estimate * float(bias)
	use_hist = baseline_hist is not None and (neighbors is not None and len(neighbors) >= int(min_similar_contracts))
	if use_hist:
		ai_w = max(0.0, min(1.0, float(ai_confidence)))
		h_w = max(0.0, min(1.0, float(historical_confidence)))
		if ai_w + h_w == 0:
			ai_w, h_w = 0.3, 0.7
		blended = ai_w * corrected_ai + h_w * float(baseline_hist)
		return {"ai_estimate": ai_estimate, "hist_baseline": float(baseline_hist), "corrected_ai": float(corrected_ai), "blended_baseline": float(blended), "strategy": "blended"}
	if fallback_strategy == "conservative":
		fallback_val = min([v for v in [ai_estimate, baseline_hist] if v is not None]) if baseline_hist is not None else ai_estimate
	else:
		fallback_val = ai_estimate if ai_estimate > 0 else (baseline_hist or 0.0)
	return {"ai_estimate": ai_estimate, "hist_baseline": float(baseline_hist) if baseline_hist is not None else 0.0, "corrected_ai": float(corrected_ai), "blended_baseline": float(fallback_val), "strategy": "fallback"}
