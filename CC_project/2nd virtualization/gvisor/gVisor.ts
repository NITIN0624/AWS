// src/services/GVisorExecutionEngine.ts

import Docker from 'dockerode';
import fs from 'fs';
import path from 'path';
import { promisify } from 'util';
import tar from 'tar-fs';

const writeFile = promisify(fs.writeFile);
const mkdir = promisify(fs.mkdir);

// Define types
interface FunctionData {
  name: string;
  language: 'javascript' | 'python';
  code: string;
  virtualizationType: string;
  route: string;
  timeout?: number;
}

interface ContainerInfo {
  id: string;
  name: string;
  container: Docker.Container;
  lastUsed: number;
}

interface ExecutionResult {
  success: boolean;
  result?: any;
  error?: string;
  output?: string;
  stack?: string;
  executionTime?: number;
  containerId?: string;
}

class GVisorExecutionEngine {
  private docker: Docker;
  private containers: Map<string, ContainerInfo>;
  private workspaceDir: string;
  private idleTimeout: number;
  private cleanupInterval: NodeJS.Timeout;
  private runtimeName: string;

  constructor() {
    // Initialize Docker client
    console.log("Docker path");
    this.docker = new Docker();
    this.containers = new Map<string, ContainerInfo>(); // Map to track running containers
    this.workspaceDir = path.join(process.cwd(), 'workspaces');
    this.idleTimeout = 5 * 60 * 1000; // 5 minutes in milliseconds
    this.runtimeName = 'runsc';
    
    // Ensure workspace directory exists
    if (!fs.existsSync(this.workspaceDir)) {
      fs.mkdirSync(this.workspaceDir, { recursive: true });
    }
    
    this.loadExistingContainers();
    this.cleanupInterval = setInterval(() => this.cleanupIdleContainers(), 60 * 1000); // Check every minute
    
    console.log('gVisor Execution Engine initialized');
    this.checkGVisorRuntime();
  }
  

  private async checkGVisorRuntime(): Promise<void> {
    try {
      const info = await this.docker.info();
      const runtimes = info.Runtimes || {};
      
      if (!runtimes[this.runtimeName]) {
        console.warn(`WARNING: gVisor runtime '${this.runtimeName}' not found in Docker. Functions will run with the default runtime. Install gVisor for better isolation.`);
      } else {
        console.log(`gVisor runtime '${this.runtimeName}' is available.`);
      }
    } catch (error) {
      console.error('Error checking Docker info:', error);
    }
  }
  
  /**
   * Check if a container exists for the given route
   */
  async checkContainer(route: string): Promise<boolean> {
    if (!this.containers.has(route)) {
      return false;
    }
    
    const containerInfo = this.containers.get(route)!;
    
    try {
      const container = this.docker.getContainer(containerInfo.id);
      const data = await container.inspect();
      return data.State.Running;
    } catch (error) {
      // Container doesn't exist or can't be inspected
      this.containers.delete(route);
      return false;
    }
  }

