# frontend/app.py
import streamlit as st
import requests
import json
import time
from typing import Dict, Any, List
import statistics
import pandas as pd
import plotly.express as px

# Configuration
API_BASE_URL = "http://127.0.0.1:8000"

# Set page config
st.set_page_config(
    page_title="Serverless Function Platform",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 42px;
        background: linear-gradient(90deg, #4b6cb7 0%, #182848 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        padding-bottom: 20px;
    }
    .sub-header {
        font-size: 26px;
        color: #4b6cb7;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .card {
        padding: 20px;
        border-radius: 10px;
        background-color: #f8f9fa;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin-bottom: 20px;
    }
    .success-text {
        color: #28a745;
        font-weight: bold;
    }
    .error-text {
        color: #dc3545;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar navigation with icons
st.sidebar.markdown("<h1>🚀 Serverless Platform</h1>", unsafe_allow_html=True)
pages = {
    "📋 Function Manager": "Functions",
    "📊 Performance Metrics": "Metrics", 
    "⚖️ Runtime Comparison": "Comparison"
}
page = st.sidebar.radio("Navigation", list(pages.keys()))

# Create session state for storing data
if "functions" not in st.session_state:
    st.session_state.functions = []
if "selected_function" not in st.session_state:
    st.session_state.selected_function = None
if "function_code" not in st.session_state:
    st.session_state.function_code = ""

# API Functions
def get_functions():
    try:
        response = requests.get(f"{API_BASE_URL}/functions/")
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error fetching functions: {response.text}")
            return []
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return []

def create_function(name, language, code, timeout):
    try:
        data = {
            "name": name,
            "language": language,
            "code": code,
            "timeout": timeout
        }
        response = requests.post(
            f"{API_BASE_URL}/functions/",
            headers={"Content-Type": "application/json"},
            data=json.dumps(data)
        )
        if response.status_code == 200:
            st.success(f"Function '{name}' created successfully")
            return True
        else:
            st.error(f"Error creating function: {response.text}")
            return False
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return False

def update_function(name, language, code, timeout):
    try:
        data = {
            "name": name,
            "language": language,
            "code": code,
            "timeout": timeout
        }
        response = requests.put(
            f"{API_BASE_URL}/functions/{name}",
            headers={"Content-Type": "application/json"},
            data=json.dumps(data)
        )
        if response.status_code == 200:
            st.success(f"Function '{name}' updated successfully")
            return True
        else:
            st.error(f"Error updating function: {response.text}")
            return False
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return False

def delete_function(name):
    try:
        response = requests.delete(f"{API_BASE_URL}/functions/{name}")
        if response.status_code == 200:
            st.success(f"Function '{name}' deleted successfully")
            return True
        else:
            st.error(f"Error deleting function: {response.text}")
            return False
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return False

def execute_function(name, runtime="docker", warm_start=False):
    try:
        data = {
            "runtime": runtime,
            "warm_start": warm_start
        }
        with st.spinner(f"⚙️ Executing function '{name}' with {runtime}..."):
            response = requests.post(
                f"{API_BASE_URL}/functions/execute/{name}",
                headers={"Content-Type": "application/json"},
                data=json.dumps(data)
            )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error executing function: {response.text}")
            return None
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return None

def get_function_metrics(name):
    try:
        response = requests.get(f"{API_BASE_URL}/metrics/functions/{name}")
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error fetching metrics: {response.text}")
            return None
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return None

def compare_runtimes(name, iterations=3):
    try:
        with st.spinner(f"⚖️ Comparing runtimes for '{name}' ({iterations} iterations)..."):
            response = requests.get(
                f"{API_BASE_URL}/runtime/compare",
                params={"function_name": name, "iterations": iterations}
            )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error comparing runtimes: {response.text}")
            return None
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return None

# Function Management Page
def show_functions_page():
    st.markdown("<h1 class='main-header'>Function Management</h1>", unsafe_allow_html=True)
    
    # Refresh function list
    if st.sidebar.button("🔄 Refresh Functions", key="refresh_btn"):
        st.session_state.functions = get_functions()
    
    # Initial load of functions if empty
    if not st.session_state.functions:
        st.session_state.functions = get_functions()
    
    # Display functions in sidebar for selection
    st.sidebar.markdown("<h3>Your Functions</h3>", unsafe_allow_html=True)
    function_names = [func["name"] for func in st.session_state.functions]
    function_names.insert(0, "➕ Create New Function")
    
    selected_function_name = st.sidebar.selectbox(
        "Select Function", 
        function_names,
        index=0
    )
    
    # Handle function creation
    if selected_function_name == "➕ Create New Function":
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<h2 class='sub-header'>Create New Function</h2>", unsafe_allow_html=True)
        
        col1, col2 = st.columns([2, 1])
        with col1:
            name = st.text_input("Function Name", key="new_name", placeholder="Enter function name")
        with col2:
            language = st.selectbox(
                "Language", 
                ["python", "javascript"],
                format_func=lambda x: "Python" if x == "python" else "JavaScript",
                key="new_language"
            )
        
        code_template = "print('Hello, World!')" if language == "python" else "console.log('Hello, World!');"
        code = st.text_area("Code Editor", code_template, height=300, key="new_code")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            timeout = st.slider("Execution Timeout (seconds)", 1, 300, 30, key="new_timeout")
        with col2:
            st.write("")
            st.write("")
            if st.button("🚀 Create Function", key="create_btn", use_container_width=True):
                if not name:
                    st.error("Function name is required")
                elif not code:
                    st.error("Function code is required")
                else:
                    if create_function(name, language, code, timeout):
                        # Refresh function list
                        st.session_state.functions = get_functions()
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Handle function editing/execution
    else:
        # Find the selected function
        func = next((f for f in st.session_state.functions if f["name"] == selected_function_name), None)
        if func:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.markdown(f"<h2 class='sub-header'>Edit Function: {func['name']}</h2>", unsafe_allow_html=True)
            
            # Function details in columns
            col1, col2 = st.columns(2)
            with col1:
                language = st.selectbox(
                    "Language", 
                    ["python", "javascript"],
                    format_func=lambda x: "Python" if x == "python" else "JavaScript",
                    index=0 if func["language"] == "python" else 1,
                    key="edit_language"
                )
            with col2:
                timeout = st.slider(
                    "Timeout (seconds)", 
                    1, 300, 
                    int(func["timeout"]), 
                    key="edit_timeout"
                )
            
            code = st.text_area("Code Editor", func["code"], height=300, key="edit_code")
            
            # Function actions
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Update Function", key="update_btn", use_container_width=True):
                    if update_function(func["name"], language, code, timeout):
                        # Refresh function list
                        st.session_state.functions = get_functions()
            with col2:
                if st.button("🗑️ Delete Function", key="delete_btn", use_container_width=True):
                    if delete_function(func["name"]):
                        # Refresh function list and reset selection
                        st.session_state.functions = get_functions()
                        st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
            
            # Function execution
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.markdown("<h2 class='sub-header'>Execute Function</h2>", unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                runtime = st.selectbox(
                    "Runtime Environment", 
                    ["docker", "gvisor"], 
                    format_func=lambda x: "Docker" if x == "docker" else "gVisor",
                    key="exec_runtime"
                )
            with col2:
                warm_start = st.checkbox("Enable Warm Start", value=False, key="exec_warm_start")
            with col3:
                st.write("")
                st.write("")
                execute_button = st.button("▶️ Execute", key="exec_btn", use_container_width=True)
            
            if execute_button:
                result = execute_function(func["name"], runtime, warm_start)
                if result:
                    st.markdown("<h3>Execution Result</h3>", unsafe_allow_html=True)
                    
                    # Show status and metrics
                    status = result["result"]["status"]
                    status_color = "success-text" if status == "success" else "error-text"
                    st.markdown(f"Status: <span class='{status_color}'>{status.upper()}</span>", unsafe_allow_html=True)
                    
                    # Show execution metrics
                    metrics = result["result"]["metrics"]
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Init Time (ms)", metrics["initialization_time_ms"], delta=None)
                    with col2:
                        st.metric("Execution Time (ms)", metrics["execution_time_ms"], delta=None)
                    with col3:
                        st.metric("Total Time (ms)", metrics["total_time_ms"], delta=None)
                    
                    # Show output
                    tabs = st.tabs(["Output", "Errors"])
                    with tabs[0]:
                        st.code(result["result"]["stdout"], language=func["language"])
                    
                    with tabs[1]:
                        if result["result"]["stderr"]:
                            st.code(result["result"]["stderr"], language=func["language"])
                        else:
                            st.info("No errors reported")
            st.markdown("</div>", unsafe_allow_html=True)
                    
def calculate_function_stats(executions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate statistics for a list of function executions"""
    if not executions:
        return {
            "total_executions": 0,
            "success_rate": 0,
            "avg_initialization_time": 0,
            "min_initialization_time": 0,
            "max_initialization_time": 0,
            "avg_execution_time": 0,
            "min_execution_time": 0,
            "max_execution_time": 0,
            "avg_total_time": 0,
            "min_total_time": 0,
            "max_total_time": 0,
            "runtime_distribution": {"docker": 0, "gvisor": 0},
            "warm_vs_cold": {"warm": 0, "cold": 0}
        }
    
    # Calculate success rate
    successful = sum(1 for e in executions if e.get("success", False))
    success_rate = (successful / len(executions)) * 100 if executions else 0
    
    # Calculate time averages
    exec_times = [e["execution_time_ms"] for e in executions if "execution_time_ms" in e]
    init_times = [e["initialization_time_ms"] for e in executions if "initialization_time_ms" in e]
    total_times = [e["total_time_ms"] for e in executions if "total_time_ms" in e]
    
    return {
        "total_executions": len(executions),
        "success_rate": success_rate,
        "avg_initialization_time": sum(init_times)/len(init_times) if init_times else 0,
        "min_initialization_time": min(init_times) if init_times else 0,
        "max_initialization_time": max(init_times) if init_times else 0,
        "avg_execution_time": sum(exec_times)/len(exec_times) if exec_times else 0,
        "min_execution_time": min(exec_times) if exec_times else 0,
        "max_execution_time": max(exec_times) if exec_times else 0,
        "avg_total_time": sum(total_times)/len(total_times) if total_times else 0,
        "min_total_time": min(total_times) if total_times else 0,
        "max_total_time": max(total_times) if total_times else 0,
        "runtime_distribution": {
            "docker": sum(1 for e in executions if e.get("runtime") == "docker"),
            "gvisor": sum(1 for e in executions if e.get("runtime") == "gvisor")
        },
        "warm_vs_cold": {
            "warm": sum(1 for e in executions if not e.get("cold_start", True)),
            "cold": sum(1 for e in executions if e.get("cold_start", True))
        }
    }

# Metrics Visualization Page
def show_metrics_page():
    st.markdown("<h1 class='main-header'>Function Performance Metrics</h1>", unsafe_allow_html=True)
    
    # Get list of functions for selection
    functions = get_functions()
    function_names = [func["name"] for func in functions]
    
    if not function_names:
        st.warning("⚠️ No functions found. Create a function first.")
        return
    
    selected_function = st.selectbox("Select Function for Analysis", function_names)
    
    if selected_function:
        with st.spinner("Loading metrics data..."):
            metrics_data = get_function_metrics(selected_function)
            
            if not metrics_data:
                st.warning(f"⚠️ No metrics data available for {selected_function}")
                return
                
            # Convert metrics to the expected format
            executions = []
            for metric in metrics_data:
                executions.append({
                    "id": metric["id"],
                    "function_name": metric["function_name"],
                    "runtime": metric["runtime"],
                    "language": metric["language"],
                    "initialization_time_ms": metric["initialization_time_ms"],
                    "execution_time_ms": metric["execution_time_ms"],
                    "total_time_ms": metric["total_time_ms"],
                    "cold_start": metric["cold_start"],
                    "error": metric["error_message"],
                    "timestamp": metric["timestamp"],
                    "success": metric["status"] == "success"
                })
            
            # Calculate statistics
            stats = calculate_function_stats(executions)
            
            # Display metrics
            st.markdown(f"<h2 class='sub-header'>Analytics for {selected_function}</h2>", unsafe_allow_html=True)
            
            # Display summary statistics in a card
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.markdown("<h3>Performance Summary</h3>", unsafe_allow_html=True)
            
            # First row
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Executions", stats["total_executions"])
            with col2:
                st.metric("Success Rate", f"{stats['success_rate']:.1f}%")
            with col3:
                st.metric("Docker Runs", stats["runtime_distribution"]["docker"])
            with col4:
                st.metric("gVisor Runs", stats["runtime_distribution"]["gvisor"])
            
            # Second row
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Avg Init Time", f"{stats['avg_initialization_time']:.2f} ms")
                st.caption(f"Range: {stats['min_initialization_time']} - {stats['max_initialization_time']} ms")
            with col2:
                st.metric("Avg Execution Time", f"{stats['avg_execution_time']:.2f} ms")
                st.caption(f"Range: {stats['min_execution_time']} - {stats['max_execution_time']} ms")
            with col3:
                st.metric("Avg Total Time", f"{stats['avg_total_time']:.2f} ms")
                st.caption(f"Range: {stats['min_total_time']} - {stats['max_total_time']} ms")
            st.markdown("</div>", unsafe_allow_html=True)
            
            # Prepare data for charts
            df = pd.DataFrame(executions)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            
            # Tabs for different visualizations
            tabs = st.tabs(["Time Analysis", "Runtime Comparison", "Cold vs Warm Start", "Raw Data"])
            
            with tabs[0]:
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                st.subheader("Execution Time Trend")
                
                # Use a more appealing color palette
                color_discrete_map = {
                    "docker": "#3366CC", 
                    "gvisor": "#DC3912"
                }
                
                fig = px.line(
                    df, 
                    x="timestamp", 
                    y="execution_time_ms",
                    color="runtime",
                    markers=True,
                    title="Execution Performance Over Time",
                    labels={"execution_time_ms": "Execution Time (ms)", "timestamp": "Execution Time"},
                    color_discrete_map=color_discrete_map
                )
                fig.update_layout(
                    legend_title="Runtime Environment",
                    hovermode="x unified",
                    plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Add init time and total time graphs
                col1, col2 = st.columns(2)
                with col1:
                    fig = px.line(
                        df, 
                        x="timestamp", 
                        y="initialization_time_ms",
                        color="runtime",
                        markers=True,
                        title="Initialization Time Trend",
                        labels={"initialization_time_ms": "Init Time (ms)", "timestamp": "Execution Time"},
                        color_discrete_map=color_discrete_map
                    )
                    fig.update_layout(
                        legend_title="Runtime",
                        hovermode="x unified",
                        plot_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    fig = px.line(
                        df, 
                        x="timestamp", 
                        y="total_time_ms",
                        color="runtime",
                        markers=True,
                        title="Total Time Trend",
                        labels={"total_time_ms": "Total Time (ms)", "timestamp": "Execution Time"},
                        color_discrete_map=color_discrete_map
                    )
                    fig.update_layout(
                        legend_title="Runtime",
                        hovermode="x unified",
                        plot_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(fig, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
            
            with tabs[1]:
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Runtime Distribution")
                    runtime_counts = df["runtime"].value_counts().reset_index()
                    runtime_counts.columns = ["Runtime", "Count"]
                    fig = px.pie(
                        runtime_counts, 
                        values="Count", 
                        names="Runtime",
                        color="Runtime",
                        color_discrete_map={"docker": "#3366CC", "gvisor": "#DC3912"},
                        hole=0.4
                    )
                    fig.update_layout(
                        legend_title="Runtime Type",
                        plot_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    st.subheader("Runtime Performance Comparison")
                    fig = px.box(
                        df,
                        x="runtime",
                        y="execution_time_ms",
                        color="runtime",
                        points="all",
                        color_discrete_map=color_discrete_map,
                        labels={"execution_time_ms": "Execution Time (ms)", "runtime": "Runtime Environment"}
                    )
                    fig.update_layout(
                        legend_title="Runtime",
                        plot_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(fig, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
            
            with tabs[2]:
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                st.subheader("Cold vs Warm Start Analysis")
                
                # Create a column for start type
                df["start_type"] = df["cold_start"].apply(lambda x: "Cold Start" if x else "Warm Start")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Pie chart for cold vs warm distribution
                    warm_cold_counts = df["start_type"].value_counts().reset_index()
                    warm_cold_counts.columns = ["Start Type", "Count"]
                    fig = px.pie(
                        warm_cold_counts, 
                        values="Count", 
                        names="Start Type",
                        color="Start Type",
                        color_discrete_map={"Cold Start": "#FF9900", "Warm Start": "#109618"},
                        hole=0.4
                    )
                    fig.update_layout(
                        legend_title="Start Type",
                        plot_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    # Box plot comparing init times
                    fig = px.box(
                        df,
                        x="start_type",
                        y="initialization_time_ms",
                        color="start_type",
                        points="all",
                        color_discrete_map={"Cold Start": "#FF9900", "Warm Start": "#109618"},
                        labels={"initialization_time_ms": "Initialization Time (ms)", "start_type": "Start Type"}
                    )
                    fig.update_layout(
                        legend_title="Start Type",
                        plot_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Bar chart comparing average times by start type
                st.subheader("Performance by Start Type")
                start_type_stats = df.groupby("start_type").agg({
                    "initialization_time_ms": "mean",
                    "execution_time_ms": "mean",
                    "total_time_ms": "mean"
                }).reset_index()
                
                start_type_stats_melted = pd.melt(
                    start_type_stats, 
                    id_vars=["start_type"],
                    value_vars=["initialization_time_ms", "execution_time_ms", "total_time_ms"],
                    var_name="Metric", 
                    value_name="Time (ms)"
                )
                
                start_type_stats_melted["Metric"] = start_type_stats_melted["Metric"].replace({
                    "initialization_time_ms": "Initialization Time",
                    "execution_time_ms": "Execution Time",
                    "total_time_ms": "Total Time"
                })
                
                fig = px.bar(
                    start_type_stats_melted,
                    x="start_type",
                    y="Time (ms)",
                    color="Metric",
                    barmode="group",
                    labels={"start_type": "Start Type"},
                    color_discrete_map={
                        "Initialization Time": "#4C78A8", 
                        "Execution Time": "#F58518", 
                        "Total Time": "#72B7B2"
                    }
                )
                fig.update_layout(
                    legend_title="Time Metric",
                    plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
            
            with tabs[3]:
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                st.subheader("Execution Log")
                
                # Add search/filter functionality
                search_term = st.text_input("🔍 Search executions", placeholder="Filter by runtime, status...")
                
                filtered_df = df
                if search_term:
                    filtered_df = df[df.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)]
                
                # Format the dataframe for better display
                display_df = filtered_df[["timestamp", "runtime", "success", "cold_start", 
                                         "initialization_time_ms", "execution_time_ms", "total_time_ms"]]
                display_df = display_df.rename(columns={
                    "timestamp": "Timestamp",
                    "runtime": "Runtime",
                    "success": "Success",
                    "cold_start": "Cold Start",
                    "initialization_time_ms": "Init Time (ms)",
                    "execution_time_ms": "Exec Time (ms)",
                    "total_time_ms": "Total Time (ms)"
                })
                
                # Apply conditional styling
                def highlight_success(val):
                    color = 'background-color: #d4edda' if val == True else 'background-color: #f8d7da'
                    return color
                
                styled_df = display_df.style.applymap(highlight_success, subset=['Success'])
                
                st.dataframe(styled_df, use_container_width=True)
                st.caption(f"Showing {len(filtered_df)} of {len(df)} executions")
                st.markdown("</div>", unsafe_allow_html=True)
            
def show_comparison_page():
    st.markdown("<h1 class='main-header'>Runtime Comparison Analysis</h1>", unsafe_allow_html=True)
    
    # Get list of functions for selection
    functions = get_functions()
    function_names = [func["name"] for func in functions]
    
    if not function_names:
        st.warning("⚠️ No functions found. Create a function first.")
        return
    
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<h2 class='sub-header'>Runtime Performance Benchmark</h2>", unsafe_allow_html=True)
    st.write("Compare Docker vs gVisor performance for running your serverless functions")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        selected_function = st.selectbox("Select Function to Benchmark", function_names)
    with col2:
        iterations = st.slider("Test Iterations", 1, 10, 3)
    
    if st.button("🚀 Run Benchmark", use_container_width=True):
        with st.spinner("Running performance benchmark..."):
            comparison_data = compare_runtimes(selected_function, iterations)
        
        if comparison_data:
            st.markdown("<h3>Benchmark Results</h3>")
            st.markdown("<h3>Benchmark Results</h3>", unsafe_allow_html=True)
            
            # Display summary statistics
            docker_stats = comparison_data["docker"]
            gvisor_stats = comparison_data["gvisor"]
            
            # Calculate percentage differences for delta display
            init_diff = ((gvisor_stats['avg_init_time_ms'] - docker_stats['avg_init_time_ms']) / docker_stats['avg_init_time_ms']) * 100 if docker_stats['avg_init_time_ms'] else 0
            exec_diff = ((gvisor_stats['avg_exec_time_ms'] - docker_stats['avg_exec_time_ms']) / docker_stats['avg_exec_time_ms']) * 100 if docker_stats['avg_exec_time_ms'] else 0
            total_diff = ((gvisor_stats['avg_total_time_ms'] - docker_stats['avg_total_time_ms']) / docker_stats['avg_total_time_ms']) * 100 if docker_stats['avg_total_time_ms'] else 0
            
            # Summary metrics with comparisons
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("<h4>Docker Runtime</h4>", unsafe_allow_html=True)
                st.metric("Init Time (ms)", f"{docker_stats['avg_init_time_ms']:.2f}")
                st.metric("Execution Time (ms)", f"{docker_stats['avg_exec_time_ms']:.2f}")
                st.metric("Total Time (ms)", f"{docker_stats['avg_total_time_ms']:.2f}")
            with col2:
                st.markdown("<h4>gVisor Runtime</h4>", unsafe_allow_html=True)
                st.metric("Init Time (ms)", f"{gvisor_stats['avg_init_time_ms']:.2f}", delta=f"{init_diff:.1f}%", delta_color="inverse")
                st.metric("Execution Time (ms)", f"{gvisor_stats['avg_exec_time_ms']:.2f}", delta=f"{exec_diff:.1f}%", delta_color="inverse")
                st.metric("Total Time (ms)", f"{gvisor_stats['avg_total_time_ms']:.2f}", delta=f"{total_diff:.1f}%", delta_color="inverse")
            
            # Prepare data for charts
            import pandas as pd
            import plotly.express as px
            
            # Create comparison dataframe
            data = {
                "Runtime": ["Docker", "gVisor"],
                "Initialization Time (ms)": [docker_stats["avg_init_time_ms"], gvisor_stats["avg_init_time_ms"]],
                "Execution Time (ms)": [docker_stats["avg_exec_time_ms"], gvisor_stats["avg_exec_time_ms"]],
                "Total Time (ms)": [docker_stats["avg_total_time_ms"], gvisor_stats["avg_total_time_ms"]]
            }
            df = pd.DataFrame(data)
            
            # Format the data for a grouped bar chart
            long_df = pd.melt(
                df, 
                id_vars=["Runtime"],
                value_vars=["Initialization Time (ms)", "Execution Time (ms)", "Total Time (ms)"],
                var_name="Metric", 
                value_name="Time (ms)"
            )
            
            # Comprehensive comparison chart
            st.subheader("Performance Comparison")
            fig = px.bar(
                long_df,
                x="Metric",
                y="Time (ms)",
                color="Runtime",
                barmode="group",
                color_discrete_map={"Docker": "#3366CC", "gVisor": "#DC3912"},
                title=f"Docker vs gVisor Performance Metrics ({iterations} iterations)"
            )
            fig.update_layout(
                legend_title="Runtime Environment",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis_title="",
                yaxis_title="Time (ms)",
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Individual metric charts
            tabs = st.tabs(["Initialization Time", "Execution Time", "Total Time", "Raw Data"])
            
            with tabs[0]:
                fig = px.bar(
                    df,
                    x="Runtime",
                    y="Initialization Time (ms)",
                    color="Runtime",
                    color_discrete_map={"Docker": "#3366CC", "gVisor": "#DC3912"},
                    title="Average Initialization Time Comparison"
                )
                fig.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    showlegend=False
                )
                
                # Add value labels on top of bars
                fig.update_traces(
                    text=[f"{val:.2f} ms" for val in df["Initialization Time (ms)"]],
                    textposition="outside"
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                if init_diff > 0:
                    st.info(f"💡 gVisor initialization is {abs(init_diff):.1f}% slower than Docker")
                else:
                    st.info(f"💡 gVisor initialization is {abs(init_diff):.1f}% faster than Docker")
            
            with tabs[1]:
                fig = px.bar(
                    df,
                    x="Runtime",
                    y="Execution Time (ms)",
                    color="Runtime",
                    color_discrete_map={"Docker": "#3366CC", "gVisor": "#DC3912"},
                    title="Average Execution Time Comparison"
                )
                fig.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    showlegend=False
                )
                
                # Add value labels on top of bars
                fig.update_traces(
                    text=[f"{val:.2f} ms" for val in df["Execution Time (ms)"]],
                    textposition="outside"
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                if exec_diff > 0:
                    st.info(f"💡 Function execution in gVisor is {abs(exec_diff):.1f}% slower than Docker")
                else:
                    st.info(f"💡 Function execution in gVisor is {abs(exec_diff):.1f}% faster than Docker")
            
            with tabs[2]:
                fig = px.bar(
                    df,
                    x="Runtime",
                    y="Total Time (ms)",
                    color="Runtime",
                    color_discrete_map={"Docker": "#3366CC", "gVisor": "#DC3912"},
                    title="Average Total Time Comparison"
                )
                fig.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    showlegend=False
                )
                
                # Add value labels on top of bars
                fig.update_traces(
                    text=[f"{val:.2f} ms" for val in df["Total Time (ms)"]],
                    textposition="outside"
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                if total_diff > 0:
                    st.info(f"💡 Overall, gVisor is {abs(total_diff):.1f}% slower than Docker for this function")
                else:
                    st.info(f"💡 Overall, gVisor is {abs(total_diff):.1f}% faster than Docker for this function")
            
            with tabs[3]:
                # Show detailed data across all iterations
                st.subheader("Detailed Results by Iteration")
                
                # Docker data table
                st.markdown("**Docker Runtime Details**")
                docker_details = pd.DataFrame({
                    "Iteration": list(range(1, iterations + 1)),
                    "Init Time (ms)": docker_stats["init_times_ms"],
                    "Execution Time (ms)": docker_stats["exec_times_ms"],
                    "Total Time (ms)": docker_stats["total_times_ms"]
                })
                st.dataframe(docker_details, use_container_width=True)
                
                # gVisor data table
                st.markdown("**gVisor Runtime Details**")
                gvisor_details = pd.DataFrame({
                    "Iteration": list(range(1, iterations + 1)),
                    "Init Time (ms)": gvisor_stats["init_times_ms"],
                    "Execution Time (ms)": gvisor_stats["exec_times_ms"],
                    "Total Time (ms)": gvisor_stats["total_times_ms"]
                })
                st.dataframe(gvisor_details, use_container_width=True)
                
                # Raw JSON data
                with st.expander("View Raw JSON Data"):
                    st.json(comparison_data)
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Additional tips section
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<h3>Runtime Selection Guide</h3>", unsafe_allow_html=True)
    st.markdown("""
    <p>When to choose each runtime environment:</p>
    <ul>
        <li><strong>Docker</strong>: Best for performance-critical functions where speed is the top priority.</li>
        <li><strong>gVisor</strong>: Recommended for functions that require enhanced security isolation and protection.</li>
    </ul>
    """, unsafe_allow_html=True)
    st.info("💡 Run this benchmark with your specific functions to determine which runtime provides the best balance of performance and security for your workloads.")
    st.markdown("</div>", unsafe_allow_html=True)

# Show selected page based on sidebar selection
selected_page = pages[page]
if selected_page == "Functions":
    show_functions_page()
elif selected_page == "Metrics":
    show_metrics_page()
elif selected_page == "Comparison":
    show_comparison_page()