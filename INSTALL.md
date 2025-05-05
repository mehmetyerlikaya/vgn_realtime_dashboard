# Installation Guide for Nuremberg Transit Dashboard

This guide provides detailed instructions for setting up and running the Nuremberg Transit Dashboard.

## Prerequisites

Before you begin, ensure you have the following installed:

1. **Python 3.7+**: The dashboard is built with Python. [Download Python](https://www.python.org/downloads/)
2. **PostgreSQL**: Database for storing static GTFS data. [Download PostgreSQL](https://www.postgresql.org/download/)
3. **Redis**: In-memory database for caching real-time data. [Download Redis](https://redis.io/download)

## Step 1: Clone the Repository

```bash
git clone <repository-url>
cd vgn_realtime_dashboard
```

## Step 2: Set Up a Virtual Environment

### On Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

### On macOS/Linux:
```bash
python -m venv venv
source venv/bin/activate
```

## Step 3: Install Dependencies

```bash
pip install -r new_requirements.txt
```

## Step 4: Set Up the Database

1. Create a PostgreSQL database for the GTFS data:
   ```sql
   CREATE DATABASE vgn_gtfs;
   ```

2. Import the GTFS data into the database:
   ```bash
   # Download the GTFS data from VGN
   # Example: wget https://www.vgn.de/opendata/gtfs.zip
   
   # Unzip the GTFS data
   unzip gtfs.zip -d gtfs_data
   
   # Run the database setup script
   python scripts/setup_database.py
   ```

## Step 5: Configure Environment Variables

Create a `.env` file in the project root directory with the following content:

```
# Database settings
DB_HOST=localhost
DB_PORT=5432
DB_NAME=vgn_gtfs
DB_USER=your_username
DB_PASSWORD=your_password

# Redis settings
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Fetcher settings
FETCH_INTERVAL=60
```

Replace `your_username` and `your_password` with your PostgreSQL credentials.

## Step 6: Start Redis Server

### On Windows:
```bash
redis-server
```

### On macOS/Linux:
```bash
redis-server
```

Keep this terminal window open while running the dashboard.

## Step 7: Run the Dashboard

### Option 1: Using the All-in-One Launcher (Recommended)

#### On Windows:
```bash
run_nuremberg_dashboard.bat
```

#### On any platform:
```bash
python run_nuremberg_dashboard.py
```

This will:
1. Check if Redis is running
2. Start the data fetcher
3. Launch the Streamlit dashboard

### Option 2: Manual Startup

If you prefer to start components individually:

1. Start the data fetcher:
   ```bash
   python data_fetcher.py
   ```

2. In a new terminal, start the dashboard:
   ```bash
   streamlit run nuremberg_dashboard.py
   ```

## Step 8: Access the Dashboard

Once the dashboard is running, open your web browser and go to:
```
http://localhost:8501
```

## Troubleshooting

### Database Connection Issues

- Verify your PostgreSQL credentials in the `.env` file
- Ensure the PostgreSQL service is running
- Check if the database exists and has the GTFS data loaded

### Redis Connection Issues

- Ensure Redis server is running
- Verify the Redis connection settings in the `.env` file
- Try connecting to Redis using the Redis CLI: `redis-cli ping`

### Data Fetcher Issues

- Check the data fetcher logs for any errors
- Verify that the VGN API is accessible
- Ensure the stop IDs are correctly configured

### Dashboard Issues

- Check the Streamlit logs for any errors
- Verify that both the database and Redis connections are working
- Clear the Streamlit cache if you see stale data: click "Refresh Data" in the sidebar

## Additional Resources

- [Streamlit Documentation](https://docs.streamlit.io/)
- [Redis Documentation](https://redis.io/documentation)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [GTFS Reference](https://developers.google.com/transit/gtfs/reference)
