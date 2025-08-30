# GeoBit Backend

A modular, multi-agent FastAPI backend for geo-compliance and parental control feature analysis.

## Table of Content

- [Features](#features)

- [Project Structure](#project-structure)
  - [Folder Structure:](#folder-structure-)
  - [Agentic AI Structure](#agentic-ai-structure)
- [Setup](#setup)
- [API Endpoints](#api-endpoints)
- [Development](#development)
- [Docker](#docker)
- [Contributing](#contributing)
- [License](#license)
- [Usage Example](#usage-example)
- [Agent Pipeline Overview](#agent-pipeline-overview)

## Features

**Production-Ready Architecture**:

- **FastAPI** asynchronous backend with streaming endpoints
- **Singleton `agent_service`** initialized at application startup for optimal resource utilization
- **Stateful agent persistence** eliminates redundant initialization overhead
- **Dependency injection pattern** ensures consistent agent state across all API endpoints, as well as clean code practices
- **Lifespan management** with proper service initialization and cleanup lifecycle
- **Event-driven architecture** with comprehensive workflow state management

**Multi-Agent Pipeline**:

- Levarages multi-agent architecture with **OpenAI Agents SDK** integration for robust agent orchestration and tracing
- **Modular agent design** with clear separation of concerns and pluggable components

## Project Structure

### Folder Structure

```sh
app/
  api/            # FastAPI routers and endpoints
  agent/          # All agent logic and agent-specific schemas
  core/           # Core config, environment, logging
  database/       # Database models and enums
  schemas/        # Global schemas for API and cross-agent use
  services/       # Service layer (agent orchestration, auth, etc.)
  config/         # Logging and app config
scripts/          # Startup and utility scripts
Dockerfile        # Docker build
README.md         # This file
```

### Agentic AI Structure

```mermaid
---
config:
  layout: elk
---
flowchart TD
  %% === ORCHESTRATION & ENTRY ===
  subgraph ORCH["Orchestrator"]
    O["Start: Feature Spec (CSV or Quick-Add)"]
  end

  subgraph PS["Pre-Screener Agent"]
    P["LLM prescreen ⇒ acceptable | problematic | needs_review"]
  end

  subgraph JN["Jargon Agent"]
    J["Normalize acronyms & codenames → standardized name/description"]
  end

  %% === ANALYSIS CORE ===
  subgraph AP["Analysis Planner"]
    PL["Derive retrieval intents (queries + soft tags)"]
  end

  subgraph RA["Retrieval Agent"]
    RET["Execute planner intents → Evidence[]"]
    K["Web Search"]
    M["Legal KB / Docs (RAG)"]
  end

  subgraph SYN["Analysis Synthesizer"]
    S1["Evidence → findings + open_questions (blocking allowed)"]
  end

  subgraph REV["Reviewer Agent"]
    Rv["Decision + confidence + conditions + citations"]
  end

  subgraph SUM["Summarizer Agent"]
    Su["Format FEEnvelope (decision, justification, citations, UI)"]
  end

  %% === HITL GATE & LOOP ===
  E{"HITL Decision Gate (*TO IMPLEMENT*)"}
  N["Triggers:<br>• confidence < τ<br>• blocking questions<br>• high-risk jurisdiction<br>• contradictions"]
  H["Human Reviewer (rationale captured)"]

  %% --- Flows ---
  O --> PS
  PS -->|acceptable| JN
  PS -->|needs_review or problematic| E

  JN --> AP
  AP --> RA
  RA --> RET
  RET -.-> K & M
  RA --> SYN
  SYN --> REV
  REV --> E

  E -->|auto-approve| SUM
  E -->|needs human| H
  H --> Su
  H -. Update required .-> AP

  %% --- Styling & notes ---
  classDef agentStyle fill:#e1f5fe,stroke:#01579b,stroke-width:2px
  classDef serviceStyle fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
  classDef hitlStyle fill:#fff3e0,stroke:#e65100,stroke-width:2px

  class P,J,PL,RET,S1,Rv,Su agentStyle
  class K,M serviceStyle
  class E,N,H hitlStyle
```

## Getting Started <a id="getting-started"></a>

### Prerequisites <a id="prerequisites"></a>

- [Python 3.13 or higher](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package and project manager

### Create a Virtual Environment <a id="create-a-virtual-environment"></a>

This project uses `uv` as the Python package and project manager.

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

### .env Setup

Copy `.env.example` to `.env` in the project root and fill in all required API keys and settings (e.g., `OPENAI_API_KEY`, `SERPER_API_KEY`).
See the [Environment Variables](#environment-variables-env) section below for details.

## Running the App <a id="running-the-app"></a>

### Running with Docker <a id="running-with-docker"></a>

*NOTE: docker only runs for the backend, frontend has to be ran separately*

On macOS or Linux, run:

```sh
./scripts/start_docker.sh
```

On Windows, run:

```ps1
./scripts/start_docker.ps1
```

### Running with Uvicorn <a id="running-with-uvicorn-manual"></a>

Run the following command to run the app with Uvicorn:

```sh
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Environment Variables (.env)

Create a `.env` file in the respective project root with the following content:

```env
OPENAI_API_KEY=your-key
SERPER_API_KEY=your-key
MONGODB_URI=your-mongodb-uri
MONGODB_DB_NAME=geobit

FRONTEND_HOST=http://localhost:3000
BACKEND_CORS_ORIGINS=http://localhost:8000
```

```frontend env (inside compliance dashboard folder)
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

- Replace `your-key` with your actual API keys.
- These variables are required for both backend and frontend integration.
- Never commit your real `.env` file to version control.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/analyze/stream` | `POST` | Main streaming analysis endpoint that processes feature specifications through the multi-agent pipeline and returns real-time results in NDJSON format |
| `/agents` | `GET` | Retrieves a list of all available agents in the pipeline along with their configuration details and current status |

## Development

- All agent logic is in `app/agent/` (each agent is modular and testable)
- Add new agents by extending the agent pipeline and schemas
- Workflow logic and agent orchestration will be handled in `AgentService` under `services/`
- Use the `scripts/` folder for Docker and local startup scripts

## Agent Pipeline Overview

1. **Pre-screen Agent**: Quickly filters out business-only or non-legal features.
2. **Jargon Agent**: Expands acronyms and internal terms, queries web if needed.
3. **Planner Agent**: Generates targeted retrieval needs for legal and compliance evidence.
4. **Retrieval Agent**: Searches internal KB and web for evidence
5. **Synthesizer Agent**: Synthesizes findings and open questions from evidence.
6. **Reviewer Agent**: Scores findings, applies deterministic rules, and flags for HITL if needed.
7. **Summariser Agent**: Formats the final result for frontend consumption.

Each agent is modular and can be extended or replaced independently. For more details, see the code in the `app/agent/` and `app/api/` folders, or open an issue for help!

## Contributor

Built by BitStorm team for TikTok Techjam 2025

- @jdengoh
- @ChickenChiang
- @alvintjw
- @ZuyuanChong

## License

MIT
