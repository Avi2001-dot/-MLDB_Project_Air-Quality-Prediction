#!/usr/bin/env python3
"""
Main Pipeline Entry Point - Air Quality Prediction System
=========================================================
Scalable Real-Time Air Quality Prediction and Pollution Alert System
for Indian Cities.

Team Members:
  Asit Jain       (M25DE1049) - Data ingestion, Kafka streaming, alert pipeline
  Avinash Singh   (M25DE1024) - Data cleaning, feature engineering, model training
  Prashant Kumar  (M25DE1063) - Distributed ML, model evaluation, architecture docs

Usage:
    python main.py                        # Run full pipeline
    python main.py --mode ingest          # Data ingestion only
    python main.py --mode etl             # ETL pipeline only
    python main.py --mode train           # Model training only
    python main.py --mode stream          # Streaming simulation only
    python main.py --mode demo            # Demo with synthetic data (no API keys needed)
    python main.py --help
"""

import argparse
import os
import sys
import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.logger import setup_logging, get_logger
from src.utils.config_loader import load_config
from src.utils.constants import (
    CITIES, RANDOM_SEED, AQI_THRESHOLDS, AQI_COLORS,
    LAG_OFFSETS, ROLLING_WINDOWS
)

# ── Logger ────────────────────────────────────────────────────────────────────
setup_logging('INFO', 'logs/system.log')
logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _banner(title: str) -> None:
    width = 70
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def _section(title: str) -> None:
    print(f"\n{'-' * 60}")
    print(f"  {title}")
    print('-' * 60)


