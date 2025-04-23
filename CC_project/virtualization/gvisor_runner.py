# virtualization/gvisor_runner.py
import docker
import time
import uuid
import os
import json
import logging
from typing import Dict, List, Any, Optional
import io
import tarfile

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_image_for_language(language: str) -> str:
    """Return Docker image name for the specified language"""
    if language.lower() == "python":
        return "python:3.9-slim"
    elif language.lower() == "javascript" or language.lower() == "js":
        return "node:16-alpine"
    else:
        raise ValueError(f"Unsupported language: {language}")

def run_in_gvisor(code: str, language: str, timeout: int = 30) -> Dict[str, Any]:
    """Execute code in a Docker container with gVisor runtime and specified timeout"""
    start_time = time.time()
    client = docker.from_env()
    
    # Metrics to collect
    metrics = {
        'start_time': start_time,
        'runtime': 'gvisor',
        'language': language,
        'execution_time_ms': 0,
        'initialization_time_ms': 0,
        'total_time_ms': 0,
        'error': None
    }
    
    try:
        # Create new container with gVisor runtime
        image = get_image_for_language(language)
        container_name = f"gvisor-function-{str(uuid.uuid4())[:8]}"
        
        # Using gVisor runtime (runsc)
        container = client.containers.run(
            image,
            command="sleep infinity",  # Keep container running
            detach=True,
            name=container_name,
            remove=True,
            working_dir="/app",
            runtime="runsc"  # This is the key part - using gVisor's runsc runtime
        )
        
        # Calculate initialization time
        init_end_time = time.time()
        metrics['initialization_time_ms'] = int((init_end_time - start_time) * 1000)
        
        # Prepare the code for execution
        execution_id = str(uuid.uuid4())
        if language.lower() == "python":
            # Create a file in the /app directory of the container directly
            filename = f"function_{execution_id}.py"
            
            # Create a temporary file locally
            with open(f"/tmp/{filename}", "w") as f:
                f.write(code)
            
            # Copy the file to the container's /app directory
            os.system(f"docker cp /tmp/{filename} {container.id}:/app/")
            
            # Clean up the local temporary file
            os.remove(f"/tmp/{filename}")
            
            # Set the command to execute the file in the /app directory
            exec_cmd = f"python /app/{filename}"
            
        elif language.lower() == "javascript" or language.lower() == "js":
            # Create a file in the /app directory of the container directly
            filename = f"function_{execution_id}.js"
            
            # Create a temporary file locally
            with open(f"/tmp/{filename}", "w") as f:
                f.write(code)
            
            # Copy the file to the container's /app directory
            os.system(f"docker cp /tmp/{filename} {container.id}:/app/")
            
            # Clean up the local temporary file
            os.remove(f"/tmp/{filename}")
            
            # Set the command to execute the file in the /app directory
            exec_cmd = f"node /app/{filename}"
        
        # Execute the code with timeout
        exec_start_time = time.time()
        exec_result = container.exec_run(
            exec_cmd,
            workdir="/app",
            demux=True,
            tty=True
        )
        
        # Process execution result
        exit_code = exec_result.exit_code
        if exec_result.output:
            stdout, stderr = exec_result.output
        else:
            stdout, stderr = b"", b""
        
        stdout = stdout.decode('utf-8') if stdout else ""
        stderr = stderr.decode('utf-8') if stderr else ""
        
        exec_end_time = time.time()
        execution_time = exec_end_time - exec_start_time
        metrics['execution_time_ms'] = int(execution_time * 1000)
        
        # Check if execution exceeded timeout
        if execution_time > timeout:
            result = {
                "status": "timeout",
                "stdout": stdout,
                "stderr": f"Function execution timed out after {timeout} seconds",
                "exit_code": -1
            }
            metrics['error'] = "timeout"
        else:
            result = {
                "status": "success" if exit_code == 0 else "error",
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code
            }
            if exit_code != 0:
                metrics['error'] = f"exit_code_{exit_code}"
        
        # Calculate total execution time
        end_time = time.time()
        metrics['total_time_ms'] = int((end_time - start_time) * 1000)
        
        # Stop the container
        container.stop(timeout=1)
        
        # Include metrics in the result
        result['metrics'] = metrics
        return result
        
    except Exception as e:
        end_time = time.time()
        metrics['total_time_ms'] = int((end_time - start_time) * 1000)
        metrics['error'] = str(e)
        
        return {
            "status": "error",
            "stdout": "",
            "stderr": f"Error executing function: {str(e)}",
            "exit_code": -1,
            "metrics": metrics
        }
