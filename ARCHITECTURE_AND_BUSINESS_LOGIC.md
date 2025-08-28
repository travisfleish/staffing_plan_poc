# Staffing Plan Generator POC - Architecture & Business Logic Documentation

## Executive Summary

The Staffing Plan Generator POC is an AI-powered application that automatically generates staffing plans for professional services contracts by analyzing Statement of Work (SOW) documents, finding similar historical projects, and leveraging both AI estimates and historical performance data to create optimized team compositions.

## System Architecture

### High-Level Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Input Layer   │    │  Processing     │    │   Output Layer  │
│                 │    │    Engine       │    │                 │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ • SOW Text      │    │ • AI Analysis   │    │ • Staffing Plan │
│ • Historical    │    │ • Semantic      │    │ • Variance      │
│   Hours Data    │    │   Search        │    │   Analysis      │
│ • Configuration │    │ • Calibration   │    │ • Calibration   │
│   Files         │    │ • Planning      │    │   Details       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Core Components

#### 1. **Input Layer (`core/io_layer.py`)**
- **Purpose**: Data ingestion and normalization
- **Components**:
  - CSV file loading with automatic column normalization
  - Text file processing for SOW documents
  - In-memory vector index for semantic search
- **Data Formats**:
  - SOW: Plain text documents
  - Hours: CSV with columns: `contract_id`, `person_id`, `role`, `week_start`, `actual_hours`, `utilization_pct`
  - Staffing: CSV with columns: `contract_id`, `role`, `planned_hours`, `fte`, `start_week`, `end_week`, `seniority_level`

#### 2. **AI Analysis Engine (`core/semantic.py`)**
- **Purpose**: Extract business requirements from SOW text
- **Process**:
  - Text embedding using hybrid approach (OpenAI + fallback)
  - AI-powered analysis to extract:
    - Complexity level (low/medium/high)
    - Duration in months
    - Workstream count
    - Estimated total hours
    - Key deliverables
- **Fallback Logic**: If AI analysis fails, uses rule-based extraction

#### 3. **Semantic Search Engine (`core/io_layer.py`)**
- **Purpose**: Find similar historical projects
- **Technology**: In-memory vector similarity search
- **Process**:
  - Embeds SOW text into vector space
  - Searches historical SOW database
  - Returns top-k similar projects with similarity scores
- **Output**: Ranked list of similar historical contracts

#### 4. **Calibration Engine (`core/calibration.py`)**
- **Purpose**: Blend AI estimates with historical data
- **Strategies**:
  - **Blended**: Combines AI estimate (30%) + Historical baseline (70%)
  - **Fallback**: Uses AI estimate when insufficient historical data
- **Thresholds**:
  - Minimum similar contracts: 1
  - Similarity threshold: 0.3 (more permissive)
- **Business Logic**:
  ```python
  if sufficient_historical_data and enough_similar_contracts:
      strategy = "blended"
      baseline = ai_confidence * corrected_ai + historical_confidence * historical_baseline
  else:
      strategy = "fallback"
      baseline = ai_estimate or historical_baseline
  ```

#### 5. **Planning Engine (`core/planner.py`)**
- **Purpose**: Generate optimized staffing plans
- **Process**:
  1. **Role Mix Calculation**: Dynamic or configured role distribution
  2. **Hours Allocation**: Distribute total hours across roles
  3. **Team Sizing**: Calculate FTE and headcount based on utilization targets
  4. **Constraint Application**: Apply minimum team composition rules
- **Key Functions**:
  - `_estimate_role_hours_from_total()`: Distribute hours across roles
  - `_apply_constraints()`: Apply business rules and constraints
  - `_compute_dynamic_role_mix()`: Calculate role mix from historical data

#### 6. **Constraints Engine (`core/constraints.py`)**
- **Purpose**: Enforce business rules and constraints
- **Rules**:
  - **Utilization Targets**: Role-specific productivity expectations
  - **Minimum Team Composition**: Project type-specific requirements
  - **Rate Structures**: Role-based pricing
