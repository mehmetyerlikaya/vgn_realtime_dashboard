# scripts/load_static_gtfs.py
import pandas as pd
import os
import logging
from sqlalchemy.exc import SQLAlchemyError
# Import helper functions from your db_utils script
from db_utils import get_engine, create_static_tables

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
# Define the directory where your extracted GTFS .txt files are
STATIC_GTFS_DIR = os.path.join('data', 'extracted_static') # Assumes it's relative to project root

# --- ACTION: Verify this dictionary matches your extracted files and desired table names ---
# Ensure table names match those defined in db_utils.create_static_tables
GTFS_FILES_TO_TABLES = {
    'agency.txt': 'agency',
    'stops.txt': 'stops',
    'routes.txt': 'routes',
    'trips.txt': 'trips',
    'stop_times.txt': 'stop_times',
    'calendar.txt': 'calendar',
    'calendar_dates.txt': 'calendar_dates',
    'transfers.txt': 'transfers'
    # Add/remove lines here if your VGN feed differs (e.g., add 'shapes.txt': 'shapes')
}

# --- ACTION: Verify/Adjust dtypes to match your schema in db_utils.py and GTFS spec ---
# Use Pandas dtype strings ('Int64' for nullable int, 'float', 'str')
# This helps Pandas read the data correctly and efficiently.
DTYPE_MAP = {
    'agency.txt': {'agency_id': str, 'agency_name': str, 'agency_url': str, 'agency_timezone': str, 'agency_lang': str, 'agency_phone': str},
    'stops.txt': {'stop_id': str, 'stop_name': str, 'stop_lat': float, 'stop_lon': float, 'location_type': 'Int64', 'parent_station': str},
    'routes.txt': {'route_id': str, 'agency_id': str, 'route_short_name': str, 'route_long_name': str, 'route_desc': str, 'route_type': 'Int64'},
    'trips.txt': {'route_id': str, 'service_id': str, 'trip_id': str, 'trip_headsign': str, 'direction_id': 'Int64', 'block_id': str},
    'stop_times.txt': {'trip_id': str, 'arrival_time': str, 'departure_time': str, 'stop_id': str, 'stop_sequence': 'Int64', 'stop_headsign': str, 'pickup_type': 'Int64', 'drop_off_type': 'Int64'},
    'calendar.txt': {'service_id': str, 'monday': 'Int64', 'tuesday': 'Int64', 'wednesday': 'Int64', 'thursday': 'Int64', 'friday': 'Int64', 'saturday': 'Int64', 'sunday': 'Int64', 'start_date': str, 'end_date': str},
    'calendar_dates.txt': {'service_id': str, 'date': str, 'exception_type': 'Int64'},
    'transfers.txt': {'from_stop_id': str, 'to_stop_id': str, 'transfer_type': 'Int64', 'min_transfer_time': 'Int64'} # Use Int64 for nullable min_transfer_time
}

def clean_dataframe(df):
    """Applies basic cleaning: strip whitespace from strings."""
    for col in df.select_dtypes(include=['object', 'string']).columns:
        # Check if column exists and actually contains strings before stripping
        if col in df.columns and pd.api.types.is_string_dtype(df[col]):
             try:
                   df[col] = df[col].str.strip()
             except AttributeError:
                   # Handle potential non-string data mixed in object columns if necessary
                   logging.warning(f"Could not apply strip() to column '{col}'. It might contain non-string data.")
    return df

def load_static_data():
    """Main function to load all static GTFS files into the database."""
    logging.info("--- Starting Static GTFS Data Load Process ---")
    try:
        engine = get_engine()
        logging.info("Database engine created successfully.")
        # Ensure tables are created based on db_utils definition
        create_static_tables(engine)
        logging.info("Verified database table schemas.")
    except Exception as e:
        logging.error(f"CRITICAL: Failed to connect to database or setup tables: {e}", exc_info=True)
        logging.error("Please ensure PostgreSQL/Redis Docker containers are running and .env file is correct.")
        return # Stop execution if DB setup fails

    # Loop through the files defined in the mapping
    for filename, tablename in GTFS_FILES_TO_TABLES.items():
        filepath = os.path.join(STATIC_GTFS_DIR, filename)

        # Check if the file exists
        if not os.path.exists(filepath):
            logging.warning(f"File not found: {filepath}. Skipping table '{tablename}'.")
            continue

        logging.info(f"Processing: {filename} -> Table: '{tablename}'")
        try:
            # Read CSV using specified dtypes for efficiency and accuracy
            dtypes = DTYPE_MAP.get(filename, {})
            df = pd.read_csv(
                filepath,
                dtype=dtypes,
                keep_default_na=True, # Interpret standard NA values (like empty strings) as NaN
                na_values=[''],       # Explicitly treat empty strings as NaN
                low_memory=False      # Can help with mixed type inference warnings
            )
            logging.info(f"Read {len(df)} rows from {filename}.")

            # Apply basic cleaning
            df = clean_dataframe(df)

            # Specific type conversions / handling needed AFTER reading
            # Example: Handle location_type in stops.txt which might be read as float due to NaN
            if tablename == 'stops' and 'location_type' in df.columns:
                 # Convert to nullable Integer, forcing errors to NaN, then fill NaN with a default (e.g., 0 or None if DB allows NULL)
                 df['location_type'] = pd.to_numeric(df['location_type'], errors='coerce').astype('Int64')#.fillna(0) # Decide on fillna based on schema/needs

            # --- Load data into the database ---
            logging.info(f"Loading {len(df)} rows into '{tablename}'...")
            df.to_sql(
                tablename,
                engine,
                if_exists='replace', # Replace table content on each run for static data
                index=False,         # Do not write pandas index as a column
                method='multi',      # Efficient bulk insert method
                chunksize=5000       # Process data in chunks to manage memory
            )
            logging.info(f"Successfully loaded data into table '{tablename}'.")

        except FileNotFoundError:
            logging.warning(f"File not found during processing: {filepath}. Skipping.")
        except pd.errors.EmptyDataError:
            logging.warning(f"File is empty: {filepath}. Skipping table '{tablename}'.")
        except SQLAlchemyError as e:
            logging.error(f"Database error loading table '{tablename}': {e}", exc_info=True)
            logging.warning("Check if table schema in db_utils.py matches file columns.")
        except ValueError as e:
             logging.error(f"Data type or value error processing {filename} for table '{tablename}': {e}", exc_info=True)
             logging.warning("Check DTYPE_MAP and data cleanliness.")
        except Exception as e:
            logging.error(f"An unexpected error occurred processing file {filename}: {e}", exc_info=True)

    logging.info("--- Static GTFS Data Load Process Finished ---")

# Make the script runnable from the command line
if __name__ == "__main__":
    load_static_data()