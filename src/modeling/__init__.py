"""
Machine Learning Modeling Module – lazy imports.

xgboost and scikit-learn are only imported when the classes are actually used.
"""

def __getattr__(name):
    _map = {
        'XGBoostModel':                  ('src.modeling.xgboost_model',                  'XGBoostModel'),
        'XGBoostModelError':             ('src.modeling.xgboost_model',                  'XGBoostModelError'),
        'RandomForestModel':             ('src.modeling.random_forest_model',             'RandomForestModel'),
        'RandomForestModelError':        ('src.modeling.random_forest_model',             'RandomForestModelError'),
        'TimeSeriesCrossValidator':      ('src.modeling.time_series_cross_validator',     'TimeSeriesCrossValidator'),
        'TimeSeriesCrossValidatorError': ('src.modeling.time_series_cross_validator',     'TimeSeriesCrossValidatorError'),
        'ModelEvaluator':                ('src.modeling.model_evaluator',                 'ModelEvaluator'),
        'ModelEvaluatorError':           ('src.modeling.model_evaluator',                 'ModelEvaluatorError'),
        'ModelTrainer':                  ('src.modeling.model_trainer',                   'ModelTrainer'),
        'ModelTrainerError':             ('src.modeling.model_trainer',                   'ModelTrainerError'),
        'ModelRegistry':                 ('src.modeling.model_registry',                  'ModelRegistry'),
        'ModelRegistryError':            ('src.modeling.model_registry',                  'ModelRegistryError'),
    }
    if name in _map:
        import importlib
        module_path, attr = _map[name]
        module = importlib.import_module(module_path)
        return getattr(module, attr)
    raise AttributeError(f"module 'src.modeling' has no attribute {name!r}")


__all__ = [
    'XGBoostModel', 'XGBoostModelError',
    'RandomForestModel', 'RandomForestModelError',
    'TimeSeriesCrossValidator', 'TimeSeriesCrossValidatorError',
    'ModelEvaluator', 'ModelEvaluatorError',
    'ModelTrainer', 'ModelTrainerError',
    'ModelRegistry', 'ModelRegistryError',
]
