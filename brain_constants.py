"""
Brain System Constants.
Single source of truth for tool groupings, safety boundaries, and execution limits.
"""

# Tools that modify physical GUI state, window focus, or desktop appearance
UI_MODIFYING_TOOLS = frozenset({
    "OPEN_APP", "CLOSE_APP", "FOCUS_APP", "CLICK", "DOUBLE_CLICK",
    "CLICK_ELEMENT", "TYPE_TEXT", "TYPE_IN_ELEMENT", "PRESS_KEY",
    "HOTKEY", "SCROLL", "BROWSER_SEARCH", "BROWSER_NAVIGATE",
    "BROWSER_SEARCH_FOREGROUND"
})

# Destructive system operations requiring strict safety gates
DESTRUCTIVE_TOOLS = frozenset({
    "DELETE_FILE", "SHUTDOWN", "RESTART", "LOGOUT"
})

# Legacy supported intent types for planner validation
ALLOWED_INTENTS = frozenset({
    "OPEN_APP", "CLOSE_APP", "FOCUS_APP", "OPEN_BRAVE", "WEB_SEARCH",
    "BROWSER_SEARCH", "BROWSER_NAVIGATE", "BROWSER_SEARCH_FOREGROUND",
    "LIST_FILES", "FIND_FILES", "READ_TEXT_FILE", "CREATE_FOLDER",
    "CHAT", "TIME", "SCREENSHOT", "ANALYZE_SCREEN", "REMEMBER"
})

# Keywords indicating explicit visual GUI browser interaction
APPROVED_BROWSER_KEYWORDS = (
    "in brave", "use brave", "open brave", "open browser",
    "in browser", "using brave", "visibly", "in the browser"
)

# Pipeline execution bounds
MAX_STEPS = 10
MAX_RECOVERY_ATTEMPTS = 2
