from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd


def load_csv(file_like) -> pd.DataFrame:
	if file_like is None:
		raise ValueError("file_like must not be None")
	if hasattr(file_like, "read"):
		return pd.read_csv(file_like)
	return pd.read_csv(file_like)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
	df = df.copy()
	df.columns = [str(c).strip().lower() for c in df.columns]
	return df


def load_text(file_like) -> str:
	if hasattr(file_like, "read"):
		return file_like.read().decode("utf-8")
	p = Path(str(file_like))
	return p.read_text(encoding="utf-8")


class InMemoryVectorIndex:
	def __init__(self):
		self.items: List[Dict[str, Any]] = []

	def add(self, item_id: str, text: str, embedding: List[float]):
		self.items.append({"id": item_id, "text": text, "embedding": embedding})

	def search(self, query_embedding: List[float], top_k: int = 5):
		import numpy as np
		if not self.items:
			return []
		q = np.array(query_embedding, dtype=float)
		rows = []
		for it in self.items:
			e = np.array(it["embedding"], dtype=float)
			d = float(np.linalg.norm(q - e))
			rows.append({"id": it["id"], "text": it["text"], "distance": d})
		rows.sort(key=lambda r: r["distance"])
		return rows[:top_k]
