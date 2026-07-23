"""Main FastAPI application for MCP eval."""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Header, Request, Response

from .agent_eval import handle_run_mcp_eval
from .schema import RunAgentAPIRequestBody
from .errors import MCPClientToolExecutionError
from .config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MCP Eval",
    description="Standalone MCP evaluation environment",
    version="0.1.0",
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log requests with their actual response status codes."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    logger.info(
        f"{request.client.host}:{request.client.port} - "
        f'"{request.method} {request.url.path} HTTP/1.1" {response.status_code} '
        f"- {process_time:.3f}s"
    )

    return response


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "MCP Eval is running"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/v2/mcp_eval/run_agent")
async def run_agent(
    body: RunAgentAPIRequestBody,
    authorization: Optional[str] = Header(None),
):
    """
    MCP evaluation endpoint. The main entrypoint. For simplicity, no authentication or rate limiting is used.
    """
    logger.info(f"v2 API /run_agent called with model: {body.model}")

    try:
        # Process agent outputs and return results
        results = []
        async for agent_output in handle_run_mcp_eval(body):
            result = {
                "type": agent_output.type,
                "data": agent_output.data,
            }
            results.append(result)

        return results

    except MCPClientToolExecutionError as error:
        logger.error(f"MCP client tool execution error: {error}")
        raise HTTPException(status_code=500, detail={"error": str(error)})

    except Exception as error:
        logger.error(f"Error during MCP eval execution: {error}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Unknown error during mcp_eval: {str(error)}",
            },
        )


def main():
    # Validate required configuration at startup
    config.validate_required_config()

    logger.info(f"Starting MCP Eval server on {config.HOST}:{config.PORT}")

    uvicorn.run(
        "mcp_completion.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,  # Set to True for development
        log_level=config.LOG_LEVEL.lower(),
        access_log=False,  # Disable default access logs (we have custom middleware)
    )


if __name__ == "__main__":
    main()
