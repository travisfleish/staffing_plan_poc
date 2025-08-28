# Technical Implementation Guide - Staffing Plan Generator POC

## Quick Start Guide

### Prerequisites
- Python 3.8 or higher
- pip package manager
- Git (for version control)

### Installation Steps

```bash
# Clone the repository
git clone <repository-url>
cd staffing_plan_poc

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables (optional)
cp .env.example .env
# Edit .env with your OpenAI API key if using AI features

# Run the application
streamlit run app.py
```

## Project Structure

```
staffing_plan_poc/
├── app.py                          # Main Streamlit application
├── requirements.txt                # Python dependencies
├── README.md                      # Project overview
├── ARCHITECTURE_AND_BUSINESS_LOGIC.md  # Architecture documentation
├── TECHNICAL_IMPLEMENTATION_GUIDE.md   # This file
├── config/                        # Configuration files
│   ├── roles.yaml                 # Role definitions and rates
│   ├── weights.yaml               # Business logic weights
│   └── prompts.yaml               # AI prompt templates
├── core/                          # Core business logic
│   ├── __init__.py
│   ├── calibration.py             # AI/historical data blending
│   ├── constraints.py             # Business rules engine
│   ├── features.py                # Feature extraction
│   ├── io_layer.py                # Data input/output
│   ├── planner.py                 # Staffing plan generation
│   └── semantic.py                # AI analysis engine
└── samples/                       # Sample data files
    ├── hours_sample.csv           # Historical hours data
    ├── sow_historicals.txt        # Historical SOW documents
    ├── sow_sample.txt             # Sample SOW input
    └── staffing_sample.csv        # Sample staffing output
```

## Configuration Management

### 1. **Roles Configuration (`config/roles.yaml`)**

```yaml
default_rate: 200
rates:
  account_manager: 250
  project_manager: 250
  creative_director: 200
  designer: 200
  copywriter: 150
  producer: 150
  analyst: 150

utilization_targets:
  account_manager: 0.85
  project_manager: 0.85
  creative_director: 0.85
  designer: 0.85
  copywriter: 0.85
  producer: 0.85
  analyst: 0.85
```

**Key Concepts**:
- **Rates**: Hourly billing rates for each role
- **Utilization Targets**: Expected productivity percentage (0.85 = 85% productive time)

### 2. **Weights Configuration (`config/weights.yaml`)**

```yaml
alpha_complexity: 0.25
beta_workstreams: 0.12

role_mix:
  account_manager: 0.15
  project_manager: 0.15
  creative_director: 0.20
  designer: 0.25
  copywriter: 0.15
  producer: 0.05
  analyst: 0.05

calibration:
  ai_confidence: 0.3
  historical_confidence: 0.7
  min_similar_contracts: 1
  similarity_threshold: 0.3
  fallback_strategy: "conservative"
```

**Key Concepts**:
- **Role Mix**: Percentage distribution of hours across roles
- **Calibration**: AI vs. historical data weighting
- **Similarity Thresholds**: How strict to be when finding similar projects

## Data Models & Schemas

### 1. **Input Data Formats**

#### SOW Text Input
Plain text document containing project scope, deliverables, and requirements.

#### Historical Hours CSV
```csv
contract_id,person_id,role,week_start,actual_hours,utilization_pct
C-300,P-301,account_manager,2024-01-01,40,0.85
C-300,P-302,project_manager,2024-01-01,32,0.8
```

**Required Columns**:
- `contract_id`: Unique identifier for the contract
- `person_id`: Unique identifier for the person
- `role`: Role name (must match config/roles.yaml)
- `week_start`: Start date of the week (YYYY-MM-DD)
- `actual_hours`: Hours worked in the week
- `utilization_pct`: Utilization percentage for the week

### 2. **Output Data Formats**

#### Staffing Plan CSV
```csv
contract_id,role,planned_hours,fte,start_week,end_week,seniority_level,num_people
SOW-TEXT-001,account_manager,1440,1.0,1,48,senior,1
SOW-TEXT-001,designer,2400,1.67,1,48,senior,2
```