def generate_synthetic_data(n_records: int = 500, days_back: int = 30) -> pd.DataFrame:
    """
    Generate realistic synthetic AQI data for Indian cities.

    Used when real API keys are not available (demo / CI mode).
    Produces deterministic data via fixed random seed.
    """
    np.random.seed(RANDOM_SEED)
    records = []
    base_time = datetime.now() - timedelta(days=days_back)

    # City-specific AQI baselines (Delhi is most polluted, Bangalore least)
    city_baselines = {
        'Delhi': 180, 'Mumbai': 130, 'Bangalore': 80,
        'Kolkata': 150, 'Chennai': 100, 'Hyderabad': 110,
        'Pune': 95, 'Ahmedabad': 140, 'Jaipur': 120, 'Lucknow': 160
    }

    for i in range(n_records):
        city = CITIES[i % len(CITIES)]
        timestamp = base_time + timedelta(hours=i // len(CITIES))
        baseline = city_baselines.get(city, 120)

        # Add realistic diurnal variation + noise
        hour = timestamp.hour
        diurnal = 30 * np.sin(np.pi * (hour - 6) / 12)
        aqi = max(10, baseline + diurnal + np.random.normal(0, 20))

        records.append({
            'city': city,
            'timestamp': timestamp,
            'aqi': round(aqi, 2),
            'pm25': round(aqi * 0.45 + np.random.normal(0, 5), 2),
            'pm10': round(aqi * 0.75 + np.random.normal(0, 8), 2),
            'no2': round(aqi * 0.25 + np.random.normal(0, 3), 2),
            'o3': round(max(0, 60 - aqi * 0.1 + np.random.normal(0, 5)), 2),
            'so2': round(max(0, aqi * 0.08 + np.random.normal(0, 2)), 2),
            'co': round(max(0, aqi * 0.015 + np.random.normal(0, 0.3)), 2),
        })

    df = pd.DataFrame(records)
    logger.info(f"Generated {len(df)} synthetic records for {len(CITIES)} cities")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1 – DATA INGESTION
# ─────────────────────────────────────────────────────────────────────────────

def run_ingestion(config, use_synthetic: bool = False) -> pd.DataFrame:
    """
    Stage 1: Ingest data from CPCB dataset (historical) and IQAir (real-time).

    Falls back to synthetic data when API keys are absent.
    """
    _section("STAGE 1 – Data Ingestion")

    if use_synthetic:
        logger.info("Using synthetic data (demo mode)")
        return generate_synthetic_data()

    df_parts = []

    # ── CPCB historical data ──────────────────────────────────────────────────
    cpcb_cfg = config.get('data_sources.cpcb', {})
    api_key_path = os.path.expanduser(cpcb_cfg.get('api_key_path', '~/.cpcb/credentials.json'))
    dataset_name = cpcb_cfg.get('dataset_name', '')

    if os.path.exists(api_key_path) and dataset_name:
        try:
            from src.data_ingestion.cpcb_ingestion import CpcbDataIngestion
            cpcb = CpcbDataIngestion(api_key_path, dataset_name)
            cpcb_df = cpcb.fetch_data(output_path='data/bronze/cpcb')
            df_parts.append(cpcb_df)
            logger.info(f"CPCB: fetched {len(cpcb_df)} records")
        except Exception as e:
            logger.warning(f"CPCB ingestion failed: {e}. Skipping.")
    else:
        logger.warning("CPCB API key or dataset name not configured. Skipping.")

    # ── IQAir real-time data ──────────────────────────────────────────────────
    iqair_api_key = os.environ.get('IQAIR_API_KEY', '')
    if iqair_api_key and not iqair_api_key.startswith('${'):
        try:
            from src.data_ingestion.iqair_ingestion import IQAirDataIngestion
            iqair = IQAirDataIngestion(api_key=iqair_api_key)
            iqair_df = iqair.fetch_all_cities_aqi()
            df_parts.append(iqair_df)
            logger.info(f"IQAir: fetched {len(iqair_df)} records")
        except Exception as e:
            logger.warning(f"IQAir ingestion failed: {e}. Skipping.")
    else:
        logger.warning("IQAIR_API_KEY not set. Skipping real-time ingestion.")

    if df_parts:
        combined = pd.concat(df_parts, ignore_index=True)
        logger.info(f"Total ingested: {len(combined)} records")
        return combined

    logger.warning("No real data ingested. Falling back to synthetic data.")
    return generate_synthetic_data()


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 2 – ETL PIPELINE  (Bronze → Silver → Gold)
# ─────────────────────────────────────────────────────────────────────────────

def run_etl(raw_df: pd.DataFrame, config) -> pd.DataFrame:
    """
    Stage 2: Run the distributed ETL pipeline.

    Bronze  – raw storage (Parquet, partitioned by source/date)
    Silver  – cleaned, deduplicated, validated
    Gold    – feature-engineered (lag, rolling, temporal, seasonal)
    """
    _section("STAGE 2 – ETL Pipeline (Bronze → Silver → Gold)")

    bronze_path = config.get('storage.bronze_path', 'data/bronze')
    silver_path = config.get('storage.silver_path', 'data/silver')
    gold_path   = config.get('storage.gold_path',   'data/gold')

    try:
        from src.etl_pipeline.pipeline import ETLPipeline  # noqa: PySpark required

        with ETLPipeline(bronze_path, silver_path, gold_path) as pipeline:
            gold_df, metrics = pipeline.run_pipeline(raw_df, source='combined')

        # Print summary
        rec = metrics.get('records', {})
        qual = metrics.get('quality', {})
        print(f"  Bronze ingested : {rec.get('bronze_ingested', 0):>6} records")
        print(f"  Silver valid    : {rec.get('valid_records', 0):>6} records")
        print(f"  Silver rejected : {rec.get('rejected_records', 0):>6} records")
        print(f"  Gold stored     : {rec.get('gold_stored', 0):>6} records")
        print(f"  Quality score   : {qual.get('quality_score', 0):>6.2f}%")
        print(f"  Pipeline time   : {metrics.get('total_time_seconds', 0):>6.2f}s")

        return gold_df

    except Exception as e:
        logger.error(f"ETL pipeline failed: {e}")
        logger.info("Falling back to pandas-only feature engineering")
        return _pandas_etl_fallback(raw_df)


def _pandas_etl_fallback(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Pandas-only ETL when Spark is unavailable."""
    # Basic cleaning (no PySpark imports)
    df = raw_df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.dropna(subset=['city', 'timestamp', 'aqi'])
    df = df[(df['aqi'] >= 0) & (df['aqi'] <= 500)]
    df = df.drop_duplicates(subset=['city', 'timestamp'])
    df = df.sort_values(['city', 'timestamp']).reset_index(drop=True)

    # Pure pandas feature engineering
    gold_df = df.copy()
    gold_df['hour_of_day'] = gold_df['timestamp'].dt.hour
    gold_df['day_of_week'] = gold_df['timestamp'].dt.dayofweek
    gold_df['month'] = gold_df['timestamp'].dt.month
    gold_df['is_weekend'] = gold_df['day_of_week'].isin([5, 6]).astype(int)

    def _season(m):
        if m in [12, 1, 2]: return 'Winter'
        if m in [3, 4, 5]:  return 'Summer'
        if m in [6, 7, 8, 9]: return 'Monsoon'
        return 'Post-Monsoon'

    gold_df['season'] = gold_df['month'].apply(_season)

    for lag in LAG_OFFSETS:
        gold_df[f'aqi_lag_{lag}h'] = (
            gold_df.groupby('city')['aqi'].shift(lag)
        )
    for win in ROLLING_WINDOWS:
        rolled = gold_df.groupby('city')['aqi'].rolling(win, min_periods=1)
        gold_df[f'aqi_mean_{win}h'] = rolled.mean().reset_index(level=0, drop=True)
        gold_df[f'aqi_std_{win}h']  = rolled.std().reset_index(level=0, drop=True)
        gold_df[f'aqi_min_{win}h']  = rolled.min().reset_index(level=0, drop=True)
        gold_df[f'aqi_max_{win}h']  = rolled.max().reset_index(level=0, drop=True)

    gold_df = gold_df.fillna(0)
    logger.info(f"Pandas ETL fallback produced {len(gold_df)} records with {len(gold_df.columns)} features")
    return gold_df


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 3 – MODEL TRAINING & EVALUATION
# ─────────────────────────────────────────────────────────────────────────────

def run_training(gold_df: pd.DataFrame, config) -> dict:
    """
    Stage 3: Train XGBoost and Random Forest models with time-series CV.

    Returns trained models and evaluation metrics.
    """
    _section("STAGE 3 – Model Training & Evaluation")

    from src.modeling.model_trainer import ModelTrainer
    from src.modeling.model_registry import ModelRegistry
    from src.feature_engineering.time_series_splitter import TimeSeriesSplitter

    models_path = config.get('storage.models_path', 'data/models')
    registry = ModelRegistry(registry_path=models_path)

    # Prepare features
    exclude_cols = {'city', 'timestamp', 'aqi', 'season', 'source',
                    'quality_flags', 'date', 'ingestion_timestamp', 'retrieval_time'}
    feature_cols = [c for c in gold_df.columns
                    if c not in exclude_cols
                    and pd.api.types.is_numeric_dtype(gold_df[c])]

    if not feature_cols:
        logger.error("No numeric feature columns found. Skipping training.")
        return {}

    X = gold_df[feature_cols].fillna(0)
    y = gold_df['aqi']

    if len(X) < 30:
        logger.warning(f"Only {len(X)} samples – skipping training (need ≥ 30).")
        return {}

    # Time-series train/test split
    splitter = TimeSeriesSplitter(test_size=0.2)
    X_train, X_test, y_train, y_test = splitter.get_train_test_split(X, y)

    print(f"  Training samples : {len(X_train)}")
    print(f"  Test samples     : {len(X_test)}")
    print(f"  Features         : {len(feature_cols)}")

    cv_folds = config.get('modeling.cv_folds', 3)
    trainer = ModelTrainer(n_cv_folds=cv_folds, random_state=RANDOM_SEED)

    results = {}

    # ── XGBoost ───────────────────────────────────────────────────────────────
    try:
        xgb_params = config.get('modeling.xgboost', {})
        xgb_result = trainer.train_xgboost(
            X_train, y_train,
            hyperparameters=xgb_params if xgb_params else None,
            use_cv=True, verbose=False
        )
        xgb_metrics = trainer.evaluate_model('xgboost', X_test, y_test, verbose=False)
        results['xgboost'] = xgb_metrics

        print(f"\n  XGBoost Results:")
        print(f"    RMSE : {xgb_metrics.get('rmse', 0):.4f}")
        print(f"    MAE  : {xgb_metrics.get('mae', 0):.4f}")
        print(f"    R²   : {xgb_metrics.get('r2', 0):.4f}")

        # Register model
        registry.register_model(
            model=trainer.models['xgboost'].model,
            model_name='xgboost',
            model_type='XGBoost',
            version=f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            metrics=xgb_metrics,
            hyperparameters=trainer.models['xgboost'].hyperparameters,
            feature_columns=feature_cols
        )
    except Exception as e:
        logger.error(f"XGBoost training failed: {e}")

    # ── Random Forest ─────────────────────────────────────────────────────────
    try:
        rf_params = config.get('modeling.random_forest', {})
        rf_result = trainer.train_random_forest(
            X_train, y_train,
            hyperparameters=rf_params if rf_params else None,
            use_cv=True, verbose=False
        )
        rf_metrics = trainer.evaluate_model('random_forest', X_test, y_test, verbose=False)
        results['random_forest'] = rf_metrics

        print(f"\n  Random Forest Results:")
        print(f"    RMSE : {rf_metrics.get('rmse', 0):.4f}")
        print(f"    MAE  : {rf_metrics.get('mae', 0):.4f}")
        print(f"    R²   : {rf_metrics.get('r2', 0):.4f}")

        registry.register_model(
            model=trainer.models['random_forest'].model,
            model_name='random_forest',
            model_type='Random Forest',
            version=f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            metrics=rf_metrics,
            hyperparameters=trainer.models['random_forest'].hyperparameters,
            feature_columns=feature_cols
        )
    except Exception as e:
        logger.error(f"Random Forest training failed: {e}")

    # ── Best model ────────────────────────────────────────────────────────────
    if results:
        best = max(results.items(), key=lambda kv: kv[1].get('r2', -999))
        print(f"\n  Best model: {best[0]}  (R² = {best[1].get('r2', 0):.4f})")

    return {'trainer': trainer, 'metrics': results, 'feature_cols': feature_cols}


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 4 – STREAMING SIMULATION & ALERT GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def run_streaming_simulation(gold_df: pd.DataFrame, training_output: dict) -> None:
    """
    Stage 4: Simulate real-time streaming inference and alert generation.

    Replays the last 20 records through the streaming inference pipeline,
    generates rule-based and model-based alerts, and prints a summary.
    """
    _section("STAGE 4 – Streaming Simulation & Alert Generation")

    from src.streaming.streaming_inference_pipeline import StreamingInferencePipeline
    from src.streaming.alert_service import AlertService

    trainer      = training_output.get('trainer')
    feature_cols = training_output.get('feature_cols', [])

    # Pick a model for inference
    model = None
    model_name_used = None
    if trainer and trainer.models:
        model_name_used = next(iter(trainer.models))
        model = trainer.models[model_name_used].model
        logger.info(f"Using {model_name_used} for streaming inference")

    alert_service = AlertService(
        alert_store_path='data/alerts.db',
        dedup_window_hours=1
    )

    # Build ONE inference pipeline (reused across all events)
    infer_pipeline = None
    if model is not None and feature_cols:
        # The model was trained on lag/rolling/temporal features.
        # Streaming events only carry city/timestamp/aqi, so the
        # StreamingFeatureComputer will compute the same feature set on-the-fly.
        # We pass feature_columns=[] so the pipeline uses ALL numeric features
        # it can compute (avoids "column not found" for raw pollutant cols).
        infer_pipeline = StreamingInferencePipeline(
            model=model,
            feature_columns=[],   # use all numeric features computed by the window
            max_latency_ms=1000
        )

    # Simulate streaming events from the last 20 gold records
    sample_events = gold_df.tail(20).to_dict('records')
    total_alerts  = 0
    latencies     = []

    print(f"  Simulating {len(sample_events)} streaming events...\n")

    for record in sample_events:
        city = record.get('city', 'Unknown')
        aqi  = float(record.get('aqi', 0))
        ts   = record.get('timestamp')
        if hasattr(ts, 'timestamp'):
            ts = ts.timestamp()
        else:
            ts = time.time()

        event = {'city': city, 'timestamp': ts, 'aqi': aqi}

        # Streaming inference
        predicted_aqi = None
        if infer_pipeline is not None:
            try:
                result = infer_pipeline.process_event(event)
                latencies.append(result.get('latency_ms', 0))
                predicted_aqi = result.get('predicted_aqi')
            except Exception as e:
                logger.debug(f"Inference skipped for {city}: {e}")

        # Rule-based alert
        rule_alerts = alert_service.process_current_aqi(city, aqi, ts)
        total_alerts += len(rule_alerts)

        # Model-based alert
        if predicted_aqi is not None:
            model_alerts = alert_service.process_prediction(
                city, predicted_aqi, aqi, ts
            )
            total_alerts += len(model_alerts)

        # Print high-severity events
        category = _get_aqi_category(aqi)
        if category not in ('Good', 'Satisfactory'):
            pred_str = f"  Predicted={predicted_aqi:.1f}" if predicted_aqi else ""
            print(f"  [{category:20s}] {city:12s}  AQI={aqi:6.1f}{pred_str}")

    # Summary
    active = alert_service.get_active_alerts()

    print(f"\n  Events processed : {len(sample_events)}")
    print(f"  Alerts generated : {total_alerts}")
    print(f"  Active alerts    : {len(active)}")
    if latencies:
        print(f"  Mean latency     : {sum(latencies)/len(latencies):.2f} ms")
        print(f"  Max latency      : {max(latencies):.2f} ms")

    alert_service.close()


def _get_aqi_category(aqi: float) -> str:
    for cat, (lo, hi) in AQI_THRESHOLDS.items():
        if lo <= aqi <= hi:
            return cat
    return 'Unknown'


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 5 – FEATURE ANALYSIS REPORT
# ─────────────────────────────────────────────────────────────────────────────

def run_feature_analysis(gold_df: pd.DataFrame) -> None:
    """Stage 5: Generate feature analysis report."""
    _section("STAGE 5 – Feature Analysis Report")

    from src.feature_engineering.feature_analyzer import FeatureAnalyzer

    try:
        analyzer = FeatureAnalyzer(gold_df, target_col='aqi')
        report = analyzer.generate_analysis_report(
            output_path='reports/feature_analysis.json'
        )

        corr = analyzer.compute_target_correlations()
        top5 = corr.abs().nlargest(5)

        print("  Top-5 features correlated with AQI:")
        for feat, val in top5.items():
            print(f"    {feat:30s}  |r| = {val:.4f}")

        high_corr = analyzer.get_high_correlation_features(threshold=0.9)
        if high_corr:
            print(f"\n  High inter-feature correlations (|r| > 0.9): {len(high_corr)} pairs")

        print(f"\n  Full report saved to reports/feature_analysis.json")

    except Exception as e:
        logger.warning(f"Feature analysis failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# FULL PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def run_full_pipeline(args) -> int:
    """Run the complete end-to-end pipeline."""
    _banner("Scalable Real-Time Air Quality Prediction System")
    print("  Indian Cities Air Quality Monitoring & Forecasting")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Load config
    try:
        config = load_config('config.yaml')
    except Exception as e:
        logger.warning(f"Could not load config.yaml: {e}. Using defaults.")
        config = type('cfg', (), {'get': lambda self, k, d=None: d})()

    use_synthetic = args.demo or args.mode == 'demo'

    # Stage 1 – Ingestion
    if args.mode in ('full', 'ingest', 'demo'):
        raw_df = run_ingestion(config, use_synthetic=use_synthetic)
    else:
        raw_df = generate_synthetic_data()

    if raw_df is None or raw_df.empty:
        logger.error("No data available. Exiting.")
        return 1

    # Stage 2 – ETL
    if args.mode in ('full', 'etl', 'train', 'stream', 'demo'):
        gold_df = run_etl(raw_df, config)
    else:
        gold_df = raw_df

    if gold_df is None or gold_df.empty:
        logger.error("ETL produced no data. Exiting.")
        return 1

    # Stage 3 – Training
    training_output = {}
    if args.mode in ('full', 'train', 'demo'):
        training_output = run_training(gold_df, config)

    # Stage 4 – Streaming simulation
    if args.mode in ('full', 'stream', 'demo'):
        run_streaming_simulation(gold_df, training_output)

    # Stage 5 – Feature analysis
    if args.mode in ('full', 'demo'):
        run_feature_analysis(gold_df)

    _banner("Pipeline Complete")
    print(f"  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("  Next steps:")
    print("    Dashboard  : python scripts/start_dashboard.py")
    print("    Monitoring : python scripts/start_monitoring_dashboard.py")
    print("    Repro check: python scripts/validate_reproducibility.py")
    print()
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Air Quality Prediction System – Main Pipeline Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  full    Run all stages end-to-end (default)
  ingest  Data ingestion only
  etl     ETL pipeline only (Bronze→Silver→Gold)
  train   Model training & evaluation only
  stream  Streaming simulation & alerts only
  demo    Full pipeline with synthetic data (no API keys needed)

Examples:
  python main.py                  # full pipeline
  python main.py --mode demo      # demo with synthetic data
  python main.py --mode train     # training only
        """
    )
    parser.add_argument(
        '--mode',
        choices=['full', 'ingest', 'etl', 'train', 'stream', 'demo'],
        default='full',
        help='Pipeline mode (default: full)'
    )
    parser.add_argument(
        '--demo',
        action='store_true',
        help='Use synthetic data (no API keys required)'
    )
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    sys.exit(run_full_pipeline(args))
