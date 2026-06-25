from __future__ import annotations

import json
import logging
from typing import Any

from agent.llm import chat
from mcp_tools.client import MCPToolClient

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 10


async def agent_loop(
    messages: list[dict[str, Any]],
    mcp_client: MCPToolClient,
    *,
    max_iterations: int = MAX_ITERATIONS,
) -> str:
    tools = mcp_client.get_tools()
    working = list(messages)

    for i in range(max_iterations):
        logger.debug("Agent loop iteration %d", i + 1)
        response = chat(working, tools=tools if tools else None)
        choice = response.choices[0]
        assistant_msg = choice.message

        working.append(assistant_msg.model_dump())

        if choice.finish_reason == "tool_calls" and assistant_msg.tool_calls:
            for tool_call in assistant_msg.tool_calls:
                fn_name = tool_call.function.name
                try:
                    fn_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    fn_args = {}

                logger.info("Calling tool: %s(%s)", fn_name, fn_args)
                try:
                    result = await mcp_client.call_tool(fn_name, fn_args)
                except Exception as exc:
                    logger.exception("Tool %s failed", fn_name)
                    result = f"Error calling tool {fn_name}: {exc}"

                working.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })
        else:
            return assistant_msg.content or ""

    return assistant_msg.content or ""
