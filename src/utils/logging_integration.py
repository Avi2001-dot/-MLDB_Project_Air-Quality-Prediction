import functools
import time
import traceback
from typing import Any, Callable, Dict, Optional
from datetime import datetime

from .logger import get_logger
from .monitoring import (
    get_performance_monitor,
    start_operation_timer,
    end_operation_timer,
    record_event_metric
)

logger = get_logger(__name__)


def log_operation(
    operation_name: str,
    log_level: str = 'INFO',
    track_performance: bool = True
):
   
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            log_func = getattr(logger, log_level.lower(), logger.info)

            # Log operation start
            log_func(f"Starting {operation_name}")

            # Start performance tracking
            if track_performance:
                start_operation_timer(operation_name)

            try:
                # Execute function
                result = func(*args, **kwargs)

                # Log operation completion
                if track_performance:
                    duration = end_operation_timer(operation_name)
                    log_func(
                        f"Completed {operation_name} in {duration:.3f}s"
                    )
                else:
                    log_func(f"Completed {operation_name}")

                return result

            except Exception as e:
                # Log error with stack trace
                logger.error(
                    f"Error in {operation_name}: {str(e)}\n"
                    f"{traceback.format_exc()}"
                )
                raise

        return wrapper
    return decorator


def log_data_processing(
    stage_name: str,
    input_records: int,
    output_records: int,
    rejected_records: int = 0,
    quality_score: Optional[float] = None
) -> None:
    
    log_msg = (
        f"{stage_name}: "
        f"input={input_records}, output={output_records}, "
        f"rejected={rejected_records}"
    )

    if quality_score is not None:
        log_msg += f", quality_score={quality_score:.2f}%"

    logger.info(log_msg)


def log_model_training(
    model_name: str,
    training_samples: int,
    test_samples: int,
    metrics: Dict[str, float],
    duration_seconds: float
) -> None:
    
    metrics_str = ", ".join(
        f"{k}={v:.4f}" for k, v in metrics.items()
    )

    logger.info(
        f"Model training completed: {model_name} | "
        f"train_samples={training_samples}, test_samples={test_samples} | "
        f"metrics: {metrics_str} | "
        f"duration={duration_seconds:.2f}s"
    )


def log_prediction(
    city: str,
    current_aqi: float,
    predicted_aqi: float,
    latency_ms: float,
    alert_triggered: bool = False
) -> None:
    
    alert_str = " [ALERT]" if alert_triggered else ""
    logger.info(
        f"Prediction{alert_str}: {city} | "
        f"current_aqi={current_aqi:.1f}, predicted_aqi={predicted_aqi:.1f} | "
        f"latency={latency_ms:.2f}ms"
    )


def log_alert(
    alert_type: str,
    city: str,
    aqi_value: float,
    alert_level: str,
    message: str
) -> None:
    
    logger.warning(
        f"ALERT [{alert_type}]: {city} | "
        f"level={alert_level}, aqi={aqi_value:.1f} | "
        f"message={message}"
    )


def log_error_with_context(
    error_message: str,
    context: Dict[str, Any],
    error_type: str = "ERROR"
) -> None:
    
    context_str = ", ".join(
        f"{k}={v}" for k, v in context.items()
    )

    log_func = getattr(logger, error_type.lower(), logger.error)
    log_func(
        f"{error_message} | context: {context_str}\n"
        f"{traceback.format_exc()}"
    )


def log_system_checkpoint(
    checkpoint_name: str,
    status: str,
    details: Optional[Dict[str, Any]] = None
) -> None:
    
    details_str = ""
    if details:
        details_str = " | " + ", ".join(
            f"{k}={v}" for k, v in details.items()
        )

    logger.info(
        f"CHECKPOINT [{checkpoint_name}]: {status}{details_str}"
    )


class StructuredLogger:
    

    def __init__(self, module_name: str):
        
        self.logger = get_logger(module_name)
        self.module_name = module_name

    def log_event(
        self,
        event_type: str,
        event_name: str,
        level: str = 'INFO',
        **kwargs
    ) -> None:
        
        timestamp = datetime.now().isoformat()
        attributes = ", ".join(f"{k}={v}" for k, v in kwargs.items())

        message = (
            f"[{event_type}] {event_name} | "
            f"timestamp={timestamp} | {attributes}"
        )

        log_func = getattr(self.logger, level.lower(), self.logger.info)
        log_func(message)

    def log_performance(
        self,
        operation: str,
        duration_seconds: float,
        records_processed: int = 0,
        **kwargs
    ) -> None:
        
        throughput = (
            records_processed / duration_seconds
            if duration_seconds > 0 else 0
        )

        metrics = {
            'duration_seconds': f"{duration_seconds:.3f}",
            'records_processed': records_processed,
            'throughput_records_per_second': f"{throughput:.2f}"
        }
        metrics.update(kwargs)

        self.log_event(
            'PERFORMANCE',
            operation,
            level='INFO',
            **metrics
        )

    def log_data_quality(
        self,
        stage: str,
        total_records: int,
        valid_records: int,
        rejected_records: int,
        quality_score: float
    ) -> None:
        
        self.log_event(
            'DATA_QUALITY',
            stage,
            level='INFO',
            total_records=total_records,
            valid_records=valid_records,
            rejected_records=rejected_records,
            quality_score=f"{quality_score:.2f}%"
        )

    def log_error(
        self,
        operation: str,
        error_message: str,
        error_type: Optional[str] = None,
        **kwargs
    ) -> None:
        
        context = {
            'error_message': error_message,
            'error_type': error_type or 'Unknown'
        }
        context.update(kwargs)

        self.log_event(
            'ERROR',
            operation,
            level='ERROR',
            **context
        )


def create_structured_logger(module_name: str) -> StructuredLogger:
    
    return StructuredLogger(module_name)
