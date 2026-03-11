# Claude Agent Teams Framework

A framework for orchestrating multiple Claude agents working together to solve complex tasks.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│           Team Orchestrator (Coordinator)               │
│  - Manages agent lifecycle                              │
│  - Routes tasks to specialized agents                   │
│  - Aggregates results                                   │
└─────────────────────────────────────────────────────────┘
         ↓         ↓         ↓         ↓
    ┌────────┬──────────┬──────────┬──────────┐
    │        │          │          │          │
    ▼        ▼          ▼          ▼          ▼
  Agent1  Agent2     Agent3     Agent4     Agent5
 (Data)  (Analysis) (Calc)    (Report)   (QA)
```

## Agents

### 1. **Data Collector Agent**
- Fetches data from external sources
- Validates data quality
- Handles errors gracefully
- Returns structured data

### 2. **Analysis Agent**
- Processes collected data
- Identifies patterns
- Performs deep analysis
- Flags anomalies

### 3. **Calculator Agent**
- Performs complex calculations
- Aggregates metrics
- Computes costs/savings
- Validates results

### 4. **Report Generator Agent**
- Formats results
- Creates visualizations
- Generates executive summaries
- Produces multiple output formats

### 5. **Quality Assurance Agent**
- Validates intermediate results
- Checks calculations
- Verifies report accuracy
- Suggests improvements

## Usage

```python
from agent_teams import TeamOrchestrator, AgentConfig

# Define agents
agents = [
    AgentConfig(name="data_collector", role="Fetch and validate data"),
    AgentConfig(name="analyzer", role="Analyze patterns and anomalies"),
    AgentConfig(name="calculator", role="Perform calculations"),
    AgentConfig(name="reporter", role="Generate reports"),
    AgentConfig(name="qa", role="Validate quality")
]

# Create orchestrator
team = TeamOrchestrator(agents=agents)

# Execute task
result = await team.execute(
    task="Audit Sentinel workspace and generate cost report",
    context={"workspace_id": "...", "days": 90}
)
```

## Features

- ✅ Parallel agent execution where possible
- ✅ Sequential dependencies when needed
- ✅ Automatic retry on failures
- ✅ Context passing between agents
- ✅ Result aggregation
- ✅ Error handling and fallbacks
- ✅ Detailed execution logging

## Configuration

See `config.yaml` for team settings, agent parameters, and execution options.

## Development

Each agent is defined in `agents/` directory with its own instructions and tools.