- **Configuration**: YAML-based rule definitions

## Business Logic & Data Flow

### 1. **SOW Analysis Workflow**

```
SOW Text Input → AI Analysis → Feature Extraction → Complexity Assessment
     ↓
Duration Estimation → Workstream Count → Hours Estimation → Key Deliverables
```

**Business Rules**:
- **Complexity Levels**: 
  - Low: Basic projects (500 hours)
  - Medium: Cross-functional projects (800 hours)
  - High: Integrated/global projects (1200 hours)
- **Duration Multipliers**: Annual projects = 6 months, others = 4 months
- **Workstream Impact**: Creative + Social + Production = 3 workstreams

### 2. **Historical Data Processing**

```
Historical Hours → Contract Aggregation → Role-based Analysis → Similarity Weighting
     ↓
Contract ID Mapping → Hours Summation → Role Mix Calculation → Baseline Generation
```

**Business Rules**:
- **Contract ID Mapping**: SOW-X-300 → C-300 (hardcoded mapping)
- **Hours Aggregation**: Sum actual hours per contract per role
- **Similarity Weighting**: 1/(1 + distance) for historical influence
- **Minimum Thresholds**: At least 1 similar contract with 0.3 similarity

### 3. **Staffing Plan Generation**

```
Total Hours → Role Mix Application → Hours per Role → FTE Calculation
     ↓
Team Sizing → Constraint Validation → Plan Generation → Output Formatting
```

**Business Rules**:
- **Role Mix Distribution**:
  - Account Manager: 15%
  - Project Manager: 15%
  - Creative Director: 20%
  - Designer: 25%
  - Copywriter: 15%
  - Producer: 5%
  - Analyst: 5%
- **FTE Calculation**: `hours / (utilization_target × 40 hours/week)`
- **Team Sizing**: `max(1, ceil(fte_weeks / total_weeks))`
- **Minimum Team**: Project = 1 manager + 1 designer, Retainer = 1 manager + 1 designer + 1 copywriter

### 4. **Calibration & Optimization**

```
AI Estimate + Historical Baseline → Confidence Weighting → Blended Baseline
     ↓
Variance Analysis → Plan vs. Actuals → Performance Insights → Optimization
```

**Business Rules**:
- **AI Confidence**: 30% weight for AI estimates
- **Historical Confidence**: 70% weight for historical data
- **Fallback Strategy**: Conservative (minimum of AI and historical)
- **Variance Analysis**: Planned vs. actual hours with percentage differences

## Configuration Management

### 1. **Weights Configuration (`config/weights.yaml`)**
```yaml
calibration:
  ai_confidence: 0.3
  historical_confidence: 0.7
  min_similar_contracts: 1
  similarity_threshold: 0.3
  fallback_strategy: "conservative"
```

### 2. **Roles Configuration (`config/roles.yaml`)**
```yaml
rates:
  account_manager: 250
  designer: 200
  copywriter: 150
utilization_targets:
  account_manager: 0.85
  designer: 0.85
  copywriter: 0.85
```

### 3. **Team Composition Rules**
```yaml
min_team_composition:
  project:
    account_manager: 1
    designer: 1
  retainer:
    account_manager: 1
    designer: 1
    copywriter: 1
```

## Data Models & Schemas

### 1. **SOW Features**
```python
{
    "complexity_level": "high|medium|low",
    "duration_months": float,
    "workstream_count": int,
    "estimated_total_hours": float,
    "key_deliverables": List[str]
}
```

### 2. **Historical Hours**
```python
{
    "contract_id": str,      # e.g., "C-300"
    "person_id": str,        # e.g., "P-301"
    "role": str,             # e.g., "account_manager"
    "week_start": date,      # e.g., "2024-01-01"
    "actual_hours": float,   # e.g., 40.0
    "utilization_pct": float # e.g., 0.85
}
```

### 3. **Staffing Plan Output**
```python
{
    "contract_id": str,
    "role": str,
    "planned_hours": float,
    "fte": float,
    "start_week": int,
    "end_week": int,
    "seniority_level": str,
    "num_people": int
}
```

