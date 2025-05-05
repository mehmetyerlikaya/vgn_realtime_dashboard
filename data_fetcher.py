"""
Nuremberg Transit Data Fetcher

A simplified background process that fetches real-time transit data
for Nuremberg stops and stores it in Redis.
"""

import redis
import time
import json
import os
import logging
from dotenv import load_dotenv
from typing import List, Optional
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Import functions from our scripts
try:
    from scripts.analysis_queries import get_redis_conn, get_stops_by_region
    from scripts.db_utils import get_engine
    from vag_api_client import fetch_and_parse_departures
except ImportError as e:
    logging.basicConfig(level=logging.ERROR)
    logging.error(f"CRITICAL: Failed to import necessary functions: {e}")
    exit(1)

# --- Configuration ---
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("NurembergDataFetcher")

FETCH_INTERVAL_SECONDS = int(os.getenv('FETCH_INTERVAL', '60'))
REDIS_EXPIRY = FETCH_INTERVAL_SECONDS + 30
REGION_NAME = "Nuremberg"  # Focus only on Nuremberg

# --- Main Job Function ---
def fetch_nuremberg_stops_job(stop_ids: List[str], redis_connection: Optional[redis.Redis]):
    """
    Fetches real-time data for Nuremberg stops and stores it in Redis.

    Args:
        stop_ids: List of stop IDs to fetch data for
        redis_connection: Redis connection to store the data
    """
    if not stop_ids:
        logger.warning("No stop IDs provided. Nothing to fetch.")
        return

    if not redis_connection:
        # Try to reconnect if connection was lost
        logger.warning("Redis connection lost. Attempting to reconnect...")
        redis_connection = get_redis_conn()
        if not redis_connection:
            logger.error("Reconnection to Redis failed. Skipping fetch cycle.")
            return

    logger.info(f"Starting fetch cycle for {len(stop_ids)} Nuremberg stops")
    successful_fetches = 0
    total_departures_stored = 0

    # Try a few known working stop IDs first to ensure we get some data
    priority_stops = ["510", "546", "3151"]  # Known working stop IDs
    remaining_stops = [s for s in stop_ids if s not in priority_stops]
    ordered_stops = priority_stops + remaining_stops

    # Limit to a reasonable number of stops for testing
    stops_to_fetch = ordered_stops[:50]  # Start with a smaller set

    logger.info(f"Fetching data for {len(stops_to_fetch)} stops (prioritizing known working stops)")

    for stop_id in stops_to_fetch:
        logger.info(f"Fetching departures for stop ID: {stop_id}")

        # Fetch departures from the API
        departures_data = fetch_and_parse_departures(stop_id)

        if departures_data is not None and len(departures_data) > 0:
            try:
                # Store in Redis
                json_data = json.dumps(departures_data)
                redis_key = f"departures:{stop_id}"
                redis_connection.set(redis_key, json_data, ex=REDIS_EXPIRY)

                successful_fetches += 1
                departures_count = len(departures_data)
                total_departures_stored += departures_count

                logger.info(f"✅ Successfully stored {departures_count} departures for {stop_id} in Redis")

                # Print sample data for debugging
                if departures_count > 0:
                    sample = departures_data[0]
                    logger.info(f"Sample departure: Line: {sample.get('line')}, Dest: {sample.get('destination')}")
                    logger.info(f"  Scheduled: {sample.get('scheduled_time')}, Actual: {sample.get('actual_time')}")
            except redis.exceptions.ConnectionError as e:
                logger.error(f"Redis connection error: {e}")
                redis_connection = None
                break
            except Exception as e:
                logger.error(f"Error storing data in Redis: {e}")
        else:
            if departures_data is not None:
                logger.warning(f"No departures returned for stop ID: {stop_id} (empty list)")
            else:
                logger.warning(f"Failed to fetch data for stop ID: {stop_id} (API error)")

        # Small delay between API calls
        time.sleep(0.5)  # Increased delay to avoid rate limiting

    logger.info(f"Fetch cycle completed. Successful fetches: {successful_fetches}/{len(stops_to_fetch)}. Total departures stored: {total_departures_stored}")

    # If we didn't get any data, log a more detailed error
    if successful_fetches == 0:
        logger.error("❌ CRITICAL: No data was successfully fetched from any stop. Check API connectivity and stop IDs.")
    elif total_departures_stored == 0:
        logger.error("❌ CRITICAL: No departures were found for any stop. Check if transit service is currently running.")

# --- Main Execution ---
def main():
    """Main function to run the data fetcher"""
    logger.info("Initializing Nuremberg Transit Data Fetcher")

    # Get database engine to fetch stop IDs
    db_engine = get_engine()
    if not db_engine:
        logger.critical("Could not connect to database. Cannot get stop IDs.")
        exit(1)

    # Get Redis connection
    redis_conn = get_redis_conn()
    if not redis_conn:
        logger.critical("Could not connect to Redis. Fetcher cannot start.")
        exit(1)

    # Get stop IDs for Nuremberg
    logger.info(f"Fetching stop IDs for {REGION_NAME}")
    nuremberg_stop_ids = get_stops_by_region(db_engine, REGION_NAME)

    if not nuremberg_stop_ids:
        logger.critical(f"Could not find any stop IDs for {REGION_NAME}. Fetcher cannot start.")
        exit(1)

    logger.info(f"Found {len(nuremberg_stop_ids)} stop IDs for {REGION_NAME}")

    # Add some known working numeric IDs as a fallback
    fallback_ids = ["546", "510", "511", "512", "513", "514", "515"]
    all_stop_ids = list(set(nuremberg_stop_ids + fallback_ids))

    logger.info(f"Monitoring a total of {len(all_stop_ids)} stops")

    # Set up scheduler
    scheduler = BlockingScheduler(timezone="Europe/Berlin")

    # Schedule the job
    scheduler.add_job(
        fetch_nuremberg_stops_job,
        trigger=IntervalTrigger(seconds=FETCH_INTERVAL_SECONDS),
        args=[all_stop_ids, redis_conn],
        id='nuremberg_fetcher_job',
        name='Fetch Nuremberg Departures',
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=15
    )

    logger.info(f"Scheduler configured. Starting fetch job to run every {FETCH_INTERVAL_SECONDS} seconds.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler received shutdown signal.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
    finally:
        if scheduler.running:
            scheduler.shutdown()
        logger.info("Scheduler shut down.")

if __name__ == "__main__":
    main()
