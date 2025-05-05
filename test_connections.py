"""
Test script to verify Redis and API connections
"""

import redis
import requests
import json
import os
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ConnectionTester")

# Load environment variables
load_dotenv()

# Redis configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

def test_redis_connection():
    """Test Redis connection"""
    logger.info(f"Testing Redis connection to {REDIS_HOST}:{REDIS_PORT}...")
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
        r.ping()
        logger.info("✅ Redis connection successful!")
        
        # Try to set and get a value
        r.set("test_key", "test_value", ex=60)
        value = r.get("test_key")
        if value == "test_value":
            logger.info("✅ Redis set/get test successful!")
        else:
            logger.error(f"❌ Redis set/get test failed. Expected 'test_value', got '{value}'")
        
        return True
    except redis.exceptions.ConnectionError as e:
        logger.error(f"❌ Redis connection failed: {e}")
        logger.error("Make sure Redis server is running.")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error connecting to Redis: {e}")
        return False

def test_api_connection():
    """Test API connection"""
    logger.info("Testing VGN API connection...")
    test_stop_id = "510"  # Nuremberg Hauptbahnhof
    api_url = f"https://start.vag.de/dm/api/v1/abfahrten/VGN/{test_stop_id}"
    
    try:
        logger.info(f"Requesting data from: {api_url}")
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if "Abfahrten" in data:
            departures_count = len(data["Abfahrten"])
            logger.info(f"✅ API connection successful! Retrieved {departures_count} departures.")
            
            # Print sample data
            if departures_count > 0:
                sample = data["Abfahrten"][0]
                logger.info(f"Sample departure: Line: {sample.get('Linienname')}, Dest: {sample.get('Richtungstext')}")
                logger.info(f"  Scheduled: {sample.get('AbfahrtszeitSoll')}, Actual: {sample.get('AbfahrtszeitIst')}")
            
            return True
        else:
            logger.warning("⚠️ API response doesn't contain expected 'Abfahrten' key.")
            logger.info(f"Response content: {json.dumps(data, indent=2)[:500]}...")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ API connection failed: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error testing API: {e}")
        return False

def main():
    """Main function"""
    logger.info("=== Connection Tester ===")
    
    # Test Redis
    redis_ok = test_redis_connection()
    
    # Test API
    api_ok = test_api_connection()
    
    # Summary
    logger.info("\n=== Test Summary ===")
    logger.info(f"Redis Connection: {'✅ OK' if redis_ok else '❌ FAILED'}")
    logger.info(f"API Connection: {'✅ OK' if api_ok else '❌ FAILED'}")
    
    if redis_ok and api_ok:
        logger.info("✅ All connections are working! The dashboard should work correctly.")
    else:
        logger.error("❌ Some connections failed. Please fix the issues before running the dashboard.")

if __name__ == "__main__":
    main()
