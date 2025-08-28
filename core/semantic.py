from __future__ import annotations
import os
from typing import Dict, Any, List

try:
	from openai import OpenAI
except Exception:
	OpenAI = None

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")


def _client():
	key = os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_API_KEY")
	if not key or OpenAI is None:
		return None
	return OpenAI(api_key=key)


def embed_text(text: str) -> List[float]:
	cli = _client()
	if cli is None:
		import numpy as np
		rng = abs(hash(text)) % (10**6)
		return (np.ones(256) * (rng % 97) / 97.0).astype(float).tolist()
	resp = cli.embeddings.create(model=EMBED_MODEL, input=text[:8000])
	return resp.data[0].embedding


def analyze_sow_text(text: str) -> Dict[str, Any]:
	cli = _client()
	if cli is None:
		lower = text.lower()
		complexity = "high" if ("integrated" in lower or "global" in lower) else ("medium" if "cross" in lower else "low")
		return {
			"complexity_level": complexity,
			"duration_months": 6 if "annual" in lower else 4,
			"workstream_count": 3 if ("creative" in lower and "social" in lower and "production" in lower) else 2,
			"estimated_total_hours": 1200 if complexity == "high" else (800 if complexity == "medium" else 500),
			"key_deliverables": ["campaign concepting", "social content", "event activation"],
		}
	prompt = (
		"You are a staffing planner. Read the SOW text and return JSON with: "
		"complexity_level (low|medium|high), duration_months, workstream_count, estimated_total_hours, key_deliverables (list)."
	)
	resp = cli.chat.completions.create(
		model=DEFAULT_MODEL,
		messages=[{"role": "system", "content": prompt}, {"role": "user", "content": text[:12000]}],
		response_format={"type": "json_object"},
	)
	import json
	try:
		return json.loads(resp.choices[0].message.content)
	except Exception:
		return {"complexity_level": "medium", "duration_months": 4, "workstream_count": 2, "estimated_total_hours": 800}
