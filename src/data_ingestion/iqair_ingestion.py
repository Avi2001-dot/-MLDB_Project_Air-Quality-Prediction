import time
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd
import requests

from ..utils.logger import get_logger
from ..utils.constants import (
    MAX_RETRIES,
    RETRY_DELAY_SECONDS,
    CITIES,
    AQI_MIN,
    AQI_MAX,
    CRITICAL_FIELDS
)

logger = get_logger(__name__)


class IQAirAPIError(Exception):
    """Exception raised for IQAir API failures."""

    pass


class IQAirDataIngestion:
    """
    Service for fetching real-time AQI data from IQAir API.

    This class handles authentication with the IQAir API, city-based queries,
    retry logic with exponential backoff, and data parsing.

    Attributes:
        api_key: IQAir API key for authentication
        cities: List of cities to fetch data for
        base_url: Base URL for IQAir API
    """

    # IQAir API base URL
    BASE_URL = "https://api.waqi.info"

    def __init__(self, api_key: str, cities: Optional[List[str]] = None):
       
        # Validate API key
        if not api_key or not api_key.strip():
            error_msg = "API key cannot be empty"
            logger.error(error_msg)
            raise ValueError(error_msg)

        self.api_key = api_key.strip()

        # Use provided cities or default to all major Indian cities
        if cities is None:
            self.cities = CITIES
        else:
            self.cities = cities

        # Validate cities list has at least 10 cities
        if len(self.cities) < 10:
            error_msg = (
                f"Cities list must contain at least 10 cities, "
                f"got {len(self.cities)}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(
            f"IQAir API initialized at {datetime.now().isoformat()} "
            f"with {len(self.cities)} cities: {', '.join(self.cities)}"
        )

    def fetch_current_aqi(
        self,
        city: str,
        max_retries: int = MAX_RETRIES
    ) -> Dict:
      
        logger.info(
            f"Fetching current AQI for {city} at {datetime.now().isoformat()}"
        )

        # Fetch with retry logic
        response = self._retry_with_backoff(
            func=lambda: self._fetch_from_api(city),
            max_retries=max_retries,
            initial_delay=RETRY_DELAY_SECONDS
        )

        if response is None:
            error_msg = (
                f"Failed to fetch AQI for {city} after {max_retries} retries"
            )
            logger.error(error_msg)
            raise IQAirAPIError(error_msg)

        # Parse response
        try:
            parsed_data = self._parse_iqair_response(response, city)
            logger.info(
                f"Successfully fetched AQI for {city}: {parsed_data['aqi']} "
                f"at {datetime.now().isoformat()}"
            )
            return parsed_data
        except Exception as e:
            error_msg = f"Failed to parse IQAir response for {city}: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    def fetch_all_cities_aqi(
        self,
        max_retries: int = MAX_RETRIES
    ) -> pd.DataFrame:
      
        logger.info(
            f"Fetching AQI for all {len(self.cities)} cities at "
            f"{datetime.now().isoformat()}"
        )

        results = []
        failed_cities = []

        for city in self.cities:
            try:
                data = self.fetch_current_aqi(city, max_retries)
                results.append(data)
                logger.info(f"Successfully fetched data for {city}")
            except Exception as e:
                logger.warning(f"Failed to fetch data for {city}: {e}")
                failed_cities.append(city)

        if not results:
            error_msg = (
                f"Failed to fetch AQI data for all {len(self.cities)} cities"
            )
            logger.error(error_msg)
            raise IQAirAPIError(error_msg)

        # Log summary
        logger.info(
            f"Fetched AQI for {len(results)}/{len(self.cities)} cities. "
            f"Failed cities: {failed_cities if failed_cities else 'None'}"
        )

        # Convert to DataFrame
        df = pd.DataFrame(results)
        logger.info(
            f"Created DataFrame with {len(df)} records at "
            f"{datetime.now().isoformat()}"
        )

        return df

    def _fetch_from_api(self, city: str) -> Dict:
        """
        Fetch data from IQAir API for a single city.

        Args:
            city: City name to fetch data for

        Returns:
            Raw API response as dictionary

        Raises:
            requests.RequestException: If API call fails
        """
        try:
            url = f"{self.BASE_URL}/feed/{city}/?token={self.api_key}"
            logger.debug(f"Calling IQAir API: {url}")

            response = requests.get(url, timeout=10)
            response.raise_for_status()

            logger.debug(f"API response status: {response.status_code}")
            return response.json()

        except requests.exceptions.Timeout:
            error_msg = f"API request timeout for {city}"
            logger.error(error_msg)
            raise requests.RequestException(error_msg)
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error for {city}: {e}"
            logger.error(error_msg)
            raise requests.RequestException(error_msg)
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP error for {city}: {e}"
            logger.error(error_msg)
            raise requests.RequestException(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error fetching data for {city}: {e}"
            logger.error(error_msg)
            raise requests.RequestException(error_msg)

    def _parse_iqair_response(self, response: Dict, city: str) -> Dict:
     
        try:
            # Check for API error status
            if response.get('status') != 'ok':
                error_msg = (
                    f"API returned error status for {city}: "
                    f"{response.get('status')}"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Extract data section
            data = response.get('data', {})
            if not data:
                error_msg = f"No data section in API response for {city}"
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Extract AQI value
            aqi = data.get('aqi')
            if aqi is None:
                error_msg = f"Missing AQI value in response for {city}"
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Validate AQI range
            try:
                aqi = float(aqi)
                if aqi < AQI_MIN or aqi > AQI_MAX:
                    logger.warning(
                        f"AQI value {aqi} for {city} outside valid range "
                        f"[{AQI_MIN}, {AQI_MAX}]"
                    )
            except (ValueError, TypeError) as e:
                error_msg = f"Invalid AQI value for {city}: {aqi}"
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Extract timestamp
            timestamp = data.get('time', {}).get('iso')
            if not timestamp:
                logger.warning(f"Missing timestamp for {city}, using current time")
                timestamp = datetime.now().isoformat()

            # Extract pollutants (handle missing fields gracefully)
            pollutants = {}
            pollutant_keys = ['pm25', 'pm10', 'no2', 'o3', 'so2', 'co']
            for pollutant in pollutant_keys:
                value = data.get('iaqi', {}).get(pollutant, {}).get('v')
                pollutants[pollutant] = value if value is not None else None

            logger.debug(
                f"Parsed response for {city}: AQI={aqi}, "
                f"Pollutants={pollutants}"
            )

            return {
                'city': city,
                'timestamp': timestamp,
                'aqi': aqi,
                'pm25': pollutants.get('pm25'),
                'pm10': pollutants.get('pm10'),
                'no2': pollutants.get('no2'),
                'o3': pollutants.get('o3'),
                'so2': pollutants.get('so2'),
                'co': pollutants.get('co'),
                'source': 'iqair'
            }

        except ValueError:
            raise
        except Exception as e:
            error_msg = f"Unexpected error parsing response for {city}: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    def _retry_with_backoff(
        self,
        func,
        max_retries: int = MAX_RETRIES,
        initial_delay: int = RETRY_DELAY_SECONDS
    ) -> Optional[Dict]:
       
        for attempt in range(max_retries):
            try:
                logger.debug(
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
