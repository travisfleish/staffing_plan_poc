from __future__ import annotations
import pandas as pd
import numpy as np
from typing import Dict, Any


def extract_contract_features(sow_df: pd.DataFrame) -> Dict[str, float]:
	df = sow_df.copy()
	if df.empty:
		return {"complexity_mean": 0.0, "workstream_count": 0, "estimated_hours": 0.0, "duration_months": 0.0}
	complexity_map = {"low": 1, "medium": 2, "high": 3}
	if df["complexity"].dtype == object:
		df["complexity_score"] = df["complexity"].str.lower().map(complexity_map).fillna(2)
	else:
		df["complexity_score"] = df["complexity"].fillna(2)
	return {
		"complexity_mean": float(df["complexity_score"].mean()),
		"workstream_count": int(df["workstream"].nunique()),
		"estimated_hours": float(df["estimated_hours"].sum()),
		"duration_months": float(df["duration_months"].max() if not df["duration_months"].isna().all() else 0),
	}


def features_from_ai(ai_summary: Dict[str, Any]) -> Dict[str, float]:
	complexity = {"low": 1, "medium": 2, "high": 3}.get(str(ai_summary.get("complexity_level", "medium")).lower(), 2)
	workstreams = int(ai_summary.get("workstream_count", 1) or 1)
	est_hours = float(ai_summary.get("estimated_total_hours", 0) or 0)
	duration = float(ai_summary.get("duration_months", 3) or 3)
	return {
		"complexity_mean": float(complexity),
		"workstream_count": workstreams,
		"estimated_hours": est_hours,
		"duration_months": duration,
	}
