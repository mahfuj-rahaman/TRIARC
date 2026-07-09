"""Untrusted-ingress tagging (docs/security.md Face 2).

Wraps external content -- MCP tool results, file contents, web pages -- in a tagged
block before it enters any model context, so a model treats it as data to transform,
never as instructions to follow.
"""

from __future__ import annotations


def wrap_untrusted(content: str, *, source: str) -> str:
    """Wrap CONTENT from SOURCE (e.g. "code-sandbox", "filesystem") as untrusted data."""
    return f'<untrusted-data source="{source}">\n{content}\n</untrusted-data>'
