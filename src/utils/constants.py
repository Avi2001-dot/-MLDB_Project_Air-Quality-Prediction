from typing import Dict, List, Tuple

# ============================================================================
# AQI THRESHOLDS AND CATEGORIES
# ============================================================================

AQI_THRESHOLDS = {
    'Good': (0, 50),
    'Satisfactory': (51, 100),
    'Moderately Polluted': (101, 200),
    'Heavily Polluted': (201, 300),
    'Severely Polluted': (301, 500)
}

AQI_CATEGORIES = list(AQI_THRESHOLDS.keys())

# Alert levels corresponding to AQI categories
ALERT_LEVELS = {
    'Good': 'none',
    'Satisfactory': 'info',
    'Moderately Polluted': 'warning',
    'Heavily Polluted': 'severe',
    'Severely Polluted': 'critical'
}

# Color codes for visualization
AQI_COLORS = {
    'Good': '#00E400',           # Green
    'Satisfactory': '#FFFF00',   # Yellow
    'Moderately Polluted': '#FF7E00',  # Orange
    'Heavily Polluted': '#FF0000',     # Red
    'Severely Polluted': '#8F0000'     # Dark Red
}

# ============================================================================
# CITIES AND COORDINATES
# ============================================================================

CITIES = [
    'Delhi',
    'Mumbai',
    'Bangalore',
    'Kolkata',
    'Chennai',
    'Hyderabad',
    'Pune',
    'Ahmedabad',
    'Jaipur',
    'Lucknow'
]

# City coordinates (latitude, longitude)
CITY_COORDINATES: Dict[str, Tuple[float, float]] = {
    'Delhi': (28.7041, 77.1025),
    'Mumbai': (19.0760, 72.8777),
    'Bangalore': (12.9716, 77.5946),
    'Kolkata': (22.5726, 88.3639),
    'Chennai': (13.0827, 80.2707),
    'Hyderabad': (17.3850, 78.4867),
    'Pune': (18.5204, 73.8567),
    'Ahmedabad': (23.0225, 72.5714),
    'Jaipur': (26.9124, 75.7873),
    'Lucknow': (26.8467, 80.9462)
}

# ============================================================================
# FEATURE ENGINEERING PARAMETERS
# ============================================================================

# Lag offsets in hours
LAG_OFFSETS = [1, 3, 6, 12, 24]

# Rolling window sizes in hours
ROLLING_WINDOWS = [3, 6, 12, 24]

# Temporal features
HOURS_IN_DAY = 24
DAYS_IN_WEEK = 7
MONTHS_IN_YEAR = 12

# Seasonal definitions (meteorological seasons)
SEASONS = {
    'Winter': [12, 1, 2],
    'Summer': [3, 4, 5],
    'Monsoon': [6, 7, 8, 9],
    'Post-Monsoon': [10, 11]
}

# ============================================================================
# FEATURE NAMES
# ============================================================================

# Target variable
TARGET_VARIABLE = 'aqi'

# Pollutant columns
POLLUTANTS = ['pm25', 'pm10', 'no2', 'o3', 'so2', 'co']

# Lag feature names
LAG_FEATURES = [f'aqi_lag_{offset}h' for offset in LAG_OFFSETS]

# Rolling statistics feature names
ROLLING_FEATURES = []
for window in ROLLING_WINDOWS:
    ROLLING_FEATURES.extend([
        f'aqi_mean_{window}h',
        f'aqi_std_{window}h',
        f'aqi_min_{window}h',
        f'aqi_max_{window}h'
    ])

# Temporal feature names
TEMPORAL_FEATURES = [
    'hour_of_day',
    'day_of_week',
    'month',
    'is_weekend'
]

# Seasonal feature names
SEASONAL_FEATURES = ['season']

# All feature names (excluding target)
ALL_FEATURES = LAG_FEATURES + ROLLING_FEATURES + TEMPORAL_FEATURES + SEASONAL_FEATURES

# ============================================================================
# MODEL HYPERPARAMETERS
# ============================================================================

