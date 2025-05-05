# scripts/db_utils.py
import sqlalchemy as db
import os
import logging
from dotenv import load_dotenv
from sqlalchemy import MetaData, Table, Column, Text, Integer, Float, PrimaryKeyConstraint, Date

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DBUtils")

# Load environment variables
load_dotenv()


def get_engine():
    """Creates a SQLAlchemy engine using environment variables."""
    db_type = os.environ.get('DB_TYPE', 'postgresql')

    if db_type == "postgresql":
        try:
            user = os.environ['PG_USER']
            password = os.environ['PG_PASS']
            host = os.environ['PG_HOST']
            port = os.environ['PG_PORT']
            dbname = os.environ['PG_DBNAME']

            # --- Optional Debug Prints (Consistent Indentation) ---
            print("-" * 20)
            print(f"DEBUG: DB User Read from .env: '{user}'")
            # Avoid printing password in final version, but okay for temporary debug
            # print(f"DEBUG: DB Password Read from .env: '{password}'")
            print(f"DEBUG: DB Host Read from .env: '{host}'")
            print(f"DEBUG: DB Port Read from .env: '{port}'")
            print(f"DEBUG: DB Name Read from .env: '{dbname}'")
            print("-" * 20)
            # --- End Debug Prints ---

            connection_str = f'postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}'
            print(f"DEBUG: Constructed Connection String: postgresql+psycopg2://{user}:***PASSWORD_HIDDEN***@{host}:{port}/{dbname}")

            engine = db.create_engine(connection_str, pool_size=5, max_overflow=10)
            # Test connection
            with engine.connect() as conn:
                print("PostgreSQL Connection Successful (via get_engine test connect)")
            return engine # Return the created engine
        except KeyError as e:
            # Clearer error for missing env var
            logger.error(f"CRITICAL: Missing PostgreSQL environment variable in .env file: {e}")
            raise KeyError(f"Missing PostgreSQL environment variable in .env file: {e}")
        except Exception as e:
            # Log the specific connection error
            logger.error(f"CRITICAL: PostgreSQL connection failed: {e}", exc_info=True) # Log traceback
            raise ConnectionError(f"PostgreSQL connection failed: {e}")
    else:
        logger.error(f"CRITICAL: DB_TYPE environment variable not set to 'postgresql' in .env")
        raise ValueError("DB_TYPE environment variable not set to 'postgresql' in .env")

# Updated function for scripts/db_utils.py

def create_static_tables(engine):
    """
    Defines and creates static GTFS tables based on the specific columns
    found in the user's downloaded VGN GTFS feed (Nov 27, 2024 dataset).
    """
    metadata = MetaData() # Create MetaData instance here
    print("Defining table schemas for static GTFS data (VGN Nov 2024 specific)...")

    agency = Table('agency', metadata,
        # Based on: agency_id,agency_name,agency_url,agency_timezone,agency_lang,agency_phone
        Column('agency_id', Text, primary_key=True, nullable=False),
        Column('agency_name', Text, nullable=False),
        Column('agency_url', Text, nullable=False),
        Column('agency_timezone', Text, nullable=False),
        Column('agency_lang', Text),
        Column('agency_phone', Text)
        # Removed agency_fare_url as it wasn't in the header
    )

    calendar_dates = Table('calendar_dates', metadata,
        # Based on: service_id,date,exception_type
        Column('service_id', Text, nullable=False), # Part of composite PK
        Column('date', Text, nullable=False), # Part of composite PK, Keep as Text (YYYYMMDD)
        Column('exception_type', Integer, nullable=False), # 1=added, 2=removed
        # Composite Primary Key definition
        PrimaryKeyConstraint('service_id', 'date', name='calendar_dates_pk')
    )

    calendar = Table('calendar', metadata,
        # Based on: service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date
        Column('service_id', Text, primary_key=True, nullable=False),
        Column('monday', Integer, nullable=False),
        Column('tuesday', Integer, nullable=False),
        Column('wednesday', Integer, nullable=False),
        Column('thursday', Integer, nullable=False),
        Column('friday', Integer, nullable=False),
        Column('saturday', Integer, nullable=False),
        Column('sunday', Integer, nullable=False),
        Column('start_date', Text, nullable=False), # Keep as Text (YYYYMMDD)
        Column('end_date', Text, nullable=False)   # Keep as Text (YYYYMMDD)
    )

    routes = Table('routes', metadata,
        # Based on: route_id,agency_id,route_short_name,route_long_name,route_desc,route_type
        Column('route_id', Text, primary_key=True, nullable=False),
        Column('agency_id', Text), # VGN feed has empty string here sometimes
        Column('route_short_name', Text),
        Column('route_long_name', Text),
        Column('route_desc', Text), # VGN feed has empty string here sometimes
        Column('route_type', Integer)
        # Removed route_url, route_color, route_text_color as they weren't in the header
    )

    stop_times = Table('stop_times', metadata,
        # Based on: trip_id,arrival_time,departure_time,stop_id,stop_sequence,stop_headsign,pickup_type,drop_off_type
        Column('trip_id', Text, nullable=False), # Part of composite PK
        Column('arrival_time', Text), # Keep as TEXT for HH:MM:SS format
        Column('departure_time', Text),# Keep as TEXT
        Column('stop_id', Text, nullable=False), # Part of composite PK
        Column('stop_sequence', Integer, nullable=False), # Part of composite PK
        Column('stop_headsign', Text),
        Column('pickup_type', Integer), # Use Integer for GTFS enum (0, 1, 2, 3)
        Column('drop_off_type', Integer), # Use Integer for GTFS enum (0, 1, 2, 3)
        # Removed shape_dist_traveled, timepoint as they weren't in the header
        # Composite Primary Key definition
        PrimaryKeyConstraint('trip_id', 'stop_sequence', name='stop_times_pk')
    )

    stops = Table('stops', metadata,
        # Based on: stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station
        Column('stop_id', Text, primary_key=True, nullable=False),
        Column('stop_name', Text),
        Column('stop_lat', Float),
        Column('stop_lon', Float),
        Column('location_type', Integer), # Use Integer for GTFS enum (0, 1, 2...) VGN uses empty string sometimes, handle during load
        Column('parent_station', Text)
        # Removed stop_code, stop_desc, zone_id, stop_url, wheelchair_boarding as they weren't in the header
    )

    transfers = Table('transfers', metadata,
        # Based on: from_stop_id,to_stop_id,transfer_type,min_transfer_time
        Column('from_stop_id', Text, nullable=False),
        Column('to_stop_id', Text, nullable=False),
        Column('transfer_type', Integer, nullable=False), # Use Integer for GTFS enum
        Column('min_transfer_time', Integer) # Seconds
        # No explicit primary key needed by spec, can be added if desired
    )

    trips = Table('trips', metadata,
        # Based on: route_id,service_id,trip_id,trip_headsign,direction_id,block_id
        Column('route_id', Text, nullable=False),
        Column('service_id', Text, nullable=False),
        Column('trip_id', Text, primary_key=True, nullable=False),
        Column('trip_headsign', Text),
        Column('direction_id', Integer), # Use Integer for GTFS enum (0 or 1)
        Column('block_id', Text)
        # Removed trip_short_name, shape_id, wheelchair_accessible, bikes_allowed as they weren't in the header
    )

    # Attempt to create all defined tables if they don't already exist
    try:
        metadata.create_all(engine, checkfirst=True)
        print("Static tables ensured in the database (VGN Nov 2024 Schema).")
    except Exception as e:
        print(f"Error creating static tables: {e}")
        raise