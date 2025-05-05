# Setting Up Real-time Data for VGN Transit Dashboard

This guide provides step-by-step instructions for setting up the real-time data pipeline for the VGN Transit Dashboard.

## Overview

The dashboard relies on a data pipeline with these components:

1. **Background Fetcher** - A Python script that periodically fetches real-time transit data
2. **Redis Cache** - Stores the fetched data temporarily
3. **Dashboard** - Reads from Redis and displays the data

## Prerequisites

- Python 3.7+ installed
- Redis server installed and running
- Required Python packages (see below)

## Step 1: Install Required Packages

```bash
# Navigate to the project directory
cd vgn_realtime_dashboard

# Install required packages
pip install redis pandas apscheduler python-dotenv sqlalchemy psycopg2-binary streamlit plotly
```

## Step 2: Configure Environment Variables

Ensure your `.env` file is properly configured:

```
# Redis Settings
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# API Settings for real-time data
VAG_API_BASE_URL=https://start.vag.de/dm/api/v1
# Add any API keys if required
```

## Step 3: Start Redis Server

If Redis is not already running, start it:

### On Windows:
```bash
# If using Redis for Windows
redis-server
```

### On Linux/Mac:
```bash
redis-server
```

## Step 4: Run the Background Fetcher

The background fetcher needs to run continuously to keep the Redis cache updated with fresh data:

```bash
# In a separate terminal window
cd vgn_realtime_dashboard
python background_fetcher.py
```

You should see log messages indicating that the fetcher is running and retrieving data.

## Step 5: Verify Data in Redis

To check if data is being properly stored in Redis:

```bash
# Connect to Redis CLI
redis-cli

# List all keys related to departures
KEYS "departures:*"

# View data for a specific stop (replace STOP_ID with an actual stop ID)
GET "departures:STOP_ID"
```

## Step 6: Run the Dashboard with Real Data

1. Start the Streamlit dashboard:
   ```bash
   cd vgn_realtime_dashboard
   streamlit run dashboard.py
   ```

2. In the dashboard interface:
   - Make sure the "Use Demo Data" toggle is turned OFF
   - Select a region to view real-time data

## Troubleshooting

### No Data Appearing in Dashboard

1. **Check Background Fetcher**:
   - Is it running without errors?
   - Check logs for any API connection issues

2. **Check Redis**:
   - Is Redis running?
   - Are keys being created? (`KEYS "departures:*"`)
   - Do the keys contain valid JSON data?

3. **Check API Configuration**:
   - Is the API base URL correct?
   - Are any required API keys set?

4. **Check Stop IDs**:
   - Are the stop IDs in the region correct?
   - Try manually fetching data for a specific stop ID

### Common Errors

1. **Redis Connection Error**:
   - Ensure Redis is running on the configured host and port
   - Check firewall settings if using a remote Redis server

2. **API Errors**:
   - Check API documentation for correct endpoints
   - Verify rate limits and authentication requirements

3. **Data Format Issues**:
   - Ensure the API response is being properly parsed
   - Check for changes in the API response format

## Maintaining the Data Pipeline

For production use:

1. **Run as Services**:
   - Set up the background fetcher as a system service
   - Configure Redis with persistence for reliability

2. **Monitoring**:
   - Add monitoring for the background fetcher
   - Set up alerts for Redis connection issues

3. **Scaling**:
   - For larger deployments, consider Redis clustering
   - Implement multiple fetcher instances for different regions

## Additional Resources

- [Redis Documentation](https://redis.io/documentation)
- [APScheduler Documentation](https://apscheduler.readthedocs.io/)
- [Streamlit Documentation](https://docs.streamlit.io/)
