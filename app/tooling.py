"""Reusable, permission-aware tool registry for the FlowPilot agent runtime."""
from dataclasses import dataclass
from typing import Any, Callable

@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    required: tuple[str, ...]
    permission: str
    handler: Callable[..., Any]

class ToolError(RuntimeError):
    pass

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def describe(self) -> list[dict[str, Any]]:
        return [
            {"name": t.name, "description": t.description, "required": list(t.required), "permission": t.permission}
            for t in sorted(self._tools.values(), key=lambda item: item.name)
        ]

    def execute(self, name: str, arguments: dict[str, Any], permissions: set[str]) -> Any:
        spec = self._tools.get(name)
        if not spec:
            raise ToolError(f"Unknown tool: {name}")
        missing = [key for key in spec.required if key not in arguments]
        if missing:
            raise ToolError(f"Missing required arguments for {name}: {', '.join(missing)}")
        if spec.permission not in permissions:
            raise PermissionError(f"Permission denied for tool {name}: requires {spec.permission}")
        # Only declared parameters are passed to handlers; model-generated extras are ignored.
        import inspect
        params = inspect.signature(spec.handler).parameters
        clean = {key: value for key, value in arguments.items() if key in params}
        return spec.handler(**clean)

def build_registry() -> ToolRegistry:
    """Create a fresh registry. Tool handlers are narrow and side effects stay in app code."""
    from .agent import extract_invoice, read_document
    from .browser_tool import inspect_local_page
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="documents.read",
        description="Read a named file from the configured, sandboxed sample-data directory.",
        required=("document_name",),
        permission="documents:read",
        handler=read_document,
    ))
    registry.register(ToolSpec(
        name="browser.inspect_local_page",
        description="Inspect the title and visible text of a local allowlisted web page using Playwright.",
        required=("url",),
        permission="browser:local_read",
        handler=inspect_local_page,
    ))
    registry.register(ToolSpec(
        name="invoices.extract",
        description="Extract and validate structured invoice fields from supplied document text.",
        required=("text",),
        permission="invoices:extract",
        handler=extract_invoice,
    ))
    return registry
