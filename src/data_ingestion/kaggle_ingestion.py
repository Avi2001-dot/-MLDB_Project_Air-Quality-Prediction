"""
Kaggle data ingestion module for Air Quality Prediction System.

This module provides the KaggleDataIngestion class for downloading and
processing historical AQI data from the Kaggle dataset with retry logic,
error handling, and data validation.
"""

import os
import time
from typing import Optional
from datetime import datetime
import pandas as pd

from ..utils.logger import get_logger
from ..utils.constants import (
    MAX_RETRIES,
    RETRY_DELAY_SECONDS,
    AQI_MIN,
    AQI_MAX,
    CRITICAL_FIELDS
)

logger = get_logger(__name__)


class KaggleConnectionError(Exception):
    """Exception raised for Kaggle API connection failures."""

    pass


class KaggleDataIngestion:
    """
    Service for downloading and processing historical AQI data from Kaggle.

    This class handles authentication with the Kaggle API, dataset download,
    retry logic with exponential backoff, and data validation.

    Attributes:
        api_key_path: Path to Kaggle API credentials file
        dataset_name: Name of the Kaggle dataset to download
        api: Kaggle API client instance
    """

    def __init__(self, api_key_path: str, dataset_name: str):
        """
        Initialize Kaggle data ingestion service.

        Args:
            api_key_path: Path to Kaggle API credentials file (kaggle.json)
            dataset_name: Name of the Kaggle dataset (e.g., 'username/dataset-name')

        Raises:
            FileNotFoundError: If API key file does not exist
            KaggleConnectionError: If API authentication fails
        """
        self.api_key_path = api_key_path
        self.dataset_name = dataset_name

        # Validate API key file exists
        if not os.path.exists(api_key_path):
            error_msg = f"Kaggle API key file not found: {api_key_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        # Initialize Kaggle API client
        try:
            from kaggle.api.kaggle_api_extended import KaggleApi
            self.api = KaggleApi()
            self.api.authenticate()
            logger.info(
                f"Kaggle API authenticated successfully at "
                f"{datetime.now().isoformat()}"
            )
        except Exception as e:
            error_msg = f"Failed to authenticate with Kaggle API: {e}"
            logger.error(error_msg)
            raise KaggleConnectionError(error_msg)

    def fetch_data(
        self,
        output_path: str,
        max_retries: int = MAX_RETRIES
    ) -> pd.DataFrame:
        """
        Download dataset from Kaggle with exponential backoff retry logic.

        Args:
            output_path: Local path to store downloaded data
            max_retries: Maximum number of retry attempts (default: 3)

        Returns:
            DataFrame containing the downloaded AQI data

        Raises:
            KaggleConnectionError: If download fails after all retries
            FileNotFoundError: If downloaded files cannot be found
            ValueError: If data schema validation fails
        """
        logger.info(
            f"Starting Kaggle dataset download at {datetime.now().isoformat()}"
        )

        # Create output directory if it doesn't exist
        os.makedirs(output_path, exist_ok=True)

        # Download with retry logic
        df = self._retry_with_backoff(
            func=lambda: self._download_dataset(output_path),
            max_retries=max_retries,
            initial_delay=RETRY_DELAY_SECONDS
        )

        if df is None:
            error_msg = (
                f"Failed to download Kaggle dataset after {max_retries} retries"
            )
            logger.error(error_msg)
            raise KaggleConnectionError(error_msg)

        # Validate downloaded data
        if not self._validate_schema(df):
            error_msg = "Downloaded data failed schema validation"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(
            f"Kaggle dataset download completed at "
            f"{datetime.now().isoformat()}. "
            f"Records: {len(df)}"
        )

        return df

    def _download_dataset(self, output_path: str) -> Optional[pd.DataFrame]:
        """
        Download dataset from Kaggle API.

        Args:
            output_path: Local path to store downloaded data

        Returns:
            DataFrame with downloaded data, or None if download fails

        Raises:
            KaggleConnectionError: If API call fails
        """
        try:
            logger.info(
                f"Downloading dataset '{self.dataset_name}' from Kaggle at "
                f"{datetime.now().isoformat()}"
            )

            # Download dataset files
            self.api.dataset_download_files(
                self.dataset_name,
                path=output_path,
                unzip=True
            )

            logger.info(
                f"Dataset files downloaded to {output_path} at "
                f"{datetime.now().isoformat()}"
            )

            # Find and load CSV files
            csv_files = [
                f for f in os.listdir(output_path)
                if f.endswith('.csv')
            ]

            if not csv_files:
                error_msg = f"No CSV files found in {output_path}"
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)

            logger.info(f"Found {len(csv_files)} CSV file(s): {csv_files}")

            # Load the first CSV file (or combine multiple if needed)
            csv_path = os.path.join(output_path, csv_files[0])
            logger.info(f"Loading data from {csv_path}")

            df = pd.read_csv(csv_path)

            logger.info(
                f"Data loaded successfully. Shape: {df.shape}. "
                f"Columns: {list(df.columns)}"
            )

            return df

        except Exception as e:
            logger.error(
                f"Failed to download dataset from Kaggle: {e}. "
                f"Timestamp: {datetime.now().isoformat()}"
            )
            raise KaggleConnectionError(str(e))

    def _validate_schema(self, df: pd.DataFrame) -> bool:
        """
        Validate downloaded data structure and schema.

        Checks for:
        - Required columns (city, timestamp, aqi, pollutants)
        - Data types
        - Empty DataFrame
        - AQI value ranges

        Args:
            df: DataFrame to validate

        Returns:
            True if validation passes, False otherwise
        """
        logger.info(
            f"Starting schema validation at {datetime.now().isoformat()}"
        )

        # Check for empty DataFrame
        if df.empty:
            logger.error("Downloaded DataFrame is empty")
            return False

        logger.info(f"DataFrame shape: {df.shape}")
        logger.info(f"Columns: {list(df.columns)}")

        # Check for required columns
        required_columns = ['city', 'timestamp', 'aqi']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            logger.error(
                f"Missing required columns: {missing_columns}. "
                f"Available columns: {list(df.columns)}"
            )
            return False

        logger.info("All required columns present")

        # Check for critical fields with null values
        for field in CRITICAL_FIELDS:
            null_count = df[field].isna().sum()
            if null_count > 0:
                logger.warning(
                    f"Field '{field}' has {null_count} null values "
                    f"({null_count / len(df) * 100:.2f}%)"
                )

        # Validate AQI data type and range
        try:
            df['aqi'] = pd.to_numeric(df['aqi'], errors='coerce')
            invalid_aqi = df[(df['aqi'] < AQI_MIN) | (df['aqi'] > AQI_MAX)].shape[0]

            if invalid_aqi > 0:
                logger.warning(
                    f"Found {invalid_aqi} records with AQI outside range "
                    f"[{AQI_MIN}, {AQI_MAX}]"
                )

            logger.info(f"AQI range validation: {invalid_aqi} invalid records")

        except Exception as e:
            logger.error(f"Failed to validate AQI column: {e}")
            return False

        # Validate timestamp format
        try:
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            invalid_timestamps = df['timestamp'].isna().sum()

            if invalid_timestamps > 0:
                logger.warning(
                    f"Found {invalid_timestamps} records with invalid timestamps"
                )

            logger.info(
                f"Timestamp validation: {invalid_timestamps} invalid records"
            )

        except Exception as e:
            logger.error(f"Failed to validate timestamp column: {e}")
            return False

        logger.info(
            f"Schema validation completed successfully at "
            f"{datetime.now().isoformat()}"
        )

        return True

    def _retry_with_backoff(
        self,
        func,
        max_retries: int = MAX_RETRIES,
        initial_delay: int = RETRY_DELAY_SECONDS
    ) -> Optional[pd.DataFrame]:
        """
        Execute function with exponential backoff retry logic.

        Implements exponential backoff: delay * (2 ** attempt)

        Args:
            func: Function to execute
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds

        Returns:
            Function result if successful, None if all retries fail
        """
        for attempt in range(max_retries):
            try:
                logger.info(
                    f"Attempt {attempt + 1}/{max_retries} at "
                    f"{datetime.now().isoformat()}"
                )
                return func()

            except Exception as e:
                if attempt < max_retries - 1:
                    # Calculate exponential backoff delay
                    delay = initial_delay * (2 ** attempt)
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay} seconds at "
                        f"{datetime.now().isoformat()}"
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"All {max_retries} retry attempts failed. "
                        f"Last error: {e}. "
                        f"Timestamp: {datetime.now().isoformat()}"
                    )
                    return None

        return None
