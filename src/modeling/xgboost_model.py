import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import xgboost as xgb
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from src.utils.logger import get_logger
from src.utils.constants import XGBOOST_PARAMS, RANDOM_SEED

logger = get_logger(__name__)


class XGBoostModelError(Exception):
    """Custom exception for XGBoost model errors."""
    pass


class XGBoostModel:
    
    
    def __init__(
        self,
        hyperparameters: Optional[Dict] = None,
        random_state: int = RANDOM_SEED
    ):
        
        self.model = None
        self.feature_columns = None
        self.cv_results = {}
        self.feature_importance = None
        self.random_state = random_state
        
        # Set hyperparameters
        if hyperparameters is None:
            self.hyperparameters = XGBOOST_PARAMS.copy()
        else:
            self.hyperparameters = hyperparameters
        
        # Ensure random_state is set
        self.hyperparameters['random_state'] = random_state
        
        logger.info(
            f"XGBoostModel initialized with hyperparameters: "
            f"{self.hyperparameters}"
        )
    
    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        cv_splits: Optional[List[Tuple[np.ndarray, np.ndarray]]] = None,
        verbose: bool = True
    ) -> Dict:
        
        if X_train is None or len(X_train) == 0:
            raise XGBoostModelError("X_train cannot be None or empty")
        
        if y_train is None or len(y_train) == 0:
            raise XGBoostModelError("y_train cannot be None or empty")
        
        if len(X_train) != len(y_train):
            raise XGBoostModelError(
                f"X_train and y_train must have same length: "
                f"{len(X_train)} != {len(y_train)}"
            )
        
        self.feature_columns = X_train.columns.tolist()
        
        # Perform cross-validation if splits provided
        if cv_splits is not None:
            return self._train_with_cv(X_train, y_train, cv_splits, verbose)
        else:
            # Train on full training set
            return self._train_final(X_train, y_train, verbose)
    
    def _train_with_cv(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        cv_splits: List[Tuple[np.ndarray, np.ndarray]],
        verbose: bool = True
    ) -> Dict:
        
        rmse_scores = []
        mae_scores = []
        r2_scores = []
        
        for fold_idx, (train_idx, test_idx) in enumerate(cv_splits):
            if verbose:
                logger.info(f"Training fold {fold_idx + 1}/{len(cv_splits)}")
            
            # Split data
            X_cv_train = X_train.iloc[train_idx]
            y_cv_train = y_train.iloc[train_idx]
            X_cv_test = X_train.iloc[test_idx]
            y_cv_test = y_train.iloc[test_idx]
            
            # Train model on this fold
            fold_model = xgb.XGBRegressor(**self.hyperparameters)
            fold_model.fit(X_cv_train, y_cv_train)
            
            # Evaluate on test fold
            y_pred = fold_model.predict(X_cv_test)
            
            rmse = np.sqrt(mean_squared_error(y_cv_test, y_pred))
            mae = mean_absolute_error(y_cv_test, y_pred)
            r2 = r2_score(y_cv_test, y_pred)
            
            rmse_scores.append(rmse)
            mae_scores.append(mae)
            r2_scores.append(r2)
            
            if verbose:
                logger.info(
                    f"Fold {fold_idx + 1} - RMSE: {rmse:.4f}, "
                    f"MAE: {mae:.4f}, R²: {r2:.4f}"
                )
        
        # Store CV results
        self.cv_results = {
            'rmse_mean': np.mean(rmse_scores),
            'rmse_std': np.std(rmse_scores),
            'mae_mean': np.mean(mae_scores),
            'mae_std': np.std(mae_scores),
            'r2_mean': np.mean(r2_scores),
            'r2_std': np.std(r2_scores)
        }
        
        if verbose:
            logger.info(
                f"Cross-validation results: "
                f"RMSE={self.cv_results['rmse_mean']:.4f}±{self.cv_results['rmse_std']:.4f}, "
                f"MAE={self.cv_results['mae_mean']:.4f}±{self.cv_results['mae_std']:.4f}, "
                f"R²={self.cv_results['r2_mean']:.4f}±{self.cv_results['r2_std']:.4f}"
            )
        
        # Train final model on full training set
        self._train_final(X_train, y_train, verbose=False)
        
        return self.cv_results
    
    def _train_final(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        verbose: bool = True
    ) -> Dict:
        
        try:
            self.model = xgb.XGBRegressor(**self.hyperparameters)
            self.model.fit(X_train, y_train)
            
            # Extract feature importance
            self.feature_importance = dict(
                zip(self.feature_columns, self.model.feature_importances_)
            )
            
            if verbose:
                logger.info(
                    f"Final model trained on {len(X_train)} samples "
                    f"with {len(self.feature_columns)} features"
                )
            
            return {}
        
        except Exception as e:
            raise XGBoostModelError(f"Model training failed: {str(e)}")
    
    def predict(
        self,
        X: pd.DataFrame,
        return_uncertainty: bool = False
    ) -> np.ndarray:
        
        if self.model is None:
            raise XGBoostModelError("Model not trained. Call train() first.")
        
        if X is None or len(X) == 0:
            raise XGBoostModelError("X cannot be None or empty")
        
        try:
            predictions = self.model.predict(X)
            
            if return_uncertainty:
                return predictions, None
            
            return predictions
        
        except Exception as e:
            raise XGBoostModelError(f"Prediction failed: {str(e)}")
    
    def predict_24h(
        self,
        X_current: pd.DataFrame,
        feature_template: pd.DataFrame
    ) -> np.ndarray:
        
        if self.model is None:
            raise XGBoostModelError("Model not trained. Call train() first.")
        
        if X_current is None or len(X_current) == 0:
            raise XGBoostModelError("X_current cannot be None or empty")
        
        try:
            # For now, use current features for all 24 hours
            # In production, would update temporal features for each hour
            predictions = []
            
            for hour_ahead in range(1, 25):
                # Create feature vector for this hour
                X_pred = X_current.copy()
                
                # Update hour_of_day if it exists
                if 'hour_of_day' in X_pred.columns:
                    current_hour = X_pred['hour_of_day'].values[0]
                    X_pred['hour_of_day'] = (current_hour + hour_ahead) % 24
                
                # Generate prediction
                pred = self.model.predict(X_pred)[0]
                predictions.append(pred)
            
            return np.array(predictions)
        
        except Exception as e:
            raise XGBoostModelError(f"24-hour prediction failed: {str(e)}")
    
    def get_feature_importance(
        self,
        top_n: Optional[int] = None,
        sort: bool = True
    ) -> Dict[str, float]:
       
        if self.feature_importance is None:
            raise XGBoostModelError(
                "Feature importance not available. Train model first."
            )
        
        importance = self.feature_importance.copy()
        
        if sort:
            importance = dict(
                sorted(importance.items(), key=lambda x: x[1], reverse=True)
            )
        
        if top_n is not None:
            importance = dict(list(importance.items())[:top_n])
        
        return importance
    
    def evaluate(
        self,
        X_test: pd.DataFrame,
        y_test: pd.Series
    ) -> Dict[str, float]:
        
        if self.model is None:
            raise XGBoostModelError("Model not trained. Call train() first.")
        
        try:
            y_pred = self.predict(X_test)
            
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            mae = mean_absolute_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)
            
            # MAPE (Mean Absolute Percentage Error)
            mape = np.mean(np.abs((y_test - y_pred) / y_test)) * 100
            
            metrics = {
                'rmse': rmse,
                'mae': mae,
                'r2': r2,
                'mape': mape
            }
            
            logger.info(
                f"Test set evaluation: RMSE={rmse:.4f}, MAE={mae:.4f}, "
                f"R²={r2:.4f}, MAPE={mape:.2f}%"
            )
            
            return metrics
        
        except Exception as e:
            raise XGBoostModelError(f"Evaluation failed: {str(e)}")
    
    def save(self, path: str) -> None:
        
        if self.model is None:
            raise XGBoostModelError("Model not trained. Cannot save.")
        
        try:
            self.model.save_model(path)
            logger.info(f"Model saved to {path}")
        except Exception as e:
            raise XGBoostModelError(f"Failed to save model: {str(e)}")
    
    def load(self, path: str) -> None:
        
        try:
            self.model = xgb.XGBRegressor(**self.hyperparameters)
            self.model.load_model(path)
            logger.info(f"Model loaded from {path}")
        except Exception as e:
            raise XGBoostModelError(f"Failed to load model: {str(e)}")
    
    def get_model_info(self) -> Dict:
        
        return {
            'model_type': 'XGBoost',
            'hyperparameters': self.hyperparameters,
            'feature_columns': self.feature_columns,
            'cv_results': self.cv_results,
            'feature_importance': self.feature_importance,
            'is_trained': self.model is not None
        }
