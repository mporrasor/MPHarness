import asyncio
from typing import Optional
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from rich.console import Console

console = Console()

class HarnessMCPClient:
    """
    A foundational MCP (Model Context Protocol) client for the Harness.
    This client can connect to any standard MCP server via stdio.
    """
    def __init__(self, command: str, args: list[str], env: Optional[dict] = None):
        self.server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env
        )
        self.session: Optional[ClientSession] = None
        self._exit_stack = None

    async def connect(self):
        from contextlib import AsyncExitStack
        
        self._exit_stack = AsyncExitStack()
        read, write = await self._exit_stack.enter_async_context(stdio_client(self.server_params))
        self.session = await self._exit_stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()
        console.print(f"[green]Connected to MCP Server: {self.server_params.command}[/green]")

    async def disconnect(self):
        if self._exit_stack:
            await self._exit_stack.aclose()
            self.session = None
            console.print("[yellow]Disconnected from MCP Server[/yellow]")

    async def list_tools(self):
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
        response = await self.session.list_tools()
        return response.tools

    async def call_tool(self, name: str, arguments: dict):
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
        response = await self.session.call_tool(name, arguments)
        return response

# Example usage function for the CLI (can be exposed via a `harness mcp` command later)
async def test_mcp_connection(command: str, args: list[str]):
    client = HarnessMCPClient(command, args)
    try:
        await client.connect()
        tools = await client.list_tools()
        console.print(f"Available tools: {[t.name for t in tools]}")
    except Exception as e:
        console.print(f"[bold red]Failed to connect to MCP:[/bold red] {e}")
    finally:
        await client.disconnect()
