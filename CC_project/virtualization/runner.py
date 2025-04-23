# virtualization/runner.py
import docker
import time
import uuid
import os
import logging
import threading
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Container pools for warm starts
container_pools = {}
pool_lock = threading.Lock()
max_pool_size = 5
pool_expiry_seconds = 300  # 5 minutes

def get_image_for_language(language: str) -> str:
    """Return Docker image name for the specified language"""
    if language.lower() == "python":
        return "python:3.9-slim"
    elif language.lower() == "javascript" or language.lower() == "js":
        return "node:16-alpine"
    else:
        raise ValueError(f"Unsupported language: {language}")

def initialize_container_pool(language: str) -> None:
    """Initialize a container pool for the specified language"""
    image = get_image_for_language(language)
    pool_key = f"{language}_pool"
    
    with pool_lock:
        if pool_key not in container_pools:
            container_pools[pool_key] = {
                "containers": [],
                "last_accessed": time.time()
            }
    
    # Warm up the pool with initial containers
    for _ in range(2):  # Start with 2 containers
        add_container_to_pool(language, image)

def add_container_to_pool(language: str, image: str) -> None:
    """Add a new container to the pool"""
    pool_key = f"{language}_pool"
    client = docker.from_env()
    
    try:
        # Create a new container that stays alive
        container_name = f"function-{language}-{str(uuid.uuid4())[:8]}"
        container = client.containers.run(
            image,
            command="sleep infinity",  # Keep container running
            detach=True,
            name=container_name,
            remove=True,
            working_dir="/app"
        )
        
        with pool_lock:
            if pool_key in container_pools:
                # Add to pool if we're under max size
                if len(container_pools[pool_key]["containers"]) < max_pool_size:
                    container_pools[pool_key]["containers"].append({
                        "container": container,
                        "created_at": time.time(),
                        "id": container.id
                    })
                    container_pools[pool_key]["last_accessed"] = time.time()
                    logger.info(f"Added container {container_name} to {language} pool")
                else:
                    # Pool full, stop this container
                    container.stop(timeout=1)
    except Exception as e:
        logger.error(f"Error adding container to pool: {str(e)}")

def get_container_from_pool(language: str) -> Optional[docker.models.containers.Container]:
    """Get an available container from the pool or None if none available"""
    pool_key = f"{language}_pool"
    
    with pool_lock:
        if pool_key not in container_pools or not container_pools[pool_key]["containers"]:
            return None
        
        container_data = container_pools[pool_key]["containers"].pop(0)
        container_pools[pool_key]["last_accessed"] = time.time()
        
        # Schedule adding a replacement container
        threading.Thread(target=add_container_to_pool, 
                         args=(language, get_image_for_language(language))).start()
        
        return container_data["container"]

def clean_expired_pools() -> None:
    """Clean up expired container pools"""
    current_time = time.time()
    
    with pool_lock:
        to_remove = []
        
        for pool_key, pool_data in container_pools.items():
            # Check if pool has expired
            if current_time - pool_data["last_accessed"] > pool_expiry_seconds:
                # Stop all containers in this pool
                for container_data in pool_data["containers"]:
                    try:
                        container_data["container"].stop(timeout=1)
                        logger.info(f"Stopped expired container {container_data['id']}")
                    except Exception as e:
                        logger.error(f"Error stopping container: {str(e)}")
                
                to_remove.append(pool_key)
        
        # Remove expired pools
        for pool_key in to_remove:
            del container_pools[pool_key]
            logger.info(f"Removed expired pool: {pool_key}")

# Start a background thread to clean expired pools
def start_cleanup_thread():
    def cleanup_task():
        while True:
            time.sleep(60)  # Check every minute
            clean_expired_pools()
    
    cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
    cleanup_thread.start()

# Start the cleanup thread
start_cleanup_thread()

def run_in_docker(code: str, language: str, timeout: int = 30, warm: bool = True) -> Dict[str, Any]:
    """Execute code in a Docker container with specified timeout"""
    start_time = time.time()
    client = docker.from_env()
    container = None
    
    # Metrics to collect
    metrics = {
        'start_time': start_time,
        'runtime': 'docker',
        'language': language,
        'execution_time_ms': 0,
        'initialization_time_ms': 0,
        'total_time_ms': 0,
        'warm_start': warm,
        'error': None
    }
    
    try:
        # Choose whether to use the pool based on warm parameter
        if warm:
            # Try to get a container from the pool
            container = get_container_from_pool(language)
            if not container:
                # Initialize pool if it doesn't exist
                initialize_container_pool(language)
                
                # Create new container since pool was empty
                image = get_image_for_language(language)
                container_name = f"function-{language}-{str(uuid.uuid4())[:8]}"
                container = client.containers.run(
                    image,
                    command="sleep infinity",  # Keep container running
                    detach=True,
                    name=container_name,
                    remove=True,
                    working_dir="/app"
                )
        else:
            # Create new container for cold start
            image = get_image_for_language(language)
            container_name = f"function-{language}-{str(uuid.uuid4())[:8]}"
            container = client.containers.run(
                image,
                command="sleep infinity",  # Keep container running
                detach=True,
                name=container_name,
                remove=True,
                working_dir="/app"
            )
        
        # Calculate initialization time
        init_end_time = time.time()
        metrics['initialization_time_ms'] = int((init_end_time - start_time) * 1000)
        
        # Prepare the code for execution
        execution_id = str(uuid.uuid4())
        if language.lower() == "python":
            filename = f"/tmp/function_{execution_id}.py"
            exec_cmd = f"python /app/function_{execution_id}.py"
            
            # Write the code to a file in the container
            with open(filename, "w") as f:
                f.write(code)
            
            # Copy the file to the container
            os.system(f"docker cp {filename} {container.id}:/app/function_{execution_id}.py")
            
            # Clean up the local file
            os.remove(filename)
            
        elif language.lower() == "javascript" or language.lower() == "js":
            filename = f"/tmp/function_{execution_id}.js"
            exec_cmd = f"node /app/function_{execution_id}.js"
            
            # Write the code to a file
            with open(filename, "w") as f:
                f.write(code)
            
            # Copy the file to the container
            os.system(f"docker cp {filename} {container.id}:/app/function_{execution_id}.js")
            
            # Clean up the local file
            os.remove(filename)
        
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
        
        # Return container to pool if using warm start
        if warm and not warm or warm and execution_time < timeout and exit_code == 0:
            # Only clean up the created file, don't stop the container
            container.exec_run(f"rm -f /app/function_{execution_id}.*")
            
            # Add container back to pool - we create a new container in get_container_from_pool
            # This avoids potential issues with reusing the same container
            pass
        else:
            # Stop the container for cold starts or if there was an error
            container.stop(timeout=1)
        
        # Include metrics in the result
        result['metrics'] = metrics
        return result
        
    except Exception as e:
        # Clean up container if there was an error and we created one
        if container and not warm:
            try:
                container.stop(timeout=1)
            except:
                pass
        
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
