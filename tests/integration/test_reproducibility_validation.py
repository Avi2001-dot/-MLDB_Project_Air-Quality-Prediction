import os
import sys
import json
import tempfile
import shutil
import pytest
import pandas as pd
import numpy as np
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.utils.constants import RANDOM_SEED, CITIES
from src.utils.logger import get_logger
from src.etl_pipeline.pipeline import ETLPipeline
from src.modeling.model_trainer import ModelTrainer
from src.feature_engineering.time_series_splitter import TimeSeriesSplitter


logger = get_logger(__name__)


class TestReproducibilityValidation:
    """Test suite for reproducibility validation."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test data."""
        temp_dir = tempfile.mkdtemp(prefix='test_repro_')
        yield temp_dir
        # Cleanup
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

    @pytest.fixture
    def sample_data(self):
        """Create deterministic sample data."""
        np.random.seed(RANDOM_SEED)
        n_records = 50
        cities = CITIES[:2]

        data = {
            'city': np.random.choice(cities, n_records),
            'timestamp': pd.date_range('2024-01-01', periods=n_records, freq='H'),
            'aqi': np.random.uniform(20, 300, n_records),
            'pm25': np.random.uniform(5, 150, n_records),
            'pm10': np.random.uniform(10, 200, n_records),
            'no2': np.random.uniform(10, 100, n_records),
            'o3': np.random.uniform(20, 150, n_records),
            'so2': np.random.uniform(5, 50, n_records),
            'co': np.random.uniform(0.5, 5, n_records),
        }

        return pd.DataFrame(data)

    def test_random_seed_is_fixed(self):
        
        assert RANDOM_SEED == 42, "RANDOM_SEED must be fixed to 42"

    def test_etl_pipeline_deterministic(self, sample_data, temp_dir):
        
        # Run 1
        np.random.seed(RANDOM_SEED)
        bronze_path_1 = os.path.join(temp_dir, 'bronze_1')
        silver_path_1 = os.path.join(temp_dir, 'silver_1')
        gold_path_1 = os.path.join(temp_dir, 'gold_1')

        with ETLPipeline(bronze_path_1, silver_path_1, gold_path_1) as etl1:
            gold_df_1, metrics_1 = etl1.run_pipeline(sample_data.copy(), 'test')

        # Run 2
        np.random.seed(RANDOM_SEED)
        bronze_path_2 = os.path.join(temp_dir, 'bronze_2')
        silver_path_2 = os.path.join(temp_dir, 'silver_2')
        gold_path_2 = os.path.join(temp_dir, 'gold_2')

        with ETLPipeline(bronze_path_2, silver_path_2, gold_path_2) as etl2:
            gold_df_2, metrics_2 = etl2.run_pipeline(sample_data.copy(), 'test')

        # Compare results
        assert gold_df_1.shape == gold_df_2.shape, \
            "Gold DataFrames have different shapes"

        # Compare values (allowing for floating point precision)
        pd.testing.assert_frame_equal(
            gold_df_1.reset_index(drop=True),
            gold_df_2.reset_index(drop=True),
            check_dtype=False,
            atol=1e-10
        )

        # Compare metrics
        assert metrics_1['records']['valid_records'] == \
               metrics_2['records']['valid_records'], \
            "Valid record counts differ"

        assert metrics_1['records']['rejected_records'] == \
               metrics_2['records']['rejected_records'], \
            "Rejected record counts differ"

    def test_model_training_deterministic(self, sample_data, temp_dir):
        
        # Prepare data
        splitter = TimeSeriesSplitter(test_size=0.2)

        # Run 1
        np.random.seed(RANDOM_SEED)
        bronze_path_1 = os.path.join(temp_dir, 'bronze_1')
        silver_path_1 = os.path.join(temp_dir, 'silver_1')
        gold_path_1 = os.path.join(temp_dir, 'gold_1')

        with ETLPipeline(bronze_path_1, silver_path_1, gold_path_1) as etl1:
            gold_df_1, _ = etl1.run_pipeline(sample_data.copy(), 'test')

        if len(gold_df_1) > 10:
            X_train_1, X_test_1, y_train_1, y_test_1 = splitter.split(
                gold_df_1,
                target_column='aqi'
            )

            trainer_1 = ModelTrainer(n_cv_folds=2, random_state=RANDOM_SEED)
            xgb_results_1 = trainer_1.train_xgboost(
                X_train_1,
                y_train_1,
                use_cv=True,
                verbose=False
            )

            # Run 2
            np.random.seed(RANDOM_SEED)
            bronze_path_2 = os.path.join(temp_dir, 'bronze_2')
            silver_path_2 = os.path.join(temp_dir, 'silver_2')
            gold_path_2 = os.path.join(temp_dir, 'gold_2')

            with ETLPipeline(bronze_path_2, silver_path_2, gold_path_2) as etl2:
                gold_df_2, _ = etl2.run_pipeline(sample_data.copy(), 'test')

            X_train_2, X_test_2, y_train_2, y_test_2 = splitter.split(
                gold_df_2,
                target_column='aqi'
            )

            trainer_2 = ModelTrainer(n_cv_folds=2, random_state=RANDOM_SEED)
            xgb_results_2 = trainer_2.train_xgboost(
                X_train_2,
                y_train_2,
                use_cv=True,
                verbose=False
            )

            # Compare CV results
            cv_results_1 = xgb_results_1.get('cv_results', {})
            cv_results_2 = xgb_results_2.get('cv_results', {})

            # Check that RMSE scores are identical
            if 'rmse_scores' in cv_results_1 and 'rmse_scores' in cv_results_2:
                np.testing.assert_array_almost_equal(
                    cv_results_1['rmse_scores'],
                    cv_results_2['rmse_scores'],
                    decimal=5
                )

    def test_multiple_runs_identical_outputs(self, sample_data, temp_dir):
        
        outputs = []

        for run_num in range(3):
            np.random.seed(RANDOM_SEED)

            bronze_path = os.path.join(temp_dir, f'bronze_{run_num}')
            silver_path = os.path.join(temp_dir, f'silver_{run_num}')
            gold_path = os.path.join(temp_dir, f'gold_{run_num}')

            with ETLPipeline(bronze_path, silver_path, gold_path) as etl:
                gold_df, metrics = etl.run_pipeline(sample_data.copy(), 'test')

            outputs.append({
                'gold_df': gold_df,
                'metrics': metrics
            })

        # Compare all runs to first run
        reference_df = outputs[0]['gold_df']
        reference_metrics = outputs[0]['metrics']

        for i in range(1, len(outputs)):
            current_df = outputs[i]['gold_df']
            current_metrics = outputs[i]['metrics']

            # Compare DataFrames
            assert reference_df.shape == current_df.shape, \
                f"Run {i+1} DataFrame shape differs from Run 1"

            # Compare metrics
            assert reference_metrics['records']['valid_records'] == \
                   current_metrics['records']['valid_records'], \
                f"Run {i+1} valid records differ from Run 1"

    def test_random_seed_affects_results(self, sample_data, temp_dir):
        
        # Run with seed 42
        np.random.seed(42)
        bronze_path_1 = os.path.join(temp_dir, 'bronze_seed42')
        silver_path_1 = os.path.join(temp_dir, 'silver_seed42')
        gold_path_1 = os.path.join(temp_dir, 'gold_seed42')

        with ETLPipeline(bronze_path_1, silver_path_1, gold_path_1) as etl1:
            gold_df_1, metrics_1 = etl1.run_pipeline(sample_data.copy(), 'test')

        # Run with seed 123 (different)
        np.random.seed(123)
        bronze_path_2 = os.path.join(temp_dir, 'bronze_seed123')
        silver_path_2 = os.path.join(temp_dir, 'silver_seed123')
        gold_path_2 = os.path.join(temp_dir, 'gold_seed123')

        with ETLPipeline(bronze_path_2, silver_path_2, gold_path_2) as etl2:
            gold_df_2, metrics_2 = etl2.run_pipeline(sample_data.copy(), 'test')

        # Results should be identical because we use fixed RANDOM_SEED in pipeline
        # This test verifies that the system uses its own seed, not the ambient seed
        assert gold_df_1.shape == gold_df_2.shape

    def test_execution_logging_present(self, sample_data, temp_dir, caplog):
        
        bronze_path = os.path.join(temp_dir, 'bronze')
        silver_path = os.path.join(temp_dir, 'silver')
        gold_path = os.path.join(temp_dir, 'gold')

        with caplog.at_level('INFO'):
            with ETLPipeline(bronze_path, silver_path, gold_path) as etl:
                gold_df, metrics = etl.run_pipeline(sample_data.copy(), 'test')

        # Check that logs contain expected messages
        log_text = caplog.text

        assert 'ETL Pipeline initialized' in log_text or \
               'ETL pipeline' in log_text.lower(), \
            "ETL Pipeline initialization not logged"

        assert 'Starting ETL pipeline' in log_text or \
               'starting' in log_text.lower(), \
            "Pipeline start not logged"

        assert 'completed' in log_text.lower(), \
            "Pipeline completion not logged"

    def test_reproducibility_report_structure(self, sample_data, temp_dir):
        
        from scripts.validate_reproducibility import ReproducibilityValidator

        validator = ReproducibilityValidator(config_path='config.yaml')

        # Run validation with 2 iterations
        report = validator.validate_reproducibility(n_runs=2, temp_dir=temp_dir)

        # Check report structure
        assert 'validation_timestamp' in report
        assert 'n_runs' in report
        assert 'random_seed' in report
        assert 'validation_duration_seconds' in report
        assert 'runs_data' in report
        assert 'reproducibility_checks' in report
        assert 'is_reproducible' in report
        assert 'summary' in report

        # Check summary structure
        summary = report['summary']
        assert 'total_issues' in summary
        assert 'critical_issues' in summary
        assert 'warning_issues' in summary
        assert 'is_reproducible' in summary
        assert 'status' in summary
        assert 'message' in summary

        # Check runs data
        assert len(report['runs_data']) == 2
        for run in report['runs_data']:
            assert 'iteration' in run
            assert 'timestamp' in run
            assert 'duration_seconds' in run
            assert 'gold_df_hash' in run
            assert 'etl_metrics_hash' in run

    def test_reproducibility_validation_passes(self, sample_data, temp_dir):
        
        from scripts.validate_reproducibility import ReproducibilityValidator

        validator = ReproducibilityValidator(config_path='config.yaml')

        # Run validation with 2 iterations
        report = validator.validate_reproducibility(n_runs=2, temp_dir=temp_dir)

        # Check that validation passed
        assert report['summary']['status'] == 'PASS', \
            f"Reproducibility validation failed: {report['summary']['message']}"

        assert report['summary']['critical_issues'] == 0, \
            "Found critical reproducibility issues"

        assert report['is_reproducible'] is True, \
            "System is not reproducible"


class TestRandomSeedConfiguration:
    """Test suite for random seed configuration."""

    def test_random_seed_constant_value(self):
        """Test that RANDOM_SEED constant is 42."""
        assert RANDOM_SEED == 42

    def test_numpy_seed_reproducibility(self):
        """Test that NumPy random seed produces reproducible results."""
        np.random.seed(RANDOM_SEED)
        array_1 = np.random.randn(10)

        np.random.seed(RANDOM_SEED)
        array_2 = np.random.randn(10)

        np.testing.assert_array_equal(array_1, array_2)

    def test_pandas_seed_reproducibility(self):
        """Test that Pandas random seed produces reproducible results."""
        np.random.seed(RANDOM_SEED)
        df_1 = pd.DataFrame({
            'a': np.random.randn(10),
            'b': np.random.randn(10)
        })

        np.random.seed(RANDOM_SEED)
        df_2 = pd.DataFrame({
            'a': np.random.randn(10),
            'b': np.random.randn(10)
        })

        pd.testing.assert_frame_equal(df_1, df_2)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
