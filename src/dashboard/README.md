# Air Quality Prediction Dashboard

## Overview

The Air Quality Prediction Dashboard is a real-time web application built with Streamlit that provides comprehensive visualization and monitoring of air quality across major Indian cities. The dashboard integrates with the entire air quality prediction system to display current AQI values, 24-hour forecasts, active alerts, and historical trends.

## Features

### 1. Current AQI Display
- Real-time AQI values for selected cities
- Color-coded severity indicators (Green, Yellow, Orange, Red, Dark Red)
- AQI category classification (Good, Satisfactory, Moderately Polluted, Heavily Polluted, Severely Polluted)
- Last update timestamp for each city
- AQI category reference legend

### 2. 24-Hour Forecasts
- Predicted AQI values for the next 24 hours
- Confidence intervals and uncertainty bands
- Interactive line charts with hover information
- Multi-city forecast comparison

### 3. Active Alerts
- Real-time display of active pollution alerts
- Alert severity levels (Info, Warning, Severe, Critical)
- Current and predicted AQI values in alerts
- Alert timestamps and types (rule-based or model-based)
- Color-coded alert display by severity

### 4. Historical Trends
- 7-day historical AQI trends (configurable)
- Multi-city comparison charts
- Date range selection (1-30 days)
- Interactive visualization with hover details
- Trend analysis and pattern identification

### 5. Dashboard Controls
- City selection via sidebar multiselect
- Manual refresh button for immediate data updates
- Auto-refresh mechanism (5-minute interval by default)
- Responsive design for desktop and tablet viewing

## Architecture

### Components

```
Dashboard (Streamlit)
├── Data Store (data_store.py)
│   ├── Alert Store (SQLite)
│   ├── Model Registry (Trained Models)
│   └── Gold Layer (Feature-Engineered Data)
├── Current AQI Tab
├── Forecasts Tab
├── Alerts Tab
└── Historical Trends Tab
```

### Data Flow

1. **Data Ingestion**: Raw data from Kaggle and IQAir API
2. **ETL Pipeline**: Bronze → Silver → Gold layer transformations
3. **Model Training**: XGBoost and Random Forest models trained on Gold Layer data
4. **Streaming Pipeline**: Real-time feature computation and inference
5. **Alert Generation**: Rule-based and model-based alerts
6. **Dashboard Display**: Data Store retrieves and caches data for dashboard visualization

## Installation

### Prerequisites

- Python 3.8+
- pip package manager
- All dependencies from requirements.txt

### Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure data directories exist:
```bash
mkdir -p data/bronze data/silver data/gold data/models logs
```

3. Configure the system (optional):
```bash
cp config.yaml config.yaml.backup
# Edit config.yaml as needed
```

## Usage

### Starting the Dashboard

#### Option 1: Using the startup script
```bash
python scripts/start_dashboard.py --port 8501 --host 0.0.0.0
```

#### Option 2: Direct Streamlit command
```bash
streamlit run src/dashboard/app.py
```

#### Option 3: With custom configuration
```bash
python scripts/start_dashboard.py --port 8080 --config custom_config.yaml
```

### Accessing the Dashboard

Once started, the dashboard is available at:
```
http://localhost:8501
```

Or with custom port:
```
http://localhost:<PORT>
```

### Using the Dashboard

1. **Select Cities**: Use the sidebar multiselect to choose cities to monitor
2. **View Current AQI**: Check the "Current AQI" tab for real-time values
3. **Check Forecasts**: View the "Forecasts" tab for 24-hour predictions
4. **Monitor Alerts**: Check the "Alerts" tab for active pollution alerts
5. **Analyze Trends**: Use the "Historical Trends" tab to analyze patterns
6. **Refresh Data**: Click "Refresh Now" button or wait for auto-refresh

## Configuration

### Dashboard Settings

Edit `config.yaml` to customize dashboard behavior:

```yaml
dashboard:
  refresh_interval_minutes: 5    # Auto-refresh interval
  port: 8501                      # Dashboard port
  host: "0.0.0.0"                 # Dashboard host
```

### Data Sources

Configure data source paths in `config.yaml`:

```yaml
storage:
  bronze_path: "data/bronze"      # Raw data
  silver_path: "data/silver"      # Cleaned data
  gold_path: "data/gold"          # Features
  models_path: "data/models"      # Trained models
  logs_path: "logs"               # Logs
```

## Data Store Interface

The `DataStore` class provides the following methods:

### Current AQI
```python
data_store.get_latest_aqi(city: str) -> Optional[Dict]
```
Returns the latest AQI value for a city.

### Forecasts
```python
data_store.get_forecast(city: str, hours: int = 24) -> Optional[pd.DataFrame]
```
Returns 24-hour forecast for a city.

