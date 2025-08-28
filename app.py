import streamlit as st
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

from core.io_layer import load_csv, normalize_columns, load_text, InMemoryVectorIndex
from core.features import features_from_ai
from core.planner import generate_staffing_plan, compare_plan_vs_actual
from core.constraints import load_configs
from core.semantic import analyze_sow_text, embed_text

load_dotenv()

st.set_page_config(page_title="Staffing Plan Generator", layout="wide")

DATA_SCHEMAS = {
	"Staffing": "contract_id,role,planned_hours,fte,start_week,end_week,seniority_level",
	"Hours": "contract_id,person_id,role,week_start,actual_hours,utilization_pct",
}

HIST_SOW_TO_CONTRACT = {
	# Map SOW IDs from sow_historicals.txt to contract IDs
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

@st.cache_data
def get_configs():
	return load_configs(Path("config/roles.yaml"), Path("config/weights.yaml"))

@st.cache_resource
def build_vector_index(embedding_model: str = None) -> InMemoryVectorIndex:
	idx = InMemoryVectorIndex()
	# Parse sow_historicals.txt to build index from cross-functional SOWs
	sow_historicals_path = Path("samples/sow_historicals.txt")
	if sow_historicals_path.exists():
		content = sow_historicals_path.read_text(encoding="utf-8")
		# Split by SOW entries (lines starting with [SOW-)
		sow_entries = []
		current_entry = []
		current_id = None
		
		for line in content.split('\n'):
			if line.strip().startswith('[SOW-'):
				# Save previous entry if exists
				if current_entry and current_id:
					sow_entries.append((current_id, '\n'.join(current_entry)))
				# Start new entry
				current_id = line.strip()
				current_entry = [line]
			elif line.strip() and current_entry:
				current_entry.append(line)
		
		# Add the last entry
		if current_entry and current_id:
			sow_entries.append((current_id, '\n'.join(current_entry)))
		
		# Index each SOW entry
		for sow_id, sow_text in sow_entries:
			emb = embed_text(sow_text)
			idx.add(sow_id, sow_text, emb)
	
	return idx


def sidebar_controls():
	st.sidebar.header("Inputs")
	sow_txt_file = st.sidebar.file_uploader("SOW Text (.txt)", type=["txt"], help="Upload the SOW document as plain text")
	staffing_file = st.sidebar.file_uploader("Historical Staffing CSV", type=["csv"], help=DATA_SCHEMAS["Staffing"])
	hours_file = st.sidebar.file_uploader("Reported Hours CSV", type=["csv"], help=DATA_SCHEMAS["Hours"])
	duration_adj = st.sidebar.slider("Duration multiplier", 0.5, 2.0, 1.0, 0.1)
	scope_adj = st.sidebar.slider("Scope multiplier", 0.5, 2.0, 1.0, 0.1)
	max_team = st.sidebar.slider("Max team size", 2, 20, 8, 1)
	return sow_txt_file, staffing_file, hours_file, duration_adj, scope_adj, max_team


def load_inputs_text(sow_txt_file, staffing_file, hours_file):
	if sow_txt_file:
		sow_text = load_text(sow_txt_file)
	else:
		sow_text = Path("samples/sow_sample.txt").read_text(encoding="utf-8") if Path("samples/sow_sample.txt").exists() else ""
	staffing_df = load_csv(staffing_file) if staffing_file else (pd.read_csv("samples/staffing_sample.csv") if Path("samples/staffing_sample.csv").exists() else pd.DataFrame())
	hours_df = load_csv(hours_file) if hours_file else (pd.read_csv("samples/hours_sample.csv") if Path("samples/hours_sample.csv").exists() else pd.DataFrame())
	if not staffing_df.empty:
		staffing_df = normalize_columns(staffing_df)
	if not hours_df.empty:
		hours_df = normalize_columns(hours_df)
	return sow_text, staffing_df, hours_df


def main():
	st.title("Staffing Plan Generator POC - Semantic SOW")
	roles_cfg, weights_cfg = get_configs()
	# Get embedding model for cache invalidation
	embedding_model = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
	index = build_vector_index(embedding_model)
	sow_txt_file, staffing_file, hours_file, duration_adj, scope_adj, max_team = sidebar_controls()

	sow_text, staffing_df, hours_df = load_inputs_text(sow_txt_file, staffing_file, hours_file)
	st.subheader("SOW Preview")
	st.text_area("SOW Text", value=sow_text, height=300)

	analyze = st.button("Analyze SOW and Generate Plan", type="primary")
	if analyze:
		ai_summary = analyze_sow_text(sow_text)
		neighbors = index.search(embed_text(sow_text), top_k=5) if index.items else []
		features = features_from_ai(ai_summary)
		neighbors_df = pd.DataFrame(neighbors) if neighbors else pd.DataFrame()

		st.markdown("### AI Findings")
		st.json(ai_summary)

		st.markdown("### Similar Historical SOWs")
		mapped_contract_id = None
		if neighbors:
			for i, n in enumerate(neighbors):
				st.write(f"{n['id']} (distance {n['distance']:.2f})")
				with st.expander("View snippet"):
					st.write(n["text"])
				if i == 0:
					mapped_contract_id = HIST_SOW_TO_CONTRACT.get(str(n['id']).strip())
		else:
			st.info("No historical SOWs indexed yet.")

		contract_id = "SOW-TEXT-001"
		rec_plan = generate_staffing_plan(
			contract_id=contract_id,
			sow_df=pd.DataFrame(),
			roles_cfg=roles_cfg,
			weights_cfg=weights_cfg,
			duration_multiplier=duration_adj,
			scope_multiplier=scope_adj,
			max_team_size=max_team,
			features_override=features,
			historical_data=hours_df,
			similar_neighbors=neighbors_df,
			ai_total_estimate=float(features.get("estimated_hours", 0.0)),
		)

		st.markdown("### Recommended Staffing Plan")
		st.dataframe(rec_plan, width='stretch')

		with st.expander("Calibration details"):
			cal = getattr(rec_plan, "_calibration_debug", {})
			st.json(cal)

		comparison = compare_plan_vs_actual(rec_plan if not mapped_contract_id else rec_plan.assign(contract_id=mapped_contract_id), hours_df)
		st.markdown("### Variance Analysis (Plan vs. Actuals)")
		st.dataframe(comparison, width='stretch')

		st.download_button(
			label="Export Plan CSV",
			data=rec_plan.to_csv(index=False).encode("utf-8"),
			file_name=f"{contract_id}_recommended_plan.csv",
			mime="text/csv",
		)

if __name__ == "__main__":
	main()
