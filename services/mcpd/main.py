# SPDX-License-Identifier: AGPL-3.0-or-later
"""
MCP Server Daemon (mcpd)
========================
Exposes ClawOS services as Model Context Protocol servers.
This allows external AI assistants to use ClawOS tools and resources.

Phase 2 of MCP integration: ClawOS becomes an MCP server.

Capabilities:
- skills/ → MCP tools
- memories/ → MCP resources  
- workflows/ → MCP prompts
- agent execution → MCP tools
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import uvicorn

from clawos_core.constants import CLAWOS_DIR, PORT_MCPD
from clawos_core.config.loader import get as get_config

log = logging.getLogger("mcpd")

# MCP Protocol Version
MCP_PROTOCOL_VERSION = "2024-11-05"

app = FastAPI(title="ClawOS MCP Server", version="0.1.0")


class ClawOSMCPServer:
    """
    MCP Server exposing ClawOS capabilities.
    
    Tools:
    - clawos_skill_execute: Execute any ClawOS skill
    - clawos_memory_search: Search agent memory
    - clawos_memory_save: Save to agent memory
    - clawos_workflow_run: Run a workflow
    - clawos_system_info: Get system information
    
    Resources:
    - clawos://skills - List available skills
    - clawos://memory/{workspace} - Access workspace memories
    - clawos://workflows - List available workflows
    - clawos://system/status - System health status
    
    Prompts:
    - clawos_daily_briefing: Generate morning briefing
    - clawos_task_planner: Plan and execute tasks
    """
    
    def __init__(self):
        self.tools = self._discover_tools()
        self.resources = self._discover_resources()
        self.prompts = self._discover_prompts()
    
    def _discover_tools(self) -> list[dict]:
        """Discover all available tools."""
        return [
            {
                "name": "clawos_skill_execute",
                "description": "Execute a ClawOS skill with given parameters. Skills include file operations, web search, shell commands, memory operations, and more.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "skill": {
                            "type": "string",
                            "description": "Skill name (e.g., fs.read, web.search, memory.read)"
                        },
                        "parameters": {
                            "type": "object",
                            "description": "Skill-specific parameters"
                        },
                        "workspace": {
                            "type": "string",
                            "description": "Workspace ID (default: nexus_default)"
                        }
                    },
                    "required": ["skill"]
                }
            },
            {
                "name": "clawos_memory_search",
                "description": "Search agent memory for relevant information. Uses semantic search across all 14 memory layers.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "workspace": {
                            "type": "string",
                            "description": "Workspace ID (default: nexus_default)"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results (default: 10)"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "clawos_memory_save",
                "description": "Save information to agent memory for future recall.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Content to save"
                        },
                        "workspace": {
                            "type": "string",
                            "description": "Workspace ID (default: nexus_default)"
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional tags for organization"
                        }
                    },
                    "required": ["content"]
                }
            },
            {
                "name": "clawos_workflow_run",
                "description": "Run a ClawOS workflow. Workflows include file organization, document processing, system maintenance, and more.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "workflow_id": {
                            "type": "string",
                            "description": "Workflow identifier (e.g., organize-downloads, summarize-pdf)"
                        },
                        "parameters": {
                            "type": "object",
                            "description": "Workflow-specific parameters"
                        },
                        "workspace": {
                            "type": "string",
                            "description": "Workspace ID (default: nexus_default)"
                        }
                    },
                    "required": ["workflow_id"]
                }
            },
            {
                "name": "clawos_system_info",
                "description": "Get ClawOS system information including disk usage, RAM, running services, and model status.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "clawos_list_workflows",
                "description": "List all available workflows with descriptions.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Filter by category (optional)"
                        }
                    }
                }
            },
            {
                "name": "clawos_list_skills",
                "description": "List all available skills/tools.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
    
    def _discover_resources(self) -> list[dict]:
        """Discover available resources."""
        return [
            {
                "uri": "clawos://skills",
                "name": "Available Skills",
                "description": "List of all available ClawOS skills/tools",
                "mimeType": "application/json"
            },
            {
                "uri": "clawos://workflows",
                "name": "Available Workflows",
                "description": "List of all available ClawOS workflows",
                "mimeType": "application/json"
            },
            {
                "uri": "clawos://system/status",
                "name": "System Status",
                "description": "Current system health and service status",
                "mimeType": "application/json"
            },
            {
                "uri": "clawos://memory/{workspace}",
                "name": "Workspace Memory",
                "description": "Access memories for a specific workspace",
                "mimeType": "application/json"
            }
        ]
    
    def _discover_prompts(self) -> list[dict]:
        """Discover available prompts."""
        return [
            {
                "name": "clawos_daily_briefing",
                "description": "Generate a morning briefing with calendar, weather, system status, and priorities",
                "arguments": [
                    {
                        "name": "workspace",
                        "description": "Workspace ID",
                        "required": False
                    }
                ]
            },
            {
                "name": "clawos_task_planner",
                "description": "Plan and break down a complex task into actionable steps",
                "arguments": [
                    {
                        "name": "task",
                        "description": "Task description",
                        "required": True
                    },
                    {
                        "name": "workspace",
                        "description": "Workspace ID",
                        "required": False
                    }
                ]
            }
        ]
    
    async def execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool and return result."""
        log.info(f"Executing tool: {tool_name} with args: {arguments}")
        
        workspace = arguments.get("workspace", "nexus_default")
        
        try:
            if tool_name == "clawos_skill_execute":
                return await self._execute_skill(
                    arguments.get("skill", ""),
                    arguments.get("parameters", {}),
                    workspace
                )
            
            elif tool_name == "clawos_memory_search":
                return await self._search_memory(
                    arguments.get("query", ""),
                    workspace,
                    arguments.get("limit", 10)
                )
            
            elif tool_name == "clawos_memory_save":
                return await self._save_memory(
                    arguments.get("content", ""),
                    workspace,
                    arguments.get("tags", [])
                )
            
            elif tool_name == "clawos_workflow_run":
                return await self._run_workflow(
                    arguments.get("workflow_id", ""),
                    arguments.get("parameters", {}),
                    workspace
                )
            
            elif tool_name == "clawos_system_info":
                return await self._get_system_info()
            
            elif tool_name == "clawos_list_workflows":
                return await self._list_workflows(arguments.get("category"))
            
            elif tool_name == "clawos_list_skills":
                return await self._list_skills()
            
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
                
        except Exception as e:
            log.error(f"Tool execution failed: {e}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error: {str(e)}"
                    }
                ],
                "isError": True
            }
    
    async def _execute_skill(self, skill: str, parameters: dict, workspace: str) -> dict:
        """Execute a ClawOS skill via toolbridge."""
        try:
            # Import here to avoid circular dependencies
            from services.toolbridge.service import ToolBridge
            from services.policyd.client import PolicyClient
            from services.memd.client import MemoryClient
            
            policy = PolicyClient()
            memory = MemoryClient()
            bridge = ToolBridge(policy, memory, workspace)
            
            # Extract target and content from parameters
            target = parameters.get("target", parameters.get("path", parameters.get("query", "")))
            content = parameters.get("content", "")
            
            result = await bridge.run(skill, target, content)
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": str(result)
                    }
                ]
            }
        except Exception as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Skill execution failed: {str(e)}"
                    }
                ],
                "isError": True
            }
    
    async def _search_memory(self, query: str, workspace: str, limit: int) -> dict:
        """Search agent memory."""
        try:
            from services.memd.client import MemoryClient
            
            memory = MemoryClient()
            results = memory.recall(query, workspace, top_k=limit)
            
            formatted_results = []
            for i, result in enumerate(results, 1):
                formatted_results.append(f"{i}. {result[:200]}...")
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Found {len(results)} memories:\n\n" + "\n".join(formatted_results)
                    }
                ]
            }
        except Exception as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Memory search failed: {str(e)}"
                    }
                ],
                "isError": True
            }
    
    async def _save_memory(self, content: str, workspace: str, tags: list) -> dict:
        """Save to agent memory."""
        try:
            from services.memd.client import MemoryClient
            
            memory = MemoryClient()
            mid = memory.remember(content, workspace, source="mcp")
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Memory saved successfully (ID: {mid})"
                    }
                ]
            }
        except Exception as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Failed to save memory: {str(e)}"
                    }
                ],
                "isError": True
            }
    
    async def _run_workflow(self, workflow_id: str, parameters: dict, workspace: str) -> dict:
        """Run a ClawOS workflow."""
        try:
            from workflows.engine import run_workflow
            
            result = await run_workflow(workflow_id, parameters, workspace)
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Workflow '{workflow_id}' completed:\n\n{result}"
                    }
                ]
            }
        except Exception as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Workflow failed: {str(e)}"
                    }
                ],
                "isError": True
            }
    
    async def _get_system_info(self) -> dict:
        """Get system information."""
        try:
            import shutil
            from clawos_core.platform import ram_snapshot_gb
            
            disk = shutil.disk_usage("/")
            ram = ram_snapshot_gb()
            
            info = {
                "disk_free_gb": round(disk.free / 1e9, 1),
                "disk_total_gb": round(disk.total / 1e9, 1),
                "ram_used_gb": ram.get("used_gb", 0),
                "ram_total_gb": ram.get("total_gb", 0),
                "clawos_version": "0.1.0",
                "mcp_protocol_version": MCP_PROTOCOL_VERSION
            }
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"ClawOS System Information:\n\n" +
                                f"Disk: {info['disk_free_gb']}GB free of {info['disk_total_gb']}GB\n" +
                                f"RAM: {info['ram_used_gb']}GB / {info['ram_total_gb']}GB used\n" +
                                f"Version: {info['clawos_version']}\n" +
                                f"MCP Protocol: {info['mcp_protocol_version']}"
                    }
                ]
            }
        except Exception as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Failed to get system info: {str(e)}"
                    }
                ],
                "isError": True
            }
    
    async def _list_workflows(self, category: Optional[str]) -> dict:
        """List available workflows."""
        try:
            from workflows.catalog import list_workflows
            
            workflows = list_workflows(category=category)
            
            lines = [f"Available Workflows ({len(workflows)} total):\n"]
            for wf in workflows:
                lines.append(f"• {wf['id']}: {wf['description'][:80]}...")
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "\n".join(lines)
                    }
                ]
            }
        except Exception as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Failed to list workflows: {str(e)}"
                    }
                ],
                "isError": True
            }
    
    async def _list_skills(self) -> dict:
        """List available skills."""
        skills = [
            "fs.read", "fs.write", "fs.list", "fs.delete", "fs.search",
            "web.search", "web.fetch",
            "shell.restricted",
            "memory.read", "memory.write", "memory.delete",
            "system.info",
            "workspace.create", "workspace.inspect",
            "browser.open", "browser.read", "browser.click", "browser.type",
            "browser.screenshot", "browser.close", "browser.scroll", "browser.wait"
        ]
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Available Skills ({len(skills)} total):\n\n" + "\n".join(f"• {s}" for s in skills)
                }
            ]
        }
    
    async def read_resource(self, uri: str) -> dict:
        """Read a resource by URI."""
        log.info(f"Reading resource: {uri}")
        
        try:
            if uri == "clawos://skills":
                result = await self._list_skills()
                return {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "application/json",
                            "text": json.dumps(result)
                        }
                    ]
                }
            
            elif uri == "clawos://workflows":
                result = await self._list_workflows(None)
                return {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "application/json",
                            "text": json.dumps(result)
                        }
                    ]
                }
            
            elif uri == "clawos://system/status":
                result = await self._get_system_info()
                return {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "application/json",
                            "text": json.dumps(result)
                        }
                    ]
                }
            
            elif uri.startswith("clawos://memory/"):
                workspace = uri.replace("clawos://memory/", "")
                # Return memory stats
                return {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "application/json",
                            "text": json.dumps({"workspace": workspace, "note": "Use clawos_memory_search to query memories"})
                        }
                    ]
                }
            
            else:
                raise ValueError(f"Unknown resource URI: {uri}")
                
        except Exception as e:
            log.error(f"Resource read failed: {e}")
            raise
    
    async def get_prompt(self, prompt_name: str, arguments: dict) -> dict:
        """Get a prompt template."""
        log.info(f"Getting prompt: {prompt_name} with args: {arguments}")
        
        workspace = arguments.get("workspace", "nexus_default")
        
        if prompt_name == "clawos_daily_briefing":
            return {
                "description": "Generate a morning briefing",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": f"Generate a morning briefing for workspace '{workspace}'. Include: calendar summary, weather, system status, and today's priorities."
                        }
                    }
                ]
            }
        
        elif prompt_name == "clawos_task_planner":
            task = arguments.get("task", "")
            return {
                "description": f"Plan task: {task}",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": f"Break down this task into actionable steps: {task}\n\nFor workspace: {workspace}"
                        }
                    }
                ]
            }
        
        else:
            raise ValueError(f"Unknown prompt: {prompt_name}")


