#!/usr/bin/env python
"""Test script to verify project setup."""

import sys
sys.path.insert(0, '.')

def test_constants():
    """Test constants module."""
    try:
        from src.utils.constants import CITIES, AQI_THRESHOLDS, LAG_OFFSETS
        print('✓ Constants imported successfully')
        print(f'  - Cities: {len(CITIES)} cities configured')
        print(f'  - AQI Categories: {len(AQI_THRESHOLDS)} categories')
        print(f'  - Lag Offsets: {LAG_OFFSETS}')
        return True
    except Exception as e:
        print(f'✗ Failed to import constants: {e}')
        return False

def test_logger():
    """Test logger setup."""
    try:
        from src.utils.logger import setup_logging, get_logger
        logger = setup_logging('INFO', 'logs/test.log')
        print('✓ Logger configured successfully')
        return True
    except Exception as e:
        print(f'✗ Failed to setup logger: {e}')
        return False

def test_config():
    """Test config loader."""
    try:
        from src.utils.config_loader import load_config
        config = load_config('config.yaml')
        print('✓ Configuration loaded successfully')
        print(f'  - Environment: {config.get("system.environment")}')
        print(f'  - Log Level: {config.get("system.log_level")}')
        print(f'  - Cities: {len(config.get("cities", []))} configured')
        return True
    except Exception as e:
        print(f'✗ Failed to load configuration: {e}')
        return False

if __name__ == '__main__':
    print('Testing project setup...\n')
    
    results = [
        test_constants(),
        test_logger(),
        test_config()
    ]
    
    if all(results):
        print('\n✓ All setup checks passed!')
        sys.exit(0)
    else:
        print('\n✗ Some setup checks failed!')
        sys.exit(1)
