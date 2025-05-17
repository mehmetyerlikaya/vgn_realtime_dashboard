# scripts/analysis_queries.py (Corrected and Cleaned)

import pandas as pd
import redis
import json
import os
import logging
from dotenv import load_dotenv
from sqlalchemy import text # For executing raw SQL
from typing import Optional, List, Dict # For type hints
import datetime # Needed for time parsing in get_live_departures...
from scripts.db_utils import get_engine

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AnalysisQueries")

# Load environment variables from .env file
load_dotenv()

# Read Redis config from .env
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))
# --- End Configuration ---


# --- Redis Connection Pool ---
redis_pool = None
try:
    # decode_responses=True -> returns strings from Redis
    redis_pool = redis.ConnectionPool(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True,
        socket_connect_timeout=5
    )
    # Test connection during pool creation
    r = redis.Redis(connection_pool=redis_pool)
    r.ping()
    logger.info(f"Redis connection pool created successfully for {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
except Exception as e:
    logger.error(f"Failed to create Redis connection pool: {e}")
    # The get_redis_conn function will handle this below

# --- Redis Connection Function ---
def get_redis_conn() -> Optional[redis.Redis]:
    """Gets a Redis connection from the pool. Returns None on failure."""
    if redis_pool is None:
        logger.error("Redis connection pool is not available.")
        return None
    try:
        # Get a connection from the pool
        r = redis.Redis(connection_pool=redis_pool)
        # Test the connection before returning
        r.ping()
        return r
    except redis.exceptions.ConnectionError as e:
        logger.error(f"Failed to get Redis connection from pool: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred getting Redis connection: {e}")
        return None

# --- Route Type Mapping ---
ROUTE_TYPE_MAP = {
    0: 'Tram',
    1: 'Subway (U-Bahn)',
    2: 'Rail (S-Bahn/Regional)',
    3: 'Bus',
    4: 'Ferry',
    5: 'Cable Tram',
    6: 'Aerial Lift',
    7: 'Funicular',
    11: 'Trolleybus',
    12: 'Monorail'
}

# --- Constants for Delay Analysis ---
ON_TIME_THRESHOLD_MINUTES_LOW = -1 # Allow arriving 1 min early
ON_TIME_THRESHOLD_MINUTES_HIGH = 3  # Allow departing up to 3 mins late
DELAY_BUCKET_LABELS = [
    f"< {ON_TIME_THRESHOLD_MINUTES_LOW}m (Early)",
    f"{ON_TIME_THRESHOLD_MINUTES_LOW}m to +{ON_TIME_THRESHOLD_MINUTES_HIGH}m (On Time)",
    f"+{ON_TIME_THRESHOLD_MINUTES_HIGH + 1}m to +10m (Late)",
    "> +10m (Very Late)"
]
# Bins corresponding to the labels above
DELAY_BUCKET_BINS = [-float('inf'), ON_TIME_THRESHOLD_MINUTES_LOW - 1, ON_TIME_THRESHOLD_MINUTES_HIGH, 10, float('inf')]
# --- End Constants ---

# --- Static Data Query Functions ---

def get_overview_stats(engine) -> dict:
    """Gets total counts for routes, stops, and trips from static DB."""
    logger.info("Fetching overview stats from PostgreSQL...")
    stats = {'total_routes': 'N/A', 'total_stops': 'N/A', 'total_trips': 'N/A'}
    if not engine:
        logger.error("DB engine not available for overview stats.")
        return stats
    try:
        with engine.connect() as connection:
            stats['total_routes'] = connection.execute(text("SELECT COUNT(*) FROM routes")).scalar_one_or_none() or 0
            stats['total_stops'] = connection.execute(
                text("SELECT COUNT(*) FROM stops WHERE location_type = 0 OR location_type IS NULL")
            ).scalar_one_or_none() or 0
            stats['total_trips'] = connection.execute(text("SELECT COUNT(*) FROM trips")).scalar_one_or_none() or 0
        logger.info(f"Successfully fetched overview stats: {stats}")
    except Exception as e:
        logger.error(f"Error fetching overview stats: {e}", exc_info=True)
    return stats

def get_route_type_counts(engine) -> pd.DataFrame:
    """Gets counts of routes per type from static DB."""
    logger.info("Fetching route type counts from PostgreSQL...")
    query = "SELECT route_type, COUNT(*) as count FROM routes GROUP BY route_type ORDER BY route_type"
    empty_df = pd.DataFrame({'route_type_name': [], 'count': []})
    if not engine:
        logger.error("DB engine not available for route type counts.")
        return empty_df
    try:
        with engine.connect() as connection:
            df = pd.read_sql(text(query), connection)
        df['route_type_name'] = df['route_type'].map(ROUTE_TYPE_MAP).fillna('Other/' + df['route_type'].astype(str))
        logger.info(f"Successfully fetched and processed {len(df)} route type counts.")
        return df[['route_type_name', 'count']]
    except Exception as e:
        logger.error(f"Error fetching route type counts: {e}", exc_info=True)
        return empty_df

def get_top_routes_by_trips(engine, top_n: int = 15) -> pd.DataFrame:
    """Gets the top N routes by number of scheduled trips from static DB."""
    logger.info(f"Fetching top {top_n} routes by trips from PostgreSQL...")
    query = f"""
    SELECT r.route_short_name, r.route_long_name, COUNT(t.trip_id) as trip_count
    FROM trips t JOIN routes r ON t.route_id = r.route_id
    GROUP BY r.route_id, r.route_short_name, r.route_long_name
    ORDER BY trip_count DESC
    LIMIT :top_n;
    """
    empty_df = pd.DataFrame({'route_display_name': [], 'trip_count': []})
    if not engine:
        logger.error("DB engine not available for top routes.")
        return empty_df
    try:
        with engine.connect() as connection:
            df = pd.read_sql(text(query), connection, params={'top_n': top_n})
        df['route_display_name'] = df['route_short_name'].fillna('') + ' (' + df['route_long_name'].fillna('') + ')'
        df['route_display_name'] = df['route_display_name'].str.strip().replace('()', '').replace('( )', '')
        logger.info(f"Successfully fetched {len(df)} top routes.")
        return df[['route_display_name', 'trip_count']]
    except Exception as e:
        logger.error(f"Error fetching top routes: {e}", exc_info=True)
        return empty_df

def get_all_stops_locations(engine) -> pd.DataFrame:
    """Gets ID, name, lat, lon for all actual stops from static DB."""
    logger.info("Fetching all stop locations from PostgreSQL...")
    query = """
    SELECT stop_id, stop_name, stop_lat, stop_lon
    FROM stops
    WHERE (location_type = 0 OR location_type IS NULL)
    AND stop_lat IS NOT NULL AND stop_lon IS NOT NULL;
    """
    empty_df = pd.DataFrame({'stop_id': [], 'stop_name': [], 'stop_lat': [], 'stop_lon': []})
    if not engine:
        logger.error("DB engine not available for stop locations.")
        return empty_df
    try:
        with engine.connect() as connection:
            df = pd.read_sql(text(query), connection)
        logger.info(f"Successfully fetched {len(df)} stop locations.")
        return df
    except Exception as e:
        logger.error(f"Error fetching stop locations: {e}", exc_info=True)
        return empty_df

def get_stop_list(engine) -> pd.DataFrame:
    """
    Gets list of actual stops (ID and Name) for dropdowns etc.
    Fetches from the PostgreSQL database.
    """
    query = """
    SELECT stop_id, stop_name
    FROM stops
    WHERE (location_type = 0 OR location_type IS NULL) -- Only actual stops
    ORDER BY stop_name;
    """
    logger.info("Fetching stop list from PostgreSQL...")
    empty_df = pd.DataFrame({'stop_id': [], 'stop_name': []})
    if not engine:
         logger.error("DB engine not available for get_stop_list.")
         return empty_df
    try:
        with engine.connect() as connection:
            df = pd.read_sql(text(query), connection)
            logger.info(f"Successfully fetched {len(df)} stops from database.")
            return df
    except Exception as e:
        logger.error(f"Error fetching stop list from database: {e}", exc_info=True)
        return empty_df

# --- Region Functions ---
def get_region_list() -> List[str]:
    """Returns a predefined list of regions for selection."""
    logger.info("Returning predefined region list.")
    return ["Nuremberg", "Fürth", "Erlangen"] # Add more if desired

# Replace the previous get_stops_by_region function with this one

def get_stops_by_region(engine, region_name: str) -> List[str]:
    """
    Gets a list of stop_ids for a given region name by matching stop_id prefix.
    Uses standard German AGS city codes for N, FÜ, ER.
    """
    logger.info(f"Fetching stop IDs for region: '{region_name}' from PostgreSQL using stop_id prefix...")
    stop_ids = []
    if not engine:
        logger.error("DB engine not available for get_stops_by_region.")
        return stop_ids

    # Map region name to the expected stop_id prefix based on AGS codes
    # 09564=Nürnberg, 09563=Fürth, 09562=Erlangen
    prefix_map = {
        "Nuremberg": "de:09564:%",
        "Fürth": "de:09563:%",
        "Erlangen": "de:09562:%",
        # Add other regions/codes if needed, e.g. Schwabach 'de:09565:%'
    }

    search_pattern = prefix_map.get(region_name)

    if not search_pattern:
        logger.error(f"No stop_id prefix defined for region: '{region_name}'")
        return stop_ids

    # Query to select stop_ids matching the prefix, focusing on actual stop points
    query = text("""
        SELECT stop_id
        FROM stops
        WHERE stop_id LIKE :pattern
          AND (location_type = 0 OR location_type IS NULL)
    """)

    try:
        with engine.connect() as connection:
            result = connection.execute(query, {"pattern": search_pattern})
            stop_ids = [row[0] for row in result] # Extract stop_ids into a list
        logger.info(f"Found {len(stop_ids)} stops matching region pattern for '{region_name}'.")
    except Exception as e:
        logger.error(f"Error fetching stops for region '{region_name}': {e}", exc_info=True)
        # Return empty list on error

    # Add numeric stop IDs that are known to work with the API
    if region_name == "Nuremberg":
        # These are numeric stop IDs that are known to work with the API
        numeric_stop_ids = ["510", "546", "3151"]
        logger.info(f"Adding {len(numeric_stop_ids)} numeric stop IDs for {region_name}.")
        stop_ids.extend(numeric_stop_ids)

    return stop_ids


# --- Real-time Data Query Function ---
def get_live_departures_for_stop(redis_conn: redis.Redis, stop_id: str) -> pd.DataFrame:
    """
    Gets upcoming departures for a stop from Redis cache, calculates delays,
    and returns as DataFrame.
    """
    if not redis_conn:
        logger.error("Redis connection not provided to get_live_departures_for_stop.")
        return pd.DataFrame()

    redis_key = f"departures:{stop_id}"
    logger.info(f"Fetching live departures from Redis key: '{redis_key}'")
    df = pd.DataFrame() # Default to empty

    try:
        data_string = redis_conn.get(redis_key)
        if data_string:
            logger.debug(f"Data found in Redis for key: '{redis_key}'")
            try:
                departures_list = json.loads(data_string)
                if departures_list:
                    df = pd.DataFrame(departures_list)
                    logger.info(f"Successfully parsed {len(df)} departures for stop {stop_id} from Redis.")

                    # Calculate Delay
                    if 'scheduled_time' in df.columns and 'actual_time' in df.columns:
                        df['scheduled_dt'] = pd.to_datetime(df['scheduled_time'], errors='coerce', utc=True) # Assume UTC or handle timezone conversion based on data source
                        df['actual_dt'] = pd.to_datetime(df['actual_time'], errors='coerce', utc=True) # Assume UTC
                        df = df.dropna(subset=['scheduled_dt', 'actual_dt']) # Drop rows where times couldn't parse
                        if not df.empty:
                             time_diff = df['actual_dt'] - df['scheduled_dt']
                             df['delay_minutes'] = (time_diff.dt.total_seconds() / 60).round().astype('Int64')
                             logger.info(f"Calculated delays for {len(df)} departures with valid times.")
                        else:
                             logger.warning("No valid time pairs found after parsing to calculate delays.")
                             df['delay_minutes'] = pd.NA # Ensure column exists even if empty
                        # Drop temporary datetime columns
                        df = df.drop(columns=['scheduled_dt', 'actual_dt'], errors='ignore')
                    else:
                        logger.warning("Could not calculate delays: 'scheduled_time' or 'actual_time' columns missing.")
                        df['delay_minutes'] = pd.NA
                else:
                     logger.info(f"Parsed data for key '{redis_key}' is an empty list.")
            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON data from Redis key '{redis_key}'. Data: {data_string[:100]}...")
        else:
            logger.warning(f"No data found in Redis for key: '{redis_key}'.")

    except redis.exceptions.ConnectionError as e:
         logger.error(f"Redis connection error during 'get' operation for key '{redis_key}': {e}")
         raise # Re-raise connection error
    except Exception as e:
         logger.error(f"An unexpected error occurred retrieving/processing data from Redis for key '{redis_key}': {e}", exc_info=True)

    return df

# --- Regional Analysis Functions ---

def get_regional_departures_df(redis_conn: redis.Redis, region_stop_ids: List[str]) -> pd.DataFrame:
    """
    Fetches all cached departures for a list of stop IDs, parses them, calculates delays,
    and returns a combined DataFrame.
    """
    if not redis_conn:
        logger.error("Redis connection not provided to get_regional_departures_df.")
        return pd.DataFrame()
    if not region_stop_ids:
        logger.warning("No stop IDs provided for regional departure fetch.")
        return pd.DataFrame()

    logger.info(f"Fetching regional departures from Redis for {len(region_stop_ids)} stops...")
    redis_keys = [f"departures:{stop_id}" for stop_id in region_stop_ids]
    all_departures_list = []
    df_combined = pd.DataFrame()

    try:
        # Use MGET to fetch all data strings at once
        data_strings = redis_conn.mget(redis_keys)
        found_count = 0
        for i, data_string in enumerate(data_strings):
            if data_string:
                found_count += 1
                try:
                    # Parse JSON for each stop and extend the master list
                    departures = json.loads(data_string)
                    if isinstance(departures, list):
                        all_departures_list.extend(departures)
                    else:
                        logger.warning(f"Unexpected data type parsed from Redis key '{redis_keys[i]}': {type(departures)}")
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode JSON from Redis key '{redis_keys[i]}'. Data: {data_string[:100]}...")
            # else: logger.debug(f"No data for key: {redis_keys[i]}") # Optional: log misses

        logger.info(f"Found data for {found_count}/{len(redis_keys)} requested keys. Total departures fetched: {len(all_departures_list)}")

        if all_departures_list:
            df_combined = pd.DataFrame(all_departures_list)

            # --- Calculate Delay on Combined Data ---
            if 'scheduled_time' in df_combined.columns and 'actual_time' in df_combined.columns:
                df_combined['scheduled_dt'] = pd.to_datetime(df_combined['scheduled_time'], errors='coerce', utc=True)
                df_combined['actual_dt'] = pd.to_datetime(df_combined['actual_time'], errors='coerce', utc=True)
                df_combined = df_combined.dropna(subset=['scheduled_dt', 'actual_dt']) # Drop rows where times failed parsing

                if not df_combined.empty:
                    time_diff = df_combined['actual_dt'] - df_combined['scheduled_dt']
                    df_combined['delay_minutes'] = (time_diff.dt.total_seconds() / 60).round().astype('Int64')
                    logger.info(f"Calculated delays for {len(df_combined)} regional departures with valid times.")
                else:
                    logger.warning("No valid time pairs found after parsing to calculate regional delays.")
                    df_combined['delay_minutes'] = pd.NA
                df_combined = df_combined.drop(columns=['scheduled_dt', 'actual_dt'], errors='ignore')
            else:
                logger.warning("Could not calculate regional delays: time columns missing.")
                df_combined['delay_minutes'] = pd.NA
            # --- End Delay Calculation ---
        else:
             logger.info("No valid departures found for the region after parsing Redis data.")


    except redis.exceptions.ConnectionError as e:
        logger.error(f"Redis connection error during MGET operation: {e}")
        raise # Re-raise for caller (Streamlit) to handle
    except Exception as e:
        logger.error(f"An unexpected error occurred fetching/processing regional data from Redis: {e}", exc_info=True)
        df_combined = pd.DataFrame() # Return empty on error

    return df_combined


def calculate_regional_kpis(departures_df: pd.DataFrame) -> Dict:
    """
    Calculates performance KPIs (% On-Time, Avg Delay) from a DataFrame
    of departures which includes a 'delay_minutes' column.
    """
    kpis = {
        "avg_delay": None,
        "on_time_percent": None,
        "total_departures": len(departures_df),
        "valid_delay_count": 0
    }
    if departures_df.empty or 'delay_minutes' not in departures_df.columns:
        logger.warning("Cannot calculate KPIs: DataFrame is empty or missing 'delay_minutes'.")
        return kpis

    # Use only departures where delay could be calculated
    valid_delays = departures_df['delay_minutes'].dropna()
    kpis["valid_delay_count"] = len(valid_delays)

    if not valid_delays.empty:
        # Calculate Average Delay
        kpis["avg_delay"] = valid_delays.mean()

        # Calculate % On Time
        on_time_count = valid_delays[
            (valid_delays >= ON_TIME_THRESHOLD_MINUTES_LOW) &
            (valid_delays <= ON_TIME_THRESHOLD_MINUTES_HIGH)
        ].count()
        kpis["on_time_percent"] = (on_time_count / kpis["valid_delay_count"]) * 100

        logger.info(f"Calculated regional KPIs: Avg Delay={kpis['avg_delay']:.1f}min, On Time={kpis['on_time_percent']:.1f}% (from {kpis['valid_delay_count']} valid departures)")
    else:
        logger.warning("No valid delays found in DataFrame to calculate KPIs.")

    return kpis

def get_regional_delay_distribution(departures_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates the distribution of delays into predefined buckets from a
    DataFrame of departures including a 'delay_minutes' column.
    Returns a DataFrame suitable for plotting.
    """
    dist_df = pd.DataFrame({'category': DELAY_BUCKET_LABELS, 'count': 0}) # Initialize with all categories
    dist_df = dist_df.set_index('category')

    if departures_df.empty or 'delay_minutes' not in departures_df.columns:
        logger.warning("Cannot calculate delay distribution: DataFrame is empty or missing 'delay_minutes'.")
        return dist_df.reset_index() # Return DF with 0 counts

    valid_delays = departures_df['delay_minutes'].dropna()
    if valid_delays.empty:
        logger.warning("No valid delays found in DataFrame to calculate distribution.")
        return dist_df.reset_index() # Return DF with 0 counts

    # Create a categorical column based on bins and labels defined globally
    delay_categories = pd.cut(valid_delays, bins=DELAY_BUCKET_BINS, labels=DELAY_BUCKET_LABELS, right=True, ordered=True)

    # Count departures in each category
    delay_counts = delay_categories.value_counts()

    # Update the counts in our pre-defined DataFrame to ensure all categories are present
    dist_df['count'] = delay_counts
    dist_df['count'] = dist_df['count'].fillna(0).astype(int) # Fill NaN with 0 for categories with no departures

    logger.info(f"Calculated delay distribution for {len(valid_delays)} valid departures.")
    return dist_df.reset_index() # Return DataFrame with 'category' and 'count' columns



def get_key_stop_ids_for_regions(regions: List[str], top_n_per_region: int, engine = None) -> List[str]:
    """
    Placeholder function for getting key stop IDs.
    TODO: Implement actual DB query to find top N stops per region.
    For now, returns a hardcoded list of known working numeric IDs.
    The 'engine' argument is included for future compatibility but not used yet.
    """
    logger.info(f"Placeholder: Getting key stops for regions {regions} (Top {top_n_per_region}). Returning hardcoded list.")
    # Replace this with actual DB query logic later
    hardcoded_ids = ["546", "3151"] # Widhalmstr. and Erlangen Arcaden
    # Example of adding Nuremberg Hbf if its ID (e.g., 510) worked or is found later
    # Find Nbg Hbf ID first: Use lookup script for name="Hauptbahnhof", netvu="VAG" -> Let's assume it's 510 for this example structure
    # hardcoded_ids = ["546", "3151", "510"]
    logger.warning("Using hardcoded list of stop IDs in get_key_stop_ids_for_regions.")
    return hardcoded_ids

# --- Example Usage (Optional - for testing this file directly) ---
# --- Replace the entire if __name__ == "__main__": block with this ---
if __name__ == '__main__':
    logger.info("--- Testing analysis_queries.py ---")
    db_engine = None
    # Test DB connection and functions
    try:
        imported_get_engine = get_engine # From db_utils
        if callable(imported_get_engine):
            db_engine = imported_get_engine()
        else:
             logger.error("Imported get_engine is not callable.")

        if db_engine:
            logger.info("\nTesting get_overview_stats...")
            stats = get_overview_stats(db_engine)
            logger.info(f"Overview Stats: {stats}")

            logger.info("\nTesting get_route_type_counts...")
            route_types_df = get_route_type_counts(db_engine)
            logger.info(f"Route Type Counts Query returned {len(route_types_df)} types. Head:\n{route_types_df.head()}")

            logger.info("\nTesting get_top_routes_by_trips...")
            top_routes_df = get_top_routes_by_trips(db_engine)
            logger.info(f"Top Routes Query returned {len(top_routes_df)} routes. Head:\n{top_routes_df.head()}")

            logger.info("\nTesting get_all_stops_locations...")
            all_stops_df = get_all_stops_locations(db_engine)
            logger.info(f"All Stops Location Query returned {len(all_stops_df)} stops. Head:\n{all_stops_df.head()}")

            logger.info("\nTesting get_stop_list...")
            stops_df = get_stop_list(db_engine)
            logger.info(f"Stop List Query returned {len(stops_df)} stops. Head:\n{stops_df.head()}")

            logger.info("\nTesting get_region_list...")
            regions = get_region_list()
            logger.info(f"Available regions: {regions}")

            if regions:
                test_region = regions[0] # Test with the first region (e.g., Nuremberg)
                logger.info(f"\nTesting get_stops_by_region for '{test_region}'...")
                region_stop_ids = get_stops_by_region(db_engine, test_region)
                logger.info(f"Found {len(region_stop_ids)} stop IDs for region '{test_region}'. First 10: {region_stop_ids[:10]}")

                # Test the regional analysis functions
                r_conn = get_redis_conn() # Make sure we have redis connection
                if r_conn and region_stop_ids: # Check if we have IDs for the region
                    logger.info(f"\nTesting regional functions for region '{test_region}' with {len(region_stop_ids)} stops...")

                    logger.info("Testing get_regional_departures_df...")
                    regional_df = get_regional_departures_df(r_conn, region_stop_ids)
                    logger.info(f"Regional departures query returned {len(regional_df)} total departures. Head:\n{regional_df.head()}")

                    if not regional_df.empty:
                        logger.info("\nTesting calculate_regional_kpis...")
                        regional_kpis = calculate_regional_kpis(regional_df)
                        logger.info(f"Regional KPIs: {regional_kpis}")

                        logger.info("\nTesting get_regional_delay_distribution...")
                        regional_dist = get_regional_delay_distribution(regional_df)
                        logger.info(f"Regional Delay Distribution:\n{regional_dist}")
                    else:
                        logger.warning("Skipping regional KPI/Distribution tests as no regional departures were found/processed.")
                elif not r_conn:
                    logger.error("Redis Connection not available for testing regional functions.")
                elif not region_stop_ids:
                    logger.error(f"No stop IDs found for region '{test_region}' to test regional functions.")

            # Test the new key stops function
            logger.info("\nTesting get_key_stop_ids_for_regions (Placeholder)...")
            key_stops = get_key_stop_ids_for_regions(regions=["Nuremberg", "Erlangen"], top_n_per_region=10, engine=db_engine)
            logger.info(f"Key Stop IDs returned by placeholder function: {key_stops}")

        else:
            logger.error("DB Engine not available for testing DB functions.")
    except Exception as e:
         logger.error(f"Error testing DB functions: {e}", exc_info=True)

    # Test Redis connection and departure fetch
    r_conn = get_redis_conn()
    if r_conn:
        test_stop_id = "546" # Widhalmstr.
        logger.info(f"\nTesting get_live_departures_for_stop for ID {test_stop_id}...")
        departures_df = get_live_departures_for_stop(r_conn, test_stop_id)
        if 'delay_minutes' in departures_df.columns:
            logger.info(f"Live Departures Query returned {len(departures_df)} departures. Head (with delays):\n{departures_df.head()}")
        else:
            logger.info(f"Live Departures Query returned {len(departures_df)} departures. Head (delay calculation might have failed):\n{departures_df.head()}")
    else:
        logger.error("Redis Connection not available for testing get_live_departures_for_stop.")

    # Dispose engine if created
    if db_engine:
        try:
            db_engine.dispose()
            logger.info("DB Engine disposed.")
        except Exception as e:
            logger.error(f"Error disposing DB engine: {e}")

    logger.info("--- Finished testing analysis_queries.py ---")

    # Test Redis connection and departure fetch
    r_conn = get_redis_conn()
    if r_conn:
        test_stop_id = "546" # Widhalmstr.
        logger.info(f"\nTesting get_live_departures_for_stop for ID {test_stop_id}...")
        departures_df = get_live_departures_for_stop(r_conn, test_stop_id)
        # Check if delay column exists before printing head
        if 'delay_minutes' in departures_df.columns:
            logger.info(f"Live Departures Query returned {len(departures_df)} departures. Head (with delays):\n{departures_df.head()}")
        else:
            logger.info(f"Live Departures Query returned {len(departures_df)} departures. Head (delay calculation might have failed):\n{departures_df.head()}")

    else:
        logger.error("Redis Connection not available for testing get_live_departures_for_stop.")

    # Dispose engine if created
    if db_engine:
        try:
            db_engine.dispose()
            logger.info("DB Engine disposed.")
        except Exception as e:
            logger.error(f"Error disposing DB engine: {e}")

    logger.info("--- Finished testing analysis_queries.py ---")