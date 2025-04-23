# Cloud Functions Platform

A serverless platform that allows users to deploy and execute cloud functions in a safe and isolated environment.

## CI/CD Status

![CI Status](https://github.com/yourusername/CC_project/workflows/Cloud%20Functions%20Platform%20CI/badge.svg)
![CD Status](https://github.com/yourusername/CC_project/workflows/Cloud%20Functions%20Platform%20CD/badge.svg)

## Features

- Create, update, and delete cloud functions
- Deploy functions in Docker or gVisor containers
- Monitor function execution metrics
- Compare performance between different runtimes
- Web-based UI for function management

## Architecture

This project consists of three main components:

1. **Backend**: FastAPI server managing functions and execution requests
2. **Execution Engine**: Container-based execution environment (Docker/gVisor)
3. **Frontend**: Streamlit web application for function management and metrics visualization

## Development Setup

### Prerequisites

- Python 3.10+
- Docker
- gVisor (optional for enhanced security)

### Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/CC_project.git
cd CC_project
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up gVisor (optional):
```bash
python gvisor_setup.py
```

### Running the Application

1. Start the backend:
```bash
cd backend
uvicorn main:app --reload
```

2. Start the frontend:
```bash
cd frontend
streamlit run app.py
```

3. Access the application at http://localhost:8501

## Docker Deployment

To run the entire application in Docker:

```bash
docker-compose up -d
```

## Testing

Run tests with:

```bash
pytest --cov=backend --cov=frontend tests/
```

## CI/CD Pipeline

This project uses GitHub Actions for CI/CD:

- **CI Pipeline**: Automatically runs tests on push and pull requests
- **CD Pipeline**: Automatically deploys to the development environment when changes are pushed to main

## License

[MIT License](LICENSE)
