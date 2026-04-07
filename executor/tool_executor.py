"""Execute a tool by name and log the call."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from tools.registry import ToolRegistry


async def call_tool(
    registry: ToolRegistry,
    tool_name: str,
    tool_input: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    """Look up *tool_name* in the registry, invoke it, and log the call.

    Returns the tool's result dict (whose keys match state keys).
    On error returns an ``{"error": ...}`` dict so the agent loop can react.
    """
    spec = registry.get_tool(tool_name)
    if spec is None:
        error = {"error": f"Unknown tool: {tool_name}"}
        _log(state, tool_name, tool_input, error)
        return error

    try:
        import inspect
        sig = inspect.signature(spec.handler)
        if len(sig.parameters) >= 2:
            result = await spec.handler(tool_input, state)
        else:
            result = await spec.handler(tool_input)
    except Exception as exc:
        error = {"error": f"{tool_name} failed: {exc}"}
        _log(state, tool_name, tool_input, error)
        return error

    _log(state, tool_name, tool_input, result)
    return result


def _log(
    state: dict[str, Any],
    tool_name: str,
    tool_input: dict[str, Any],
    result: dict[str, Any],
) -> None:
    state["tool_call_log"].append({
        "tool": tool_name,
        "input": tool_input,
        "success": "error" not in result,
        "result_keys": list(result.keys()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
