# backend/metrics.py
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
from datetime import datetime
import json
import statistics
from typing import Dict, List, Any, Optional

from .database import Base, engine, SessionLocal

# Metrics model definition
class ExecutionMetric(Base):
    __tablename__ = "execution_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    function_name = Column(String, index=True)
    runtime = Column(String, index=True)  # docker or gvisor
    language = Column(String, index=True)
    cold_start = Column(Boolean, default=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    initialization_time_ms = Column(Integer)
    execution_time_ms = Column(Integer)
    total_time_ms = Column(Integer)
    status = Column(String)  # success, error, timeout
    error_message = Column(String, nullable=True)
    memory_usage_mb = Column(Float, nullable=True)  # Nullable for now as we don't collect this yet
    cpu_usage_percent = Column(Float, nullable=True)  # Nullable for now as we don't collect this yet

def save_execution_metrics(db, function_name: str, result: Dict[str, Any]) -> None:
    """Save execution metrics to the database"""
    if 'metrics' not in result:
        return
    
    metrics = result['metrics']
    
    # Create new metric record
    execution_metric = ExecutionMetric(
        function_name=function_name,
        runtime=metrics.get('runtime', 'docker'),
        language=metrics.get('language', 'unknown'),
        cold_start=metrics.get('cold_start', True),
        initialization_time_ms=metrics.get('initialization_time_ms', 0),
        execution_time_ms=metrics.get('execution_time_ms', 0),
        total_time_ms=metrics.get('total_time_ms', 0),
        status=result.get('status', 'unknown'),
        error_message=metrics.get('error', None),
    )
    
    # Add and commit to database
    db.add(execution_metric)
    db.commit()

def get_metrics_for_function(db, function_name: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Get recent metrics for a specific function"""
    metrics = db.query(ExecutionMetric).filter(
        ExecutionMetric.function_name == function_name
    ).order_by(ExecutionMetric.timestamp.desc()).limit(limit).all()
    
    return [
        {
            "id": m.id,
            "function_name": m.function_name,
            "runtime": m.runtime,
            "language": m.language,
            "cold_start": m.cold_start,
            "timestamp": m.timestamp.isoformat(),
            "initialization_time_ms": m.initialization_time_ms,
            "execution_time_ms": m.execution_time_ms, 
            "total_time_ms": m.total_time_ms,
            "status": m.status,
            "error_message": m.error_message
        }
        for m in metrics
    ]

def get_aggregated_metrics(db, function_name: Optional[str] = None, 
                          time_range: str = "24h") -> Dict[str, Any]:
    """Get aggregated metrics for the system or a specific function"""
    query = db.query(ExecutionMetric)
    
    # Filter by function name if provided
    if function_name:
        query = query.filter(ExecutionMetric.function_name == function_name)
    
    # Filter by time range
    if time_range == "1h":
        query = query.filter(ExecutionMetric.timestamp >= func.datetime('now', '-1 hour'))
    elif time_range == "24h":
        query = query.filter(ExecutionMetric.timestamp >= func.datetime('now', '-1 day'))
    elif time_range == "7d":
        query = query.filter(ExecutionMetric.timestamp >= func.datetime('now', '-7 days'))
    elif time_range == "30d":
        query = query.filter(ExecutionMetric.timestamp >= func.datetime('now', '-30 days'))
    
    metrics = query.all()
    
    if not metrics:
        return {
            "count": 0,
            "avg_execution_time_ms": 0,
            "avg_total_time_ms": 0,
            "success_rate": 0,
            "error_rate": 0,
            "timeout_rate": 0,
            "cold_start_percentage": 0
        }
    
    # Calculate aggregates
    total_count = len(metrics)
    success_count = sum(1 for m in metrics if m.status == "success")
    error_count = sum(1 for m in metrics if m.status == "error")
    timeout_count = sum(1 for m in metrics if m.status == "timeout")
    cold_start_count = sum(1 for m in metrics if m.cold_start)
    
    execution_times = [m.execution_time_ms for m in metrics if m.execution_time_ms is not None]
    total_times = [m.total_time_ms for m in metrics if m.total_time_ms is not None]
    
    # Compute statistics
    avg_execution_time = statistics.mean(execution_times) if execution_times else 0
    avg_total_time = statistics.mean(total_times) if total_times else 0
    
    # Additional statistics if we have enough data
    if len(execution_times) >= 2:
        p95_execution_time = sorted(execution_times)[int(len(execution_times) * 0.95)]
        p99_execution_time = sorted(execution_times)[int(len(execution_times) * 0.99)]
        stdev_execution_time = statistics.stdev(execution_times)
    else:
        p95_execution_time = avg_execution_time
        p99_execution_time = avg_execution_time
        stdev_execution_time = 0
    
    return {
        "count": total_count,
        "avg_execution_time_ms": avg_execution_time,
        "p95_execution_time_ms": p95_execution_time if len(execution_times) >= 2 else None,
        "p99_execution_time_ms": p99_execution_time if len(execution_times) >= 2 else None,
        "stdev_execution_time_ms": stdev_execution_time if len(execution_times) >= 2 else None,
        "avg_total_time_ms": avg_total_time,
        "success_rate": success_count / total_count if total_count > 0 else 0,
        "error_rate": error_count / total_count if total_count > 0 else 0,
        "timeout_rate": timeout_count / total_count if total_count > 0 else 0,
        "cold_start_percentage": cold_start_count / total_count if total_count > 0 else 0,
        "runtime_breakdown": {
            "docker": sum(1 for m in metrics if m.runtime == "docker"),
            "gvisor": sum(1 for m in metrics if m.runtime == "gvisor")
        }
    }

# Create tables if they don't exist
def create_metrics_tables():
    Base.metadata.create_all(bind=engine)
