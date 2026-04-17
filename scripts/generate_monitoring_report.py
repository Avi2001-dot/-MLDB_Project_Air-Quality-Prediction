#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.monitoring import get_performance_monitor
from src.utils.logger import get_logger

logger = get_logger(__name__)


def generate_system_report(monitor) -> Dict[str, Any]:
    """
    Generate system health report.

    Args:
        monitor: PerformanceMonitor instance

    Returns:
        Dictionary with system health data
    """
    return monitor.get_system_report()


def generate_performance_report(monitor) -> Dict[str, Any]:
    """
    Generate performance report.

    Args:
        monitor: PerformanceMonitor instance

    Returns:
        Dictionary with performance data
    """
    return monitor.get_performance_report()


def generate_full_report(monitor) -> Dict[str, Any]:
    """
    Generate full monitoring report.

    Args:
        monitor: PerformanceMonitor instance

    Returns:
        Dictionary with all monitoring data
    """
    return monitor.get_full_report()


def generate_summary_report(monitor) -> Dict[str, Any]:
    """
    Generate summary report with key metrics.

    Args:
        monitor: PerformanceMonitor instance

    Returns:
        Dictionary with summary metrics
    """
    full_report = monitor.get_full_report()

    system_report = full_report.get('system', {})
    performance_report = full_report.get('performance', {})

    current_metrics = system_report.get('current_metrics', {})
    event_metrics = performance_report.get('event_metrics', {})
    execution_times = performance_report.get('execution_times', {})

    # Calculate summary statistics
    total_operations = len(execution_times)
    total_execution_time = sum(
        stats.get('total_seconds', 0)
        for stats in execution_times.values()
    )

    slowest_operation = None
    slowest_time = 0
    for op_name, stats in execution_times.items():
        mean_time = stats.get('mean_seconds', 0)
        if mean_time > slowest_time:
            slowest_time = mean_time
            slowest_operation = op_name

    return {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'system_health': {
                'cpu_percent': current_metrics.get('cpu_percent', 0),
                'memory_percent': current_metrics.get('memory_percent', 0),
                'disk_percent': current_metrics.get('disk_percent', 0),
                'is_healthy': system_report.get('is_healthy', False),
                'warnings_count': len(system_report.get('warnings', []))
            },
            'performance': {
                'uptime_seconds': performance_report.get('uptime_seconds', 0),
                'total_operations': total_operations,
                'total_execution_time_seconds': total_execution_time,
                'slowest_operation': slowest_operation,
                'slowest_operation_time_seconds': slowest_time
            },
            'event_processing': {
                'total_events': event_metrics.get('event_count', 0),
                'error_rate': event_metrics.get('error_rate', 0),
                'mean_latency_ms': event_metrics.get('mean_latency_ms', 0),
                'p95_latency_ms': event_metrics.get('p95_latency_ms', 0),
                'throughput_events_per_second': event_metrics.get(
                    'throughput_events_per_second', 0
                )
            }
        },
        'full_report': full_report
    }


def save_report(report: Dict[str, Any], output_path: Path) -> None:
    """
    Save report to JSON file.

    Args:
        report: Report dictionary
        output_path: Path to save report
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)

    logger.info(f"Report saved to {output_path}")


def print_summary(report: Dict[str, Any]) -> None:
    """
    Print summary report to console.

    Args:
        report: Report dictionary
    """
    summary = report.get('summary', {})

    print("\n" + "=" * 80)
    print("AQI SYSTEM MONITORING REPORT")
    print("=" * 80)
    print(f"Generated: {report.get('timestamp')}\n")

    # System Health
    print("SYSTEM HEALTH")
    print("-" * 80)
    system_health = summary.get('system_health', {})
    print(f"  CPU Usage:        {system_health.get('cpu_percent', 0):.1f}%")
    print(f"  Memory Usage:     {system_health.get('memory_percent', 0):.1f}%")
    print(f"  Disk Usage:       {system_health.get('disk_percent', 0):.1f}%")
    print(f"  System Status:    {'✅ Healthy' if system_health.get('is_healthy') else '⚠️ Warning'}")
    print(f"  Warnings:         {system_health.get('warnings_count', 0)}\n")

    # Performance
    print("PERFORMANCE")
    print("-" * 80)
    performance = summary.get('performance', {})
    uptime_seconds = performance.get('uptime_seconds', 0)
    days = int(uptime_seconds // 86400)
    hours = int((uptime_seconds % 86400) // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    print(f"  Uptime:           {days}d {hours}h {minutes}m")
    print(f"  Total Operations: {performance.get('total_operations', 0)}")
    print(f"  Total Exec Time:  {performance.get('total_execution_time_seconds', 0):.2f}s")
    slowest_op = performance.get('slowest_operation', 'N/A')
    slowest_time = performance.get('slowest_operation_time_seconds', 0)
    print(f"  Slowest Op:       {slowest_op} ({slowest_time:.3f}s)\n")

    # Event Processing
    print("EVENT PROCESSING")
    print("-" * 80)
    event_proc = summary.get('event_processing', {})
    print(f"  Total Events:     {event_proc.get('total_events', 0):,}")
    print(f"  Error Rate:       {event_proc.get('error_rate', 0) * 100:.2f}%")
    print(f"  Mean Latency:     {event_proc.get('mean_latency_ms', 0):.2f}ms")
    print(f"  P95 Latency:      {event_proc.get('p95_latency_ms', 0):.2f}ms")
    print(f"  Throughput:       {event_proc.get('throughput_events_per_second', 0):.2f} events/s\n")

    print("=" * 80 + "\n")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Generate monitoring and performance reports"
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='reports',
        help='Directory to save reports (default: reports)'
    )
    parser.add_argument(
        '--report-type',
        type=str,
        choices=['summary', 'full', 'system', 'performance'],
        default='summary',
        help='Type of report to generate (default: summary)'
    )
    parser.add_argument(
        '--print-summary',
        action='store_true',
        help='Print summary to console'
    )

    args = parser.parse_args()

    try:
        # Get performance monitor
        monitor = get_performance_monitor()

        # Generate report based on type
        if args.report_type == 'summary':
            report = generate_summary_report(monitor)
        elif args.report_type == 'full':
            report = generate_full_report(monitor)
        elif args.report_type == 'system':
            report = generate_system_report(monitor)
        elif args.report_type == 'performance':
            report = generate_performance_report(monitor)

        # Save report
        output_dir = Path(args.output_dir)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"monitoring_report_{args.report_type}_{timestamp}.json"
        output_path = output_dir / report_filename

        save_report(report, output_path)

        # Print summary if requested
        if args.print_summary and args.report_type == 'summary':
            print_summary(report)

        print(f"✅ Report generated successfully: {output_path}")

    except Exception as e:
        logger.error(f"Failed to generate report: {str(e)}")
        print(f"❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