### Alerts
```python
data_store.get_active_alerts() -> List[Dict]
data_store.get_alerts_by_city(city: str) -> List[Dict]
data_store.get_alerts_by_level(level: str) -> List[Dict]
```
Returns active alerts with optional filtering.

### Historical Data
```python
data_store.get_historical_aqi(city: str, days: int = 7) -> Optional[pd.DataFrame]
```
Returns historical AQI data for specified number of days.

## Performance Considerations

### Caching

The dashboard implements intelligent caching to improve performance:
- Cache TTL: 5 minutes (configurable)
- Automatic cache invalidation
- Manual cache clearing via refresh button

### Optimization Tips

1. **Limit Cities**: Select only necessary cities to reduce data load
2. **Adjust Refresh Interval**: Increase interval for slower connections
3. **Use Filters**: Filter alerts by level or city to reduce display load
4. **Historical Range**: Limit historical data range to recent days

## Troubleshooting

### Dashboard Won't Start

**Error**: `ModuleNotFoundError: No module named 'streamlit'`
- **Solution**: Install Streamlit: `pip install streamlit`

**Error**: `Connection refused` when accessing dashboard
- **Solution**: Check if port is already in use, use different port: `--port 8502`

### No Data Displayed

**Issue**: Dashboard shows "No data available"
- **Solution**: Ensure ETL pipeline has run and Gold Layer data exists
- **Solution**: Check data paths in config.yaml
- **Solution**: Verify alert database exists at configured path

### Slow Performance

**Issue**: Dashboard is slow or unresponsive
- **Solution**: Reduce number of selected cities
- **Solution**: Increase cache TTL in config
- **Solution**: Reduce historical data range
- **Solution**: Check system resources (CPU, memory)

### Forecast Not Available

**Issue**: Forecast tab shows no data
- **Solution**: Ensure models are trained and registered
- **Solution**: Check model registry path in config
- **Solution**: Verify Gold Layer data exists for the city

## Development

### Adding New Components

To add new dashboard components:

1. Create a new render function in `app.py`:
```python
def render_custom_component(data_store: DataStore):
    """Render custom component."""
    st.subheader('Custom Component')
    # Implementation here
```

2. Add a new tab in the main dashboard:
```python
tab_custom = st.tabs([..., 'Custom'])
with tab_custom:
    render_custom_component(data_store)
```

### Extending Data Store

To add new data access methods:

1. Add method to `DataStore` class:
```python
def get_custom_data(self, city: str) -> Optional[Dict]:
    """Get custom data for city."""
    # Implementation here
```

2. Use in dashboard components:
```python
custom_data = data_store.get_custom_data(city)
```

## Testing

### Manual Testing

1. Start the dashboard
2. Verify all tabs load without errors
3. Test city selection and filtering
4. Verify data updates on refresh
5. Check alert display and formatting
6. Test historical trends with different date ranges

### Automated Testing

Run dashboard tests:
```bash
pytest tests/unit/test_dashboard.py -v
```

## Deployment

### Local Development
```bash
python scripts/start_dashboard.py --host localhost --port 8501
```

### Production Deployment

For production deployment, consider:

1. **Use Streamlit Cloud**: Deploy directly from GitHub
2. **Docker**: Containerize the application
3. **Reverse Proxy**: Use Nginx/Apache for SSL and load balancing
4. **Process Manager**: Use systemd or supervisor for process management

Example Docker deployment:
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["streamlit", "run", "src/dashboard/app.py"]
```

## Performance Metrics

### Dashboard Refresh Interval
- Default: 5 minutes
- Configurable in config.yaml
- Can be manually triggered via refresh button

### Cache TTL
- Default: 5 minutes
- Matches refresh interval for consistency
- Automatically invalidated on manual refresh

### Supported Cities
- Minimum: 1 city
- Maximum: 10+ cities (performance dependent)
- Recommended: 3-5 cities for optimal performance

## Future Enhancements

Potential improvements for future versions:

1. **Advanced Analytics**: Add statistical analysis and trend detection
2. **Predictive Alerts**: Implement predictive alert generation
3. **Export Functionality**: Add data export to CSV/PDF
4. **Mobile Optimization**: Improve mobile device support
5. **Multi-language Support**: Add language localization
6. **Custom Thresholds**: Allow users to set custom alert thresholds
7. **Comparison Tools**: Add city-to-city comparison features
8. **Health Recommendations**: Add health recommendations based on AQI

## Support

For issues or questions:

1. Check the troubleshooting section above
2. Review system logs in `logs/` directory
3. Check configuration in `config.yaml`
4. Verify data exists in storage paths

## License

This dashboard is part of the Air Quality Prediction System project.

## References

- [Streamlit Documentation](https://docs.streamlit.io/)
- [Plotly Documentation](https://plotly.com/python/)
- [Air Quality Index (AQI) Standards](https://www.epa.gov/air-quality/air-quality-index-aqi)
