from __future__ import annotations
import os
from typing import Dict, Any, List
import re

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


def extract_key_sections(text: str) -> Dict[str, str]:
	"""Extract key sections from SOW text that matter for staffing decisions."""
	sections = {}
	text_lower = text.lower()
	
	# Extract scope section (look for scope, objectives, work sections)
	scope_patterns = [
		r'scope[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)',
		r'objectives[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)',
		r'work[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)',
	]
	for pattern in scope_patterns:
		match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
		if match:
			sections["scope"] = match.group(1).strip()
			break
	
	# Extract business units (look for business unit mentions)
	business_unit_patterns = [
		r'creative|design|copy|content',
		r'experience|event|activation|production',
		r'client\s*services|account|project\s*management',
		r'data|analytics|insights|reporting',
		r'operations|process|workflow|enablement',
		r'sponsorship|strategy|partnership'
	]
	business_units = []
	for pattern in business_unit_patterns:
		if re.search(pattern, text_lower):
			business_units.append(pattern)
	sections["business_units"] = " ".join(business_units) if business_units else ""
	
	# Extract duration
	duration_match = re.search(r'(\d+)\s*(?:month|year|week)', text_lower)
	sections["duration"] = duration_match.group(1) if duration_match else ""
	
	# Extract deliverables
	deliverables_match = re.search(r'deliverables[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)', text, re.IGNORECASE | re.DOTALL)
	sections["deliverables"] = deliverables_match.group(1).strip() if deliverables_match else ""
	
	# Extract complexity indicators
	complexity_indicators = []
	if any(word in text_lower for word in ['integrated', 'global', 'multi', 'cross']):
		complexity_indicators.append('high')
	elif any(word in text_lower for word in ['regional', 'multi', 'cross']):
		complexity_indicators.append('medium')
	else:
		complexity_indicators.append('low')
	sections["complexity"] = " ".join(complexity_indicators)
	
	return sections


def embed_text_hybrid(text: str) -> List[float]:
	"""Hybrid embedding combining full text with key sections for better SOW similarity."""
	cli = _client()
	if cli is None:
		# Fallback to deterministic embedding
		import numpy as np
		rng = abs(hash(text)) % (10**6)
		return (np.ones(256) * (rng % 97) / 97.0).astype(float).tolist()
	
	# Extract key sections
	key_sections = extract_key_sections(text)
	
	# Create weighted embedding
	embeddings = []
	weights = []
	
	# Full text (truncated) - 40% weight
	full_text = text[:8000]
	full_resp = cli.embeddings.create(model=EMBED_MODEL, input=full_text)
	full_emb = full_resp.data[0].embedding
	embeddings.append(full_emb)
	weights.append(0.4)
	
	# Key sections - 60% weight distributed across sections
	section_weight = 0.6 / max(len([s for s in key_sections.values() if s]), 1)
	
	for section_name, section_text in key_sections.items():
		if section_text and len(section_text) > 10:  # Only use substantial sections
			section_resp = cli.embeddings.create(model=EMBED_MODEL, input=section_text[:4000])
			section_emb = section_resp.data[0].embedding
			embeddings.append(section_emb)
			weights.append(section_weight)
	
	# Weighted average of embeddings
	if len(embeddings) == 1:
		return embeddings[0]
	
	import numpy as np
	weighted_emb = np.zeros(len(embeddings[0]))
	for emb, weight in zip(embeddings, weights):
		weighted_emb += np.array(emb) * weight
	
	return weighted_emb.tolist()


def embed_text(text: str) -> List[float]:
	"""Enhanced embedding function using hybrid approach."""
	try:
		if not text or len(text.strip()) == 0:
			return []
		return embed_text_hybrid(text)
	except Exception as e:
		print(f"Embedding failed: {e}")
		return []


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
		"complexity_level (low|medium|high), duration_months (number), workstream_count (number), "
		"estimated_total_hours (number - estimate total staffing hours needed), key_deliverables (list of strings). "
		"Provide realistic estimates based on the scope and duration described."
	)
	resp = cli.chat.completions.create(
		model=DEFAULT_MODEL,
		messages=[{"role": "system", "content": prompt}, {"role": "user", "content": text[:12000]}],
		response_format={"type": "json_object"},
	)
	import json
	try:
		result = json.loads(resp.choices[0].message.content)
		# Validate and clean the response
		if not isinstance(result.get("estimated_total_hours"), (int, float)) or result.get("estimated_total_hours", 0) <= 0:
			result["estimated_total_hours"] = 800  # fallback
		if not isinstance(result.get("duration_months"), (int, float)) or result.get("duration_months", 0) <= 0:
			result["duration_months"] = 4  # fallback
		return result
	except Exception:
		return {"complexity_level": "medium", "duration_months": 4, "workstream_count": 2, "estimated_total_hours": 800}


def test_embedding_improvement():
	"""Test function to compare old vs new embedding approaches."""
	# Test with sample SOW text
	sample_text = """Statement of Work (SOW)
Client: Delta Airlines
Agency: Apex Sports & Entertainment Creative
Engagement Type: Cross-Functional, Year-long Integrated Retainer
Duration: 12 months

Objectives:
- Provide ongoing, integrated support across Sponsorship Strategy, Creative, Experience, Client Services, Data, and Operations
- Plan and execute campaign cycles aligned to sports partnerships and brand milestones
- Measure performance and continuously optimize content and activation plans

Scope (Cross-Functional):
1) Sponsorship Strategy: portfolio planning, rights valuation, activation roadmaps
2) Creative: concepting, design, copywriting, production of multi-format content
3) Experience: event activations, production, logistics, content capture
4) Client Services: governance, planning cadence, cross-team PMO
5) Data & Analytics: dashboards, insights, experimentation summaries
6) Operations: workflow enablement, SOPs, training

Deliverables:
- Quarterly integrated plans; creative toolkits; activation playbooks; content packages; KPI dashboards; executive reports"""
	
	print("=== TESTING EMBEDDING IMPROVEMENT ===")
	print(f"Sample text length: {len(sample_text)} characters")
	
	# Extract key sections
	key_sections = extract_key_sections(sample_text)
	print(f"\nExtracted key sections:")
	for name, content in key_sections.items():
		print(f"  {name}: {content[:100]}{'...' if len(content) > 100 else ''}")
	
	# Test hybrid embedding
	try:
		hybrid_emb = embed_text_hybrid(sample_text)
		print(f"\nHybrid embedding successful: {len(hybrid_emb)} dimensions")
	except Exception as e:
		print(f"\nHybrid embedding failed: {e}")
	
	print("=== END TEST ===")


# Uncomment to test: test_embedding_improvement()