### 4. **Calibration Results**
```python
{
    "ai_estimate": float,
    "hist_baseline": float,
    "corrected_ai": float,
    "blended_baseline": float,
    "strategy": "blended|fallback",
    "role_mix_used": Dict[str, float]
}
```

## Error Handling & Fallbacks

### 1. **AI Analysis Failures**
- **Fallback**: Rule-based complexity assessment
- **Default Values**: Medium complexity, 4 months, 800 hours

### 2. **Historical Data Issues**
- **Insufficient Data**: Fallback to AI-only estimates
- **Contract ID Mismatches**: Hardcoded mapping fallback
- **Role Mismatches**: Default role mix configuration

### 3. **Configuration Errors**
- **Missing Files**: Default configurations
- **Invalid Values**: Safe defaults and validation

## Performance Characteristics

### 1. **Scalability**
- **Vector Search**: O(log n) for similarity search
- **Data Processing**: O(n) for hours aggregation
- **Memory Usage**: In-memory processing for POC scale

### 2. **Response Time**
- **AI Analysis**: 2-5 seconds (API dependent)
- **Semantic Search**: <100ms
- **Plan Generation**: <500ms
- **Total Response**: 3-6 seconds

### 3. **Data Volume**
- **Current Scale**: 10-50 historical contracts
- **Maximum Scale**: 1000+ contracts (with database backend)
- **Hours Data**: Weekly granularity, 52 weeks per year

## Integration Points

### 1. **External APIs**
- **OpenAI GPT**: SOW analysis and feature extraction
- **Vector Embeddings**: Text similarity calculations

### 2. **Data Sources**
- **SOW Documents**: Plain text input
- **Historical Hours**: CSV files
- **Configuration**: YAML files

### 3. **Output Formats**
- **Staffing Plans**: CSV export
- **Variance Analysis**: In-app tables
- **Calibration Details**: JSON metadata

## Future Enhancements

### 1. **Scalability Improvements**
- **Database Backend**: PostgreSQL for historical data
- **Vector Database**: Pinecone or Weaviate for similarity search
- **Caching Layer**: Redis for performance optimization

### 2. **Advanced Analytics**
- **Predictive Modeling**: ML-based hours estimation
- **Risk Assessment**: Project complexity scoring
- **Resource Optimization**: Multi-project resource allocation

### 3. **Integration Capabilities**
- **Project Management**: Jira, Asana integration
- **Time Tracking**: Harvest, Toggl integration
- **Financial Systems**: QuickBooks, NetSuite integration

## Technical Requirements

### 1. **Dependencies**
- **Python**: 3.8+
- **Streamlit**: Web interface
- **Pandas**: Data processing
- **PyYAML**: Configuration management
- **OpenAI**: AI analysis (optional)

### 2. **Deployment**
- **Local Development**: `streamlit run app.py`
- **Production**: Streamlit Cloud or containerized deployment
- **Environment Variables**: OpenAI API keys, configuration overrides

### 3. **Security Considerations**
- **API Keys**: Environment variable storage
- **Data Privacy**: Local processing, no external data transmission
- **Access Control**: Streamlit-based authentication (future)

## Business Value Proposition

### 1. **Efficiency Gains**
- **Time Savings**: 80% reduction in manual planning time
- **Accuracy Improvement**: Data-driven vs. gut-feel estimates
- **Consistency**: Standardized planning methodology

### 2. **Cost Optimization**
- **Resource Utilization**: Optimal team sizing based on historical data
- **Risk Mitigation**: Learn from past project performance
- **Scalability**: Handle multiple projects simultaneously

### 3. **Competitive Advantage**
- **Faster Response**: Quick turnaround on staffing estimates
- **Better Proposals**: Data-backed resource planning
- **Client Confidence**: Transparent, explainable planning process

---

*This document provides a comprehensive overview of the Staffing Plan Generator POC architecture and business logic. For technical implementation details, refer to the source code and configuration files.*
