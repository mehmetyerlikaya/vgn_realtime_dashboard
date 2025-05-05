# VGN Transit Dashboard - Running Instructions

This guide provides detailed instructions for running the VGN Transit Dashboard system.

## System Components

The dashboard system consists of three main components:

1. **Redis Server** - Caches real-time transit data
2. **Background Fetcher** - Continuously fetches data from the VGN API and stores it in Redis
3. **Streamlit Dashboard** - Web interface that displays the data

## Option 1: All-in-One Startup (Recommended)

The easiest way to run the system is using the all-in-one starter:

### On Windows:
```
start_system.bat
```

### On any platform:
```
python start_system.py
```

This script will:
1. Check if Redis is running and start it if needed
2. Test the API connection
3. Start the background fetcher
4. Launch the Streamlit dashboard

## Option 2: Manual Startup

If you prefer to start components individually:

### Step 1: Start Redis Server
```
redis-server
```

### Step 2: Start Background Fetcher
```
python background_fetcher.py
```

### Step 3: Start Streamlit Dashboard
```
streamlit run dashboard.py
```

## Troubleshooting

If you encounter issues:

### 1. Check Redis Connection
```
python check_redis_data.py
```

### 2. Verify API Connectivity
```
python vag_api_client.py
```

### 3. Check for Error Messages
- Look for error messages in the terminal output
- The background fetcher logs detailed information about API calls and Redis operations

### 4. Common Issues and Solutions

#### No Data in Dashboard
- Make sure the background fetcher is running
- Check if Redis is running with `redis-cli ping`
- Verify API connectivity with `python vag_api_client.py`

#### Background Fetcher Crashes
- Check the terminal output for error messages
- Verify that the API endpoints are accessible
- Make sure Redis is running

#### Redis Connection Errors
- Make sure Redis server is installed and running
- Check Redis configuration in `.env` file
- Default Redis port is 6379

## Starting from Scratch

If you need to restart everything:

1. Stop all running processes (Ctrl+C in each terminal)
2. Close all terminal windows
3. Open a new terminal
4. Run `start_system.py` or follow the manual startup steps

## Monitoring the System

To see what's happening in the system:

1. **Redis Monitoring**:
   ```
   redis-cli monitor
   ```

2. **Background Fetcher Logs**:
   The background fetcher prints detailed logs to the terminal

3. **Dashboard Logs**:
   Streamlit logs appear in the terminal where you started the dashboard

## Data Flow

Understanding the data flow can help with troubleshooting:

1. The background fetcher calls the VGN API for each stop ID
2. Successful responses are parsed and stored in Redis with keys like `departures:{stop_id}`
3. The dashboard reads from Redis when a region is selected
4. The dashboard processes the data to calculate KPIs and visualizations

## Stopping the System

To stop all components:

1. Press Ctrl+C in each terminal window
2. Or use Task Manager/Activity Monitor to end the processes

## Restarting Components

If one component crashes:

1. **Redis**: Run `redis-server` in a new terminal
2. **Background Fetcher**: Run `python background_fetcher.py` in a new terminal
3. **Dashboard**: Run `streamlit run dashboard.py` in a new terminal