**Generated Columns**:
- `planned_hours`: Total hours allocated to the role
- `fte`: Full-time equivalent (1.0 = 40 hours/week)
- `start_week`/`end_week`: Project timeline in weeks
- `seniority_level`: Senior or junior classification
- `num_people`: Number of people needed for the role

## Core Business Logic Implementation

### 1. **SOW Analysis Flow**

```python
# 1. Text embedding for similarity search
embeddings = embed_text(sow_text)

# 2. AI-powered feature extraction
ai_summary = analyze_sow_text(sow_text)
features = features_from_ai(ai_summary)

# 3. Semantic search for similar projects
neighbors = index.search(embeddings, top_k=5)
```

### 2. **Calibration Engine**

```python
# Blend AI estimates with historical data
calibration = calculate_calibrated_baseline(
    features=features,
    similar_contracts=neighbors_df,
    ai_estimate=ai_total_hours,
    historical_data=hours_df,
    ai_confidence=0.3,
    historical_confidence=0.7,
    min_similar_contracts=1,
    similarity_threshold=0.3
)

# Result contains strategy: "blended" or "fallback"
strategy = calibration["strategy"]
baseline_hours = calibration["blended_baseline"]
```

### 3. **Staffing Plan Generation**

```python
# Generate role-specific hours
role_hours = _estimate_role_hours_from_total(
    total_hours=baseline_hours,
    weights_cfg=weights_cfg
)

# Apply business constraints
plan = _apply_constraints(
    role_hours=role_hours,
    features=features,
    roles_cfg=roles_cfg,
    weights_cfg=weights_cfg,
    max_team_size=8
)
```

## Extending the System

### 1. **Adding New Roles**

1. **Update `config/roles.yaml`**:
```yaml
rates:
  new_role: 175
utilization_targets:
  new_role: 0.8
```

2. **Update `config/weights.yaml`**:
```yaml
role_mix:
  new_role: 0.10
  # Adjust other roles to sum to 1.0
```

3. **Update team composition rules**:
```yaml
min_team_composition:
  project:
    new_role: 1
```

### 2. **Custom Business Rules**

1. **Add new constraints in `core/constraints.py`**:
```python
def custom_business_rule(role_hours: Dict, features: Dict) -> Dict:
    # Implement custom logic
    if features.get("complexity_level") == "high":
        # Apply high-complexity rules
        pass
    return role_hours
```

2. **Integrate in `core/planner.py`**:
```python
# Apply custom rules before constraints
role_hours = custom_business_rule(role_hours, features)
plan = _apply_constraints(role_hours, features, roles_cfg, weights_cfg, max_team_size)
```

### 3. **New Data Sources**

1. **Create new input handler in `core/io_layer.py`**:
```python
def load_custom_data(file_path: str) -> pd.DataFrame:
    # Implement custom data loading logic
    pass
```

2. **Update `app.py` to use new data source**:
```python
# Add new file uploader
custom_file = st.sidebar.file_uploader("Custom Data", type=["csv", "json"])

# Load and process
if custom_file:
    custom_data = load_custom_data(custom_file)
    # Integrate with existing logic
```

## Testing & Validation

### 1. **Unit Testing**

```bash
# Install testing dependencies
pip install pytest pytest-cov

# Run tests
pytest tests/ -v --cov=core

# Generate coverage report
pytest tests/ --cov=core --cov-report=html
```

### 2. **Integration Testing**

```bash
# Test the full pipeline
python -c "
from core.planner import generate_staffing_plan
from core.constraints import load_configs
from pathlib import Path

roles_cfg, weights_cfg = load_configs(Path('config/roles.yaml'), Path('config/weights.yaml'))
print('Configuration loaded successfully')

# Test with sample data
import pandas as pd
hours_df = pd.read_csv('samples/hours_sample.csv')
print(f'Hours data loaded: {len(hours_df)} rows')
"
```

### 3. **Data Validation**

