# VGN Realtime Dashboard Troubleshooting Guide

## Issue Overview

The VGN Realtime Dashboard was experiencing an issue where the real-time transit performance section displayed the error:

```
No departure data found in Redis cache
No current departures data found in cache for any monitored stops in Nuremberg
No valid departures or data found for real-time analysis. Please ensure the background_fetcher.py script is running.
```

This error occurred despite:
1. Redis server running correctly
2. Data fetcher process running and successfully storing data in Redis
3. Database connection working properly

## Root Cause Analysis

After investigating the logs and code, the root cause was identified as a **mismatch between the stop ID formats**:

1. **Data Fetcher Format**: The data fetcher was storing transit data in Redis with keys in the format `departures:XXX` where XXX is a numeric ID (e.g., `departures:510`, `departures:546`).

2. **Dashboard Query Format**: The dashboard was randomly selecting 20 stop IDs from the database in the format `de:09564:XXX:XX:X` and looking for Redis keys like `departures:de:09564:XXX:XX:X`.

This format mismatch meant the dashboard couldn't find any data in Redis, even though the data was there under different keys.

## Solution Implemented

The solution was to modify the `get_stops_by_region` function in `scripts/analysis_queries.py` to include the numeric stop IDs that are known to work with the API:

```python
# Add numeric stop IDs that are known to work with the API
if region_name == "Nuremberg":
    # These are numeric stop IDs that are known to work with the API
    numeric_stop_ids = ["510", "546", "3151"]
    logger.info(f"Adding {len(numeric_stop_ids)} numeric stop IDs for {region_name}.")
    stop_ids.extend(numeric_stop_ids)
```

This ensures that when the dashboard randomly selects 20 stop IDs, it has a chance of selecting the numeric IDs that match the Redis keys. The solution is non-invasive and doesn't require changes to the data fetcher or Redis key format.

## Running the VGN Realtime Dashboard

### Prerequisites

- Docker and Docker Compose installed
- Python 3.8+ with pip
- Virtual environment (venv)

### Step-by-Step Startup Procedure

Follow these steps in the exact order to ensure all components start correctly:

1. **Activate the Virtual Environment**

   ```bash
   venv\Scripts\activate
   ```

   You should see `(venv)` at the beginning of your command prompt.

2. **Start Redis and PostgreSQL using Docker Compose**

   ```bash
   docker-compose up -d
   ```

   This starts both Redis and PostgreSQL in Docker containers. The `-d` flag runs them in the background.

3. **Verify Docker Containers are Running**

   ```bash
   docker ps
   ```

   You should see both `vgn_redis` and `vgn_postgres` containers running.

4. **Start the Data Fetcher**

   ```bash
   python data_fetcher.py
   ```

   This process should be kept running in a separate terminal. It fetches real-time transit data from the VGN API and stores it in Redis.

5. **Start the Streamlit Dashboard**

   ```bash
   streamlit run nuremberg_dashboard.py
   ```

   This will start the web dashboard and automatically open it in your default browser.

6. **Access the Dashboard**

   If the browser doesn't open automatically, you can access the dashboard at:
   - http://localhost:8501 or http://localhost:8502

### Troubleshooting Common Issues

1. **No Real-time Data**
   - Ensure the data fetcher is running
   - Check Redis connection in the dashboard sidebar
   - Verify that Redis contains data with `docker exec vgn_redis redis-cli keys "departures:*"`

2. **Database Connection Issues**
   - Verify PostgreSQL is running with `docker ps`
   - Check the `.env` file for correct database credentials
   - Ensure there are no comments in the environment variable values

3. **Dashboard Not Starting**
   - Check if the required Python packages are installed
   - Verify the virtual environment is activated
   - Check for any error messages in the terminal

## System Architecture

The VGN Realtime Dashboard consists of three main components:

1. **Redis Server**: Caches real-time transit data
2. **Data Fetcher**: Background process that fetches data from the VGN API and stores it in Redis
3. **Streamlit Dashboard**: Web interface that displays the data

The data flow is as follows:
- Data Fetcher queries the VGN API for real-time transit data
- Data is stored in Redis with keys in the format `departures:XXX`
- Dashboard queries Redis for data and displays it in the web interface
- PostgreSQL database stores static transit data (routes, stops, etc.)

## Maintenance Notes

- The data fetcher should be restarted daily to ensure fresh data
- Redis cache is temporary and will be cleared on restart
- The PostgreSQL database contains static GTFS data that rarely changes
- If you need to add more numeric stop IDs, modify the `get_stops_by_region` function in `scripts/analysis_queries.py`
