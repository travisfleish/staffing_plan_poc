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
	"sow_h001_retail_sports.txt": "C-105",
	"sow_h002_airline_activation.txt": "C-101",
	"sow_h003_streaming_launch.txt": "C-102",
	"sow_h004_creative_retainer.txt": "C-103",
}

@st.cache_data
def get_configs():
	return load_configs(Path("config/roles.yaml"), Path("config/weights.yaml"))

@st.cache_resource
def build_vector_index() -> InMemoryVectorIndex:
	idx = InMemoryVectorIndex()
	sows_dir = Path("samples/sows")
	if sows_dir.exists():
		for p in sorted(sows_dir.glob("*.txt")):
			text = p.read_text(encoding="utf-8")
			emb = embed_text(text)
			idx.add(p.name, text, emb)
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
	index = build_vector_index()
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
		st.dataframe(rec_plan, use_container_width=True)

		with st.expander("Calibration details"):
			cal = getattr(rec_plan, "_calibration_debug", {})
			st.json(cal)

		comparison = compare_plan_vs_actual(rec_plan if not mapped_contract_id else rec_plan.assign(contract_id=mapped_contract_id), hours_df)
		st.markdown("### Variance Analysis (Plan vs. Actuals)")
		st.dataframe(comparison, use_container_width=True)

		st.download_button(
			label="Export Plan CSV",
			data=rec_plan.to_csv(index=False).encode("utf-8"),
			file_name=f"{contract_id}_recommended_plan.csv",
			mime="text/csv",
		)

if __name__ == "__main__":
	main()