# Global server instance
mcp_server = ClawOSMCPServer()


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """Main MCP endpoint handling all JSON-RPC requests."""
    body = await request.json()
    
    method = body.get("method", "")
    params = body.get("params", {})
    request_id = body.get("id")
    
    log.info(f"MCP request: {method}")
    
    try:
        if method == "initialize":
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {
                        "tools": {},
                        "resources": {},
                        "prompts": {}
                    },
                    "serverInfo": {
                        "name": "ClawOS",
                        "version": "0.1.0"
                    }
                }
            })
        
        elif method == "tools/list":
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": mcp_server.tools
                }
            })
        
        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            
            result = await mcp_server.execute_tool(tool_name, arguments)
            
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result
            })
        
        elif method == "resources/list":
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "resources": mcp_server.resources
                }
            })
        
        elif method == "resources/read":
            uri = params.get("uri", "")
            result = await mcp_server.read_resource(uri)
            
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result
            })
        
        elif method == "prompts/list":
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "prompts": mcp_server.prompts
                }
            })
        
        elif method == "prompts/get":
            prompt_name = params.get("name", "")
            arguments = params.get("arguments", {})
            
            result = await mcp_server.get_prompt(prompt_name, arguments)
            
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result
            })
        
        else:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }, status_code=404)
    
    except Exception as e:
        log.error(f"MCP error: {e}")
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32603,
                "message": str(e)
            }
        }, status_code=500)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "up", "service": "mcpd", "protocol_version": MCP_PROTOCOL_VERSION}


def run():
    """Run the MCP server."""
    config = get_config()
    host = config.get("mcp", {}).get("host", "127.0.0.1")
    port = config.get("mcp", {}).get("port", PORT_MCPD)
    
    log.info(f"Starting MCP server on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