  private async loadExistingContainers(): Promise<void> {
    try {
      const containers = await this.docker.listContainers({ all: true });
      console.log("containers ",containers) // List all running containers
      for (const containerInfo of containers) {
        // Only load containers that were created by this engine (check for our naming convention)
        if (containerInfo.Names.some(name => name.includes('lambda-'))) {
          const container = this.docker.getContainer(containerInfo.Id);
          
          // Try to determine the route from container labels or name
          let route = '';
          try {
            const inspectData = await container.inspect();
            console.log("inspect data: ",inspectData)
            route = inspectData.Config.Labels?.route || '';
          } catch (inspectError) {
            console.warn(`Could not inspect container ${containerInfo.Id}:`, inspectError);
          }
          
          if (route) {
            this.containers.set(route, {
              id: containerInfo.Id,
              name: containerInfo.Names[0] || containerInfo.Id,
              container: container,
              lastUsed: Date.now(),
            });
          }
        }
      }
      console.log(`Loaded ${this.containers.size} existing containers.`);
    } catch (error) {
      console.error('Error loading existing containers:', error);
    }
  }

  
  /**
   * Start a container for the given function
   */
  async startContainer(functionData: FunctionData): Promise<string> {
    const { name, language, code, route,virtualizationType } = functionData;
  
    // Sanitize container name
    const containerName = `lambda-${name.replace(/[^a-zA-Z0-9-_]/g, '-')}`;
    const image = language === 'javascript' ? 'lambda-nodejs' : 'lambda-python';
  
    try {
      await this.docker.getImage(image).inspect();
    } catch {
      console.log(`Image ${image} not found, building it...`);
      await this.buildRuntimeImage(language);
    }
  
    // Create and start the container with gVisor runtime
    const container = await this.docker.createContainer({
      name: containerName,
      Image: image,
      Tty: true,
      Cmd: ['/bin/sh', '-c', 'while true; do sleep 1; done'],
      Labels: {
        'managed-by': 'lambda-platform',
        'route': route
      },
      HostConfig: {
        Memory: 128 * 1024 * 1024, // 128MB
        NanoCpus: 250000000, // 0.25 CPU
        Runtime:virtualizationType=='microvm'?this.runtimeName:'runc'
      }
    });
  
    await container.start();
    
    try {
      // Create function directory
      await this.runExec(container, ['mkdir', '-p', '/app/function']);
  
      // Ensure correct execution environment
      let functionFile = '';
      if (language === 'javascript') {
        functionFile = 'function.js';
      } else if (language === 'python') {
        functionFile = 'function.py';
      } else {
        throw new Error(`Unsupported language: ${language}`);
      }
  
      // Use printf instead of echo for better reliability
      const sanitizedCode = code.replace(/'/g, "'\\''");
      await this.runExec(container, [
        'sh', '-c', `printf '%s' '${sanitizedCode}' > /app/function/${functionFile}`
      ]);
  
      // Ensure file permissions are correct
      await this.runExec(container, ['chmod', '644', `/app/function/${functionFile}`]);
  
      // Verify the file was written
      const lsOutput = await this.runExec(container, ['ls', '-la', '/app/function']);
      console.log(`Files in /app/function: ${lsOutput}`);
  
      if (language === 'javascript') {
        const packageJson = {
          name: `function-${name}`,
          version: '1.0.0',
          main: 'function.js'
        };
  
        await this.runExec(container, [
          'sh', '-c', `printf '%s' '${JSON.stringify(packageJson, null, 2).replace(/'/g, "'\\''")}' > /app/function/package.json`
        ]);
      }
  
      // Store container info
      this.containers.set(route, {
        id: container.id,
        name: containerName,
        container,
        lastUsed: Date.now()
      });
  
      console.log(`Container ${container.id} started for route ${route} using gVisor runtime`);
      return container.id;
  
    } catch (error) {
      console.error(`Error setting up container: ${error}`);
      await this.cleanupContainer(container);
      throw error;
    }
  }
  
  // Helper function to execute commands inside the container
  private async runExec(container: any, cmd: string[]): Promise<string> {
    try {
      const exec = await container.exec({
        Cmd: cmd,
        AttachStdout: true,
        AttachStderr: true
      });
      
      const stream = await exec.start({});
      return await this.streamToString(stream);
    } catch (error) {
      console.error(`Error executing command ${cmd.join(' ')}: ${error}`);
      throw error;
    }
  }
  
  // Helper function to cleanup container on error
  private async cleanupContainer(container: any) {
    try {
      await container.stop();
      await container.remove();
    } catch (cleanupError) {
      console.error(`Error cleaning up container: ${cleanupError}`);
    }
  }
  
  // Helper function to convert a Docker stream to string output
  private async streamToString(stream: any): Promise<string> {
    return new Promise((resolve, reject) => {
      let output = '';
      stream.on('data', (chunk: Buffer) => output += chunk.toString());
      stream.on('end', () => resolve(output.trim()));
      stream.on('error', reject);
    });
  }
  
  
  /**
   * Build runtime images for our functions
   */
  async buildRuntimeImage(language: 'javascript' | 'python'): Promise<void> {
    // Create temp build directory
    const buildDir = path.join(this.workspaceDir, `build-${language}`);
    if (!fs.existsSync(buildDir)) {
      await mkdir(buildDir, { recursive: true });
    }
    
    // Create Dockerfile based on language
    let dockerfileContent: string;
    if (language === 'javascript') {
      dockerfileContent = `FROM node:16-alpine
WORKDIR /app
RUN npm install -g express axios
COPY ./runner.js /app/runner.js
CMD ["node", "/app/runner.js"]`;
      
      // Create runner.js
      const runnerJs = `
const fs = require('fs');
const path = require('path');

async function runFunction(input) {
  try {
    // Load the function
    const functionPath = '/app/function/function.js';
    if (!fs.existsSync(functionPath)) {
      throw new Error('Function file not found');
    }
    
    // Clear require cache to ensure we get fresh code
    delete require.cache[require.resolve(functionPath)];
    
    // Import the function
    const fn = require(functionPath);
    
    if (typeof fn.handler !== 'function') {
      throw new Error("Function must export a 'handler' function");
    }
    
    // Execute function
    return await fn.handler(input);
  } catch (error) {
    return {
      error: error.message,
      stack: error.stack
    };
  }
}

// This file is used by the container to execute functions
// It's not directly exposed to the API but used internally
process.on('message', async (message) => {
  try {
    const result = await runFunction(message.input);
    process.send({ success: true, result });
  } catch (error) {
    process.send({ 
      success: false, 
      error: error.message,
      stack: error.stack
    });
  }
});`;
      
      await writeFile(path.join(buildDir, 'runner.js'), runnerJs);
    } else if (language === 'python') {
      dockerfileContent = `FROM python:3.9-slim
WORKDIR /app
RUN pip install --no-cache-dir flask requests numpy pandas
COPY ./runner.py /app/runner.py
CMD ["python", "/app/runner.py"]`;
      
      // Create runner.py
      const runnerPy = `
import sys
import json
import importlib.util
import traceback

def run_function(input_data):
    try:
        # Load the function dynamically
        spec = importlib.util.spec_from_file_location("function", "/app/function/function.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        if not hasattr(module, "handler"):
            raise Exception("Function must define a 'handler' function")
        
        # Execute function
        result = module.handler(input_data)
        return result
    except Exception as e:
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }

# This file is used by the container to execute functions
# It's not directly exposed to the API but used internally
if __name__ == "__main__":
    import sys
    import os
    import json
    
    # Keep this process running and listen for execution commands
    while True:
        try:
            # This process will be invoked by the Docker engine
            # Input will be passed via stdin or environment variables
            pass
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            sys.exit(1)`;
      
      await writeFile(path.join(buildDir, 'runner.py'), runnerPy);
    } else {
      throw new Error(`Unsupported language: ${language}`);
    }
    
    await writeFile(path.join(buildDir, 'Dockerfile'), dockerfileContent);
    
    // Create tar stream for Docker build context
    const tarStream = tar.pack(buildDir);
    
    // Build the Docker image
    await new Promise<void>((resolve, reject) => {
      this.docker.buildImage(tarStream, {
        t: language === 'javascript' ? 'lambda-nodejs' : 'lambda-python'
      }, (err, stream) => {
        if (err) return reject(err);
        
        // Track build progress
        this.docker.modem.followProgress(stream as NodeJS.ReadableStream, (err, res) => {
          if (err) return reject(err);
          resolve();
        }, (event: any) => {
          if (event.stream) {
            process.stdout.write(event.stream);
          }
        });
      });
    });
    
    console.log(`Built ${language} runtime image`);
  }
  
  /**
   * Execute a function in its container
   */
// Fixed JavaScript execution function
async executeFunction(functionData: FunctionData, input: any = {}): Promise<ExecutionResult> {
  const { route } = functionData;
  let containerId: string | undefined;
  
  try {
    // Check if container exists
    const containerExists = await this.checkContainer(route);
    
    if (containerExists) {
      // Use existing container
      containerId = this.containers.get(route)!.id;
      console.log(`Using existing container ${containerId} for route ${route}`);
    } else {
      // Start new container
      containerId = await this.startContainer(functionData);
    }
    
    const container = this.docker.getContainer(containerId);
    
    // Execute function in container
    console.log(`Executing function in container ${containerId} (gVisor)`);
    const startTime = Date.now();
    
    let execResult;
    if (functionData.language === 'javascript') {
      // Create a safe JSON string to pass to the execution environment
      const safeInputJSON = JSON.stringify(input).replace(/'/g, "\\'").replace(/\\"/g, '\\\\"');
      
      // Run JavaScript function - FIXED version
      execResult = await container.exec({
        Cmd: ['node', '-e', `
          const fs = require('fs');
          const fnModule = require('/app/function/function.js');
        
          const input = ${JSON.stringify(input)};
          const event = {
            ...input,
            body: input,
            query: {},
            headers: {},
            path: {},
            context: {
              executionId: "${Date.now()}",
              functionName: "${functionData.name}",
              timestamp: ${Date.now()},
              deadline: ${Date.now() + (functionData.timeout || 30000)}
            }
          };
        
          (async () => {
            try {
              const result = await (fnModule.default || fnModule).handler(event);
              const output = JSON.stringify({ success: true, result });
              process.stdout.write(output); // flush explicitly
            } catch (err) {
              const errorOutput = JSON.stringify({
                success: false,
                error: err.message,
                stack: err.stack
              });
              process.stderr.write(errorOutput);
            }
          })();
        `],
        AttachStdout: true,
        AttachStderr: true
      });
    } else if (functionData.language === 'python') {
      // Python execution remains unchanged
      execResult = await container.exec({
        Cmd: ['python', '-c', `
import sys
import json
import importlib.util
import traceback

try:
  # Load the function dynamically
  spec = importlib.util.spec_from_file_location("function", "/app/function/function.py")
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  
  if not hasattr(module, "handler"):
      raise Exception("Function must define a 'handler' function")
  
  # Prepare the event object with various input sources
  raw_input = json.loads('${JSON.stringify(input).replace(/'/g, "\\'")}')
  event = {
      **raw_input,
      "body": raw_input,
      "query": {},
      "headers": {},
      "path": {},
      "context": {
          "executionId": "${Date.now()}",
          "functionName": "${functionData.name}",
          "timestamp": ${Date.now()},
          "deadline": ${Date.now() + (functionData.timeout || 30000)}
      }
  }
  
  # Execute function
  result = module.handler(event)
  print(json.dumps({ "success": True, "result": result }))
except Exception as e:
  print(json.dumps({ 
      "success": False, 
      "error": str(e),
      "traceback": traceback.format_exc()
  }))
        `],
        AttachStdout: true,
        AttachStderr: true
      });
    } else {
      throw new Error(`Unsupported language: ${functionData.language}`);
    }
    
    // Start execution and collect output
    const exec = await execResult.start({});
    let output = '';
    
    await new Promise((resolve) => {
      exec.on('data', (chunk: Buffer) => {
        output += chunk.toString();
      });
      
      exec.on('end', resolve);
    });
    
    const executionTime = Date.now() - startTime;
    
    // Update last used time
    const containerInfo = this.containers.get(route)!;
    containerInfo.lastUsed = Date.now();
    this.containers.set(route, containerInfo);
    
    // Parse output
    console.log(`Function output: ${output}`);
    let result: ExecutionResult;
    try {
      // Find JSON in the output
      const jsonMatch = output.match(/(\{.*\})/s);
      if (jsonMatch) {
        result = JSON.parse(jsonMatch[1]);
      } else {
        result = { success: true, output };
      }
    } catch (error) {
      result = { 
        success: false, 
        output, 
        error: 'Failed to parse function output' 
      };
    }
    
    return {
      ...result,
      executionTime,
      containerId
    };
  } catch (error: any) {
    console.error(`Error executing function for route ${route}:`, error);
    
    return {
      success: false,
      error: error.message,
      containerId
    };
  }
}

  
  /**
   * Clean up containers that have been idle for too long
   */
  async cleanupIdleContainers(): Promise<void> {
    console.log('Checking for idle containers...');
    const now = Date.now();
    
    for (const [route, containerInfo] of this.containers.entries()) {
      const idleTime = now - containerInfo.lastUsed;
      
      if (idleTime > this.idleTimeout) {
        console.log(`Container ${containerInfo.id} for route ${route} idle for ${idleTime}ms, removing...`);
        
        try {
          const container = this.docker.getContainer(containerInfo.id);
          await container.stop();
          await container.remove();
          this.containers.delete(route);
          console.log(`Removed idle container ${containerInfo.id}`);
        } catch (error) {
          console.error(`Error removing container ${containerInfo.id}:`, error);
        }
      }
    }
  }
  
  /**
   * Clean up all containers managed by this engine
   */
  async cleanupAllContainers(): Promise<void> {
    console.log('Cleaning up all containers...');
    
    const promises: Promise<void>[] = [];
    for (const [route, containerInfo] of this.containers.entries()) {
      console.log(`Removing container ${containerInfo.id} for route ${route}`);
      
      const promise = (async () => {
        try {
          const container = this.docker.getContainer(containerInfo.id);
          await container.stop();
          await container.remove();
          console.log(`Removed container ${containerInfo.id}`);
        } catch (error) {
          console.error(`Error removing container ${containerInfo.id}:`, error);
        }
      })();
      
      promises.push(promise);
    }
    
    await Promise.all(promises);
    this.containers.clear();
    
    // Clear the cleanup interval
    clearInterval(this.cleanupInterval);
    
    console.log('All containers removed');
  }


  async deleteContainer(name: string): Promise<void> {
    const containerName = `lambda-${name.replace(/[^a-zA-Z0-9-_]/g, '-')}`;
    try {
      console.log(`Attempting to delete container: ${containerName}`);
      const containers = await this.docker.listContainers({ all: true });
      const targetContainer = containers.find(container => {
        return container.Names.some(name => name === `/${containerName}` || name === containerName);
      });
      
      if (!targetContainer) {
        console.log(`Container ${containerName} not found`);
        return;
      }
      
      const container = this.docker.getContainer(targetContainer.Id);
      
      const containerInfo = await container.inspect();
      if (containerInfo.State.Running) {
        console.log(`Stopping container ${containerName}`);
        await container.stop();
      }
      
      console.log(`Removing container ${containerName}`);
      await container.remove();
      for (const [route, info] of this.containers.entries()) {
        if (info.name === containerName || info.id === targetContainer.Id) {
          this.containers.delete(route);
          console.log(`Removed container ${containerName} from tracking map`);
          break;
        }
      }
      
      console.log(`Container ${containerName} deleted successfully`);
    } catch (error) {
      console.error(`Error deleting container ${containerName}:`, error);
      throw error;
    }
  }
}

export default new GVisorExecutionEngine();