import logging
import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple
from scipy import stats
from sklearn.metrics import (
    mean_squared_error,
    mean_absolute_error,
    r2_score,
    mean_absolute_percentage_error
)

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ModelEvaluatorError(Exception):
    """Custom exception for ModelEvaluator errors."""
    pass


class ModelEvaluator:
    
    def __init__(self):
        """Initialize ModelEvaluator."""
        self.predictions = None
        self.actuals = None
        self.residuals = None
        self.metrics = {}
        
        logger.info("ModelEvaluator initialized")
    
    def evaluate(
        self,
        y_true: pd.Series,
        y_pred: np.ndarray,
        compute_residuals: bool = True
    ) -> Dict[str, float]:
        
        if y_true is None or len(y_true) == 0:
            raise ModelEvaluatorError("y_true cannot be None or empty")
        
        if y_pred is None or len(y_pred) == 0:
            raise ModelEvaluatorError("y_pred cannot be None or empty")
        
        if len(y_true) != len(y_pred):
            raise ModelEvaluatorError(
                f"y_true and y_pred must have same length: "
                f"{len(y_true)} != {len(y_pred)}"
            )
        
        self.actuals = np.array(y_true)
        self.predictions = np.array(y_pred)
        
        try:
            # Compute standard metrics
            rmse = np.sqrt(mean_squared_error(self.actuals, self.predictions))
            mae = mean_absolute_error(self.actuals, self.predictions)
            r2 = r2_score(self.actuals, self.predictions)
            mape = mean_absolute_percentage_error(self.actuals, self.predictions)
            
            self.metrics = {
                'rmse': rmse,
                'mae': mae,
                'r2': r2,
                'mape': mape
            }
            
            # Compute residual analysis if requested
            if compute_residuals:
                residual_analysis = self.analyze_residuals()
                self.metrics.update(residual_analysis)
            
            logger.info(
                f"Evaluation metrics: RMSE={rmse:.4f}, MAE={mae:.4f}, "
                f"R²={r2:.4f}, MAPE={mape:.4f}"
            )
            
            return self.metrics
        
        except Exception as e:
            raise ModelEvaluatorError(f"Evaluation failed: {str(e)}")
    
    def analyze_residuals(self) -> Dict[str, float]:
        
        if self.predictions is None or self.actuals is None:
            raise ModelEvaluatorError(
                "Predictions and actuals must be set before residual analysis"
            )
        
        self.residuals = self.actuals - self.predictions
        
        try:
            analysis = {
                'residual_mean': np.mean(self.residuals),
                'residual_std': np.std(self.residuals),
                'residual_min': np.min(self.residuals),
                'residual_max': np.max(self.residuals),
                'residual_skewness': stats.skew(self.residuals),
                'residual_kurtosis': stats.kurtosis(self.residuals)
            }
            
            logger.info(
                f"Residual analysis: mean={analysis['residual_mean']:.4f}, "
                f"std={analysis['residual_std']:.4f}, "
                f"skewness={analysis['residual_skewness']:.4f}, "
                f"kurtosis={analysis['residual_kurtosis']:.4f}"
            )
            
            return analysis
        
        except Exception as e:
            raise ModelEvaluatorError(f"Residual analysis failed: {str(e)}")
    
    def get_metrics(self) -> Dict[str, float]:
        
        if not self.metrics:
            raise ModelEvaluatorError("No metrics computed. Call evaluate() first.")
        
        return self.metrics.copy()
    
    def get_residuals(self) -> np.ndarray:
        
        if self.residuals is None:
            raise ModelEvaluatorError(
                "Residuals not computed. Call analyze_residuals() first."
            )
        
        return self.residuals.copy()
    
    def get_prediction_errors(self) -> np.ndarray:
        
        if self.predictions is None or self.actuals is None:
            raise ModelEvaluatorError(
                "Predictions and actuals must be set first"
            )
        
        return np.abs(self.actuals - self.predictions)
    
    def get_percentage_errors(self) -> np.ndarray:
        
        if self.predictions is None or self.actuals is None:
            raise ModelEvaluatorError(
                "Predictions and actuals must be set first"
            )
        
        # Avoid division by zero
        with np.errstate(divide='ignore', invalid='ignore'):
            pct_errors = np.abs(
                (self.actuals - self.predictions) / self.actuals
            ) * 100
            pct_errors = np.nan_to_num(pct_errors, nan=0.0, posinf=0.0, neginf=0.0)
        
        return pct_errors
    
    def get_error_statistics(self) -> Dict[str, float]:
        
        errors = self.get_prediction_errors()
        
        try:
            stats_dict = {
                'error_mean': np.mean(errors),
                'error_std': np.std(errors),
                'error_min': np.min(errors),
                'error_max': np.max(errors),
                'error_median': np.median(errors),
                'error_q25': np.percentile(errors, 25),
                'error_q75': np.percentile(errors, 75)
            }
            
            return stats_dict
        
        except Exception as e:
            raise ModelEvaluatorError(f"Error statistics computation failed: {str(e)}")
    
    def identify_outliers(
        self,
        threshold_std: float = 3.0
    ) -> Tuple[np.ndarray, np.ndarray]:
        
        if self.residuals is None:
            raise ModelEvaluatorError(
                "Residuals not computed. Call analyze_residuals() first."
            )
        
        residual_std = np.std(self.residuals)
        threshold = threshold_std * residual_std
        
        outlier_mask = np.abs(self.residuals) > threshold
        outlier_indices = np.where(outlier_mask)[0]
        outlier_residuals = self.residuals[outlier_mask]
        
        logger.info(
            f"Identified {len(outlier_indices)} outliers "
            f"(threshold: {threshold:.4f})"
        )
        
        return outlier_indices, outlier_residuals
    
    def get_evaluation_report(self) -> Dict:
        
        if not self.metrics:
            raise ModelEvaluatorError("No metrics computed. Call evaluate() first.")
        
        report = {
            'metrics': self.metrics.copy(),
            'error_statistics': self.get_error_statistics(),
            'n_samples': len(self.actuals),
            'n_outliers': len(self.identify_outliers()[0])
        }
        
        return report
    
    def compare_models(
        self,
        model_results: Dict[str, Dict[str, float]]
    ) -> pd.DataFrame:
       
        try:
            comparison_df = pd.DataFrame(model_results).T
            comparison_df = comparison_df.sort_values('r2', ascending=False)
            
            logger.info(f"Model comparison:\n{comparison_df}")
            
            return comparison_df
        
        except Exception as e:
            raise ModelEvaluatorError(f"Model comparison failed: {str(e)}")
    
    def reset(self) -> None:
        """Reset evaluator state."""
        self.predictions = None
        self.actuals = None
        self.residuals = None
        self.metrics = {}
        
        logger.info("ModelEvaluator reset")
