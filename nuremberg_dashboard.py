"""
Nuremberg Transit Dashboard

A Streamlit dashboard focused on providing insightful transit data analysis
for Nuremberg citizens. Shows both static and real-time transit information.
"""

import streamlit as st
import pandas as pd
import redis
import json
import time
import os
import logging
from dotenv import load_dotenv
from typing import Optional, List, Dict
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Import functions from our scripts
try:
    from scripts.db_utils import get_engine
    from scripts.analysis_queries import (
        get_redis_conn,
        get_overview_stats,
        get_route_type_counts,
        get_top_routes_by_trips,
        get_all_stops_locations,
        get_stops_by_region,
        get_regional_departures_df,
        calculate_regional_kpis,
        get_regional_delay_distribution,
        ON_TIME_THRESHOLD_MINUTES_LOW,
        ON_TIME_THRESHOLD_MINUTES_HIGH
    )
    from vag_api_client import fetch_and_parse_departures
except ImportError as e:
    st.error(f"Failed to import necessary functions: {e}")
    st.stop()

# --- Configuration ---
load_dotenv()  # Load environment variables from .env file

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("NurembergDashboard")

# Constants
REFRESH_INTERVAL_SECONDS = int(os.getenv('REFRESH_INTERVAL', '60'))
REGION_NAME = "Nuremberg"  # Focus only on Nuremberg

