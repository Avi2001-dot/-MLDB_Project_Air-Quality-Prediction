import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Dict, List, Optional

from src.utils.monitoring import get_performance_monitor
from src.utils.logger import get_logger

logger = get_logger(__name__)


def setup_page_config():
    """Configure Streamlit page settings."""
    st.set_page_config(
        page_title="AQI System Monitoring Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )


def render_system_health_section():
    """Render system health metrics section."""
    st.header("System Health")

    monitor = get_performance_monitor()
    system_report = monitor.get_system_report()

    col1, col2, col3, col4 = st.columns(4)

    current_metrics = system_report.get('current_metrics', {})

    with col1:
        cpu_percent = current_metrics.get('cpu_percent', 0)
        st.metric(
            "CPU Usage",
            f"{cpu_percent:.1f}%",
            delta=None,
            delta_color="inverse"
        )

    with col2:
        memory_percent = current_metrics.get('memory_percent', 0)
        st.metric(
            "Memory Usage",
            f"{memory_percent:.1f}%",
            delta=None,
            delta_color="inverse"
        )

    with col3:
        disk_percent = current_metrics.get('disk_percent', 0)
        st.metric(
            "Disk Usage",
            f"{disk_percent:.1f}%",
            delta=None,
            delta_color="inverse"
        )

    with col4:
        is_healthy = system_report.get('is_healthy', False)
        status = "Healthy" if is_healthy else " Warning"
        st.metric("System Status", status)

    # Display warnings if any
    warnings = system_report.get('warnings', [])
    if warnings:
        st.warning(" System Warnings:")
        for warning in warnings:
            st.write(f"• {warning}")

    # Average metrics
    st.subheader("Average Metrics (Historical)")
    avg_metrics = system_report.get('average_metrics', {})

    if avg_metrics:
        col1, col2, col3 = st.columns(3)

        with col1:
            st.write(f"**Avg CPU:** {avg_metrics.get('avg_cpu_percent', 0):.1f}%")
            st.write(f"**Max CPU:** {avg_metrics.get('max_cpu_percent', 0):.1f}%")

        with col2:
            st.write(f"**Avg Memory:** {avg_metrics.get('avg_memory_percent', 0):.1f}%")
            st.write(f"**Max Memory:** {avg_metrics.get('max_memory_percent', 0):.1f}%")

        with col3:
            st.write(f"**Avg Disk:** {avg_metrics.get('avg_disk_percent', 0):.1f}%")
            st.write(f"**Max Disk:** {avg_metrics.get('max_disk_percent', 0):.1f}%")


def render_execution_times_section():
    """Render execution times section."""
    st.header("⏱️ Execution Times")

    monitor = get_performance_monitor()
    performance_report = monitor.get_performance_report()
    execution_times = performance_report.get('execution_times', {})

    if not execution_times:
        st.info("No execution time data available yet.")
        return

    # Create dataframe for execution times
    data = []
    for operation, stats in execution_times.items():
        data.append({
            'Operation': operation,
            'Count': stats.get('count', 0),
            'Min (s)': stats.get('min_seconds', 0),
            'Max (s)': stats.get('max_seconds', 0),
            'Mean (s)': stats.get('mean_seconds', 0),
            'Total (s)': stats.get('total_seconds', 0)
        })

    df = pd.DataFrame(data)

    # Display table
    st.dataframe(df, use_container_width=True)

    # Create visualization
    if len(df) > 0:
        fig = px.bar(
            df,
            x='Operation',
            y='Mean (s)',
            title='Average Execution Time by Operation',
            labels={'Mean (s)': 'Time (seconds)'},
            color='Mean (s)',
            color_continuous_scale='Viridis'
        )
        st.plotly_chart(fig, use_container_width=True)


def render_event_metrics_section():
    """Render event processing metrics section."""
    st.header("📈 Event Processing Metrics")

    monitor = get_performance_monitor()
    performance_report = monitor.get_performance_report()
    event_metrics = performance_report.get('event_metrics', {})

    if not event_metrics or event_metrics.get('event_count', 0) == 0:
        st.info("No event processing data available yet.")
        return

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total Events",
            f"{event_metrics.get('event_count', 0):,}"
        )

    with col2:
        error_rate = event_metrics.get('error_rate', 0) * 100
        st.metric(
            "Error Rate",
            f"{error_rate:.2f}%",
            delta=None,
            delta_color="inverse"
        )

    with col3:
        throughput = event_metrics.get('throughput_events_per_second', 0)
        st.metric(
            "Throughput",
            f"{throughput:.2f} events/s"
        )

    with col4:
        mean_latency = event_metrics.get('mean_latency_ms', 0)
        st.metric(
            "Mean Latency",
            f"{mean_latency:.2f} ms"
        )

    # Latency percentiles
    st.subheader("Latency Percentiles")
    col1, col2, col3 = st.columns(3)

    with col1:
        min_latency = event_metrics.get('min_latency_ms', 0)
        st.write(f"**Min:** {min_latency:.2f} ms")

    with col2:
        p95_latency = event_metrics.get('p95_latency_ms', 0)
        st.write(f"**P95:** {p95_latency:.2f} ms")

    with col3:
        max_latency = event_metrics.get('max_latency_ms', 0)
        st.write(f"**Max:** {max_latency:.2f} ms")

    # Create latency distribution visualization
    if event_metrics.get('event_count', 0) > 0:
        latency_data = {
            'Metric': ['Min', 'Mean', 'P95', 'P99', 'Max'],
            'Latency (ms)': [
                event_metrics.get('min_latency_ms', 0),
                event_metrics.get('mean_latency_ms', 0),
                event_metrics.get('p95_latency_ms', 0),
                event_metrics.get('p99_latency_ms', 0),
                event_metrics.get('max_latency_ms', 0)
            ]
        }

        fig = px.bar(
            latency_data,
            x='Metric',
            y='Latency (ms)',
            title='Event Processing Latency Distribution',
            color='Latency (ms)',
            color_continuous_scale='RdYlGn_r'
        )
        st.plotly_chart(fig, use_container_width=True)


