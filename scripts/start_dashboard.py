#!/usr/bin/env python3


import subprocess
import sys
import argparse
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import get_logger
from src.utils.config_loader import ConfigLoader

# ============================================================================
# LOGGER SETUP
# ============================================================================

logger = get_logger(__name__)

# ============================================================================
# MAIN FUNCTION
# ============================================================================


def main():
    """
    Main entry point for dashboard startup.
    
    Parses command-line arguments and launches the Streamlit application.
    """
    # Parse arguments
    parser = argparse.ArgumentParser(
        description='Start the Air Quality Prediction Dashboard'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8501,
        help='Port to run dashboard on (default: 8501)'
    )
    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='Host to bind dashboard to (default: 0.0.0.0)'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config.yaml',
        help='Path to configuration file (default: config.yaml)'
    )
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        config_loader = ConfigLoader(args.config)
        config = config_loader.to_dict()
        logger.info(f'Configuration loaded from {args.config}')
    except Exception as e:
        logger.warning(f'Failed to load configuration: {e}')
        config = {}
    
    # Get dashboard configuration
    dashboard_config = config.get('dashboard', {})
    port = args.port or dashboard_config.get('port', 8501)
    host = args.host or dashboard_config.get('host', '0.0.0.0')
    
    # Build streamlit command
    app_path = os.path.join(project_root, 'src', 'dashboard', 'app.py')
    
    streamlit_cmd = [
        'streamlit',
        'run',
        app_path,
        '--server.port', str(port),
        '--server.address', host,
        '--logger.level=info'
    ]
    
    logger.info(f'Starting dashboard on {host}:{port}')
    logger.info(f'Dashboard URL: http://localhost:{port}')
    
    # Launch streamlit
    try:
        subprocess.run(streamlit_cmd, check=True)
    except FileNotFoundError:
        logger.error('Streamlit not found. Please install it with: pip install streamlit')
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info('Dashboard stopped by user')
        sys.exit(0)
    except Exception as e:
        logger.error(f'Error starting dashboard: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
