import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import os
import sys

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.utils.constants import (
    CITIES,
    AQI_THRESHOLDS,
    AQI_COLORS,
    ALERT_LEVELS,
    DASHBOARD_REFRESH_INTERVAL_MINUTES
)
from src.utils.logger import get_logger
from src.dashboard.data_store import DataStore

# ============================================================================
# CONSTANTS
# ============================================================================

REFRESH_INTERVAL_SECONDS = DASHBOARD_REFRESH_INTERVAL_MINUTES * 60
PAGE_CONFIG = {
    'page_title': 'Air Quality Dashboard',
    'page_icon': '🌍',
    'layout': 'wide',
    'initial_sidebar_state': 'expanded'
}

# ============================================================================
# LOGGER SETUP
# ============================================================================

logger = get_logger(__name__)

# ============================================================================
# STREAMLIT PAGE CONFIGURATION
# ============================================================================


def configure_page():
    """Configure Streamlit page settings and styling."""
    st.set_page_config(**PAGE_CONFIG)
    
    # Custom CSS for styling
    st.markdown("""
        <style>
        .metric-card {
            background-color: #f0f2f6;
            padding: 20px;
            border-radius: 10px;
            margin: 10px 0;
        }
        .alert-critical {
            background-color: #ff4444;
            color: white;
            padding: 15px;
            border-radius: 5px;
            margin: 10px 0;
        }
        .alert-severe {
            background-color: #ff6666;
            color: white;
            padding: 15px;
            border-radius: 5px;
            margin: 10px 0;
        }
        .alert-warning {
            background-color: #ffaa00;
            color: white;
            padding: 15px;
            border-radius: 5px;
            margin: 10px 0;
        }
        .alert-info {
            background-color: #0066cc;
            color: white;
            padding: 15px;
            border-radius: 5px;
            margin: 10px 0;
        }
        </style>
    """, unsafe_allow_html=True)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def get_aqi_category(aqi: float) -> str:
   
    for category, (min_val, max_val) in AQI_THRESHOLDS.items():
        if min_val <= aqi <= max_val:
            return category
    return 'Unknown'


def get_aqi_color(aqi: float) -> str:
  
    category = get_aqi_category(aqi)
    return AQI_COLORS.get(category, '#CCCCCC')


def get_alert_emoji(level: str) -> str:
 
    emoji_map = {
        'none': '🟢',
        'info': '🔵',
        'warning': '🟡',
        'severe': '🔴',
        'critical': '🔴'
    }
    return emoji_map.get(level, '⚪')


# ============================================================================
# SIDEBAR COMPONENTS
# ============================================================================


