#!/usr/bin/env python3


import subprocess
import sys
import argparse
from pathlib import Path


def main():
    """Start the monitoring dashboard."""
    parser = argparse.ArgumentParser(
        description="Start the AQI System Monitoring Dashboard"
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8502,
        help='Port to run the dashboard on (default: 8502)'
    )
    parser.add_argument(
        '--host',
        type=str,
        default='localhost',
        help='Host to bind to (default: localhost)'
    )
    parser.add_argument(
        '--logger-level',
        type=str,
        default='info',
        choices=['debug', 'info', 'warning', 'error'],
        help='Streamlit logger level (default: info)'
    )

    args = parser.parse_args()

    # Get the path to the monitoring dashboard
    dashboard_path = Path(__file__).parent.parent / 'src' / 'dashboard' / 'monitoring_dashboard.py'

    if not dashboard_path.exists():
        print(f"Error: Dashboard file not found at {dashboard_path}")
        sys.exit(1)

    # Build streamlit command
    cmd = [
        'streamlit',
        'run',
        str(dashboard_path),
        '--server.port', str(args.port),
        '--server.address', args.host,
        '--logger.level', args.logger_level,
        '--client.showErrorDetails', 'true'
    ]

    print(f"Starting monitoring dashboard on {args.host}:{args.port}")
    print(f"Dashboard URL: http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop the dashboard")
    print()

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nDashboard stopped")
        sys.exit(0)
    except FileNotFoundError:
        print("Error: Streamlit is not installed. Install it with:")
        print("  pip install streamlit")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error running dashboard: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
