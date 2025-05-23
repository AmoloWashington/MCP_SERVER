# MCP_SERVER
# MCP Research Chatbot with Web Interface

This project provides a web-based GUI for the MCP (Model Context Protocol) Research Chatbot, replacing the command-line interface with a modern web application.

## Features

- Real-time chat interface using WebSockets
- Markdown rendering for formatted responses
- Syntax highlighting for code blocks
- Support for all MCP commands (@folders, @topics, /prompts, etc.)
- Sidebar with available tools and prompts
- Responsive design that works on desktop and mobile

## Installation

1. Clone the repository:
\`\`\`bash
git clone <repository-url>
cd mcp-chatbot
\`\`\`

2. Install the required dependencies:
\`\`\`bash
pip install -r requirements.txt
\`\`\`

3. Make sure you have an OpenAI API key in your `.env` file:
\`\`\`
OPENAI_API_KEY=your_api_key_here
\`\`\`

## Usage

1. Start the web server:
\`\`\`bash
python app.py
\`\`\`

2. Open your browser and navigate to:
\`\`\`
http://localhost:5000
\`\`\`

3. The chatbot will automatically connect to the configured MCP servers and display available tools and prompts in the sidebar.

## Commands

- `@folders` - List all available paper topics
- `@<topic>` - View papers for a specific topic
- `/prompts` - List all available prompts
- `/prompt <name> <arg1=value1>` - Execute a specific prompt
- `/clear` - Clear conversation history

## Project Structure

- `app.py` - Main Flask application
- `templates/index.html` - HTML template for the web interface
- `static/css/styles.css` - CSS styles for the interface
- `static/js/main.js` - JavaScript for handling WebSocket communication and UI updates
- `mcp_chatbot.py` - Original MCP chatbot implementation (used as a backend)
- `research_server.py` - MCP server for academic paper research

## Dependencies

- Flask - Web framework
- Flask-SocketIO - WebSocket support for real-time communication
- OpenAI - For AI model access
- Arxiv - For academic paper searches
- Marked.js (client-side) - For Markdown rendering
- Highlight.js (client-side) - For syntax highlighting
