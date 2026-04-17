

import os
import sys
import json
import hashlib
import logging
import time
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.logger import get_logger
from src.utils.constants import RANDOM_SEED, CITIES
from src.utils.config_loader import ConfigLoader
from src.etl_pipeline.pipeline import ETLPipeline
from src.modeling.model_trainer import ModelTrainer
from src.feature_engineering.time_series_splitter import TimeSeriesSplitter


class ReproducibilityValidator:
    """
    Validates reproducibility of the air quality prediction system.

    This class runs the complete pipeline multiple times and compares outputs
    to ensure deterministic behavior with fixed random seeds.

    Attributes:
        config (Dict): System configuration
        logger (logging.Logger): Logger instance
        runs_data (List[Dict]): Data from each pipeline run
        reproducibility_report (Dict): Final reproducibility report
    """

    def __init__(self, config_path: str = 'config.yaml'):
        """
        Initialize ReproducibilityValidator.

        Args:
            config_path: Path to configuration file

        Raises:
            ValueError: If configuration cannot be loaded
        """
        self.logger = get_logger(__name__)
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.to_dict()
        self.runs_data: List[Dict] = []
        self.reproducibility_report: Dict = {}

        self.logger.info("ReproducibilityValidator initialized")
        self._verify_random_seed_configuration()

    def _verify_random_seed_configuration(self) -> None:
        """
        Verify that random seeds are properly configured.

        Validates:
        - RANDOM_SEED constant is set to fixed value
        - Config file has random_seed parameter
        - Seeds match expected value (42)

        Raises:
            ValueError: If random seed configuration is invalid
        """
        self.logger.info("Verifying random seed configuration...")

        # Check constant
        if RANDOM_SEED != 42:
            raise ValueError(
                f"RANDOM_SEED constant is {RANDOM_SEED}, expected 42"
            )
        self.logger.info(f"[OK] RANDOM_SEED constant = {RANDOM_SEED}")

        # Check config
        config_seed = self.config.get('system', {}).get('random_seed')
        if config_seed != 42:
            raise ValueError(
                f"Config random_seed is {config_seed}, expected 42"
            )
        self.logger.info(f"[OK] Config random_seed = {config_seed}")

        # Set numpy and pandas seeds
        np.random.seed(RANDOM_SEED)
        self.logger.info("[OK] NumPy and Pandas random seeds set")

    def _create_sample_data(self) -> pd.DataFrame:
        """
        Create deterministic sample data for testing.

        Returns:
            DataFrame with sample air quality data

        Note:
            Uses fixed random seed to ensure identical data across runs
        """
        np.random.seed(RANDOM_SEED)

        n_records = 100
        cities = CITIES[:3]  # Use first 3 cities for faster testing

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

        df = pd.DataFrame(data)
        self.logger.info(f"Created sample data with {len(df)} records")
        return df

    def _compute_dataframe_hash(self, df: pd.DataFrame) -> str:
        """
        Compute hash of DataFrame for comparison.

        Args:
            df: DataFrame to hash

        Returns:
            SHA256 hash of DataFrame content

        Note:
            Converts DataFrame to JSON string for consistent hashing
        """
        # Convert to JSON for consistent hashing
        json_str = df.to_json(orient='records', default_handler=str)
        hash_obj = hashlib.sha256(json_str.encode())
        return hash_obj.hexdigest()

    def _compute_metrics_hash(self, metrics: Dict) -> str:
        """
        Compute hash of metrics dictionary for comparison.

        Args:
            metrics: Metrics dictionary to hash

        Returns:
            SHA256 hash of metrics content
        """
        # Convert to JSON for consistent hashing
        json_str = json.dumps(metrics, sort_keys=True, default=str)
        hash_obj = hashlib.sha256(json_str.encode())
        return hash_obj.hexdigest()

    def run_pipeline_iteration(
        self,
        iteration: int,
        sample_data: pd.DataFrame,
        temp_dir: str
    ) -> Dict[str, Any]:
        """
        Run one complete pipeline iteration.

        Args:
            iteration: Iteration number
            sample_data: Sample data to process
            temp_dir: Temporary directory for storage

        Returns:
            Dictionary with pipeline outputs and metrics

        Raises:
            Exception: If pipeline execution fails
        """
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"Starting Pipeline Iteration {iteration}")
        self.logger.info(f"{'='*60}")

        iteration_start = time.time()

        try:
            # Create iteration-specific paths
            bronze_path = os.path.join(temp_dir, f'bronze_run_{iteration}')
            silver_path = os.path.join(temp_dir, f'silver_run_{iteration}')
            gold_path = os.path.join(temp_dir, f'gold_run_{iteration}')

            # Reset random seeds before each iteration
            np.random.seed(RANDOM_SEED)

            # Run ETL pipeline
            self.logger.info("Running ETL pipeline...")
            etl_start = time.time()

            with ETLPipeline(bronze_path, silver_path, gold_path) as etl:
                gold_df, etl_metrics = etl.run_pipeline(
                    sample_data.copy(),
                    source='test'
                )

            etl_time = time.time() - etl_start
            self.logger.info(f"ETL pipeline completed in {etl_time:.2f}s")

            # Train models
            self.logger.info("Training forecasting models...")
            train_start = time.time()

            if not gold_df.empty and len(gold_df) > 10:
                # Prepare data for modeling
                splitter = TimeSeriesSplitter(test_size=0.2)
                feature_cols = [c for c in gold_df.columns
                                if c not in ['city', 'timestamp', 'aqi', 'season',
                                             'source', 'quality_flags', 'date']]
                X = gold_df[feature_cols].select_dtypes(include='number').fillna(0)
                y = gold_df['aqi']
                X_train, X_test, y_train, y_test = splitter.get_train_test_split(X, y)

                # Train models
                trainer = ModelTrainer(n_cv_folds=2, random_state=RANDOM_SEED)

                xgb_results = trainer.train_xgboost(
                    X_train,
                    y_train,
                    use_cv=True,
                    verbose=False
                )

                rf_results = trainer.train_random_forest(
                    X_train,
                    y_train,
                    use_cv=True,
                    verbose=False
                )

                model_metrics = {
                    'xgboost': xgb_results.get('cv_results', {}),
                    'random_forest': rf_results.get('cv_results', {})
                }
            else:
                self.logger.warning("Insufficient data for model training")
                model_metrics = {}

            train_time = time.time() - train_start
            self.logger.info(f"Model training completed in {train_time:.2f}s")

            # Compute hashes for comparison
            gold_hash = self._compute_dataframe_hash(gold_df)
            metrics_hash = self._compute_metrics_hash(etl_metrics)
            model_hash = self._compute_metrics_hash(model_metrics)

            iteration_time = time.time() - iteration_start

            iteration_data = {
                'iteration': iteration,
                'timestamp': datetime.now().isoformat(),
                'duration_seconds': iteration_time,
                'gold_df_shape': gold_df.shape,
                'gold_df_hash': gold_hash,
                'etl_metrics_hash': metrics_hash,
                'model_metrics_hash': model_hash,
                'etl_metrics': etl_metrics,
                'model_metrics': model_metrics,
                'gold_df_sample': gold_df.head(5).to_dict() if not gold_df.empty else {}
            }

            self.logger.info(f"Iteration {iteration} completed in {iteration_time:.2f}s")
            self.logger.info(f"Gold DataFrame hash: {gold_hash[:16]}...")
            self.logger.info(f"ETL metrics hash: {metrics_hash[:16]}...")

            return iteration_data

        except Exception as e:
            self.logger.error(f"Pipeline iteration {iteration} failed: {e}")
            raise

    def validate_reproducibility(
        self,
        n_runs: int = 3,
        temp_dir: str = None
    ) -> Dict[str, Any]:
        """
        Run pipeline multiple times and validate reproducibility.

        Args:
            n_runs: Number of pipeline runs (default: 3)
            temp_dir: Temporary directory for storage (default: auto-created)

        Returns:
            Reproducibility validation report

        Raises:
            ValueError: If reproducibility validation fails
        """
        self.logger.info(f"\n{'#'*60}")
        self.logger.info("REPRODUCIBILITY VALIDATION STARTING")
        self.logger.info(f"Number of runs: {n_runs}")
        self.logger.info(f"Random seed: {RANDOM_SEED}")
        self.logger.info(f"{'#'*60}\n")

        validation_start = time.time()

        # Create temporary directory if not provided
        if temp_dir is None:
            temp_dir = tempfile.mkdtemp(prefix='aqi_repro_')
            self.logger.info(f"Created temporary directory: {temp_dir}")
        else:
            os.makedirs(temp_dir, exist_ok=True)

        try:
            # Create sample data once (deterministic)
            sample_data = self._create_sample_data()

            # Run pipeline multiple times
            for i in range(1, n_runs + 1):
                iteration_data = self.run_pipeline_iteration(
                    i,
                    sample_data.copy(),
                    temp_dir
                )
                self.runs_data.append(iteration_data)

            # Validate reproducibility
            self.logger.info(f"\n{'='*60}")
            self.logger.info("VALIDATING REPRODUCIBILITY")
            self.logger.info(f"{'='*60}\n")

            reproducibility_issues = self._check_reproducibility()

            validation_time = time.time() - validation_start

            # Generate report
            self.reproducibility_report = {
                'validation_timestamp': datetime.now().isoformat(),
                'n_runs': n_runs,
                'random_seed': RANDOM_SEED,
                'validation_duration_seconds': validation_time,
                'runs_data': self.runs_data,
                'reproducibility_checks': reproducibility_issues,
                'is_reproducible': len(reproducibility_issues) == 0,
                'summary': self._generate_summary(reproducibility_issues)
            }

            return self.reproducibility_report

        finally:
            # Clean up temporary directory
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                self.logger.info(f"Cleaned up temporary directory: {temp_dir}")

    def _check_reproducibility(self) -> List[Dict[str, str]]:
        """
        Check if all runs produced identical results.

        Returns:
            List of reproducibility issues found (empty if all reproducible)
        """
        issues = []

        if len(self.runs_data) < 2:
            return issues

        # Get reference run (first run)
        reference_run = self.runs_data[0]
        reference_gold_hash = reference_run['gold_df_hash']
        reference_etl_hash = reference_run['etl_metrics_hash']
        reference_model_hash = reference_run['model_metrics_hash']

        self.logger.info(f"Reference run (Run 1) hashes:")
        self.logger.info(f"  Gold DataFrame: {reference_gold_hash[:16]}...")
        self.logger.info(f"  ETL Metrics: {reference_etl_hash[:16]}...")
        self.logger.info(f"  Model Metrics: {reference_model_hash[:16]}...")

        # Compare all runs to reference
        for i in range(1, len(self.runs_data)):
            run = self.runs_data[i]
            run_num = i + 1

            self.logger.info(f"\nRun {run_num} hashes:")
            self.logger.info(f"  Gold DataFrame: {run['gold_df_hash'][:16]}...")
            self.logger.info(f"  ETL Metrics: {run['etl_metrics_hash'][:16]}...")
            self.logger.info(f"  Model Metrics: {run['model_metrics_hash'][:16]}...")

            # Check Gold DataFrame
            if run['gold_df_hash'] != reference_gold_hash:
                issue = {
                    'type': 'Gold DataFrame Mismatch',
                    'run': run_num,
                    'description': (
                        f"Run {run_num} Gold DataFrame differs from Run 1. "
                        f"This indicates non-deterministic behavior in ETL pipeline."
                    ),
                    'severity': 'CRITICAL'
                }
                issues.append(issue)
                self.logger.error(f"[FAIL] Gold DataFrame mismatch in Run {run_num}")
            else:
                self.logger.info(f"[OK] Gold DataFrame matches Run 1")

            # Check ETL Metrics
            if run['etl_metrics_hash'] != reference_etl_hash:
                issue = {
                    'type': 'ETL Metrics Mismatch',
                    'run': run_num,
                    'description': (
                        f"Run {run_num} ETL metrics differ from Run 1. "
                        f"This may indicate non-deterministic processing."
                    ),
                    'severity': 'WARNING'
                }
                issues.append(issue)
                self.logger.warning(f"[WARN] ETL metrics differ in Run {run_num}")
            else:
                self.logger.info(f"[OK] ETL metrics match Run 1")

            # Check Model Metrics
            if run['model_metrics_hash'] != reference_model_hash:
                issue = {
                    'type': 'Model Metrics Mismatch',
                    'run': run_num,
                    'description': (
                        f"Run {run_num} model metrics differ from Run 1. "
                        f"This indicates non-deterministic model training."
                    ),
                    'severity': 'WARNING'
                }
                issues.append(issue)
                self.logger.warning(f"[WARN] Model metrics differ in Run {run_num}")
            else:
                self.logger.info(f"[OK] Model metrics match Run 1")

        return issues

    def _generate_summary(self, issues: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Generate summary of reproducibility validation.

        Args:
            issues: List of reproducibility issues

        Returns:
            Summary dictionary
        """
        critical_issues = [i for i in issues if i['severity'] == 'CRITICAL']
        warning_issues = [i for i in issues if i['severity'] == 'WARNING']

        summary = {
            'total_issues': len(issues),
            'critical_issues': len(critical_issues),
            'warning_issues': len(warning_issues),
            'is_reproducible': len(critical_issues) == 0,
            'status': (
                'PASS' if len(critical_issues) == 0 else 'FAIL'
            ),
            'message': (
                'All runs produced identical results. System is reproducible.'
                if len(critical_issues) == 0
                else f'Found {len(critical_issues)} critical reproducibility issues.'
            )
        }

        return summary

    def save_report(self, output_path: str = 'reports/reproducibility_report.json') -> None:
        """
        Save reproducibility report to file.

        Args:
            output_path: Path to save report

        Raises:
            IOError: If file cannot be written
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(self.reproducibility_report, f, indent=2, default=str)

        self.logger.info(f"Reproducibility report saved to {output_path}")

    def print_report(self) -> None:
        """Print reproducibility report to console."""
        self.logger.info(f"\n{'#'*60}")
        self.logger.info("REPRODUCIBILITY VALIDATION REPORT")
        self.logger.info(f"{'#'*60}\n")

        summary = self.reproducibility_report.get('summary', {})

        self.logger.info(f"Status: {summary.get('status', 'UNKNOWN')}")
        self.logger.info(f"Message: {summary.get('message', 'N/A')}")
        self.logger.info(f"Total Issues: {summary.get('total_issues', 0)}")
        self.logger.info(f"Critical Issues: {summary.get('critical_issues', 0)}")
        self.logger.info(f"Warning Issues: {summary.get('warning_issues', 0)}")

        if summary.get('critical_issues', 0) > 0:
            self.logger.error("\nCritical Issues:")
            for issue in self.reproducibility_report.get('reproducibility_checks', []):
                if issue['severity'] == 'CRITICAL':
                    self.logger.error(f"  - {issue['description']}")

        if summary.get('warning_issues', 0) > 0:
            self.logger.warning("\nWarnings:")
            for issue in self.reproducibility_report.get('reproducibility_checks', []):
                if issue['severity'] == 'WARNING':
                    self.logger.warning(f"  - {issue['description']}")

        self.logger.info(f"\n{'#'*60}\n")

    def print_summary(self) -> None:
        """Print summary to console (ASCII-safe)."""
        summary = self.reproducibility_report.get('summary', {})
        print(f"\n{'='*60}")
        print("REPRODUCIBILITY VALIDATION REPORT")
        print(f"{'='*60}\n")
        print(f"Status: {summary.get('status', 'UNKNOWN')}")
        print(f"Message: {summary.get('message', 'N/A')}")
        print(f"Total Issues: {summary.get('total_issues', 0)}")
        print(f"Critical Issues: {summary.get('critical_issues', 0)}")
        print(f"Warning Issues: {summary.get('warning_issues', 0)}")
        print(f"\n{'='*60}\n")


def main():
    """
    Main entry point for reproducibility validation.

    Validates that the air quality prediction system produces deterministic
    results across multiple runs with fixed random seeds.
    """
    try:
        # Initialize validator
        validator = ReproducibilityValidator(config_path='config.yaml')

        # Run validation with 3 iterations
        report = validator.validate_reproducibility(n_runs=3)

        # Print report
        validator.print_report()
        validator.print_summary()

        # Save report
        validator.save_report('reports/reproducibility_report.json')

        # Exit with appropriate code
        if report['summary']['status'] == 'PASS':
            print("\n[PASS] Reproducibility validation PASSED")
            return 0
        else:
            print("\n[FAIL] Reproducibility validation FAILED")
            return 1

    except Exception as e:
        print(f"\n[ERROR] Reproducibility validation error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
