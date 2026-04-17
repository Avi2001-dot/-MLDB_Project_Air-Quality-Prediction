
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
import os
import sys
import logging

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.utils.logger import get_logger
from src.utils.constants import CITIES, DASHBOARD_REFRESH_INTERVAL_MINUTES
from src.streaming.alert_store import AlertStore
from src.modeling.model_registry import ModelRegistry

# ============================================================================
# CONSTANTS
# ============================================================================

CACHE_TTL_SECONDS = DASHBOARD_REFRESH_INTERVAL_MINUTES * 60

# ============================================================================
# LOGGER SETUP
# ============================================================================

logger = get_logger(__name__)

# ============================================================================
# DATA STORE CLASS
# ============================================================================


class DataStore:
    
    def __init__(
        self,
        alert_db_path: str = 'data/alerts.db',
        model_registry_path: str = 'data/models',
        gold_layer_path: str = 'data/gold'
    ):
        
        try:
            self.alert_store = AlertStore(db_path=alert_db_path)
            self.model_registry = ModelRegistry(registry_path=model_registry_path)
            self.gold_layer_path = gold_layer_path
            
            # Initialize cache
            self.cache = {}
            self.cache_timestamps = {}
            
            logger.info('DataStore initialized successfully')
            
        except Exception as e:
            logger.error(f'Failed to initialize DataStore: {e}')
            raise
    
    # ========================================================================
    # CURRENT AQI METHODS
    # ========================================================================
    
    def get_latest_aqi(self, city: str) -> Optional[Dict]:
      
        cache_key = f'latest_aqi_{city}'
        
        # Check cache
        if self._is_cache_valid(cache_key):
            return self.cache.get(cache_key)
        
        try:
            # Try to read from Gold Layer
            data = self._read_gold_layer_latest(city)
            
            if data is not None:
                result = {
                    'aqi': float(data.get('aqi', 0)),
                    'timestamp': str(data.get('timestamp', 'N/A'))
                }
                
                # Cache result
                self.cache[cache_key] = result
                self.cache_timestamps[cache_key] = datetime.now()
                
                return result
            
            return None
            
        except Exception as e:
            logger.error(f'Error getting latest AQI for {city}: {e}')
            return None
    
    def get_cities(self) -> List[str]:
      
        return CITIES
    
    # ========================================================================
    # FORECAST METHODS
    # ========================================================================
    
    def get_forecast(self, city: str, hours: int = 24) -> Optional[pd.DataFrame]:
      
        cache_key = f'forecast_{city}_{hours}h'
        
        # Check cache
        if self._is_cache_valid(cache_key):
            return self.cache.get(cache_key)
        
        try:
            # Get best model info dict from registry
            try:
                best_model_info = self.model_registry.get_best_model(metric='r2')
                model_id = best_model_info.get('model_id') if best_model_info else None
                model = self.model_registry.get_model(model_id) if model_id else None
            except Exception:
                model = None

            # Get latest data for city
            latest_data = self._read_gold_layer_latest(city)

            if latest_data is None:
                logger.warning(f'No data available for {city}')
                return None

            # Generate forecast
            forecast_df = self._generate_forecast(model, city, latest_data, hours)

            if forecast_df is not None:
                self.cache[cache_key] = forecast_df
                self.cache_timestamps[cache_key] = datetime.now()

            return forecast_df
            
        except Exception as e:
            logger.error(f'Error generating forecast for {city}: {e}')
            return None
    
    def _generate_forecast(self, model, city: str, latest_data: Dict, hours: int) -> Optional[pd.DataFrame]:
        """Generate a simple 24-hour forecast from the latest data point."""
        try:
            # Parse start timestamp
            raw_ts = latest_data.get('timestamp', datetime.now())
            if isinstance(raw_ts, str):
                try:
                    start_time = datetime.fromisoformat(raw_ts)
                except ValueError:
                    start_time = datetime.now()
            elif isinstance(raw_ts, (int, float)):
                start_time = datetime.fromtimestamp(raw_ts)
            elif hasattr(raw_ts, 'to_pydatetime'):
                start_time = raw_ts.to_pydatetime()
            else:
                start_time = datetime.now()

            timestamps = [start_time + timedelta(hours=i) for i in range(1, hours + 1)]
            base_aqi = float(latest_data.get('aqi', 100))

            # Simple diurnal variation forecast (improves on flat line)
            predictions = []
            for i, ts in enumerate(timestamps):
                hour = ts.hour
                diurnal = 20 * np.sin(np.pi * (hour - 6) / 12)
                pred = max(10, base_aqi + diurnal * 0.3)
                predictions.append(round(pred, 1))

            uncertainties = [p * 0.08 for p in predictions]   # 8% uncertainty band

            return pd.DataFrame({
                'timestamp':     timestamps,
                'predicted_aqi': predictions,
                'upper_bound':   [p + u for p, u in zip(predictions, uncertainties)],
                'lower_bound':   [max(0, p - u) for p, u in zip(predictions, uncertainties)],
            })

        except Exception as e:
            logger.error(f'Error generating forecast: {e}')
            return None
    
    # ========================================================================
    # ALERT METHODS
    # ========================================================================
    
    def get_active_alerts(self) -> List[Dict]:
       
        try:
            alerts = self.alert_store.get_active_alerts()
            return alerts if alerts else []
            
        except Exception as e:
            logger.error(f'Error retrieving active alerts: {e}')
            return []
    
    def get_alerts_by_city(self, city: str) -> List[Dict]:
      
        try:
            alerts = self.alert_store.get_alerts_by_city(city)
            return alerts if alerts else []
            
        except Exception as e:
            logger.error(f'Error retrieving alerts for {city}: {e}')
            return []
    
    def get_alerts_by_level(self, level: str) -> List[Dict]:
    
        try:
            alerts = self.alert_store.get_alerts_by_level(level)
            return alerts if alerts else []
            
        except Exception as e:
            logger.error(f'Error retrieving alerts by level {level}: {e}')
            return []
    
    # ========================================================================
    # HISTORICAL TRENDS METHODS
    # ========================================================================
    
    def get_historical_aqi(
        self,
        city: str,
        days: int = 7
    ) -> Optional[pd.DataFrame]:
     
        cache_key = f'historical_aqi_{city}_{days}d'
        
        # Check cache
        if self._is_cache_valid(cache_key):
            return self.cache.get(cache_key)
        
        try:
            # Read from Gold Layer
            historical_df = self._read_gold_layer_historical(city, days)
            
            if historical_df is not None and len(historical_df) > 0:
                # Select relevant columns
                result_df = historical_df[['timestamp', 'aqi']].copy()
                result_df = result_df.sort_values('timestamp')
                
                # Cache result
                self.cache[cache_key] = result_df
                self.cache_timestamps[cache_key] = datetime.now()
                
                return result_df
            
            return None
            
        except Exception as e:
            logger.error(f'Error retrieving historical AQI for {city}: {e}')
            return None
    
    # ========================================================================
    # CACHE MANAGEMENT
    # ========================================================================
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """
        Check if cache entry is still valid.
        
        Args:
            cache_key: Cache key to check
            
        Returns:
            True if cache entry exists and is not expired, False otherwise
        """
        if cache_key not in self.cache:
            return False
        
        if cache_key not in self.cache_timestamps:
            return False
        
        age = (datetime.now() - self.cache_timestamps[cache_key]).total_seconds()
        return age < CACHE_TTL_SECONDS
    
    def clear_cache(self):
        """Clear all cached data."""
        self.cache.clear()
        self.cache_timestamps.clear()
        logger.info('Cache cleared')
    
    # ========================================================================
    # GOLD LAYER DATA ACCESS
    # ========================================================================
    
    def _read_gold_layer_latest(self, city: str) -> Optional[Dict]:
        """Read the most recent record for a city from Gold Layer CSV files."""
        try:
            csv_files = list(Path(self.gold_layer_path).rglob("*.csv"))
            if not csv_files:
                return None

            dfs = []
            for f in csv_files:
                try:
                    chunk = pd.read_csv(f)
                    if 'city' in chunk.columns:
                        chunk = chunk[chunk['city'] == city]
                        if not chunk.empty:
                            dfs.append(chunk)
                except Exception:
                    pass

            if not dfs:
                return None

            combined = pd.concat(dfs, ignore_index=True)
            combined['timestamp'] = pd.to_datetime(combined['timestamp'], errors='coerce')
            combined = combined.dropna(subset=['timestamp'])
            if combined.empty:
                return None

            latest = combined.sort_values('timestamp').iloc[-1]
            return latest.to_dict()

        except Exception as e:
            logger.error(f'Error reading latest Gold Layer data for {city}: {e}')
            return None

    def _read_gold_layer_csv_latest(self, city: str) -> Optional[Dict]:
        """Alias kept for compatibility."""
        return self._read_gold_layer_latest(city)
    
    def _read_gold_layer_historical(self, city: str, days: int) -> Optional[pd.DataFrame]:
        """Read historical records for a city from Gold Layer CSV files."""
        try:
            csv_files = list(Path(self.gold_layer_path).rglob("*.csv"))
            if not csv_files:
                return None

            cutoff = datetime.now() - timedelta(days=days)
            dfs = []
            for f in csv_files:
                try:
                    chunk = pd.read_csv(f)
                    if 'city' in chunk.columns:
                        chunk = chunk[chunk['city'] == city]
                        if not chunk.empty:
                            chunk['timestamp'] = pd.to_datetime(chunk['timestamp'], errors='coerce')
                            chunk = chunk[chunk['timestamp'] >= cutoff]
                            if not chunk.empty:
                                dfs.append(chunk)
                except Exception:
                    pass

            if not dfs:
                return None

            combined = pd.concat(dfs, ignore_index=True)
            return combined.sort_values('timestamp').reset_index(drop=True)

        except Exception as e:
            logger.error(f'Error reading historical Gold Layer data for {city}: {e}')
            return None

    def _read_gold_layer_csv_historical(self, city: str, days: int) -> Optional[pd.DataFrame]:
        """Alias kept for compatibility."""
        return self._read_gold_layer_historical(city, days)
    
    def close(self):
        """Close data store connections."""
        try:
            self.alert_store.close()
            logger.info('DataStore closed')
        except Exception as e:
            logger.error(f'Error closing DataStore: {e}')
