"""
Nuremberg Transit Dashboard Launcher

This script starts both the data fetcher and the Streamlit dashboard
in separate processes, making it easy to run the complete system.
"""

import subprocess
import sys
import time
import os
import signal
import logging
import redis
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DashboardLauncher")

# Load environment variables
load_dotenv()

# Redis configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

# Global variables to track processes
processes = []

def check_redis():
    """Check if Redis is running and accessible"""
    logger.info(f"Checking Redis connection at {REDIS_HOST}:{REDIS_PORT}...")
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
        r.ping()
        logger.info("✅ Redis connection successful!")
        return True
    except redis.exceptions.ConnectionError as e:
        logger.error(f"❌ Redis connection failed: {e}")
        logger.error("Make sure Redis server is running.")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error connecting to Redis: {e}")
        return False

def start_data_fetcher():
    """Start the data fetcher process"""
    logger.info("Starting data fetcher...")
    try:
        process = subprocess.Popen(
            [sys.executable, "data_fetcher.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        processes.append(process)
        logger.info(f"Data fetcher started with PID {process.pid}")
        
        # Give the fetcher a moment to initialize
        time.sleep(2)
        
        # Check if it's still running
        if process.poll() is None:
            logger.info("Data fetcher is running.")
            return True
        else:
            logger.error(f"Data fetcher exited with code {process.returncode}")
            return False
    except Exception as e:
        logger.error(f"Failed to start data fetcher: {e}")
        return False

def start_dashboard():
    """Start the Streamlit dashboard process"""
    logger.info("Starting Nuremberg dashboard...")
    try:
        process = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "nuremberg_dashboard.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        processes.append(process)
        logger.info(f"Dashboard started with PID {process.pid}")
        return True
    except Exception as e:
        logger.error(f"Failed to start dashboard: {e}")
        return False

def cleanup(signum=None, frame=None):
    """Clean up processes on exit"""
    logger.info("Cleaning up processes...")
    for process in processes:
        if process.poll() is None:  # If process is still running
            logger.info(f"Terminating process with PID {process.pid}")
            try:
                process.terminate()
                process.wait(timeout=5)  # Wait up to 5 seconds for graceful termination
            except subprocess.TimeoutExpired:
                logger.warning(f"Process {process.pid} did not terminate gracefully, killing...")
                process.kill()
            except Exception as e:
                logger.error(f"Error terminating process {process.pid}: {e}")
    logger.info("All processes terminated")

def main():
    """Main function to run the dashboard system"""
    logger.info("Starting Nuremberg Transit Dashboard System")
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    try:
        # Check Redis connection
        redis_running = check_redis()
        if not redis_running:
            logger.error("Redis is not running. Please start Redis before running this script.")
            return 1
        
        # Start the data fetcher
        fetcher_running = start_data_fetcher()
        if not fetcher_running:
            logger.error("Failed to start data fetcher. Exiting.")
            return 1
        
        # Start the dashboard
        dashboard_running = start_dashboard()
        if not dashboard_running:
            logger.error("Failed to start dashboard. Cleaning up and exiting.")
            cleanup()
            return 1
        
        logger.info("All components started successfully")
        logger.info("Press Ctrl+C to stop all processes")
        
        # Keep the script running and monitor the processes
        while True:
            # Check if processes are still running
            for process in processes:
                if process.poll() is not None:
                    logger.warning(f"Process with PID {process.pid} exited with code {process.returncode}.")
            
            # Sleep to avoid high CPU usage
            time.sleep(5)
    
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        cleanup()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