XGBOOST_PARAMS = {
    'max_depth': 6,
    'learning_rate': 0.1,
    'n_estimators': 100,
    'random_state': 42,
    'objective': 'reg:squarederror',
    'eval_metric': 'rmse'
}

RANDOM_FOREST_PARAMS = {
    'n_estimators': 100,
    'max_depth': 15,
    'min_samples_split': 5,
    'random_state': 42,
    'n_jobs': -1
}

# Cross-validation parameters
CV_FOLDS = 3
TEST_SIZE = 0.2

# ============================================================================
# STREAMING PARAMETERS
# ============================================================================

# Streaming window size in hours
STREAMING_WINDOW_HOURS = 24

# Maximum latency for streaming inference in milliseconds
MAX_STREAMING_LATENCY_MS = 1000

# Kafka parameters
KAFKA_BOOTSTRAP_SERVERS = 'localhost:9092'
KAFKA_TOPIC = 'aqi-events'
KAFKA_CONSUMER_GROUP = 'aqi-consumer'

# ============================================================================
# ALERT PARAMETERS
# ============================================================================

# Alert deduplication window in hours
ALERT_DEDUP_WINDOW_HOURS = 1

# Prediction threshold for model-based alerts
PREDICTION_ALERT_THRESHOLD = 150

# ============================================================================
# ETL PARAMETERS
# ============================================================================

# Batch size for processing
ETL_BATCH_SIZE = 1000

# Processing interval in hours
ETL_PROCESSING_INTERVAL_HOURS = 1

# Retry parameters
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 30

# AQI validation range
AQI_MIN = 0
AQI_MAX = 500

# ============================================================================
# DASHBOARD PARAMETERS
# ============================================================================

# Dashboard refresh interval in minutes
DASHBOARD_REFRESH_INTERVAL_MINUTES = 5

# Dashboard port and host
DASHBOARD_PORT = 8501
DASHBOARD_HOST = '0.0.0.0'

# ============================================================================
# DATA VALIDATION PARAMETERS
# ============================================================================

# Critical fields that must be present
CRITICAL_FIELDS = ['city', 'timestamp', 'aqi']

# ============================================================================
# LOGGING PARAMETERS
# ============================================================================

# Log levels
LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

# Log format
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Log file rotation parameters
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 10  # Keep 10 backup files

# ============================================================================
# SYSTEM PARAMETERS
# ============================================================================

# Random seed for reproducibility
RANDOM_SEED = 42

# Default environment
DEFAULT_ENVIRONMENT = 'development'

# Default log level
DEFAULT_LOG_LEVEL = 'INFO'

# ============================================================================
# DATA SCHEMA DEFINITIONS
# ============================================================================

# Bronze layer schema
BRONZE_SCHEMA = {
    'city': 'string',
    'timestamp': 'datetime',
    'aqi': 'float',
    'pm25': 'float',
    'pm10': 'float',
    'no2': 'float',
    'o3': 'float',
    'so2': 'float',
    'co': 'float',
    'source': 'string',
    'ingestion_timestamp': 'datetime',
    'retrieval_time': 'float'
}

# Silver layer schema
SILVER_SCHEMA = {
    'city': 'string',
    'timestamp': 'datetime',
    'aqi': 'float',
    'pm25': 'float',
    'pm10': 'float',
    'no2': 'float',
    'o3': 'float',
    'so2': 'float',
    'co': 'float',
    'source': 'string',
    'quality_flags': 'list'
}

# ============================================================================
# PERFORMANCE TARGETS
# ============================================================================

# ETL pipeline processing target (minutes)
ETL_PROCESSING_TARGET_MINUTES = 5

# Streaming event latency target (seconds)
STREAMING_LATENCY_TARGET_SECONDS = 1

# Model inference latency target (seconds)
MODEL_INFERENCE_LATENCY_TARGET_SECONDS = 1

# Model R² score target
MODEL_R2_TARGET = 0.75

# ============================================================================
# CODE QUALITY TARGETS
# ============================================================================

# Unit test coverage target (percentage)
TEST_COVERAGE_TARGET = 80

# Maximum line length for PEP 8 compliance
MAX_LINE_LENGTH = 100
