# Staffing Plan Generator POC

Streamlit prototype that ingests a text SOW, analyzes it with an AI layer, finds similar historical SOWs, generates a staffing plan, and compares against historical actuals. Configuration-driven; designed for demo and extensibility.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Data Schemas
- Staffing plan CSV: `contract_id,role,planned_hours,fte,start_week,end_week,seniority_level`
- Reported hours CSV: `contract_id,person_id,role,week_start,actual_hours,utilization_pct`

## Config
- `config/roles.yaml`: rates and utilization targets
- `config/weights.yaml`: role mix, complexity/workstream weights, calibration
- `config/prompts.yaml`: placeholder prompts
