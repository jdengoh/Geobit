# GeoBit Backend

## Table of Content

- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Create a Virtual Environment](#create-a-virtual-environment)
- [Running the App](#running-the-app)
  - [Running with Docker](#running-with-docker)
  - [Running with Uvicorn (script)](#running-with-uvicorn-script)
  - [Running with Uvicorn (manual)](#running-with-uvicorn-manually)
- [Project Structure](#project-structure)
- [Development](#development)

## Getting Started <a id="getting-started"></a>

### Prerequisites <a id="prerequisites"></a>

- [Python 3.13 or higher](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package and project manager

### Create a Virtual Environment <a id="create-a-virtual-environment"></a>

This projects uses `uv` as our python package and project manager.

Create the venv:

```sh
uv venv
```

Activate the venv.

On macOS or Linux, run:

```sh
source .venv/bin/activate
```

On Windows, run:

```powershell
.venv/Scripts/activate
```

Install project dependencies:

```sh
uv sync
```

## Running the App <a id="running-the-app"></a>

### Running with Docker <a id="running-with-docker"></a>

Run the following scripts to run the app in a docker container:

On macOS or Linux, run:

```sh
./scripts/start_docker.sh

```

On Windows, run:

```ps1
./scripts/start_docker.ps1

```

### Running with Uvicorn (script) <a id="running-with-uvicorn-script"></a>

Run the following scripts to run the app with uvicorn:

On macOS or Linux, run:

```sh
./scripts/start.sh

```

On Windows, run:

TODO.

### Running with Uvicorn (manual) <a id="running-with-uvicorn-manual"></a>

Run the following command to run the app with uvicorn:

```sh
uvicorn app.backend.main:app --host 127.0.0.1 --port 8000 --reload
```

## Project Structure <a id="project-structure"></a>

TODO.

## Development <a id="development"></a>

TODO.
