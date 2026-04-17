#!/usr/bin/env python3
"""
Prepare dashboard data – seeds data/gold with CSV files so the dashboard
has something to display without needing PySpark or real API keys.

Run this ONCE before starting the dashboard:
    python prepare_dashboard_data.py

It generates 30 days of synthetic AQI data for all 10 Indian cities and
saves per-city CSV files into data/gold/.
"""

import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.utils.constants import CITIES, RANDOM_SEED, LAG_OFFSETS, ROLLING_WINDOWS

GOLD_PATH = Path("data/gold")
GOLD_PATH.mkdir(parents=True, exist_ok=True)

np.random.seed(RANDOM_SEED)

CITY_BASELINES = {
    'Delhi': 185, 'Mumbai': 130, 'Bangalore': 75,
    'Kolkata': 155, 'Chennai': 100, 'Hyderabad': 110,
    'Pune': 95,  'Ahmedabad': 140, 'Jaipur': 120, 'Lucknow': 165,
}

print("Generating 30-day synthetic AQI data for all cities...")

all_records = []
base_time = datetime.now() - timedelta(days=30)

for day in range(30 * 24):          # hourly for 30 days
    ts = base_time + timedelta(hours=day)
    for city in CITIES:
        baseline = CITY_BASELINES[city]
        hour = ts.hour
        diurnal = 30 * np.sin(np.pi * (hour - 6) / 12)
        seasonal = 20 * np.sin(2 * np.pi * day / (365 * 24))
        noise = np.random.normal(0, 15)
        aqi = max(10, baseline + diurnal + seasonal + noise)

        all_records.append({
            'city': city,
            'timestamp': ts,
            'aqi': round(aqi, 2),
            'pm25': round(aqi * 0.45 + np.random.normal(0, 5), 2),
            'pm10': round(aqi * 0.75 + np.random.normal(0, 8), 2),
            'no2':  round(aqi * 0.25 + np.random.normal(0, 3), 2),
            'o3':   round(max(0, 60 - aqi * 0.1 + np.random.normal(0, 5)), 2),
            'so2':  round(max(0, aqi * 0.08 + np.random.normal(0, 2)), 2),
            'co':   round(max(0, aqi * 0.015 + np.random.normal(0, 0.3)), 2),
        })

df = pd.DataFrame(all_records)
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values(['city', 'timestamp']).reset_index(drop=True)

# Add temporal features
df['hour_of_day'] = df['timestamp'].dt.hour
df['day_of_week'] = df['timestamp'].dt.dayofweek
df['month']       = df['timestamp'].dt.month
df['is_weekend']  = df['day_of_week'].isin([5, 6]).astype(int)

def _season(m):
    if m in [12, 1, 2]: return 'Winter'
    if m in [3, 4, 5]:  return 'Summer'
    if m in [6, 7, 8, 9]: return 'Monsoon'
    return 'Post-Monsoon'

df['season'] = df['month'].apply(_season)

# Add lag and rolling features per city
print("Computing lag and rolling features...")
for lag in LAG_OFFSETS:
    df[f'aqi_lag_{lag}h'] = df.groupby('city')['aqi'].shift(lag)

for win in ROLLING_WINDOWS:
    rolled = df.groupby('city')['aqi'].rolling(win, min_periods=1)
    df[f'aqi_mean_{win}h'] = rolled.mean().reset_index(level=0, drop=True)
    df[f'aqi_std_{win}h']  = rolled.std().reset_index(level=0, drop=True)
    df[f'aqi_min_{win}h']  = rolled.min().reset_index(level=0, drop=True)
    df[f'aqi_max_{win}h']  = rolled.max().reset_index(level=0, drop=True)

df = df.fillna(0)

# Save one CSV per city
for city in CITIES:
    city_df = df[df['city'] == city].copy()
    out_path = GOLD_PATH / f"{city.lower()}_aqi.csv"
    city_df.to_csv(out_path, index=False)
    print(f"  Saved {len(city_df)} records -> {out_path}")

# Also save a combined file for easy access
combined_path = GOLD_PATH / "all_cities_aqi.csv"
df.to_csv(combined_path, index=False)
print(f"\nCombined file: {combined_path}  ({len(df)} total records)")
print("\nDone! You can now start the dashboard:")
print("  streamlit run src/dashboard/app.py")
