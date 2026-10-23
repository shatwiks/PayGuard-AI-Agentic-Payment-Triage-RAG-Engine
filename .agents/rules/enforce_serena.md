---
name: Enforce Serena Usage
description: Forces the agent to always prefer and utilize the Serena MCP server tools for code navigation, exploration, and refactoring.
---

# Always Use Serena

For every prompt that involves exploring a codebase, modifying code, refactoring, finding references, or fetching diagnostics, you MUST prioritize using the `serena` MCP server tools.

## Rules
- Actively rely on Serena's advanced features such as `find_referencing_symbols`, `find_implementations`, and `get_diagnostics_for_file` to thoroughly understand the codebase context before making changes.
- Prefer Serena's `replace_content`, `insert_after_symbol`, and `replace_symbol_body` tools for safe and precise code edits.
- Use `get_symbols_overview` for quick architectural understanding of files.
- Treat `serena` as the default toolkit for intelligent IDE-level operations.