# --- Page Configuration ---
st.set_page_config(
    page_title="Nuremberg Transit Insights",
    page_icon="🚆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Helper Functions ---

@st.cache_resource(ttl=3600)
def load_db_engine():
    """Get a database engine (cached)"""
    logger.info("Creating database engine (cached)...")
    try:
        return get_engine()
    except Exception as e:
        logger.error(f"Failed to create database engine: {e}")
        return None

@st.cache_resource(ttl=REFRESH_INTERVAL_SECONDS)
def load_redis_connection():
    """Get a Redis connection (cached)"""
    logger.info("Creating Redis connection (cached)...")
    try:
        redis_conn = get_redis_conn()
        if redis_conn:
            # Test the connection
            redis_conn.ping()
            logger.info("Redis connection successful")
            return redis_conn
        else:
            logger.error("Failed to create Redis connection: get_redis_conn returned None")
            return None
    except Exception as e:
        logger.error(f"Failed to create Redis connection: {e}")
        return None

@st.cache_data(ttl=3600)
def load_overview_stats_data(_engine):
    """Load overview statistics from the database (cached)"""
    logger.info("Loading overview stats (cached)...")
    if not _engine:
        return {}
    return get_overview_stats(_engine)

@st.cache_data(ttl=3600)
def load_route_type_data(_engine):
    """Load route type data from the database (cached)"""
    logger.info("Loading route type counts (cached)...")
    if not _engine:
        return pd.DataFrame()
    return get_route_type_counts(_engine)

@st.cache_data(ttl=3600)
def load_top_routes_data(_engine):
    """Load top routes data from the database (cached)"""
    logger.info("Loading top routes (cached)...")
    if not _engine:
        return pd.DataFrame()
    return get_top_routes_by_trips(_engine)

@st.cache_data(ttl=3600)
def load_stops_for_region(_engine, region_name: str) -> List[str]:
    """Load stop IDs for a region from the database (cached)"""
    if not _engine or not region_name:
        return []
    logger.info(f"Loading stop IDs for region '{region_name}' (cached)...")
    return get_stops_by_region(_engine, region_name)

@st.cache_data(ttl=REFRESH_INTERVAL_SECONDS - 5)
def load_regional_departures_df(_redis_conn, region_stop_ids: List[str]):
    """Load departure data for a region from Redis (cached)"""
    logger.info(f"Loading departures for {len(region_stop_ids)} stops (cached)...")
    if not _redis_conn or not region_stop_ids:
        logger.warning("Redis connection or stop IDs not available")
        return pd.DataFrame()

    try:
        _redis_conn.ping()
    except redis.exceptions.ConnectionError:
        logger.error("Redis connection lost before fetching regional departures")
        st.cache_resource.clear()
        return pd.DataFrame()

    # Get real data from Redis
    real_data = get_regional_departures_df(_redis_conn, region_stop_ids)

    if not real_data.empty:
        logger.info(f"Successfully retrieved {len(real_data)} departures for region")
    else:
        logger.warning("No departure data found in Redis cache for the region")

    return real_data

@st.cache_data(ttl=REFRESH_INTERVAL_SECONDS - 5)
def compute_regional_kpis(regional_df: pd.DataFrame) -> Dict:
    """Calculate KPIs from departure data (cached)"""
    logger.info("Computing regional KPIs (cached)...")
    if regional_df.empty:
        return {"avg_delay": None, "on_time_percent": None, "total_departures": 0, "valid_delay_count": 0}
    return calculate_regional_kpis(regional_df)

@st.cache_data(ttl=REFRESH_INTERVAL_SECONDS - 5)
def compute_regional_distribution(regional_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate delay distribution from departure data (cached)"""
    logger.info("Computing regional delay distribution (cached)...")
    if regional_df.empty:
        return pd.DataFrame()
    return get_regional_delay_distribution(regional_df)

@st.cache_data(ttl=3600)
def load_stops_locations(_engine, region_name: str) -> pd.DataFrame:
    """Load stop locations for a region from the database (cached)"""
    logger.info(f"Loading stop locations for region '{region_name}' (cached)...")
    if not _engine:
        return pd.DataFrame()

    # Get all stops
    all_stops = get_all_stops_locations(_engine)

    # Filter for the region
    if region_name == "Nuremberg":
        # Filter for Nuremberg stops (based on stop_id pattern)
        region_stops = all_stops[all_stops['stop_id'].str.contains('de:09564', na=False)]
    else:
        region_stops = pd.DataFrame()

    return region_stops

# --- Main App Logic ---

# Load resources
db_engine = load_db_engine()
redis_connection = load_redis_connection()

if not db_engine:
    st.error("ERROR: Cannot connect to the database. Static data will not be available.")
    has_static_data = False
else:
    has_static_data = True

if not redis_connection:
    st.warning("WARNING: Cannot connect to Redis. Real-time data will not be available.")
    has_realtime_data = False
else:
    has_realtime_data = True

# --- Sidebar ---
with st.sidebar:
    st.title("Nuremberg Transit Insights")
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/9/9d/Wappen_N%C3%BCrnberg.svg/240px-Wappen_N%C3%BCrnberg.svg.png", width=100)

    st.markdown("### Data Status")

    # Show data status indicators
    col1, col2 = st.columns(2)
    with col1:
        if has_static_data:
            st.success("Static Data: ✅")
        else:
            st.error("Static Data: ❌")

    with col2:
        if has_realtime_data:
            st.success("Real-time Data: ✅")
        else:
            st.error("Real-time Data: ❌")

    st.markdown("---")

    # Navigation
    st.markdown("### Navigation")
    page = st.radio(
        "Go to",
        ["Network Overview", "Route Analysis", "Real-time Performance", "Neighborhood Insights"],
        index=0
    )

    st.markdown("---")

    # About section
    st.markdown("### About")
    st.markdown("""
    This dashboard provides insights into Nuremberg's public transit system.

    Data is sourced from:
    - VGN GTFS static data
    - VGN real-time API

    Last updated: {}
    """.format(datetime.now().strftime("%Y-%m-%d %H:%M")))

    # Refresh button
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.experimental_rerun()

# --- Main Content ---
if page == "Network Overview":
    st.header("Nuremberg Transit Network Overview")

    if has_static_data:
        # Load overview data
        overview_stats = load_overview_stats_data(db_engine)

        # Display KPIs
        with st.container(border=True):
            st.subheader("Network Statistics")
            col1, col2, col3 = st.columns(3)

            col1.metric("Total Routes", overview_stats.get('total_routes', 'N/A'))
            col2.metric("Total Stops", overview_stats.get('total_stops', 'N/A'))
            col3.metric("Total Trips (Scheduled)", overview_stats.get('total_trips', 'N/A'))

            st.caption("""
            **Data Source**: These metrics are calculated from the static GTFS data loaded into the database.
            They represent the total scheduled service across the entire VGN network.
            """)

        # Load stop locations
        stops_df = load_stops_locations(db_engine, REGION_NAME)

        if not stops_df.empty:
            with st.container(border=True):
                st.subheader("Nuremberg Transit Stops")

                # Create a map of stops
                # Create a copy of the dataframe with renamed columns for st.map
                map_df = stops_df.copy()
                map_df.rename(columns={'stop_lat': 'lat', 'stop_lon': 'lon'}, inplace=True)
                st.map(map_df)

                st.caption(f"""
                **Map shows**: {len(stops_df)} transit stops in Nuremberg.
                Each point represents a stop location.
                """)
    else:
        st.error("Cannot display network overview because database connection is not available.")

elif page == "Route Analysis":
    st.header("Nuremberg Route Analysis")

    if has_static_data:
        col_rt_1, col_rt_2 = st.columns([1, 2])

        # Load route type data
        df_route_types = load_route_type_data(db_engine)

        with col_rt_1:
            with st.container(border=True):
                st.subheader("Routes by Type")

                if not df_route_types.empty:
                    # Create pie chart
                    fig_route_types = px.pie(
                        df_route_types,
                        names='route_type_name',
                        values='count',
                        title="Distribution of Route Types",
                        hole=0.3,
                        color_discrete_sequence=px.colors.qualitative.Bold
                    )
                    fig_route_types.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig_route_types, use_container_width=True)

                    st.caption("""
                    **Chart Explanation**: This pie chart shows the breakdown of routes by their type
                    (bus, tram, subway, etc.) across the network. The percentages indicate the
                    proportion of each type relative to the total number of routes.
                    """)
                else:
                    st.warning("No route type data available.")

        # Load top routes data
        df_top_routes = load_top_routes_data(db_engine)

        with col_rt_2:
            with st.container(border=True):
                st.subheader("Top 15 Busiest Routes (by Scheduled Trips)")

                if not df_top_routes.empty:
                    # Get top 15 routes
                    top_15_routes = df_top_routes.sort_values(by='trip_count', ascending=False).head(15)

                    # Extract route type from route name for grouping
                    def extract_route_type(route_name):
                        if 'U' in route_name[:2]:  # U-Bahn routes typically start with U
                            return 'Subway'
                        elif 'S' in route_name[:2]:  # S-Bahn routes typically start with S
                            return 'Rail'
                        elif 'Tram' in route_name or 'T' in route_name[:2]:
                            return 'Tram'
                        elif 'Bus' in route_name:
                            return 'Bus'
                        else:
                            return 'Other'

                    # Add route type column
                    top_15_routes['route_type'] = top_15_routes['route_display_name'].apply(extract_route_type)

                    # Create a more descriptive label for treemap
                    top_15_routes['treemap_label'] = top_15_routes['route_display_name'].apply(
                        lambda x: x[:25] + '...' if len(x) > 25 else x
                    )

                    # Define a color map for route types
                    color_map = {
                        'Subway': '#1f77b4',  # Blue
                        'Rail': '#ff7f0e',    # Orange
                        'Tram': '#2ca02c',    # Green
                        'Bus': '#d62728',     # Red
                        'Other': '#9467bd'    # Purple
                    }

                    # Create the treemap
                    fig_top_routes = px.treemap(
                        top_15_routes,
                        path=['route_type', 'treemap_label'],
                        values='trip_count',
                        color='route_type',
                        color_discrete_map=color_map,
                        title="Top 15 Routes by Number of Trips",
                        hover_data=['route_display_name', 'trip_count']
                    )

                    # Update layout for better readability
                    fig_top_routes.update_layout(
                        height=450,
                        margin=dict(t=30, l=10, r=10, b=10),
                        hoverlabel=dict(
                            bgcolor="#333333",  # Dark background for better contrast
                            font_size=12,
                            font=dict(color="white")  # White text for better readability
                        )
                    )

                    # Update traces to show both route name and trip count in the boxes
                    fig_top_routes.update_traces(
                        textinfo='label+value',
                        hovertemplate='<b>%{customdata[0]}</b><br>Trips: %{customdata[1]}<extra></extra>'
                    )

                    st.plotly_chart(fig_top_routes, use_container_width=True)

                    st.caption("""
                    **Chart Explanation**: This treemap displays the 15 routes with the highest number of scheduled trips,
                    grouped by route type (Subway, Rail, Tram, Bus). The size of each box represents the number of trips,
                    with larger boxes indicating higher frequency service. Hover over a box to see the full route name and
                    exact trip count.
                    """)
                else:
                    st.warning("No top routes data available.")
    else:
        st.error("Cannot display route analysis because database connection is not available.")

elif page == "Real-time Performance":
    st.header("Nuremberg Real-time Transit Performance")

    if has_realtime_data:
        # Get stop IDs for Nuremberg
        all_region_stop_ids = load_stops_for_region(db_engine, REGION_NAME)

        if not all_region_stop_ids:
            st.warning(f"Could not find any stops for Nuremberg.")
        else:
            # Limit the number of stops to query for better performance
            MAX_STOPS_TO_QUERY = 20  # Limit to 20 stops for better performance

            if len(all_region_stop_ids) > MAX_STOPS_TO_QUERY:
                st.info(f"Found {len(all_region_stop_ids)} stops in Nuremberg. Limiting query to {MAX_STOPS_TO_QUERY} stops for better performance.")
                # Take a sample of stops for analysis
                import random
                region_stop_ids = random.sample(all_region_stop_ids, MAX_STOPS_TO_QUERY)
            else:
                region_stop_ids = all_region_stop_ids
                st.success(f"Found {len(region_stop_ids)} stops in Nuremberg. Analyzing real-time data...")

            # Load departure data
            try:
                # Check Redis connection
                if not redis_connection:
                    st.error("Redis connection is not available. Please make sure Redis server is running.")
                    regional_df = pd.DataFrame()
                else:
                    # Try to ping Redis to verify connection
                    try:
                        redis_connection.ping()
                        st.success("✅ Redis connection is active")

                        # Log the stop IDs being queried
                        st.info(f"Querying {len(region_stop_ids)} stops for real-time data (out of {len(all_region_stop_ids)} total stops)...")
                        if len(region_stop_ids) > 10:
                            st.caption(f"Sample stop IDs: {', '.join(region_stop_ids[:10])}...")
                        else:
                            st.caption(f"Stop IDs: {', '.join(region_stop_ids)}")

                        # Add note about the limited data
                        if len(all_region_stop_ids) > MAX_STOPS_TO_QUERY:
                            st.caption("Note: Using a subset of stops to improve performance. Metrics represent a sample of the network.")

                        # Get the data
                        regional_df = load_regional_departures_df(redis_connection, region_stop_ids)

                        # Log the result
                        if not regional_df.empty:
                            st.success(f"✅ Successfully retrieved {len(regional_df)} departures")
                        else:
                            st.warning("No departure data found in Redis cache")

                    except redis.exceptions.ConnectionError:
                        st.error("Redis connection failed. Please make sure Redis server is running.")
                        regional_df = pd.DataFrame()
            except Exception as e:
                st.error(f"Error loading real-time data: {e}")
                st.info("Please make sure the background_fetcher.py script is running to provide real-time data.")
                regional_df = pd.DataFrame()

            if not regional_df.empty:
                # Calculate KPIs
                regional_kpis = compute_regional_kpis(regional_df)

                with st.container(border=True):
                    st.subheader("Current Performance Metrics for Nuremberg")

                    # KPI metrics in columns
                    kpi_col_r1, kpi_col_r2, kpi_col_r3 = st.columns(3)

                    # Average Delay KPI
                    kpi_col_r1.metric(
                        "Average Delay",
                        f"{regional_kpis.get('avg_delay', 0):.1f} min" if regional_kpis.get('avg_delay') is not None else "N/A",
                        delta=None,
                        delta_color="inverse",
                        help="Average delay across all monitored departures with valid real-time data."
                    )

                    # On-Time Percentage KPI
                    on_time_value = regional_kpis.get('on_time_percent')
                    kpi_col_r2.metric(
                        "On-Time Performance",
                        f"{on_time_value:.1f}%" if on_time_value is not None else "N/A",
                        delta=None,
                        help=f"Percentage of departures that are on time (between {ON_TIME_THRESHOLD_MINUTES_LOW} min early and +{ON_TIME_THRESHOLD_MINUTES_HIGH} min late)."
                    )

                    # Monitored Departures KPI
                    valid_count = regional_kpis.get('valid_delay_count', 0)
                    total_count = regional_kpis.get('total_departures', 0)
                    kpi_col_r3.metric(
                        "Data Coverage",
                        f"{valid_count}/{total_count} departures",
                        delta=f"{(valid_count/total_count*100):.1f}%" if total_count > 0 else "N/A",
                        help="Number of departures with valid delay data out of total departures found in cache."
                    )

                    st.caption("""
                    **Data Source**: These metrics are calculated from real-time departure data cached in Redis.
                    The system monitors actual vs. scheduled departure times for stops in Nuremberg.

                    **On-Time Definition**: A departure is considered "on time" if it departs between 1 minute early
                    and 3 minutes late compared to the scheduled time.
                    """)

                # Calculate and display Delay Distribution
                with st.container(border=True):
                    st.subheader("Current Delay Distribution for Nuremberg")
                    regional_dist_df = compute_regional_distribution(regional_df)

                    if not regional_dist_df.empty and regional_dist_df['count'].sum() > 0:
                        try:
                            # Create color map for the categories
                            color_map = {
                                "< -1m (Early)": "#FFA15A",  # Orange for early
                                "-1m to +3m (On Time)": "#19D3F3",  # Blue for on-time
                                "+4m to +10m (Late)": "#FF6692",  # Pink for late
                                "> +10m (Very Late)": "#B6E880"  # Green for very late
                            }

                            fig_delay_dist = px.bar(
                                regional_dist_df,
                                x='category',
                                y='count',
                                title="Distribution of Delays in Nuremberg",
                                labels={'count': 'Number of Departures', 'category': 'Delay Category'},
                                category_orders={"category": ["< -1m (Early)", "-1m to +3m (On Time)", "+4m to +10m (Late)", "> +10m (Very Late)"]},
                                text_auto=True,
                                color='category',
                                color_discrete_map=color_map
                            )
                            fig_delay_dist.update_layout(
                                xaxis_title=None,
                                yaxis_title="Number of Departures",
                                legend_title="Delay Category",
                                height=400
                            )
                            st.plotly_chart(fig_delay_dist, use_container_width=True)

                            st.caption("""
                            **Chart Explanation**: This bar chart shows the distribution of departures across different delay categories.
                            - **Early**: Departures that left more than 1 minute ahead of schedule
                            - **On Time**: Departures within the acceptable window (-1 to +3 minutes)
                            - **Late**: Departures between 4 and 10 minutes behind schedule
                            - **Very Late**: Departures more than 10 minutes behind schedule

                            A higher proportion in the "On Time" category indicates better adherence to schedules.
                            """)
                        except Exception as e:
                            st.error(f"Could not generate delay distribution chart: {e}")
                    else:
                        st.info("No valid delay data found to display distribution chart.")

                # Display a sample of the real-time data
                with st.container(border=True):
                    st.subheader("Sample of Current Departures")

                    if len(regional_df) > 0:
                        # Add a human-readable delay column
                        if 'delay_minutes' in regional_df.columns:
                            def format_delay(delay):
                                if pd.isna(delay):
                                    return "Unknown"
                                elif delay < 0:
                                    return f"{abs(delay)} min early"
                                elif delay == 0:
                                    return "On time"
                                else:
                                    return f"{delay} min late"

                            regional_df['delay_status'] = regional_df['delay_minutes'].apply(format_delay)

                        # Select relevant columns and show a sample
                        display_cols = ['line', 'destination', 'scheduled_time', 'actual_time', 'delay_status']
                        display_df = regional_df[display_cols].head(10)

                        st.dataframe(display_df, use_container_width=True)

                        st.caption("""
                        **Table shows**: A sample of the most recent departures with real-time data.
                        This gives you a snapshot of current transit operations.
                        """)
                    else:
                        st.info("No departure data available to display.")
            else:
                st.warning("No current departure data found in cache for any monitored stops in Nuremberg.")
                st.error("No valid departure data found for real-time analysis. Please ensure the background_fetcher.py script is running.")

                st.caption("""
                **Possible reasons**:
                - The data fetcher may not be running or hasn't cached data yet
                - There might be no active transit service at the current time
                - The Redis cache might need to be refreshed
                - The API might be temporarily unavailable

                **Solution**:
                1. Make sure the background_fetcher.py script is running
                2. Verify API connectivity
                """)
    else:
        st.error("Cannot display real-time performance because Redis connection is not available.")

elif page == "Neighborhood Insights":
    st.header("Nuremberg Neighborhood Transit Insights")

    # This is a placeholder for future neighborhood-level analysis
    st.info("🚧 This section is under development. It will provide transit insights by neighborhood.")

    # Show a map of Nuremberg neighborhoods
    st.markdown("""
    ### Coming Soon:

    - **Neighborhood Performance**: See which neighborhoods have the best transit service
    - **Accessibility Analysis**: Discover how well different areas are served by public transit
    - **Service Frequency**: Compare transit frequency across neighborhoods
    - **Delay Patterns**: Identify areas with the most reliable service
    """)

# --- Footer ---
st.divider()

with st.container():
    col1, col2 = st.columns([3, 1])

    with col1:
        st.caption(f"""
        **About this Dashboard**: This dashboard displays both static and real-time transit data for Nuremberg.

        **Data Freshness**: Real-time data is refreshed every {REFRESH_INTERVAL_SECONDS} seconds.
        Last update: {datetime.now().strftime("%H:%M:%S")}
        """)

    with col2:
        # Add a small refresh button
        if st.button("🔄 Refresh Now", key="footer_refresh"):
            st.cache_data.clear()
            st.rerun()
        st.caption("Click to refresh immediately")

# Auto-refresh
if has_realtime_data:
    time.sleep(REFRESH_INTERVAL_SECONDS)
    st.rerun()
