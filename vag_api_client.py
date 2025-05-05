import requests
import json
import logging
from typing import Optional, List, Dict # Used for type hints

# Configure basic logging (optional, but helpful)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- The Reusable Function ---
def fetch_and_parse_departures(stop_id: str) -> Optional[List[Dict]]:
    """
    Fetches and parses real-time departure data from the VAG API for a given stop ID.

    Args:
        stop_id: The numeric ID of the stop (e.g., "3151").

    Returns:
        A list of simplified departure dictionaries upon success, otherwise None.
        Each dictionary contains: 'line', 'destination', 'scheduled_time',
        'actual_time', 'platform'.
    """
    api_base_url = "https://start.vag.de/dm/api/v1"

    # Check if the stop_id is in the format "de:09564:..." and extract the numeric part if needed
    # The API expects numeric IDs, but the dashboard uses the full GTFS IDs
    numeric_stop_id = stop_id
    if stop_id.startswith("de:"):
        # Try to extract the numeric part from the GTFS ID
        parts = stop_id.split(":")
        if len(parts) >= 4:
            # The format might be de:09564:101:11:1, we need to extract a usable ID
            try:
                # Extract the actual stop ID (third part)
                numeric_stop_id = parts[2]
                logging.info(f"Converted GTFS ID {stop_id} to numeric ID {numeric_stop_id}")
            except Exception as e:
                logging.error(f"Error converting GTFS ID {stop_id}: {e}")
                # Keep the original ID as fallback
                numeric_stop_id = stop_id

    # We construct the specific endpoint URL using the provided stop_id
    # Using netvu=VGN based on our successful test
    api_url = f"{api_base_url}/abfahrten/VGN/{numeric_stop_id}"
    logging.info(f"Requesting departures from: {api_url}")

    # Print the full URL for debugging
    print(f"API URL: {api_url} (original stop_id: {stop_id})")

    try:
        # Make the HTTP GET request to the VAG API
        response = requests.get(api_url, timeout=10) # Added timeout

        # Check if the request was successful (status code 200-299)
        # raise_for_status() will raise an exception for bad status codes (4xx or 5xx)
        response.raise_for_status()

        # Parse the JSON response from the API
        raw_data = response.json()

        # Extract the list of departures (handle case where 'Abfahrten' key might be missing)
        raw_departures = raw_data.get("Abfahrten", [])

        # Process the raw departures into a cleaner format
        parsed_departures = []
        for departure in raw_departures:
            simplified_departure = {
                "line": departure.get("Linienname"),
                "destination": departure.get("Richtungstext"),
                "scheduled_time": departure.get("AbfahrtszeitSoll"),
                "actual_time": departure.get("AbfahrtszeitIst"),
                "platform": departure.get("HaltesteigText"),
                # Add more fields here if needed later
            }
            parsed_departures.append(simplified_departure)

        logging.info(f"Successfully fetched and parsed {len(parsed_departures)} departures.")
        return parsed_departures # Return the list of processed departures

    # --- Error Handling ---
    except requests.exceptions.Timeout:
        logging.error(f"Request timed out while contacting {api_url}")
        return None
    except requests.exceptions.HTTPError as http_err:
        # Handle HTTP errors (like 404 Not Found, 400 Bad Request, 500 Internal Server Error)
        logging.error(f"HTTP error occurred: {http_err} - Status Code: {response.status_code}")
        # You might want to inspect response.text here in some cases
        # logging.error(f"Response Text: {response.text}")
        return None
    except requests.exceptions.RequestException as req_err:
        # Handle other network-related errors (DNS failure, connection refused, etc.)
        logging.error(f"Error during requests call: {req_err}")
        return None
    except json.JSONDecodeError:
        # Handle cases where the response wasn't valid JSON
        logging.error("Failed to decode JSON response from API.")
        return None
    except Exception as e:
        # Catch any other unexpected errors
        logging.error(f"An unexpected error occurred: {e}")
        return None


# --- Testing Block ---
# This code only runs when you execute this file directly (python vag_api_client.py)
# It allows you to test the function without needing other parts of your project yet.
if __name__ == "__main__":
    test_stop_id = "3151" # Erlangen Arcaden numeric ID
    logging.info(f"--- Testing fetch_and_parse_departures for stop ID: {test_stop_id} ---")

    # Call the function
    departures_list = fetch_and_parse_departures(test_stop_id)

    # Print the results
    if departures_list is not None:
        if departures_list: # Check if the list is not empty
            print("\n--- Processed Departures ---")
            for dep in departures_list:
                print(f"  Line: {dep['line']}, Dest: {dep['destination']}, Plat: {dep['platform']}, Sched: {dep['scheduled_time']}, Actual: {dep['actual_time']}")
        else:
            print("\nAPI call successful, but no departures were listed in the response.")
    else:
        # Error messages should have been logged by the function
        print("\nFailed to retrieve or parse departures. Check logs above.")