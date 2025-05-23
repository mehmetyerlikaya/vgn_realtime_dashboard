# VGN Real-time Transit Dashboard

A real-time dashboard for monitoring transit performance in the VGN (Verkehrsverbund Großraum Nürnberg) network.

## Features

- **Network Overview**: View key statistics about the transit network
- **Route Analysis**: Analyze routes by type and see the busiest routes
- **Real-time Insights**: Monitor on-time performance and delay distributions for specific regions
- **Auto-refresh**: Dashboard automatically refreshes to show the latest data

## Requirements

- Python 3.7+
- Redis server
- Required Python packages (see Installation)

## Installation

1. Clone this repository
2. Install required packages:

```bash
pip install -r requirements.txt
```

3. Make sure Redis server is installed and running

## Running the Dashboard

### Option 1: All-in-One Launcher (Recommended)

The easiest way to run the dashboard is to use the provided launcher script:

```bash
# On Windows
run_dashboard.bat

# On Linux/Mac
python run_dashboard.py
```

This will start both the background fetcher and the Streamlit dashboard in one go.

### Option 2: Manual Start

If you prefer to start components individually:

1. Start the background fetcher in one terminal:
```bash
python background_fetcher.py
```

2. Start the Streamlit dashboard in another terminal:
```bash
streamlit run dashboard.py
```

## Troubleshooting

If you encounter issues with real-time data:

1. Run the diagnostic script:
```bash
python check_redis_data.py
```

2. Check if Redis is running:
```bash
redis-cli ping
```

3. Verify API connectivity:
```bash
python vag_api_client.py
```

## Data Sources

- Static data: Loaded from CSV files in the `data` directory
- Real-time data: Fetched from the VGN API and cached in Redis

## Architecture

The dashboard consists of these main components:

1. **Background Fetcher** (`background_fetcher.py`): Periodically fetches real-time data from the VGN API and stores it in Redis
2. **Redis Cache**: Stores real-time departure data with short TTL
3. **Dashboard** (`dashboard.py`): Streamlit app that visualizes both static and real-time data
4. **Analysis Queries** (`scripts/analysis_queries.py`): Functions for data processing and analysis

## Customization

- Edit `dashboard.py` to modify the dashboard layout and visualizations
- Adjust `background_fetcher.py` to change data fetching frequency or target stops
- Modify `.env` file to configure Redis connection and other settings

## License

[MIT License](LICENSE)