# Scalable Real-Time Air Quality Prediction and Pollution Alert System for Indian Cities

**CSL7110 – ML With BigData | Team Project**

| Member | ID | Responsibilities |
|---|---|---|
| Asit Jain | M25DE1049 | Data ingestion (IQAir API + Kafka streaming), HDFS storage, alert pipeline |
| Avinash Singh | M25DE1024 | Data cleaning, feature engineering (lag, rolling, seasonal), model training |
| Prashant Kumar Mishra | M25DE1063 | Distributed ML (Spark MLlib), model evaluation, architecture docs |

---

## Overview

A Big Data-driven ML system that ingests large-scale air quality data from Indian cities, performs distributed ETL processing, and predicts short-term AQI (Air Quality Index) levels with real-time pollution alerts.

**Cities covered:** Delhi, Mumbai, Bangalore, Kolkata, Chennai, Hyderabad, Pune, Ahmedabad, Jaipur, Lucknow

---

## Architecture

```
Data Sources (CPCB CSV + IQAir API)
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│                  ETL Pipeline (PySpark)                  │
│  Bronze Layer → Silver Layer → Gold Layer               │
│  (Raw Parquet)  (Cleaned/Dedup) (Feature-Engineered)    │
└─────────────────────────────────────────────────────────┘
        │                          │
        ▼                          ▼
┌──────────────────┐    ┌──────────────────────────────────┐
│  Model Training  │    │     Streaming Pipeline (Kafka)    │
│  ─ XGBoost       │    │  Producer → Consumer → Inference  │
│  ─ Random Forest │    │  → Rule-Based Alerts              │
│  ─ Time-Series CV│    │  → Model-Based Alerts             │
│  ─ Model Registry│    │  → Alert Deduplication + Storage  │
└──────────────────┘    └──────────────────────────────────┘
        │                          │
        └──────────┬───────────────┘
                   ▼
        ┌─────────────────────┐
        │  Streamlit Dashboard │
        │  ─ Current AQI       │
        │  ─ 24h Forecasts     │
        │  ─ Active Alerts     │
        │  ─ Historical Trends │
        └─────────────────────┘
```

---

## Tech Stack

| Component | Technology | Justification |
|---|---|---|
| Distributed processing | Apache Spark (PySpark) | Scalability, MLlib integration |
| Storage | Parquet (HDFS-compatible) | Columnar, efficient for time-series |
| Streaming | Apache Kafka | Real-time sensor data simulation |
| ML Models | XGBoost, Random Forest | Gradient boosting + ensemble for AQI regression |
| Dashboard | Streamlit + Plotly | Rapid interactive visualization |
| Data Sources | CPCB API + IQAir API | Historical + real-time AQI data |

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set IQAIR_API_KEY
```

### 3. Run the pipeline

```bash
# Demo mode – no API keys needed, uses synthetic data
python main.py --mode demo

# Full pipeline with real data
python main.py --mode full

# Individual stages
python main.py --mode ingest   # Data ingestion only
python main.py --mode etl      # ETL pipeline only
python main.py --mode train    # Model training only
python main.py --mode stream   # Streaming simulation only
```

### 4. Launch dashboards

```bash
# Main AQI dashboard (port 8501)
python scripts/start_dashboard.py

