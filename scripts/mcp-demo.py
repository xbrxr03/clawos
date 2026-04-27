#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
MCP Demo Script
===============
Quick demonstration of MCP (Model Context Protocol) integration.

This script:
1. Creates default MCP configuration
2. Tests connection to filesystem MCP server
3. Lists available tools
4. Demonstrates tool execution

Usage:
  python3 scripts/mcp-demo.py

Requirements:
  - Node.js and npx installed
  - ClawOS services running (bash scripts/dev_boot.sh)
"""
import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from services.toolbridge.mcp_client import MCPClient, create_default_config


async def main():
    print("🚀 MCP Demo - Model Context Protocol Integration")
    print("=" * 60)
    
    # Step 1: Create default config
    config_path = Path.home() / ".clawos-runtime" / "config" / "mcp.json"
    if not config_path.exists():
        print("\n📁 Creating default MCP configuration...")
        await create_default_config(config_path)
        print(f"✓ Created: {config_path}")
    else:
        print(f"\n📁 Using existing config: {config_path}")
    
    # Step 2: Initialize MCP client
    print("\n🔌 Initializing MCP client...")
    client = MCPClient(config_path)
    
    try:
        await client.load_config()
        
        if not client.connections:
            print("⚠️  No MCP servers configured.")
            print("   Run: clawctl mcp init")
            return
        
        # Step 3: Show connected servers
        print(f"\n✅ Connected to {len(client.connections)} MCP server(s):")
        for name, conn in client.connections.items():
            print(f"   • {name}: {len(conn.tools)} tools, {len(conn.resources)} resources")
        
        # Step 4: List all available tools
        print("\n🔧 Available MCP Tools:")
        tools = client.get_all_tools()
        if tools:
            for tool_name, desc in list(tools.items())[:10]:  # Show first 10
                print(f"   • {tool_name}")
                print(f"     {desc[:60]}..." if len(desc) > 60 else f"     {desc}")
            if len(tools) > 10:
                print(f"   ... and {len(tools) - 10} more")
        else:
            print("   No tools available")
        
        # Step 5: Demonstrate tool execution (if filesystem server available)
        if "filesystem" in client.connections:
            print("\n📝 Testing filesystem tool execution:")
            try:
                result = await client.execute_tool(
                    "mcp.filesystem.list_directory",
                    {"path": str(Path.home())}
                )
                print(f"   ✓ Tool executed successfully")
                print(f"   Result preview: {result[:200]}...")
            except Exception as e:
                print(f"   ⚠️  Tool execution failed: {e}")
        
        print("\n" + "=" * 60)
        print("✨ MCP integration is working!")
        print("\nNext steps:")
        print("  1. Try: clawctl mcp list")
        print("  2. Try: clawctl mcp test filesystem")
        print("  3. Use MCP tools in Nexus: nexus")
        
    finally:
        # Cleanup
        print("\n🧹 Cleaning up connections...")
        await client.close_all()
        print("✓ Done!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
