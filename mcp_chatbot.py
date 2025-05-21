import os
import logging
from openai import OpenAI
from asyncio import gather, sleep
from contextlib import AsyncExitStack
import json
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
import nest_asyncio

# Set up logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('mcp_chatbot')

nest_asyncio.apply()

load_dotenv()

class MCP_ChatBot:
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        
        # Initialize OpenAI client with proper error handling
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not found in environment variables")
        
        try:
            # Try initializing with the new API (OpenAI 1.x)
            self.openai = OpenAI(api_key=api_key)
        except TypeError as e:
            if "unexpected keyword argument 'proxies'" in str(e):
                # Fallback for older versions or specific configuration issues
                logger.warning("Falling back to alternative OpenAI client initialization")
                import openai as openai_module
                openai_module.api_key = api_key
                self.openai = openai_module
            else:
                # Re-raise if it's a different TypeError
                raise
        
        # Tools list required for OpenAI API
        self.available_tools = []
        # Prompts list for quick display 
        self.available_prompts = []
        # Sessions dict maps tool/prompt names or resource URIs to MCP client sessions
        self.sessions = {}
        # Message history
        self.message_history = []

    async def connect_to_server(self, server_name, server_config):
        try:
            logger.info(f"Connecting to server: {server_name}")
            logger.debug(f"Server config: {server_config}")
            
            # Extract command and args from config
            command = server_config.get("command")
            args = server_config.get("args", [])
            cwd = server_config.get("cwd", ".")
            
            # Create server parameters
            server_params = StdioServerParameters(
                command=command,
                args=args,
                cwd=cwd
            )
            
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            read, write = stdio_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            
            logger.info(f"Initializing session for {server_name}")
            try:
                # Add a timeout for initialization
                initialization_task = asyncio.create_task(session.initialize())
                await asyncio.wait_for(initialization_task, timeout=10.0)  # 10 second timeout
                logger.info(f"Session initialized for {server_name}")
            except asyncio.TimeoutError:
                logger.error(f"Timeout initializing session for {server_name}")
                print(f"Timeout initializing session for {server_name}")
                return
            except Exception as e:
                logger.error(f"Error initializing session for {server_name}: {e}")
                print(f"Error initializing session for {server_name}: {e}")
                return
            
            try:
                # List available tools
                logger.info(f"Listing tools for {server_name}")
                response = await session.list_tools()
                logger.debug(f"Tools response: {response}")
                
                if hasattr(response, 'tools'):
                    for tool in response.tools:
                        self.sessions[tool.name] = session
                        
                        # Convert MCP tool to OpenAI tool format
                        openai_tool = {
                            "type": "function",
                            "function": {
                                "name": tool.name,
                                "description": tool.description,
                                "parameters": tool.inputSchema
                            }
                        }
                        self.available_tools.append(openai_tool)
                        logger.info(f"Added tool: {tool.name}")
                else:
                    logger.warning(f"No tools found in response: {response}")
            
                # List available prompts
                logger.info(f"Listing prompts for {server_name}")
                try:
                    # Check if the server supports list_prompts
                    if hasattr(session, 'list_prompts'):
                        prompts_response = await session.list_prompts()
                        logger.debug(f"Prompts response: {prompts_response}")
                        
                        if prompts_response and hasattr(prompts_response, 'prompts') and prompts_response.prompts:
                            for prompt in prompts_response.prompts:
                                self.sessions[prompt.name] = session
                                self.available_prompts.append({
                                    "name": prompt.name,
                                    "description": prompt.description,
                                    "arguments": prompt.arguments
                                })
                                logger.info(f"Added prompt: {prompt.name}")
                    else:
                        logger.info(f"Server {server_name} does not support list_prompts")
                except Exception as e:
                    if "Method not found" in str(e):
                        logger.info(f"Server {server_name} does not support list_prompts")
                    else:
                        logger.error(f"Error listing prompts: {e}")
                
                # List available resources
                logger.info(f"Listing resources for {server_name}")
                try:
                    # Check if the server supports list_resources
                    if hasattr(session, 'list_resources'):
                        resources_response = await session.list_resources()
                        logger.debug(f"Resources response: {resources_response}")
                        
                        if resources_response and hasattr(resources_response, 'resources') and resources_response.resources:
                            for resource in resources_response.resources:
                                resource_uri = str(resource.uri)
                                self.sessions[resource_uri] = session
                                logger.info(f"Added resource: {resource_uri}")
                    else:
                        logger.info(f"Server {server_name} does not support list_resources")
                except Exception as e:
                    if "Method not found" in str(e):
                        logger.info(f"Server {server_name} does not support list_resources")
                    else:
                        logger.error(f"Error listing resources: {e}")
                
            except Exception as e:
                logger.error(f"Error during server capabilities discovery: {e}")
                
        except Exception as e:
            logger.error(f"Error connecting to {server_name}: {e}")

    async def connect_to_servers(self):
        try:
            logger.info("Loading server configuration")
            with open("server_config.json", "r") as file:
                data = json.load(file)
            servers = data.get("mcpServers", {})
            logger.info(f"Found {len(servers)} servers in config")
            
            # Connect to servers with timeout
            for server_name, server_config in servers.items():
                try:
                    # Set a timeout for each server connection
                    connection_task = asyncio.create_task(
                        self.connect_to_server(server_name, server_config)
                    )
                    await asyncio.wait_for(connection_task, timeout=30.0)  # 30 second timeout
                except asyncio.TimeoutError:
                    logger.error(f"Timeout connecting to server: {server_name}")
                    print(f"Timeout connecting to server: {server_name}")
                except Exception as e:
                    logger.error(f"Error connecting to server {server_name}: {e}")
                    print(f"Error connecting to server {server_name}: {e}")
        except Exception as e:
            logger.error(f"Error loading server config: {e}")
            print(f"Error loading server config: {e}")
    
    async def process_query(self, query):
        logger.info(f"Processing query: {query}")
        
        # Initialize with system message if history is empty
        if not self.message_history:
            self.message_history.append({
                "role": "system", 
                "content": "You are an AI assistant with access to various tools and resources through the Model Context Protocol (MCP). You can search for academic papers, access the filesystem, and more. Be helpful, concise, and accurate."
            })
        
        # Add user message to history
        self.message_history.append({"role": "user", "content": query})
        
        while True:
            logger.info("Sending request to OpenAI")
            try:
                # Check if we're using the new OpenAI client or the fallback
                if hasattr(self.openai, 'chat') and hasattr(self.openai.chat, 'completions'):
                    # New OpenAI client (1.x)
                    response = self.openai.chat.completions.create(
                        model="gpt-4o",
                        messages=self.message_history,
                        tools=self.available_tools if self.available_tools else None,
                        tool_choice="auto"
                    )
                    message = response.choices[0].message
                    # Add assistant message to history
                    self.message_history.append(message.model_dump())
                else:
                    # Fallback to older OpenAI client
                    response = self.openai.ChatCompletion.create(
                        model="gpt-4o",
                        messages=self.message_history,
                        functions=[tool["function"] for tool in self.available_tools] if self.available_tools else None,
                        function_call="auto"
                    )
                    message = response.choices[0].message
                    # Add assistant message to history
                    self.message_history.append(dict(message))
                
                # Check if the model wants to call a tool
                has_tool_calls = False
                tool_calls = []
                
                # Handle both new and old API formats
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    has_tool_calls = True
                    tool_calls = message.tool_calls
                elif hasattr(message, 'function_call') and message.function_call:
                    has_tool_calls = True
                    # Convert old format to new format
                    tool_calls = [{
                        "id": "call_" + str(len(self.message_history)),
                        "function": {
                            "name": message.function_call.name,
                            "arguments": message.function_call.arguments
                        }
                    }]
                
                if has_tool_calls:
                    # Process each tool call
                    for tool_call in tool_calls:
                        # Extract function name and arguments based on API version
                        if hasattr(tool_call, 'function'):
                            function_name = tool_call.function.name
                            function_args = json.loads(tool_call.function.arguments)
                            tool_call_id = tool_call.id
                        else:
                            function_name = tool_call["function"]["name"]
                            function_args = json.loads(tool_call["function"]["arguments"])
                            tool_call_id = tool_call["id"]
                        
                        logger.info(f"Tool call requested: {function_name}")
                        print(f"\nCalling tool: {function_name}")
                        
                        # Get the session for this tool
                        session = self.sessions.get(function_name)
                        if not session:
                            error_msg = f"Tool '{function_name}' not found."
                            logger.error(error_msg)
                            print(error_msg)
                            
                            # Add tool result to history
                            self.message_history.append({
                                "role": "tool",
                                "tool_call_id": tool_call_id,
                                "name": function_name,
                                "content": error_msg
                            })
                            continue
                        
                        try:
                            # Call the tool via MCP
                            logger.info(f"Calling tool {function_name} with args: {function_args}")
                            result = await session.call_tool(function_name, arguments=function_args)
                            
                            # Add tool result to history
                            tool_result = {
                                "role": "tool",
                                "tool_call_id": tool_call_id,
                                "name": function_name,
                                "content": result.content
                            }
                            self.message_history.append(tool_result)
                            logger.info(f"Tool result: {result.content[:100]}...")
                            print(f"Tool result: {result.content[:100]}...")
                            
                        except Exception as e:
                            error_msg = f"Error calling tool {function_name}: {str(e)}"
                            logger.error(error_msg)
                            print(error_msg)
                            
                            # Add error message as tool result
                            self.message_history.append({
                                "role": "tool",
                                "tool_call_id": tool_call_id,
                                "name": function_name,
                                "content": f"Error: {str(e)}"
                            })
                    
                    # Continue the conversation with tool results
                    continue
                else:
                    # No tool calls, just print the response
                    content = message.content if hasattr(message, 'content') else message["content"]
                    print(f"\nAssistant: {content}")
                    break
                    
            except Exception as e:
                logger.error(f"Error in OpenAI API call: {e}")
                print(f"\nError: {str(e)}")
                break

    async def get_resource(self, resource_uri):
        logger.info(f"Getting resource: {resource_uri}")
        session = self.sessions.get(resource_uri)
        
        # Fallback for papers URIs - try any papers resource session
        if not session and resource_uri.startswith("papers://"):
            for uri, sess in self.sessions.items():
                if uri.startswith("papers://"):
                    session = sess
                    break
            
        if not session:
            logger.error(f"Resource '{resource_uri}' not found.")
            print(f"Resource '{resource_uri}' not found.")
            return
        
        try:
            logger.info(f"Reading resource: {resource_uri}")
            result = await session.read_resource(uri=resource_uri)
            logger.debug(f"Resource result: {result}")
            
            if result and hasattr(result, 'contents') and result.contents:
                print(f"\nResource: {resource_uri}")
                print("Content:")
                print(result.contents[0].text)
            else:
                logger.warning(f"No content available for resource: {resource_uri}")
                print("No content available.")
        except Exception as e:
            logger.error(f"Error reading resource: {e}")
            print(f"Error: {e}")
    
    async def list_prompts(self):
        """List all available prompts."""
        logger.info("Listing prompts")
        if not self.available_prompts:
            print("No prompts available.")
            return
        
        print("\nAvailable prompts:")
        for prompt in self.available_prompts:
            print(f"- {prompt['name']}: {prompt['description']}")
            if prompt['arguments']:
                print(f"  Arguments:")
                for arg in prompt['arguments']:
                    arg_name = arg.name if hasattr(arg, 'name') else arg.get('name', '')
                    print(f"    - {arg_name}")
    
    async def execute_prompt(self, prompt_name, args):
        """Execute a prompt with the given arguments."""
        logger.info(f"Executing prompt: {prompt_name} with args: {args}")
        session = self.sessions.get(prompt_name)
        if not session:
            logger.error(f"Prompt '{prompt_name}' not found.")
            print(f"Prompt '{prompt_name}' not found.")
            return
        
        try:
            logger.info(f"Getting prompt: {prompt_name}")
            result = await session.get_prompt(prompt_name, arguments=args)
            logger.debug(f"Prompt result: {result}")
            
            if result and hasattr(result, 'messages') and result.messages:
                prompt_content = result.messages[0].content
                
                # Extract text from content (handles different formats)
                if isinstance(prompt_content, str):
                    text = prompt_content
                elif hasattr(prompt_content, 'text'):
                    text = prompt_content.text
                else:
                    # Handle list of content items
                    text = " ".join(item.text if hasattr(item, 'text') else str(item) 
                                  for item in prompt_content)
                
                print(f"\nExecuting prompt '{prompt_name}'...")
                await self.process_query(text)
            else:
                logger.warning(f"No messages in prompt result: {result}")
                print(f"No content available for prompt: {prompt_name}")
        except Exception as e:
            logger.error(f"Error executing prompt: {e}")
            print(f"Error: {e}")
    
    async def chat_loop(self):
        print("\nMCP Chatbot Started with OpenAI GPT-4o!")
        print("Type your queries or 'quit' to exit.")
        print("Use @folders to see available topics")
        print("Use @<topic> to search papers in that topic")
        print("Use /prompts to list available prompts")
        print("Use /prompt <name> <arg1=value1> to execute a prompt")
        print("Use /clear to clear conversation history")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
                if not query:
                    continue
        
                if query.lower() == 'quit':
                    break
                
                # Check for @resource syntax first
                if query.startswith('@'):
                    # Remove @ sign  
                    topic = query[1:]
                    if topic == "folders":
                        resource_uri = "papers://folders"
                    else:
                        resource_uri = f"papers://{topic}"
                    await self.get_resource(resource_uri)
                    continue
                
                # Check for /command syntax
                if query.startswith('/'):
                    parts = query.split()
                    command = parts[0].lower()
                    
                    if command == '/prompts':
                        await self.list_prompts()
                    elif command == '/prompt':
                        if len(parts) < 2:
                            print("Usage: /prompt <name> <arg1=value1> <arg2=value2>")
                            continue
                        
                        prompt_name = parts[1]
                        args = {}
                        
                        # Parse arguments
                        for arg in parts[2:]:
                            if '=' in arg:
                                key, value = arg.split('=', 1)
                                args[key] = value
                        
                        await self.execute_prompt(prompt_name, args)
                    elif command == '/clear':
                        self.message_history = []
                        print("Conversation history cleared.")
                    else:
                        print(f"Unknown command: {command}")
                    continue
                
                await self.process_query(query)
                    
            except Exception as e:
                logger.error(f"Error in chat loop: {e}")
                print(f"\nError: {str(e)}")
    
    async def cleanup(self):
        logger.info("Cleaning up resources")
        await self.exit_stack.aclose()


async def main():
    logger.info("Starting MCP Chatbot with OpenAI GPT-4o")
    chatbot = MCP_ChatBot()
    try:
        await chatbot.connect_to_servers()
        
        # Print debug information
        print("\n=== Debug Information ===")
        print(f"Connected servers: {len(chatbot.sessions)}")
        print(f"Available tools: {len(chatbot.available_tools)}")
        for tool in chatbot.available_tools:
            print(f"  - {tool['function']['name']}: {tool['function']['description']}")
        print(f"Available prompts: {len(chatbot.available_prompts)}")
        for prompt in chatbot.available_prompts:
            print(f"  - {prompt['name']}: {prompt['description']}")
        print("========================\n")
        
        await chatbot.chat_loop()
    finally:
        await chatbot.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
