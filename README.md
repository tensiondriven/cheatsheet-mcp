# CASH - Claude Autonomous Shell MCP Server

An MCP (Model Context Protocol) server that provides autonomous shell command execution for Claude Code without human approval prompts.

## Files

- **`cash_server.py`** - Main MCP server implementation
- **`allowed_commands.txt`** - Safety allowlist of permitted commands  
- **`MCP_SETUP_INSTRUCTIONS.md`** - Configuration and usage guide

## Quick Setup

Add to Claude Code MCP configuration:

```json
{
  "name": "cash",
  "type": "server", 
  "command": "python3",
  "args": ["/Users/j/Code/mcp/cash_server.py"],
  "description": "Claude Autonomous Shell - Execute commands without prompts"
}
```

## Key Features

- **Autonomous execution** - No human prompts for git, docker, file operations
- **Safety allowlist** - Only pre-approved commands can execute
- **TTS communication** - `say` command for personality and progress updates
- **Audit logging** - Complete command history for security
- **Timeout protection** - Commands limited to 30 seconds max

## Extracted From

Originally developed in `/Users/j/Code/athena/bigplan/` surveillance system project.