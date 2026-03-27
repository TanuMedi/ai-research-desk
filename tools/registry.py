"""MCP-style tool registry — tools are described by schema and selected dynamically."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine


ToolHandler = Callable[..., Coroutine[Any, Any, dict[str, Any]]]


@dataclass
class ToolSpec:
    """Schema + handler for a single tool."""
    name: str
    description: str
    input_schema: dict[str, Any]
    use_when: str
    produces: list[str]
    handler: ToolHandler


class ToolRegistry:
    """Registry of MCP-style tools available to the agent loop."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        use_when: str,
        produces: list[str],
        handler: ToolHandler,
    ) -> None:
        self._tools[name] = ToolSpec(
            name=name,
            description=description,
            input_schema=input_schema,
            use_when=use_when,
            produces=produces,
            handler=handler,
        )

    def get_tool(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def get_schemas_for_llm(self) -> str:
        """Format all tool schemas as a text block for the LLM decision prompt."""
        lines: list[str] = []
        for tool in self._tools.values():
            lines.append(f"Tool: {tool.name}")
            lines.append(f"  Description: {tool.description}")
            lines.append(f"  Use when: {tool.use_when}")
            lines.append(f"  Input: {tool.input_schema}")
            lines.append(f"  Produces: {tool.produces}")
            lines.append("")
        return "\n".join(lines)


def _register_from_module(registry: ToolRegistry, module: Any, handler: ToolHandler) -> None:
    """Helper to register a tool from a module that exposes TOOL_SCHEMA."""
    schema = module.TOOL_SCHEMA
    registry.register(
        name=schema["name"],
        description=schema["description"],
        input_schema=schema["input_schema"],
        use_when=schema["use_when"],
        produces=schema["produces"],
        handler=handler,
    )


def build_default_registry() -> ToolRegistry:
    """Create and return a registry with all built-in tools."""
    import tools.arxiv_tool as arxiv_tool
    import tools.github_tool as github_tool
    import tools.memory_tool as memory_tool

    registry = ToolRegistry()
    _register_from_module(registry, arxiv_tool, arxiv_tool.run)
    _register_from_module(registry, github_tool, github_tool.run)
    _register_from_module(registry, memory_tool, memory_tool.run)
    return registry
