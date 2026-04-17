from typing import Dict, List, Optional, Callable
from datetime import datetime

from src.utils.logger import get_logger
from src.streaming.rule_based_alert_system import RuleBasedAlertSystem
from src.streaming.model_based_alert_system import ModelBasedAlertSystem
from src.streaming.alert_deduplicator import AlertDeduplicator
from src.streaming.alert_store import AlertStore

logger = get_logger(__name__)


class AlertService:
   
    def __init__(
        self,
        alert_store_path: str = 'data/alerts.db',
        dedup_window_hours: int = 1,
        enable_rule_based: bool = True,
        enable_model_based: bool = True
    ):
        
        self.rule_based_system = (
            RuleBasedAlertSystem() if enable_rule_based else None
        )
        self.model_based_system = (
            ModelBasedAlertSystem() if enable_model_based else None
        )
        self.deduplicator = AlertDeduplicator(dedup_window_hours)
        self.alert_store = AlertStore(alert_store_path)
        self.notification_handlers: List[Callable] = []

        logger.info(
            f"Alert service initialized "
            f"(rule_based={enable_rule_based}, "
            f"model_based={enable_model_based})"
        )

    def process_current_aqi(
        self,
        city: str,
        aqi: float,
        timestamp: Optional[float] = None
    ) -> List[Dict]:
        
        alerts = []

        if not self.rule_based_system:
            return alerts

        try:
            # Generate rule-based alert
            alert = self.rule_based_system.evaluate_current_aqi(
                city, aqi, timestamp
            )

            if alert:
                alerts.append(alert)

        except Exception as e:
            logger.error(f"Error processing current AQI for {city}: {e}")

        return self._process_alerts(alerts)

    def process_prediction(
        self,
        city: str,
        predicted_aqi: float,
        current_aqi: Optional[float] = None,
        timestamp: Optional[float] = None
    ) -> List[Dict]:
        
        alerts = []

        if not self.model_based_system:
            return alerts

        try:
            # Generate model-based alert
            alert = self.model_based_system.evaluate_prediction(
                city, predicted_aqi, current_aqi, timestamp
            )

            if alert:
                alerts.append(alert)

        except Exception as e:
            logger.error(f"Error processing prediction for {city}: {e}")

        return self._process_alerts(alerts)

    def process_inference_result(
        self,
        inference_result: Dict
    ) -> List[Dict]:
        
        alerts = []

        try:
            city = inference_result['city']
            timestamp = inference_result['timestamp']
            current_aqi = inference_result['current_aqi']
            predicted_aqi = inference_result.get('predicted_aqi')

            # Generate rule-based alert
            if self.rule_based_system:
                alert = self.rule_based_system.evaluate_current_aqi(
                    city, current_aqi, timestamp
                )
                if alert:
                    alerts.append(alert)

            # Generate model-based alert
            if self.model_based_system and predicted_aqi is not None:
                alert = self.model_based_system.evaluate_prediction(
                    city, predicted_aqi, current_aqi, timestamp
                )
                if alert:
                    alerts.append(alert)

        except Exception as e:
            logger.error(f"Error processing inference result: {e}")

        return self._process_alerts(alerts)

    def _process_alerts(self, alerts: List[Dict]) -> List[Dict]:
        
        if not alerts:
            return []

        # Deduplicate alerts
        deduplicated = self.deduplicator.filter_alerts(alerts)

        if not deduplicated:
            return []

        # Store alerts
        stored_alerts = []
        for alert in deduplicated:
            try:
                alert_id = self.alert_store.store_alert(alert)
                alert['alert_id'] = alert_id
                stored_alerts.append(alert)

                # Notify handlers
                self._notify_handlers(alert)

            except Exception as e:
                logger.error(f"Error storing alert: {e}")

        return stored_alerts

    def register_notification_handler(
        self,
        handler: Callable[[Dict], None]
    ) -> None:
        
        self.notification_handlers.append(handler)
        logger.info(f"Registered notification handler: {handler.__name__}")

    def _notify_handlers(self, alert: Dict) -> None:
        
        for handler in self.notification_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Error in notification handler: {e}")

    def get_active_alerts(
        self,
        city: Optional[str] = None,
        level: Optional[str] = None
    ) -> List[Dict]:
        
        return self.alert_store.get_active_alerts(city, level)

    def get_alerts_by_city(
        self,
        city: str,
        hours: int = 24,
        acknowledged: Optional[bool] = None
    ) -> List[Dict]:
        
        return self.alert_store.get_alerts_by_city(city, hours, acknowledged)

    def get_alerts_by_level(
        self,
        level: str,
        hours: int = 24
    ) -> List[Dict]:
        
        return self.alert_store.get_alerts_by_level(level, hours)

    def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: Optional[str] = None
    ) -> bool:
        
        return self.alert_store.acknowledge_alert(alert_id, acknowledged_by)

    def acknowledge_batch(
        self,
        alert_ids: List[str],
        acknowledged_by: Optional[str] = None
    ) -> int:
        
        return self.alert_store.acknowledge_batch(alert_ids, acknowledged_by)

    def get_stats(self, hours: int = 24) -> Dict:
        
        stats = self.alert_store.get_stats(hours)
        stats['deduplicator_stats'] = self.deduplicator.get_stats()
        return stats

    def close(self) -> None:
        """Close alert service and cleanup resources."""
        try:
            self.alert_store.close()
            logger.info("Alert service closed")
        except Exception as e:
            logger.error(f"Error closing alert service: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
