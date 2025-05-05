# Transit Dashboard Codebase Structure

This document outlines the structure of the Transit Dashboard codebase, identifying core files, supporting scripts, and redundant files that can be safely removed.

## Core Application Files

These files are essential for the main functionality of the application:

1. **nuremberg_dashboard.py** - The main Streamlit dashboard application for Nuremberg transit data
2. **vag_api_client.py** - Client for interacting with the VGN/VAG transit API
3. **data_fetcher.py** - Background process that fetches real-time transit data and stores it in Redis
4. **scripts/analysis_queries.py** - Contains functions for analyzing transit data and querying Redis/PostgreSQL
5. **scripts/db_utils.py** - Database utility functions for connecting to PostgreSQL
6. **.env** - Environment variables configuration file

## Supporting Files

These files support the application but aren't part of the core functionality:

1. **run_nuremberg_dashboard.py** - Script to run the Nuremberg dashboard
2. **run_nuremberg_dashboard.bat** - Windows batch file to run the dashboard
3. **test_connections.py** - Tests database and Redis connections
4. **scripts/load_static_gtfs.py** - Script to load static GTFS data into PostgreSQL

## Documentation Files

Important documentation files:

1. **README.md** - Main project documentation
2. **INSTALL.md** - Installation instructions
3. **RUNNING_INSTRUCTIONS.md** - Instructions for running the application
4. **SETUP_REALTIME_DATA.md** - Instructions for setting up real-time data fetching

## Redundant Files (Safe to Delete)

These files appear to be redundant, outdated, or superseded by newer versions:

### Redundant Dashboard Files
1. **dashboard.py** - Superseded by nuremberg_dashboard.py
2. **run_dashboard.py** - Superseded by run_nuremberg_dashboard.py
3. **run_dashboard.bat** - Superseded by run_nuremberg_dashboard.bat
4. **start_dashboard.py** - Redundant with run_nuremberg_dashboard.py
5. **start_dashboard.bat** - Redundant with run_nuremberg_dashboard.bat

### Redundant System Management Files
1. **background_fetcher.py** - Superseded by data_fetcher.py
2. **run_all.py** - Redundant with run_nuremberg_dashboard.py
3. **run_all.bat** - Redundant with run_nuremberg_dashboard.bat
4. **start_system.py** - Redundant with run_nuremberg_dashboard.py
5. **start_system.bat** - Redundant with run_nuremberg_dashboard.bat
6. **backend_app.py** - Appears to be an older version of the backend

### Redundant Utility Scripts
1. **find_stop_id.py** - One-time utility, not needed for ongoing operation
2. **find_stops_by_location.py** - One-time utility, not needed for ongoing operation
3. **find_vag_station_id.py** - One-time utility, not needed for ongoing operation
4. **get_coords.py** - One-time utility, not needed for ongoing operation
5. **lookup_station_api.py** - One-time utility, not needed for ongoing operation
6. **lookup_station_api2.py** - One-time utility, not needed for ongoing operation
7. **test_vag_api.py** - Testing script, not needed for production
8. **check_redis_data.py** - Debugging utility, not needed for production

### Empty or Minimal Files
1. **scripts/realtime_fetcher.py** - Empty/minimal file (2 bytes)
2. **scripts/test_realtime_api.py** - Empty/minimal file (2 bytes)

### Redundant Documentation
1. **FILE_CLEANUP_PLAN.md** - Can be deleted after cleanup is complete
2. **REBUILD_DOCUMENTATION.md** - Can be consolidated with other documentation
3. **index.html** - Appears to be a static documentation page, redundant with markdown docs

### Redundant Directories
1. **notebooks/** - If not actively used for development
2. **docs/** - If documentation has been consolidated into markdown files

## Recommended Clean Structure

After cleanup, your codebase should have this structure:

```
vgn_realtime_dashboard/
├── .env                       # Environment variables
├── .gitignore                 # Git ignore file
├── docker-compose.yml         # Docker configuration
├── nuremberg_dashboard.py     # Main Streamlit dashboard
├── data_fetcher.py            # Real-time data fetcher
├── vag_api_client.py          # API client
├── test_connections.py        # Connection testing utility
├── run_nuremberg_dashboard.py # Runner script
├── run_nuremberg_dashboard.bat # Windows batch runner
├── requirements.txt           # Python dependencies
├── README.md                  # Main documentation
├── INSTALL.md                 # Installation instructions
├── RUNNING_INSTRUCTIONS.md    # Running instructions
├── SETUP_REALTIME_DATA.md     # Real-time data setup instructions
├── scripts/
│   ├── __init__.py            # Package marker
│   ├── analysis_queries.py    # Data analysis functions
│   ├── db_utils.py            # Database utilities
│   └── load_static_gtfs.py    # GTFS data loader
├── config/                    # Configuration files
└── data/                      # Data directory (if needed)
```

## Cleanup Process

To clean up the codebase:

1. Make sure you have a backup or the code is committed to version control
2. Remove the redundant files listed above
3. Test the application to ensure it still works correctly
4. Update documentation to reflect the new structure

This cleanup will make the codebase more maintainable, easier to understand, and reduce confusion for new developers working on the project.