```python
def validate_hours_data(df: pd.DataFrame) -> bool:
    """Validate hours data format and content."""
    required_columns = ['contract_id', 'person_id', 'role', 'week_start', 'actual_hours', 'utilization_pct']
    
    # Check columns
    if not all(col in df.columns for col in required_columns):
        return False
    
    # Check data types
    if not pd.api.types.is_numeric_dtype(df['actual_hours']):
        return False
    
    # Check value ranges
    if (df['actual_hours'] < 0).any() or (df['actual_hours'] > 168).any():
        return False
    
    return True
```

## Performance Optimization

### 1. **Caching Strategies**

```python
import functools
from streamlit import cache_data

@cache_data
def expensive_calculation(data: pd.DataFrame) -> Dict:
    # Cache expensive operations
    return complex_analysis(data)
```

### 2. **Data Processing Optimization**

```python
# Use vectorized operations instead of loops
def optimized_hours_aggregation(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby(['contract_id', 'role'])['actual_hours'].sum().reset_index()

# Avoid repeated DataFrame copies
def efficient_data_processing(df: pd.DataFrame) -> pd.DataFrame:
    # Work with views when possible
    return df.loc[df['actual_hours'] > 0].copy()
```

### 3. **Memory Management**

```python
# Process data in chunks for large datasets
def process_large_dataset(file_path: str, chunk_size: int = 10000):
    for chunk in pd.read_csv(file_path, chunksize=chunk_size):
        # Process each chunk
        yield process_chunk(chunk)
```

## Deployment Considerations

### 1. **Environment Configuration**

```bash
# Production environment variables
export OPENAI_API_KEY="your-api-key"
export ENVIRONMENT="production"
export LOG_LEVEL="INFO"
export MAX_FILE_SIZE="10MB"
```

### 2. **Docker Deployment**

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### 3. **Streamlit Cloud Deployment**

1. Push code to GitHub repository
2. Connect repository to Streamlit Cloud
3. Set environment variables in Streamlit Cloud dashboard
4. Deploy automatically on push to main branch

## Troubleshooting

### 1. **Common Issues**

#### Import Errors
```bash
# Check Python path
python -c "import sys; print(sys.path)"

# Verify virtual environment
which python
pip list | grep streamlit
```

#### Configuration Errors
```bash
# Validate YAML files
python -c "import yaml; yaml.safe_load(open('config/weights.yaml'))"
```

#### Data Loading Issues
```bash
# Check file permissions
ls -la samples/

# Validate CSV format
head -5 samples/hours_sample.csv
```

### 2. **Debug Mode**

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Add debug prints in core functions
print(f"DEBUG: Processing {len(data)} rows")
print(f"DEBUG: Configuration: {config}")
```

### 3. **Performance Profiling**

```python
import cProfile
import pstats

def profile_function():
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Run your function
    result = expensive_function()
    
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(10)
    
    return result
```

## API Reference

### Core Functions

#### `generate_staffing_plan()`
```python
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
) -> pd.DataFrame
```

**Parameters**:
- `contract_id`: Unique identifier for the contract
- `sow_df`: SOW data (can be empty if using features_override)
- `roles_cfg`: Role configuration from config/roles.yaml
- `weights_cfg`: Weights configuration from config/weights.yaml
- `duration_multiplier`: Multiplier for project duration
- `scope_multiplier`: Multiplier for project scope
- `max_team_size`: Maximum number of team members
- `features_override`: Override AI-extracted features
- `historical_data`: Historical hours data
- `similar_neighbors`: Similar historical contracts
- `ai_total_estimate`: AI-generated hours estimate

**Returns**: DataFrame with staffing plan

#### `calculate_calibrated_baseline()`
```python
def calculate_calibrated_baseline(
    features: Dict,
    similar_contracts: pd.DataFrame,
    ai_estimate: float,
    historical_data: pd.DataFrame,
    *,
    ai_confidence: float = 0.3,
    historical_confidence: float = 0.7,
    min_similar_contracts: int = 1,
    similarity_threshold: float = 0.3,
    fallback_strategy: str = "conservative",
) -> Dict[str, float]
```

**Returns**: Dictionary with calibration results including strategy and baseline hours

---

*This guide provides comprehensive technical implementation details for the Staffing Plan Generator POC. For business logic and architecture information, refer to the ARCHITECTURE_AND_BUSINESS_LOGIC.md document.*
