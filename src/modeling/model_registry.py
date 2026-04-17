import logging
import json
import os
from typing import Dict, List, Optional
from datetime import datetime
import joblib

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ModelRegistryError(Exception):
    """Custom exception for ModelRegistry errors."""
    pass


class ModelRegistry:
    
    
    def __init__(self, registry_path: str = 'data/models'):
        
        self.registry_path = registry_path
        self.models = {}
        
        # Create registry directory if it doesn't exist
        try:
            os.makedirs(registry_path, exist_ok=True)
            logger.info(f"ModelRegistry initialized at {registry_path}")
        except Exception as e:
            raise ModelRegistryError(f"Failed to create registry path: {str(e)}")
    
    def register_model(
        self,
        model: object,
        model_name: str,
        model_type: str,
        version: str,
        metrics: Dict,
        hyperparameters: Dict,
        feature_columns: List[str],
        metadata: Optional[Dict] = None
    ) -> str:
        
        try:
            # Generate model ID
            model_id = f"{model_name}_{version}"
            
            # Create model info
            model_info = {
                'model_id': model_id,
                'model_name': model_name,
                'model_type': model_type,
                'version': version,
                'timestamp': datetime.now().isoformat(),
                'metrics': metrics,
                'hyperparameters': hyperparameters,
                'feature_columns': feature_columns,
                'metadata': metadata or {},
                'model_path': os.path.join(self.registry_path, f'{model_id}.pkl'),
                'metadata_path': os.path.join(self.registry_path, f'{model_id}_meta.json')
            }
            
            # Save model
            model_path = model_info['model_path']
            joblib.dump(model, model_path)
            
            # Save metadata
            metadata_path = model_info['metadata_path']
            with open(metadata_path, 'w') as f:
                json.dump(model_info, f, indent=2, default=str)
            
            # Store in registry
            self.models[model_id] = model_info
            
            logger.info(
                f"Registered model {model_id}: "
                f"R²={metrics.get('r2', 'N/A')}, "
                f"RMSE={metrics.get('rmse', 'N/A')}"
            )
            
            return model_id
        
        except Exception as e:
            raise ModelRegistryError(f"Model registration failed: {str(e)}")
    
    def get_model(self, model_id: str) -> object:
        
        if model_id not in self.models:
            raise ModelRegistryError(f"Model '{model_id}' not found in registry")
        
        try:
            model_path = self.models[model_id]['model_path']
            model = joblib.load(model_path)
            
            logger.info(f"Loaded model {model_id}")
            
            return model
        
        except Exception as e:
            raise ModelRegistryError(f"Failed to load model: {str(e)}")
    
    def get_model_info(self, model_id: str) -> Dict:
        
        if model_id not in self.models:
            raise ModelRegistryError(f"Model '{model_id}' not found in registry")
        
        return self.models[model_id].copy()
    
    def list_models(
        self,
        model_name: Optional[str] = None,
        model_type: Optional[str] = None
    ) -> List[Dict]:
        
        models = list(self.models.values())
        
        if model_name is not None:
            models = [m for m in models if m['model_name'] == model_name]
        
        if model_type is not None:
            models = [m for m in models if m['model_type'] == model_type]
        
        # Sort by timestamp (newest first)
        models = sorted(models, key=lambda m: m['timestamp'], reverse=True)
        
        return models
    
    def get_best_model(
        self,
        metric: str = 'r2',
        model_name: Optional[str] = None
    ) -> Dict:
        
        if metric not in ['r2', 'rmse', 'mae']:
            raise ModelRegistryError(f"Invalid metric: {metric}")
        
        models = self.list_models(model_name=model_name)
        
        if not models:
            raise ModelRegistryError("No models found in registry")
        
        best_model = None
        best_score = None
        
        for model_info in models:
            metrics = model_info.get('metrics', {})
            
            if metric == 'r2':
                score = metrics.get('r2', 0)
                if best_score is None or score > best_score:
                    best_score = score
                    best_model = model_info
            
            elif metric == 'rmse':
                score = metrics.get('rmse', float('inf'))
                if best_score is None or score < best_score:
                    best_score = score
                    best_model = model_info
            
            elif metric == 'mae':
                score = metrics.get('mae', float('inf'))
                if best_score is None or score < best_score:
                    best_score = score
                    best_model = model_info
        
        if best_model is None:
            raise ModelRegistryError("No valid models found")
        
        logger.info(
            f"Best model: {best_model['model_id']} "
            f"({metric}={best_score:.4f})"
        )
        
        return best_model
    
    def delete_model(self, model_id: str) -> None:
        
        if model_id not in self.models:
            raise ModelRegistryError(f"Model '{model_id}' not found in registry")
        
        try:
            model_info = self.models[model_id]
            
            # Delete model file
            if os.path.exists(model_info['model_path']):
                os.remove(model_info['model_path'])
            
            # Delete metadata file
            if os.path.exists(model_info['metadata_path']):
                os.remove(model_info['metadata_path'])
            
            # Remove from registry
            del self.models[model_id]
            
            logger.info(f"Deleted model {model_id}")
        
        except Exception as e:
            raise ModelRegistryError(f"Failed to delete model: {str(e)}")
    
    def load_registry(self) -> None:
        
        try:
            self.models = {}
            
            # Scan for metadata files
            for filename in os.listdir(self.registry_path):
                if filename.endswith('_meta.json'):
                    metadata_path = os.path.join(self.registry_path, filename)
                    
                    with open(metadata_path, 'r') as f:
                        model_info = json.load(f)
                    
                    model_id = model_info['model_id']
                    self.models[model_id] = model_info
            
            logger.info(f"Loaded {len(self.models)} models from registry")
        
        except Exception as e:
            raise ModelRegistryError(f"Failed to load registry: {str(e)}")
    
    def get_registry_stats(self) -> Dict:
        
        stats = {
            'total_models': len(self.models),
            'models_by_type': {},
            'models_by_name': {},
            'best_r2_model': None,
            'best_rmse_model': None
        }
        
        # Count by type and name
        for model_info in self.models.values():
            model_type = model_info['model_type']
            model_name = model_info['model_name']
            
            stats['models_by_type'][model_type] = \
                stats['models_by_type'].get(model_type, 0) + 1
            stats['models_by_name'][model_name] = \
                stats['models_by_name'].get(model_name, 0) + 1
        
        # Find best models
        try:
            best_r2 = self.get_best_model(metric='r2')
            stats['best_r2_model'] = best_r2['model_id']
        except:
            pass
        
        try:
            best_rmse = self.get_best_model(metric='rmse')
            stats['best_rmse_model'] = best_rmse['model_id']
        except:
            pass
        
        return stats
