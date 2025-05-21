document.addEventListener("DOMContentLoaded", () => {
  // Import Socket.io, marked, and hljs
  const io = window.io
  const marked = window.marked
  const hljs = window.hljs

  // Socket.io connection
  const socket = io()

  // DOM elements
  const messagesContainer = document.getElementById("messages")
  const messageForm = document.getElementById("messageForm")
  const messageInput = document.getElementById("messageInput")
  const toolsList = document.getElementById("toolsList")
  const promptsList = document.getElementById("promptsList")
  const helpBtn = document.getElementById("helpBtn")
  const helpModal = document.getElementById("helpModal")
  const closeHelpBtn = document.getElementById("closeHelpBtn")
  const clearBtn = document.getElementById("clearBtn")
  const themeToggle = document.getElementById("themeToggle")
  const iconLight = document.querySelector(".icon-light")
  const iconDark = document.querySelector(".icon-dark")
  const codeThemeLight = document.getElementById("code-theme")
  const codeThemeDark = document.getElementById("code-theme-dark")

  // Theme handling
  function setTheme(theme) {
    if (theme === "dark") {
      document.documentElement.setAttribute("data-theme", "dark")
      iconLight.classList.add("hidden")
      iconDark.classList.remove("hidden")
      codeThemeLight.disabled = true
      codeThemeDark.disabled = false
    } else {
      document.documentElement.setAttribute("data-theme", "light")
      iconLight.classList.remove("hidden")
      iconDark.classList.add("hidden")
      codeThemeLight.disabled = false
      codeThemeDark.disabled = true
    }
    localStorage.setItem("theme", theme)
  }

  // Check for saved theme preference or respect OS preference
  const savedTheme = localStorage.getItem("theme")
  if (savedTheme) {
    setTheme(savedTheme)
  } else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    setTheme("dark")
  }

  // Theme toggle event listener
  themeToggle.addEventListener("click", () => {
    const currentTheme = document.documentElement.getAttribute("data-theme")
    setTheme(currentTheme === "dark" ? "light" : "dark")

    // Re-apply syntax highlighting to existing code blocks with new theme
    document.querySelectorAll("pre code").forEach((block) => {
      hljs.highlightElement(block)
    })
  })

  // Connect to socket
  socket.on("connect", () => {
    console.log("Connected to server")
    addSystemMessage(
      "Connected to MCP Research Chatbot. Type a message to begin or use @folders to see available topics.",
    )
  })

  // Handle initialization data
  socket.on("initialization", (data) => {
    console.log("Received initialization data:", data)

    // Populate tools list
    if (data.tools && data.tools.length > 0) {
      toolsList.innerHTML = ""
      data.tools.forEach((tool) => {
        const toolElement = document.createElement("div")
        toolElement.className = "p-2 rounded text-xs"
        toolElement.innerHTML = `<strong>${tool.name}</strong>: ${tool.description}`
        toolsList.appendChild(toolElement)
      })
    } else {
      toolsList.innerHTML = '<div class="text-gray-500">No tools available</div>'
    }

    // Populate prompts list
    if (data.prompts && data.prompts.length > 0) {
      promptsList.innerHTML = ""
      data.prompts.forEach((prompt) => {
        const promptElement = document.createElement("div")
        promptElement.className = "p-2 rounded text-xs cursor-pointer hover:bg-gray-200"
        promptElement.innerHTML = `<strong>${prompt.name}</strong>: ${prompt.description}`
        promptElement.addEventListener("click", () => {
          messageInput.value = `/prompt ${prompt.name}`
          messageInput.focus()
        })
        promptsList.appendChild(promptElement)
      })
    } else {
      promptsList.innerHTML = '<div class="text-gray-500">No prompts available</div>'
    }
  })

  // Handle incoming messages
  socket.on("message", (data) => {
    console.log("Received message:", data)
    removeTypingIndicator()

    if (data.role === "user") {
      addUserMessage(data.content)
    } else if (data.role === "assistant") {
      addAssistantMessage(data.content)
    }

    // Scroll to bottom
    scrollToBottom()
  })

  // Handle tool outputs
  socket.on("tool_output", (data) => {
    console.log("Received tool output:", data)
    if (data.content) {
      addToolOutput(data.content)
      scrollToBottom()
    }
  })

  // Handle form submission
  messageForm.addEventListener("submit", (e) => {
    e.preventDefault()
    const message = messageInput.value.trim()

    if (message) {
      // Send message to server
      socket.emit("message", { message })

      // Clear input
      messageInput.value = ""

      // Show typing indicator
      addTypingIndicator()

      // Scroll to bottom
      scrollToBottom()
    }
  })

  // Handle command items in sidebar
  document.querySelectorAll(".command-item").forEach((item) => {
    item.addEventListener("click", () => {
      const command = item.getAttribute("data-command")
      messageInput.value = command
      messageInput.focus()
    })
  })

  // Help modal
  helpBtn.addEventListener("click", () => {
    helpModal.classList.remove("hidden")
  })

  closeHelpBtn.addEventListener("click", () => {
    helpModal.classList.add("hidden")
  })

  // Close modal when clicking outside
  helpModal.addEventListener("click", (e) => {
    if (e.target === helpModal) {
      helpModal.classList.add("hidden")
    }
  })

  // Clear chat
  clearBtn.addEventListener("click", () => {
    // Send clear command
    socket.emit("message", { message: "/clear" })

    // Clear UI
    messagesContainer.innerHTML = ""
    addSystemMessage("Chat history cleared.")
  })

  // Helper functions
  function addUserMessage(content) {
    const messageDiv = document.createElement("div")
    messageDiv.className = "flex justify-end"
    messageDiv.innerHTML = `
            <div class="message user-message">
                <div class="font-semibold">You</div>
                <div>${escapeHTML(content)}</div>
            </div>
        `
    messagesContainer.appendChild(messageDiv)
  }

  function addAssistantMessage(content) {
    const messageDiv = document.createElement("div")
    messageDiv.className = "flex justify-start"

    // Process content with marked for Markdown
    const processedContent = marked.parse(content)

    messageDiv.innerHTML = `
            <div class="message assistant-message">
                <div class="font-semibold">Assistant</div>
                <div class="markdown-content">${processedContent}</div>
            </div>
        `
    messagesContainer.appendChild(messageDiv)

    // Apply syntax highlighting to code blocks
    messageDiv.querySelectorAll("pre code").forEach((block) => {
      hljs.highlightElement(block)
    })
  }

  function addSystemMessage(content) {
    const messageDiv = document.createElement("div")
    messageDiv.className = "flex justify-center my-2"
    messageDiv.innerHTML = `
            <div class="px-4 py-2 rounded-full text-sm">
                ${escapeHTML(content)}
            </div>
        `
    messagesContainer.appendChild(messageDiv)
  }

  function addToolOutput(content) {
    const outputDiv = document.createElement("div")
    outputDiv.className = "flex justify-start"
    outputDiv.innerHTML = `
            <div class="tool-output">
                ${escapeHTML(content)}
            </div>
        `
    messagesContainer.appendChild(outputDiv)
  }

  function addTypingIndicator() {
    removeTypingIndicator() // Remove any existing indicator

    const indicatorDiv = document.createElement("div")
    indicatorDiv.className = "typing-indicator"
    indicatorDiv.id = "typingIndicator"
    indicatorDiv.innerHTML = `
            <span></span>
            <span></span>
            <span></span>
        `
    messagesContainer.appendChild(indicatorDiv)
    scrollToBottom()
  }

  function removeTypingIndicator() {
    const indicator = document.getElementById("typingIndicator")
    if (indicator) {
      indicator.remove()
    }
  }

  function scrollToBottom() {
    const chatContainer = document.getElementById("chatContainer")
    chatContainer.scrollTop = chatContainer.scrollHeight
  }

  function escapeHTML(text) {
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;")
  }
})
