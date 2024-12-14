import asyncio
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()  # load environment variables from .env

class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server
        
        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        print(f"Checking server script type...")  # Debug print
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")
            
        command = "python" if is_python else "node"
        print(f"Using command: {command} {server_script_path}")  # Debug print
        
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )
        
        print("Starting stdio client...")  # Debug print
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        print("Stdio client started")  # Debug print
        
        self.stdio, self.write = stdio_transport
        print("Creating client session...")  # Debug print
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        
        print("Initializing session...")  # Debug print
        await self.session.initialize()
        
        # List available tools
        print("Requesting tool list...")  # Debug print
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

    async def process_query(self, query: str) -> str:
        """Process a query using Claude and available tools"""
        # Get available tools
        response = await self.session.list_tools()
        available_tools = [{ 
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in response.tools]
        
        # Create dynamic system message based on available tools
        tools_description = "\n".join([
            f"- {tool['name']}: {tool['description']}" 
            for tool in available_tools
        ])
        
        # Create message with system prompt as a parameter instead of a message
        response = self.anthropic.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            system=f"""You have access to the following tools that you can and should use if they are relevant to the user's query:

{tools_description}

You should use these tools to help users accomplish their goals. Don't say you can't do something if a tool exists to do it.""",
            messages=[{
                "role": "user",
                "content": query
            }],
            tools=available_tools
        )

        final_text = []
        conversation_history = []

        while True:
            # Process the response
            has_tool_calls = False
            for content in response.content:
                if content.type == 'text':
                    final_text.append(content.text)
                    conversation_history.append({"role": "assistant", "content": content.text})
                elif content.type == 'tool_use':
                    has_tool_calls = True
                    tool_name = content.name
                    tool_args = content.input
                    
                    # Execute tool call
                    result = await self.session.call_tool(tool_name, tool_args)
                    final_text.append(f"[Tool {tool_name} result: {result.content}]")
                    
                    # Add tool interaction to conversation
                    conversation_history.append({
                        "role": "assistant",
                        "content": f"I'm using the {tool_name} tool with these parameters: {tool_args}"
                    })
                    conversation_history.append({
                        "role": "user",
                        "content": f"Tool result: {result.content}"
                    })

            # If no tool calls were made, we're done
            if not has_tool_calls:
                break
            
            # Continue conversation with updated history
            response = self.anthropic.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                system=f"""You have access to the following tools that you can and should use:

{tools_description}

You should use these tools to help users accomplish their goals. Don't say you can't do something if a tool exists to do it.""",
                messages=conversation_history + [{
                    "role": "user",
                    "content": query
                }],
                tools=available_tools
            )

        return "\n".join(final_text)

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
                
                if query.lower() == 'quit':
                    break
                    
                response = await self.process_query(query)
                print("\n" + response)
                    
            except Exception as e:
                print(f"\nError: {str(e)}")
    
    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)
        
    print(f"Starting client with server script: {sys.argv[1]}")  # Debug print
    
    client = MCPClient()
    try:
        print("Attempting to connect to server...")  # Debug print
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    except Exception as e:
        print(f"Fatal error: {str(e)}")  # Catch and print any errors
        import traceback
        print(traceback.format_exc())  # Print full stack trace
    finally:
        await client.cleanup()

if __name__ == "__main__":
    import sys
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Startup error: {str(e)}")