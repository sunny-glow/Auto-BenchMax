# MCP-Atlas: A Large-Scale Benchmark for Tool-Use Competency with Real MCP Servers

MCP-Atlas is a comprehensive benchmark for evaluating AI models' tool-use capabilities across 36 Model Context Protocol (MCP) servers. It provides a standardized environment for running agent completions and evaluating performance with LLM-as-judge methodology.

- Paper: [https://static.scale.com/uploads/674f4cc7a74e35bcaae1c29a/MCP_Atlas.pdf](https://static.scale.com/uploads/674f4cc7a74e35bcaae1c29a/MCP_Atlas.pdf) or ([local copy](assets/MCP_Atlas.pdf))
- Leaderboard: [https://scale.com/leaderboard/mcp_atlas](https://scale.com/leaderboard/mcp_atlas)
- Dataset: [https://huggingface.co/datasets/ScaleAI/MCP-Atlas](https://huggingface.co/datasets/ScaleAI/MCP-Atlas)

## What is MCP-Atlas?
MCP-Atlas evaluates how well AI agents can use tools to complete real-world tasks. The benchmark includes:

- 36 MCP servers spanning categories like search, code execution, databases, APIs, and productivity tools
  - 20 don't require any setup, 11 require you to get API keys, and 5 require API keys and data setup (detailed below).
- 500 evaluation prompts with ground-truth expected tool calls and answers
- LLM-as-judge evaluation producing pass rate, coverage rate, and detailed diagnostics
- Dockerized environment ensuring reproducible results across different machines

![MCP-Atlas Architecture](assets/architecture-diagram.png)

### Summary of MCP servers and tools

- See the MCP server definitions [`mcp_server_template.json`](services/agent-environment/src/agent_environment/mcp_server_template.json). `uvx` servers can be found at pypi.org and `npx` servers at npmjs.com.
- All servers should be open source or forked from another open source repo. We at Scale AI did not develop any new MCP servers for MCP-Atlas, and instead used real-world MCP servers.
- Versions are pinned to ensure they don't change over time, to ensure reproducibility.
- See the [summary of 36 mcp servers and all 307 tools here](https://gist.github.com/geobio/d0272d41ea395376233f1617a3988860).
- See sample tool calls in [curl_scripts directory](services/agent-environment/dev_scripts/debug_and_concurrency_tests/curl_scripts). This is the easiest way to directly call the MCP servers via agent-environment service in the docker container.
- To check what tools are available, you can use this CURL script:  
`curl -X POST http://localhost:1984/list-tools | jq > list_tools.json ; open list_tools.json`  
or see the [full tool definition for all 36 servers and 307 tools here](https://gist.github.com/geobio/e1c08cc4d74d96223cb8cf0919a72c3e).

## Quick Start

This project depends on these CLI tools: [docker](https://www.docker.com/products/docker-desktop/), [uv](https://docs.astral.sh/uv/getting-started/installation/#installation-methods), [jq](https://jqlang.org/download/), and python 3.10+.

```bash
git clone git@github.com:scaleapi/mcp-atlas.git
cd mcp-atlas
```

### 1. Configure environment

```bash
cp env.template .env
```

Edit `.env` and set:
- `LLM_API_KEY` - Your LLM API key for the model you want to evaluate (required for agent completions in step 5). We're using gpt-5.1 in our example so please use an OpenAI API key.
- `EVAL_LLM_API_KEY` - Your LLM API key for evaluation scoring. Default model is `gemini/gemini-2.5-pro`, so use a Gemini API key. You can change `EVAL_LLM_MODEL` and use the corresponding provider's key.
- `LLM_BASE_URL` - **Optional**, leave empty to use official provider APIs. Set if using a custom endpoint (e.g., LiteLLM proxy, Azure OpenAI, or self-hosted models).
- `EVAL_LLM_MODEL` - **Optional**, defaults to `gemini/gemini-2.5-pro`. Examples: `gpt-5.1`, `claude-3-5-sonnet-20241022`

We use [LiteLLM](https://docs.litellm.ai/) to support 100+ LLMs via a unified API. Our examples use `openai/gpt-5.1`, but most other models should work. Ensure that LLM_API_KEY matches the model you're using.

### 2. Start the MCP servers

**Note: Allocate at least 8GB memory to Docker (10GB+ recommended).**

**Option A: Use pre-built image (faster, recommended):**

```bash
docker pull ghcr.io/scaleapi/mcp-atlas:1.2.5
docker tag ghcr.io/scaleapi/mcp-atlas:1.2.5 agent-environment:latest
make run-docker
```

**Option B: Build from source:**

```bash
make build && make run-docker
```

This starts the agent-environment service on port 1984 (takes 1+ minute to initialize). Before continuing, please wait for this to finish, you'll see log "Uvicorn running on http://0.0.0.0:1984". 

By default, [20 servers](services/agent-environment/src/agent_environment/mcp_client.py#L23) that don't require API keys are enabled. Servers requiring API keys are auto-enabled only if you've set their keys in `.env`.

Confirm that all 20 servers are online. You should see `"total":20,"online":20,"offline":0` and the list of servers. [Expected response](https://gist.github.com/geobio/88b1c4bed8148a8fbfb28628c384d5e1)
```bash
curl -s http://localhost:1984/enabled-servers | jq -c
```

When you call `/enabled-servers`, if any error, Ctrl + C and re-run. If the docker container does not shut down gracefully, use `docker ps` and `docker kill <ID>` to force it to shut down.

Test a tool call to the `filesystem` MCP server. [Expected response](https://gist.github.com/geobio/65a9a2d9a07a4b9117a312030a7a3830)
```bash
curl -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "filesystem_read_text_file",
    "tool_args": {
      "path": "/data/Barber Shop.csv",
      "head": 1
    }
  }' | jq
```

### 3. Start the completion service (in a new terminal)

```bash
make run-mcp-completion
```

This starts the MCP completion service on port 3000. It provides an API that connects LLMs to the MCP servers, handling the agentic loop: the LLM decides which tools to call, the service executes them via the MCP servers (port 1984), and returns results back to the LLM until the task is complete.

### 4. Test with a simple agent completion (in a new terminal)

Test a call the MCP completion service. The expected answer is "Customer". [Expected response](https://gist.github.com/geobio/6e0560846800a1799431c96e64b8254d)

```bash
curl -X POST http://localhost:3000/v2/mcp_eval/run_agent \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-5.1",
    "messages": [{"role": "user", "content": "What is the first word of the file at /data/Barber Shop.csv?"}],
    "enabledTools": ["filesystem_read_text_file"],
    "maxTurns": 20
  }' | jq
```

### 5. Test with a sample of 10 tasks

**Note:** Steps 5-8 are all run from the `services/mcp_eval/` directory.

```bash
cd services/mcp_eval
```

Run the script with a small sample of 10 tasks. This will use the specified input CSV file. It should be solvable with only the 20 MCP servers that don't require any API keys (enabled by default). For details on servers, see `env.template` and [`mcp_server_template.json`](services/agent-environment/src/agent_environment/mcp_server_template.json).

```bash
uv run python mcp_completion_script.py \
  --model "openai/gpt-5.1" \
  --input "sample_tasks.csv" \
  --output "sample_51_results.csv"
```

Results are saved to `completion_results/sample_51_results.csv`. On Mac, "Numbers" app works better to open CSV files with multi-line rows.

**Note:** The script automatically skips tasks that are already in the output file. To re-run all tasks, delete or rename the output file first.

Options:
- `--model` - [required] LLM model to use (e.g., `openai/gpt-5.1`)
- `--input` or `--input_huggingface` - [required] Input CSV file or HuggingFace dataset name
- `--output` - [required] Output CSV filename (saved to `completion_results/`)
- `--no-filter` - Disable filtering by available MCP servers (runs all tasks regardless of missing API keys)
- `--num-tasks` - Limit to first N tasks (useful for testing)
- `--concurrency` - Maximum concurrent API requests (default: 10, range: 5-20)

Note: For these 10 tasks, they have more servers/tools in "ENABLED_TOOLS", but they are not required to get the correct answer (ground truth claims in "GTFA_CLAIMS"). At the time of creation of each task's prompt and trajectory, all the "ENABLED_TOOLS" were available to the LLM, but the ground truth was determined using only the servers in "TRAJECTORY". However, if you don't provide an API key then that mcp server won't start, and that server's tools will be unavailable to the LLM you're evaluating.

### 6. Evaluate the results

Make sure `EVAL_LLM_API_KEY` is set in `.env` (from step 1). The evaluator model defaults to `gemini/gemini-2.5-pro`.

```bash
uv run mcp_evals_scores.py \
--input-file="completion_results/sample_51_results.csv" \
--model-label="gpt51"

# model-label here refers to the model in step 5 that we used, and is used for output file naming
```

Options:
- `--input-file` - [required] Path to completion results CSV from step 5
- `--model-label` - [required] Short identifier for the model being evaluated from the previous completion step (used in output filenames)
- `--evaluator-model` - Override model (default: `EVAL_LLM_MODEL` env var or `gemini/gemini-2.5-pro`)
- `--num-tasks` - Limit to first N tasks
- `--concurrency` - Concurrent API requests (default: 5)
- `--pass-threshold` - Coverage score threshold for pass rate calculation (default: 0.75)

Outputs saved to `evaluation_results/`:
- `scored_gpt51.csv` - Coverage scores for each task. On Mac, "Numbers" app works better to open CSV files with multi-line rows.
- `coverage_stats_gpt51.csv` - Summary statistics
- `coverage_histogram_gpt51.png` - Score distribution plot

### 7. Add more API keys (strongly recommended)

Approximately 18% of evaluation tasks work with the 20 default servers. To run more tasks, add API keys to your `.env` file (see `env.template` for setup instructions). Note that a task may require multiple mcp servers, and that task will be skipped if any of its required servers are unavailable. For example, exa is used in 13% of tasks as part of the ground truth trajectory, and without that api key, you'll skip 13% of tasks. API-requiring mcp server usage:

- exa: 13% | airtable: 12% | mongodb: 12% | oxylabs: 11% | brave-search: 10%
- alchemy: 8% | national-parks: 8% | twelvedata: 8% | lara-translate: 7%
- notion: 6% | weather-data: 6% | github: 5% | slack: 5% | google-maps: 5%
- e2b-server: 5% | google-workspace: 4%


**Important:** Five servers require both API keys AND sample data to be uploaded to your account. Without this sample data, tasks that use these servers will return erroneous results because they cannot find the expected data.

**See [`data_exports/README.md`](data_exports/README.md) for detailed setup instructions for each service.** 

- **Airtable** - Visit the [shared base](https://airtable.com/appIF9byLfQwdHqE2/shr1KTZOgPl0qQmA8) and click "Copy base"
- **Google Calendar (google-workspace)** - Import `data_exports/calendar_mcp_eval_export.zip` (8KB)
- **Notion** - Import `data_exports/mcp-atlas-notion-data.zip` (1MB) via Settings > Import
- **MongoDB** - Restore `data_exports/mongo_dump_video_game_store-UNZIP-FIRST.zip` (486KB) using `mongorestore`
- **Slack** - Import `data_exports/slack_mcp_eval_export.zip` (43KB) at your workspace's import page

Note: Some services are paid and require billing setup. 

**Note: When you add more API keys to `.env`, you need to restart the server in step 2.** On start, it'll automatically detect what API keys are available, and start those respective MCP servers. After it has restarted, confirm that all expected servers are online. If not online, try restarting the docker container, or check for error logs. 

```bash
# After adding API keys to .env and restarting the docker container

curl -s http://localhost:1984/enabled-servers | jq -c
```

If the docker container does not shut down gracefully, use `docker ps` and `docker kill <ID>` to force it to shut down.

### 8. Evaluate with the full HuggingFace dataset

Run completions using the HuggingFace dataset (contains 500 tasks). If you don't have all API keys, you'll see less than 500 tasks being run.

```bash
uv run python mcp_completion_script.py \
  --model "openai/gpt-5.1" \
  --input_huggingface "ScaleAI/MCP-Atlas" \
  --output "mcp_eval_51_results.csv"
```

This saves the completion results to:
- `completion_results/mcp_eval_51_results.csv` - Contains both ground truth and completion data

Then evaluate the results:

```bash
uv run mcp_evals_scores.py \
--input-file="completion_results/mcp_eval_51_results.csv" \
--model-label="gpt51"
```

**Note:** Tasks are filtered by default (see step 5). To disable, add `--no-filter`, but we recommend adding missing API keys to `.env` instead.

### 9. Evaluate other models

To benchmark other models, repeat step 8 with a different `--model` and `--output`.

If you are changing `LLM_API_KEY` you'll also have to restart `make run-mcp-completion`.

See [LiteLLM's supported models](https://docs.litellm.ai/docs/providers) for the full list of available providers and model names. For self-hosted models, change `LLM_BASE_URL`.

## What's Included

- **36 MCP servers** including calculator, Wikipedia, filesystem, Git, weather, GitHub, and more
- **Agent completion service** for running multi-turn LLM conversations with tool use
- **Docker containerization** for consistent MCP server environments
- **HTTP APIs** for tool calling and listing available tools
- **Sample debug scripts** in `services/agent-environment/dev_scripts/debug_and_concurrency_tests/curl_scripts/` for directly testing individual MCP servers
- **Full source code** showing the MCP servers, docker setup, agent-environment, completion service, and eval scoring script.