def render_uptime_section():
    """Render system uptime section."""
    st.header(" System Uptime")

    monitor = get_performance_monitor()
    performance_report = monitor.get_performance_report()
    uptime_seconds = performance_report.get('uptime_seconds', 0)

    # Convert to human-readable format
    days = int(uptime_seconds // 86400)
    hours = int((uptime_seconds % 86400) // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    seconds = int(uptime_seconds % 60)

    uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Total Uptime", uptime_str)

    with col2:
        start_time = monitor.start_time.strftime('%Y-%m-%d %H:%M:%S')
        st.write(f"**Started:** {start_time}")


def render_monitoring_logs_section():
    """Render monitoring logs section."""
    st.header(" Monitoring Logs")

    # Check if logs directory exists
    log_file = Path('logs/system.log')

    if not log_file.exists():
        st.info("No log file found yet.")
        return

    # Read recent log entries
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()

        # Get last N lines
        n_lines = st.slider("Number of log lines to display", 10, 100, 50)
        recent_lines = lines[-n_lines:]

        # Display logs
        log_text = ''.join(recent_lines)
        st.code(log_text, language='log')

    except Exception as e:
        st.error(f"Failed to read log file: {str(e)}")


def render_metrics_export_section():
    """Render metrics export section."""
    st.header(" Export Metrics")

    monitor = get_performance_monitor()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("📥 Save Current Report"):
            try:
                filepath = monitor.save_report()
                st.success(f"Report saved to {filepath}")
            except Exception as e:
                st.error(f"Failed to save report: {str(e)}")

    with col2:
        if st.button("🔄 Refresh Metrics"):
            st.rerun()

    # Display last saved report
    metrics_dir = Path('metrics')
    if metrics_dir.exists():
        report_files = sorted(metrics_dir.glob('*.json'), reverse=True)

        if report_files:
            st.subheader("Recent Reports")
            for report_file in report_files[:5]:
                st.write(f"• {report_file.name}")


def main():
    """Main dashboard application."""
    setup_page_config()

    st.title("🎯 AQI System Monitoring Dashboard")
    st.markdown("---")

    # Sidebar
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Select View",
        [
            "System Health",
            "Execution Times",
            "Event Metrics",
            "System Uptime",
            "Logs",
            "Export"
        ]
    )

    # Auto-refresh
    refresh_interval = st.sidebar.slider(
        "Auto-refresh interval (seconds)",
        5,
        60,
        30
    )

    # Render selected page
    if page == "System Health":
        render_system_health_section()
    elif page == "Execution Times":
        render_execution_times_section()
    elif page == "Event Metrics":
        render_event_metrics_section()
    elif page == "System Uptime":
        render_uptime_section()
    elif page == "Logs":
        render_monitoring_logs_section()
    elif page == "Export":
        render_metrics_export_section()

    # Footer
    st.markdown("---")
    st.markdown(
        f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
        f"Auto-refresh: {refresh_interval}s"
    )

    # Auto-refresh
    import time
    time.sleep(refresh_interval)


if __name__ == "__main__":
    main()