# System monitoring dashboard (port 8502)
python scripts/start_monitoring_dashboard.py
```

### 5. Validate reproducibility

```bash
python scripts/validate_reproducibility.py
```

---

## Data Sources

| Source | Type | Format | Size |
|---|---|---|---|
| [CPCB – Real-Time AQI India 2023-2025](https://www.kaggle.com/datasets/asaniczka/real-time-air-quality-index-aqi-india-2023-2025) | Historical | CSV | Multi-year, 300+ stations |
| [IQAir / WAQI API](https://api.waqi.info) | Real-time | JSON API | Live per-city readings |

**Features:** PM2.5, PM10, NO₂, SO₂, CO, O₃, Temperature, Humidity, Timestamp, Location

---

## Project Structure

```
workspace/
├── main.py                          # Main pipeline entry point
├── config.yaml                      # System configuration
├── requirements.txt
├── src/
│   ├── data_ingestion/
│   │   ├── cpcb_ingestion.py        # CPCB dataset download
│   │   └── iqair_ingestion.py       # IQAir real-time API
│   ├── etl_pipeline/
│   │   ├── bronze_layer.py          # Raw data storage (Parquet)
│   │   ├── silver_layer.py          # Cleaning, dedup, validation
│   │   ├── gold_layer.py            # Feature engineering
│   │   ├── data_validator.py        # Quality checks & scoring
│   │   ├── feature_normalizer.py    # StandardScaler with serialization
│   │   └── pipeline.py              # ETL orchestration
│   ├── feature_engineering/
│   │   ├── feature_processor.py     # Lag, rolling, temporal, seasonal features
│   │   ├── feature_analyzer.py      # Correlation, importance, outlier analysis
│   │   └── time_series_splitter.py  # Leakage-free train/test splits
│   ├── modeling/
│   │   ├── xgboost_model.py         # XGBoost with time-series CV
│   │   ├── random_forest_model.py   # Random Forest with time-series CV
│   │   ├── model_trainer.py         # Training orchestration
│   │   ├── model_evaluator.py       # RMSE, MAE, R², residual analysis
│   │   ├── model_registry.py        # Model versioning & storage
│   │   └── time_series_cross_validator.py
│   ├── streaming/
│   │   ├── streaming_data_producer.py    # Kafka producer
│   │   ├── streaming_data_consumer.py    # Kafka consumer
│   │   ├── streaming_feature_computer.py # Real-time sliding-window features
│   │   ├── streaming_inference_pipeline.py # End-to-end <1s inference
│   │   ├── rule_based_alert_system.py    # AQI threshold alerts
│   │   ├── model_based_alert_system.py   # Prediction-based alerts
│   │   ├── alert_deduplicator.py         # Dedup within time window
│   │   ├── alert_store.py                # SQLite alert persistence
│   │   └── alert_service.py              # Alert orchestration
│   ├── dashboard/
│   │   ├── app.py                   # Streamlit main dashboard
│   │   ├── data_store.py            # Dashboard data access layer
│   │   └── monitoring_dashboard.py  # System health dashboard
│   └── utils/
│       ├── constants.py             # AQI thresholds, cities, hyperparams
│       ├── config_loader.py         # YAML config + env var substitution
│       ├── logger.py                # Structured logging with rotation
│       ├── monitoring.py            # CPU/memory/latency tracking
│       └── logging_integration.py   # Decorators & structured logging
├── scripts/
│   ├── start_dashboard.py
│   ├── start_monitoring_dashboard.py
│   ├── generate_monitoring_report.py
│   └── validate_reproducibility.py
├── tests/
│   ├── unit/                        # 25 unit test modules
│   └── integration/                 # End-to-end pipeline tests
└── docs/
    ├── API.md
    ├── CONFIGURATION.md
    ├── DEPLOYMENT.md
    ├── QUICKSTART.md
    └── TECHNICAL_REPORT.md
```

---

## Deliverables

- [x] End-to-end Big Data architecture (Bronze → Silver → Gold)
- [x] Distributed ETL pipeline implementation (PySpark)
- [x] Feature engineering: lag features, rolling statistics, temporal, seasonal
- [x] Two forecasting models: XGBoost + Random Forest
- [x] Model evaluation metrics: RMSE, MAE, R², MAPE, residual analysis
- [x] Real-time pollution alert simulation (rule-based + model-based)
- [x] Streamlit visualization dashboard
- [x] System monitoring dashboard
- [x] Reproducibility validation (fixed seeds, deterministic pipeline)
- [x] Documented codebase with unit + integration tests

---

## AQI Categories

| Category | AQI Range | Alert Level |
|---|---|---|
| Good | 0–50 | None |
| Satisfactory | 51–100 | Info |
| Moderately Polluted | 101–200 | Warning |
| Heavily Polluted | 201–300 | Severe |
| Severely Polluted | 301–500 | Critical |

---

## Running Tests

```bash
# All unit tests
pytest tests/unit/ -v

# Integration tests (requires Spark)
pytest tests/integration/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

---

## Configuration

Key settings in `config.yaml`:

```yaml
system:
  random_seed: 42          # Fixed for reproducibility

modeling:
  xgboost:
    max_depth: 6
    learning_rate: 0.1
    n_estimators: 100
  random_forest:
    n_estimators: 100
    max_depth: 15
  cv_folds: 3

streaming:
  kafka_bootstrap_servers: "localhost:9092"
  max_latency_ms: 1000     # <1s inference target

alerts:
  dedup_window_hours: 1
  prediction_threshold: 150
```
