import time
from datetime import datetime
from typing import Optional, Dict, Tuple
import pandas as pd
import logging

from pyspark.sql import SparkSession

from .bronze_layer import BronzeLayer
from .silver_layer import SilverLayer
from .gold_layer import GoldLayer
from .data_validator import DataQualityValidator
from ..utils.logger import get_logger
from ..utils.constants import (
    ETL_PROCESSING_TARGET_MINUTES,
    RANDOM_SEED
)


class ETLPipelineError(Exception):
    """Custom exception for ETL Pipeline operations."""
    pass


class ETLPipeline:
    

    def __init__(
        self,
        bronze_path: str,
        silver_path: str,
        gold_path: str,
        spark: Optional[SparkSession] = None
    ):
        
        try:
            self.logger = get_logger(__name__)

            # Initialize or use provided Spark session
            if spark is None:
                self.spark = SparkSession.builder \
                    .appName("AQI-ETL-Pipeline") \
                    .config("spark.sql.shuffle.partitions", "4") \
                    .config("spark.default.parallelism", "4") \
                    .getOrCreate()
                self.logger.info("Created new Spark session")
            else:
                self.spark = spark
                self.logger.info("Using provided Spark session")

            # Set random seed for reproducibility
            self.spark.sparkContext.setRandomSeed(RANDOM_SEED)

            # Initialize layers
            self.bronze_layer = BronzeLayer(bronze_path, self.spark)
            self.silver_layer = SilverLayer(silver_path, self.spark)
            self.gold_layer = GoldLayer(gold_path, self.spark)

            # Initialize validator
            self.validator = DataQualityValidator()

            # Performance metrics
            self.performance_metrics: Dict = {}

            self.logger.info("ETL Pipeline initialized successfully")

        except Exception as e:
            error_msg = f"Failed to initialize ETL Pipeline: {e}"
            self.logger.error(error_msg)
            raise ETLPipelineError(error_msg)

    def run_pipeline(
        self,
        bronze_df: pd.DataFrame,
        source: str
    ) -> Tuple[pd.DataFrame, Dict]:
        
        try:
            pipeline_start = time.time()
            self.logger.info(
                f"Starting ETL pipeline with {len(bronze_df)} records from '{source}'"
            )

            # Step 1: Store in Bronze Layer
            bronze_start = time.time()
            bronze_records = self.bronze_layer.store_data(bronze_df, source)
            bronze_time = time.time() - bronze_start

            # Step 2: Transform Bronze to Silver
            silver_start = time.time()
            silver_df, total_records, valid_records, rejected_records = \
                self.silver_layer.transform_bronze_to_silver(bronze_df)
            silver_time = time.time() - silver_start

            # Step 3: Validate data quality
            quality_start = time.time()
            quality_report = self.validator.validate_data(silver_df)
            quality_time = time.time() - quality_start

            # Step 4: Store in Silver Layer
            silver_store_start = time.time()
            if not silver_df.empty:
                silver_records = self.silver_layer.store_data(silver_df)
            else:
                silver_records = 0
            silver_store_time = time.time() - silver_store_start

            # Step 5: Transform Silver to Gold
            gold_start = time.time()
            if not silver_df.empty:
                gold_df = self.gold_layer.transform_silver_to_gold(silver_df)
            else:
                gold_df = pd.DataFrame()
            gold_time = time.time() - gold_start

            # Step 6: Store in Gold Layer
            gold_store_start = time.time()
            if not gold_df.empty:
                gold_records = self.gold_layer.store_data(gold_df)
            else:
                gold_records = 0
            gold_store_time = time.time() - gold_store_start

            # Calculate total pipeline time
            pipeline_time = time.time() - pipeline_start

            # Compile performance metrics
            self.performance_metrics = {
                'total_time_seconds': pipeline_time,
                'total_time_minutes': pipeline_time / 60,
                'target_time_minutes': ETL_PROCESSING_TARGET_MINUTES,
                'within_target': pipeline_time / 60 <= ETL_PROCESSING_TARGET_MINUTES,
                'bronze_time_seconds': bronze_time,
                'silver_transform_time_seconds': silver_time,
                'silver_store_time_seconds': silver_store_time,
                'quality_check_time_seconds': quality_time,
                'gold_transform_time_seconds': gold_time,
                'gold_store_time_seconds': gold_store_time,
                'records': {
                    'bronze_ingested': bronze_records,
                    'total_records': total_records,
                    'valid_records': valid_records,
                    'rejected_records': rejected_records,
                    'silver_stored': silver_records,
                    'gold_stored': gold_records
                },
                'quality': {
                    'quality_score': quality_report['quality_score'],
                    'missing_values': quality_report['missing_values'],
                    'out_of_range': quality_report['out_of_range'],
                    'duplicates': quality_report['duplicates'],
                    'alerts': len(quality_report['alerts'])
                },
                'timestamp': datetime.now().isoformat()
            }

            self.logger.info(
                f"ETL pipeline completed in {pipeline_time:.2f}s "
                f"({pipeline_time/60:.2f}m). "
                f"Records: {valid_records} valid, {rejected_records} rejected. "
                f"Quality score: {quality_report['quality_score']:.2f}%"
            )

            return gold_df, self.performance_metrics

        except Exception as e:
            error_msg = f"ETL pipeline execution failed: {e}"
            self.logger.error(error_msg)
            raise ETLPipelineError(error_msg)

    def get_performance_metrics(self) -> Dict:
        
        return self.performance_metrics

    def stop_spark_session(self) -> None:
        
        try:
            if self.spark:
                self.spark.stop()
                self.logger.info("Spark session stopped")
        except Exception as e:
            error_msg = f"Failed to stop Spark session: {e}"
            self.logger.error(error_msg)
            raise ETLPipelineError(error_msg)

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_spark_session()
