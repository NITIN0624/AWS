from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
import logging
import statistics
# Just testing CI/CD trigger 🚀


from backend.database import Function, SessionLocal, create_tables
from backend.metrics import ExecutionMetric, save_execution_metrics, get_metrics_for_function, get_aggregated_metrics, create_metrics_tables

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Serverless Function Platform")

# Initialize database tables
create_tables()
create_metrics_tables()

class FunctionCreate(BaseModel):
    name: str
    language: str
    code: str
    timeout: int

class FunctionExecuteParams(BaseModel):
    runtime: Optional[str] = "docker"  # docker or gvisor
    warm_start: Optional[bool] = True  # Use container pool if true

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/functions/")
async def create_function(func: FunctionCreate, db: Session = Depends(get_db)):
    db_func = Function(**func.dict())
    try:
        db.add(db_func)
        db.commit()
        db.refresh(db_func)
        return {"message": "Function saved"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/functions/")
async def list_functions(db: Session = Depends(get_db)):
    functions = db.query(Function).all()
    return functions

@app.get("/functions/{name}")
async def get_function(name: str, db: Session = Depends(get_db)):
    func = db.query(Function).filter(Function.name == name).first()
    if not func:
        raise HTTPException(status_code=404, detail="Function not found")
    return func

@app.put("/functions/{name}")
async def update_function(name: str, updated: FunctionCreate, db: Session = Depends(get_db)):
    func = db.query(Function).filter(Function.name == name).first()
    if not func:
        raise HTTPException(status_code=404, detail="Function not found")
    for field, value in updated.dict().items():
        setattr(func, field, value)
    db.commit()
    return {"message": "Function updated"}

@app.delete("/functions/{name}")
async def delete_function(name: str, db: Session = Depends(get_db)):
    func = db.query(Function).filter(Function.name == name).first()
    if not func:
        raise HTTPException(status_code=404, detail="Function not found")
    db.delete(func)
    db.commit()
    return {"message": "Function deleted"}
    
@app.post("/functions/execute/{name}")
async def execute_function(
    name: str, 
    params: FunctionExecuteParams = None,
    db: Session = Depends(get_db)
):
    # Set default params if not provided
    if params is None:
        params = FunctionExecuteParams()
    
    # Get the function from the database
    func = db.query(Function).filter(Function.name == name).first()
    if not func:
        raise HTTPException(status_code=404, detail="Function not found")
    
    try:
        # Execute based on selected runtime
        if params.runtime == "gvisor":
            # Import the gVisor runner and execute the function
            from virtualization.gvisor_runner import run_in_gvisor
            result = run_in_gvisor(func.code, func.language, func.timeout)
        else:
            # Import the Docker runner and execute the function
            from virtualization.runner import run_in_docker
            result = run_in_docker(func.code, func.language, func.timeout, params.warm_start)
        
        # Save metrics to database
        save_execution_metrics(db, name, result)
        
        # Return execution result to the client
        return {
            "function_name": name,
            "language": func.language,
            "runtime": params.runtime,
            "result": result
        }
    
    except Exception as e:
        logger.error(f"Error executing function {name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")

@app.get("/metrics/functions/{name}")
async def get_function_metrics(
    name: str,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    # Check if function exists
    func = db.query(Function).filter(Function.name == name).first()
    if not func:
        raise HTTPException(status_code=404, detail="Function not found")
    
    metrics = get_metrics_for_function(db, name, limit)
    return metrics

@app.get("/metrics/aggregated")
async def get_system_metrics(
    function_name: Optional[str] = None,
    time_range: str = Query("24h", regex="^(1h|24h|7d|30d)$"),
    db: Session = Depends(get_db)
):
    # If function name is provided, check if it exists
    if function_name:
        func = db.query(Function).filter(Function.name == function_name).first()
        if not func:
            raise HTTPException(status_code=404, detail="Function not found")
    
    aggregated = get_aggregated_metrics(db, function_name, time_range)
    return aggregated

@app.get("/runtime/compare")
async def compare_runtimes(
    function_name: str,
    iterations: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """Compare performance between Docker and gVisor runtimes for a function"""
    # Check if function exists
    func = db.query(Function).filter(Function.name == function_name).first()
    if not func:
        raise HTTPException(status_code=404, detail="Function not found")
    
    # Import runners
    from virtualization.runner import run_in_docker
    from virtualization.gvisor_runner import run_in_gvisor
    
    docker_results = []
    gvisor_results = []
    
    # Run the function multiple times with Docker
    for i in range(iterations):
        logger.info(f"Running Docker iteration {i+1}/{iterations}")
        result = run_in_docker(func.code, func.language, func.timeout, warm=(i > 0))
        docker_results.append(result)
        save_execution_metrics(db, function_name, result)
    
    # Run the function multiple times with gVisor
    for i in range(iterations):
        logger.info(f"Running gVisor iteration {i+1}/{iterations}")
        result = run_in_gvisor(func.code, func.language, func.timeout)
        gvisor_results.append(result)
        save_execution_metrics(db, function_name, result)
    
    # Extract metrics for analysis
    docker_init_times = [r['metrics']['initialization_time_ms'] for r in docker_results]
    docker_exec_times = [r['metrics']['execution_time_ms'] for r in docker_results]
    docker_total_times = [r['metrics']['total_time_ms'] for r in docker_results]
    
    gvisor_init_times = [r['metrics']['initialization_time_ms'] for r in gvisor_results]
    gvisor_exec_times = [r['metrics']['execution_time_ms'] for r in gvisor_results]
    gvisor_total_times = [r['metrics']['total_time_ms'] for r in gvisor_results]
    
    # Calculate statistics
    docker_stats = {
        "avg_init_time_ms": statistics.mean(docker_init_times),
        "avg_exec_time_ms": statistics.mean(docker_exec_times),
        "avg_total_time_ms": statistics.mean(docker_total_times),
        "min_total_time_ms": min(docker_total_times),
        "max_total_time_ms": max(docker_total_times),
        "success_rate": sum(1 for r in docker_results if r['status'] == 'success') / iterations
    }
    
    gvisor_stats = {
        "avg_init_time_ms": statistics.mean(gvisor_init_times),
        "avg_exec_time_ms": statistics.mean(gvisor_exec_times),
        "avg_total_time_ms": statistics.mean(gvisor_total_times),
        "min_total_time_ms": min(gvisor_total_times),
        "max_total_time_ms": max(gvisor_total_times),
        "success_rate": sum(1 for r in gvisor_results if r['status'] == 'success') / iterations
    }
    
    # Compare results
    comparison = {
        "iterations": iterations,
        "docker": docker_stats,
        "gvisor": gvisor_stats,
        "difference_percent": {
            "init_time": (gvisor_stats["avg_init_time_ms"] - docker_stats["avg_init_time_ms"]) / docker_stats["avg_init_time_ms"] * 100,
            "exec_time": (gvisor_stats["avg_exec_time_ms"] - docker_stats["avg_exec_time_ms"]) / docker_stats["avg_exec_time_ms"] * 100,
            "total_time": (gvisor_stats["avg_total_time_ms"] - docker_stats["avg_total_time_ms"]) / docker_stats["avg_total_time_ms"] * 100
        },
        "recommendation": "docker" if docker_stats["avg_total_time_ms"] < gvisor_stats["avg_total_time_ms"] else "gvisor"
    }
    
    return comparison