def render_sidebar() -> Tuple[List[str], Optional[str]]:
 
    st.sidebar.title('🔧 Dashboard Controls')
    
    # City selection
    st.sidebar.subheader('City Selection')
    selected_cities = st.sidebar.multiselect(
        'Select Cities to Monitor',
        CITIES,
        default=CITIES[:3],
        help='Choose one or more cities to display on the dashboard'
    )
    
    if not selected_cities:
        st.sidebar.warning('Please select at least one city')
        selected_cities = CITIES[:1]
    
    # Refresh information
    st.sidebar.subheader('Refresh Information')
    st.sidebar.info(
        f'Dashboard auto-refreshes every {DASHBOARD_REFRESH_INTERVAL_MINUTES} minutes'
    )
    
    # Manual refresh button
    if st.sidebar.button('🔄 Refresh Now', use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    # About section
    st.sidebar.subheader('About')
    st.sidebar.markdown("""
    **Air Quality Prediction Dashboard**
    
    Real-time monitoring and forecasting of air quality across major Indian cities.
    
    - 🌍 Current AQI values
    - 📈 24-hour forecasts
    - 🚨 Active alerts
    - 📊 Historical trends
    """)
    
    return selected_cities, None


# ============================================================================
# TAB 1: CURRENT AQI
# ============================================================================


def render_current_aqi(data_store: DataStore, cities: List[str]):
   
    st.subheader('📊 Current Air Quality Index')
    
    # Create columns for city metrics
    cols = st.columns(min(len(cities), 3))
    
    for idx, city in enumerate(cities):
        col_idx = idx % 3
        
        try:
            current_data = data_store.get_latest_aqi(city)
            
            if current_data is not None:
                aqi = current_data.get('aqi', 0)
                category = get_aqi_category(aqi)
                color = get_aqi_color(aqi)
                timestamp = current_data.get('timestamp', 'N/A')
                
                with cols[col_idx]:
                    # Display AQI metric
                    st.metric(
                        label=f'**{city}**',
                        value=f'{aqi:.1f}',
                        delta=category,
                        delta_color='off'
                    )
                    
                    # Display category with color
                    st.markdown(
                        f"""
                        <div style='background-color: {color}; 
                        padding: 10px; border-radius: 5px; 
                        text-align: center; color: white; font-weight: bold;'>
                        {category}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    
                    # Display timestamp
                    st.caption(f'Last updated: {timestamp}')
            else:
                with cols[col_idx]:
                    st.warning(f'No data available for {city}')
                    
        except Exception as e:
            logger.error(f'Error rendering AQI for {city}: {e}')
            with cols[col_idx]:
                st.error(f'Error loading data for {city}')
    
    # Display AQI category legend
    st.subheader('AQI Category Reference')
    legend_cols = st.columns(5)
    
    for idx, (category, (min_val, max_val)) in enumerate(AQI_THRESHOLDS.items()):
        color = AQI_COLORS[category]
        with legend_cols[idx]:
            st.markdown(
                f"""
                <div style='background-color: {color}; 
                padding: 10px; border-radius: 5px; 
                text-align: center; color: white;'>
                <strong>{category}</strong><br>
                {min_val}-{max_val}
                </div>
                """,
                unsafe_allow_html=True
            )


# ============================================================================
# TAB 2: FORECASTS
# ============================================================================


def render_forecasts(data_store: DataStore, cities: List[str]):
  
    st.subheader('📈 24-Hour AQI Forecast')
    
    for city in cities:
        try:
            forecast_data = data_store.get_forecast(city)
            
            if forecast_data is not None and len(forecast_data) > 0:
                # Create forecast chart
                fig = go.Figure()
                
                # Add predicted AQI line
                fig.add_trace(go.Scatter(
                    x=forecast_data['timestamp'],
                    y=forecast_data['predicted_aqi'],
                    mode='lines+markers',
                    name='Predicted AQI',
                    line=dict(color='#0066cc', width=2),
                    marker=dict(size=6)
                ))
                
                # Add confidence interval (upper bound)
                fig.add_trace(go.Scatter(
                    x=forecast_data['timestamp'],
                    y=forecast_data.get('upper_bound', forecast_data['predicted_aqi']),
                    fill=None,
                    mode='lines',
                    line_color='rgba(0,0,255,0)',
                    showlegend=False
                ))
                
                # Add confidence interval (lower bound with fill)
                fig.add_trace(go.Scatter(
                    x=forecast_data['timestamp'],
                    y=forecast_data.get('lower_bound', forecast_data['predicted_aqi']),
                    fill='tonexty',
                    mode='lines',
                    line_color='rgba(0,0,255,0)',
                    name='Confidence Interval',
                    fillcolor='rgba(0,102,204,0.2)'
                ))
                
                # Update layout
                fig.update_layout(
                    title=f'{city} - 24 Hour AQI Forecast',
                    xaxis_title='Time',
                    yaxis_title='AQI',
                    hovermode='x unified',
                    height=400,
                    template='plotly_white'
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f'No forecast data available for {city}')
                
        except Exception as e:
            logger.error(f'Error rendering forecast for {city}: {e}')
            st.error(f'Error loading forecast for {city}')


# ============================================================================
# TAB 3: ALERTS
# ============================================================================


def render_alerts(data_store: DataStore):
 
    st.subheader('🚨 Active Pollution Alerts')
    
    try:
        alerts = data_store.get_active_alerts()
        
        if alerts and len(alerts) > 0:
            # Sort alerts by level (critical first)
            level_order = {'critical': 0, 'severe': 1, 'warning': 2, 'info': 3}
            alerts = sorted(
                alerts,
                key=lambda x: level_order.get(x.get('level', 'info'), 4)
            )
            
            for alert in alerts:
                level = alert.get('level', 'info')
                city = alert.get('city', 'Unknown')
                alert_type = alert.get('alert_type', 'unknown')
                current_aqi = alert.get('current_aqi', 'N/A')
                predicted_aqi = alert.get('predicted_aqi', 'N/A')
                timestamp = alert.get('timestamp', 'N/A')
                
                emoji = get_alert_emoji(level)
                
                # Display alert with appropriate styling
                alert_class = f'alert-{level}'
                st.markdown(
                    f"""
                    <div class='{alert_class}'>
                    <strong>{emoji} {level.upper()} ALERT - {city}</strong><br>
                    Type: {alert_type}<br>
                    Current AQI: {current_aqi}<br>
                    Predicted AQI: {predicted_aqi}<br>
                    Time: {timestamp}
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            st.success('✅ No active alerts - Air quality is good!')
            
    except Exception as e:
        logger.error(f'Error rendering alerts: {e}')
        st.error('Error loading alerts')


# ============================================================================
# TAB 4: HISTORICAL TRENDS
# ============================================================================


def render_historical_trends(data_store: DataStore, cities: List[str]):
  
    st.subheader('📊 7-Day Historical Trends')
    
    # Date range selection
    col1, col2 = st.columns(2)
    with col1:
        days_back = st.slider(
            'Days to display',
            min_value=1,
            max_value=30,
            value=7,
            help='Select number of days to display in historical trends'
        )
    
    try:
        # Create figure for multi-city comparison
        fig = go.Figure()
        
        colors = ['#0066cc', '#ff6600', '#00cc66', '#cc0000', '#6600cc']
        
        for idx, city in enumerate(cities):
            historical_data = data_store.get_historical_aqi(city, days=days_back)
            
            if historical_data is not None and len(historical_data) > 0:
                color = colors[idx % len(colors)]
                
                fig.add_trace(go.Scatter(
                    x=historical_data['timestamp'],
                    y=historical_data['aqi'],
                    mode='lines+markers',
                    name=city,
                    line=dict(color=color, width=2),
                    marker=dict(size=4)
                ))
        
        # Update layout
        fig.update_layout(
            title=f'{days_back}-Day AQI Trends',
            xaxis_title='Date',
            yaxis_title='AQI',
            hovermode='x unified',
            height=500,
            template='plotly_white'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        logger.error(f'Error rendering historical trends: {e}')
        st.error('Error loading historical trends')


# ============================================================================
# MAIN DASHBOARD
# ============================================================================


def main():
  
    # Configure page
    configure_page()
    
    # Main title
    st.title('🌍 Real-Time Air Quality Prediction Dashboard')
    st.markdown(
        'Monitor air quality across major Indian cities with real-time data, '
        'forecasts, and alerts.'
    )
    
    # Initialize data store
    try:
        data_store = DataStore()
    except Exception as e:
        logger.error(f'Failed to initialize data store: {e}')
        st.error('Failed to initialize dashboard. Please check system logs.')
        return
    
    # Render sidebar
    selected_cities, _ = render_sidebar()
    
    # Create tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        '📊 Current AQI',
        '📈 Forecasts',
        '🚨 Alerts',
        '📉 Historical Trends'
    ])
    
    # Render tab content
    with tab1:
        render_current_aqi(data_store, selected_cities)
    
    with tab2:
        render_forecasts(data_store, selected_cities)
    
    with tab3:
        render_alerts(data_store)
    
    with tab4:
        render_historical_trends(data_store, selected_cities)
    
    # Footer
    st.markdown('---')
    st.markdown(
        f'Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | '
        f'Auto-refresh interval: {DASHBOARD_REFRESH_INTERVAL_MINUTES} minutes'
    )


if __name__ == '__main__':
    main()
