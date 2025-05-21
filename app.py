from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit
import asyncio
import json
import os
from dotenv import load_dotenv
import logging
from mcp_chatbot import MCP_ChatBot
import nest_asyncio
import functools

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('mcp_chatbot_web')

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
socketio = SocketIO(app, cors_allowed_origins="*")  # Let Flask-SocketIO choose the best async mode

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

# Load environment variables
load_dotenv()

# Initialize chatbot
chatbot = None
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

def initialize_chatbot():
    global chatbot
    if chatbot is None:
        chatbot = MCP_ChatBot()
        loop.run_until_complete(chatbot.connect_to_servers())
        logger.info("Chatbot initialized")
    return chatbot

@app.route('/')
def index():
    return render_template('index.html')

# Helper function to run async functions and handle errors
def async_task(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        try:
            return loop.run_until_complete(f(*args, **kwargs))
        except Exception as e:
            logger.error(f"Error in async task: {e}")
            return {"error": str(e)}
    return wrapped

@socketio.on('connect')
def handle_connect():
    logger.info("Client connected")
    initialize_chatbot()
    
    # Convert prompt arguments to JSON-serializable format
    serializable_prompts = []
    for prompt in chatbot.available_prompts:
        serializable_args = []
        if 'arguments' in prompt and prompt['arguments']:
            for arg in prompt['arguments']:
                # Handle both object and dict formats
                if hasattr(arg, 'name'):
                    arg_name = arg.name
                    arg_required = arg.required if hasattr(arg, 'required') else False
                    arg_description = arg.description if hasattr(arg, 'description') else None
                else:
                    arg_name = arg.get('name', '')
                    arg_required = arg.get('required', False)
                    arg_description = arg.get('description', None)
                
                serializable_args.append({
                    'name': arg_name,
                    'required': arg_required,
                    'description': arg_description
                })
        
        serializable_prompts.append({
            'name': prompt['name'],
            'description': prompt['description'],
            'arguments': serializable_args
        })
    
    # Send available tools and prompts to the client
    emit('initialization', {
        'tools': [{'name': tool['function']['name'], 
                  'description': tool['function']['description']} 
                 for tool in chatbot.available_tools],
        'prompts': serializable_prompts
    })

@socketio.on('message')
def handle_message(data):
    logger.info(f"Received message: {data}")
    query = data.get('message', '').strip()
    
    if not query:
        return
    
    # Emit the user message back to confirm receipt
    emit('message', {'role': 'user', 'content': query})
    
    # Handle special commands
    if query.startswith('@'):
        # Resource request
        topic = query[1:]
        if topic == "folders":
            resource_uri = "papers://folders"
        else:
            resource_uri = f"papers://{topic}"
        
        # Define a function to handle the resource request
        def handle_resource_request():
            # Use a synchronous approach to capture output
            import io
            import sys
            from contextlib import redirect_stdout
            
            # Capture stdout
            f = io.StringIO()
            with redirect_stdout(f):
                # Run the async function in the event loop
                loop.run_until_complete(chatbot.get_resource(resource_uri))
            
            # Get the captured output
            output = f.getvalue()
            return output
        
        try:
            # Get the resource content
            content = handle_resource_request()
            emit('message', {'role': 'assistant', 'content': content})
        except Exception as e:
            logger.error(f"Error getting resource: {e}")
            emit('message', {'role': 'assistant', 'content': f"Error: {str(e)}"})
        
    elif query.startswith('/'):
        parts = query.split()
        command = parts[0].lower()
        
        if command == '/prompts':
            # Define a function to handle the prompts request
            def handle_prompts_request():
                # Use a synchronous approach to capture output
                import io
                import sys
                from contextlib import redirect_stdout
                
                # Capture stdout
                f = io.StringIO()
                with redirect_stdout(f):
                    # Run the async function in the event loop
                    loop.run_until_complete(chatbot.list_prompts())
                
                # Get the captured output
                output = f.getvalue()
                return output
            
            try:
                # Get the prompts content
                content = handle_prompts_request()
                emit('message', {'role': 'assistant', 'content': content})
            except Exception as e:
                logger.error(f"Error listing prompts: {e}")
                emit('message', {'role': 'assistant', 'content': f"Error: {str(e)}"})
            
        elif command == '/prompt':
            if len(parts) < 2:
                emit('message', {'role': 'assistant', 'content': "Usage: /prompt <name> <arg1=value1> <arg2=value2>"})
                return
            
            prompt_name = parts[1]
            args = {}
            
            # Parse arguments
            for arg in parts[2:]:
                if '=' in arg:
                    key, value = arg.split('=', 1)
                    args[key] = value
            
            # Define a function to handle the prompt execution
            def handle_prompt_execution():
                # Use a synchronous approach to capture output
                import io
                import sys
                from contextlib import redirect_stdout
                
                # Capture stdout
                f = io.StringIO()
                with redirect_stdout(f):
                    # Run the async function in the event loop
                    loop.run_until_complete(chatbot.execute_prompt(prompt_name, args))
                
                # Get the captured output
                output = f.getvalue()
                return output
            
            try:
                # Execute the prompt
                content = handle_prompt_execution()
                emit('message', {'role': 'assistant', 'content': content})
            except Exception as e:
                logger.error(f"Error executing prompt: {e}")
                emit('message', {'role': 'assistant', 'content': f"Error: {str(e)}"})
            
        elif command == '/clear':
            chatbot.message_history = []
            emit('message', {'role': 'assistant', 'content': "Conversation history cleared."})
            
        else:
            emit('message', {'role': 'assistant', 'content': f"Unknown command: {command}"})
    
    else:
        # Regular query
        def handle_query():
            # Use a synchronous approach to capture output
            import io
            import sys
            from contextlib import redirect_stdout
            
            # Capture stdout
            f = io.StringIO()
            with redirect_stdout(f):
                # Run the async function in the event loop
                loop.run_until_complete(chatbot.process_query(query))
            
            # Get the captured output
            output = f.getvalue()
            
            # Extract the assistant's response from the message history
            assistant_response = None
            if chatbot.message_history:
                for msg in reversed(chatbot.message_history):
                    if msg.get('role') == 'assistant' and msg.get('content'):
                        assistant_response = msg.get('content')
                        break
            
            # Get tool outputs
            tool_outputs = "\n".join([line for line in output.split('\n') if line.startswith("Tool result:") or line.startswith("Calling tool:")])
            
            return {
                "assistant_response": assistant_response,
                "tool_outputs": tool_outputs,
                "raw_output": output
            }
        
        try:
            # Process the query
            result = handle_query()
            
            if result.get("assistant_response"):
                emit('message', {'role': 'assistant', 'content': result["assistant_response"]})
            
            if result.get("tool_outputs"):
                emit('tool_output', {'content': result["tool_outputs"]})
                
            # If no assistant response but we have output, send that
            if not result.get("assistant_response") and result.get("raw_output"):
                emit('message', {'role': 'assistant', 'content': result["raw_output"]})
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            emit('message', {'role': 'assistant', 'content': f"Error: {str(e)}"})

@socketio.on('disconnect')
def handle_disconnect():
    logger.info("Client disconnected")

if __name__ == '__main__':
    # Initialize the chatbot before starting the server
    initialize_chatbot()
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
