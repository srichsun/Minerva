"""Tools the agent can call, plus their JSON schemas.

Each tool is a plain Python function returning a string. TOOLS holds the
schemas passed to the Anthropic API; dispatch() runs the matching function.
"""
from app import rag

# A tiny fake order database so the agent has a second, non-document tool.
_FAKE_ORDERS = {
    "1001": "Order 1001: 1x iPhone 15, shipped 2026-07-02, arriving 2026-07-05.",
    "1002": "Order 1002: 1x AppleCare+, active, no delivery needed.",
    "1003": "Order 1003: 1x iPad, payment pending — not yet shipped.",
}

TOOLS = [
    {
        "name": "search_documents",
        "description": (
            "Search the support knowledge base (plans, pricing, returns policy, "
            "warranty) for passages relevant to a question. Use this for any "
            "question about products or policies."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "lookup_order",
        "description": "Look up the status of a customer order by its numeric ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "The order ID, e.g. 1001"}
            },
            "required": ["order_id"],
        },
    },
]


def format_hits(hits: list[dict]) -> str:
    """Format already-retrieved chunks into what Claude sees as a tool result.

    Split out from search_documents so callers that already retrieved hits
    (e.g. to also collect source filenames) can reuse this without a second
    rag.retrieve() call for the same query.
    """
    if not hits:
        return "No relevant documents found."
    return "\n\n".join(f"[{h['source']}] {h['text']}" for h in hits)


def search_documents(query: str) -> str:
    return format_hits(rag.retrieve(query))


def lookup_order(order_id: str) -> str:
    return _FAKE_ORDERS.get(order_id, f"No order found with ID {order_id}.")


_HANDLERS = {"search_documents": search_documents, "lookup_order": lookup_order}


def dispatch(name: str, tool_input: dict) -> str:
    """Run the named tool with its input and return the result string."""
    handler = _HANDLERS.get(name)
    if handler is None:
        return f"Unknown tool: {name}"
    return handler(**tool_input)
