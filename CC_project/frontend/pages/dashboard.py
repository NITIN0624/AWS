# frontend/pages/dashboard.py
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Configuration
API_BASE_URL = "http://127.0.0.1:8000"

# Set page title
st.set_page_config(
    page_title="System Dashboard",
    page_icon="📊",
    layout="wide"
)

# Page title
st.title("System Dashboard")

# Time range selector
time_range = st.selectbox(
    "Time Range",
    [1, 3, 7, 14, 30],
    index=2,
    format_func=lambda x: f"Last {x} days"
)

# Fetch system metrics
@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_system_metrics(days):
    try:
        response = requests.get(f"{API_BASE_URL}/metrics/aggregated?days={days}")
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error fetching system metrics: {response.text}")
            return None
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return None

with st.spinner("Loading system metrics..."):
    system_data = get_system_metrics(time_range)
    
    # Add debugging information
    st.write("API Response Keys:", list(system_data.keys()) if system_data else "No data")

if not system_data:
    st.warning("No system metrics available. Please check if your backend is running.")
    st.stop()

# Use the data directly without trying to access a nested "system_stats" key
# The entire response is your system stats
st.subheader("System Statistics")

# Create a nice layout with metrics
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Executions", system_data["count"])
    st.metric("Success Rate", f"{system_data['success_rate'] * 100:.2f}%")
    
with col2:
    st.metric("Avg Execution Time (ms)", f"{system_data['avg_execution_time_ms']:.2f}")
    st.metric("P95 Execution Time (ms)", system_data["p95_execution_time_ms"])
    
with col3:
    st.metric("Avg Total Time (ms)", f"{system_data['avg_total_time_ms']:.2f}")
    st.metric("Cold Start %", f"{system_data['cold_start_percentage'] * 100:.2f}%")

# Add runtime breakdown chart
st.subheader("Runtime Distribution")
runtime_data = system_data["runtime_breakdown"]
fig = px.pie(
    names=list(runtime_data.keys()),
    values=list(runtime_data.values()),
    title="Runtime Distribution"
)
st.plotly_chart(fig, use_container_width=True)

# Add some additional sections for visualization if you have the data
if "error_rate" in system_data and "timeout_rate" in system_data:
    st.subheader("Error Statistics")
    error_data = {
        "Status": ["Success", "Error", "Timeout"],
        "Percentage": [
            system_data["success_rate"] * 100,
            system_data["error_rate"] * 100,
            system_data["timeout_rate"] * 100
        ]
    }
    fig = px.bar(
        error_data,
        x="Status",
        y="Percentage",
        title="Execution Status Distribution",
        color="Status"
    )
    st.plotly_chart(fig, use_container_width=True)

# Add execution time distribution if we had that data
# This is a placeholder - you can add this if you enhance your backend later
st.subheader("Performance Analysis")
st.info("For detailed function-specific metrics, visit the Functions page.")
