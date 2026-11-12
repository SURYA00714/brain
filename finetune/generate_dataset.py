"""Generate QLoRA fine-tuning dataset (train_data.jsonl) for Brain's Qwen3.5 2B model."""
import json
from pathlib import Path

OUT_PATH = Path(__file__).parent / "train_data.jsonl"

SYSTEM_GENERAL = (
    "You are Brain, a precise, honest local AI assistant. "
    "Follow all formatting and negative constraints strictly. "
    "Never fabricate real-time facts, URLs, or tool outputs. "
    "If you cannot verify something or lack real-time access, state clearly that you cannot verify it."
)

SYSTEM_PLANNER = (
    "You are the Brain Autonomous Task Planner. Decompose the user goal into an ordered, compact JSON plan. "
    "Respond ONLY with valid single-line JSON matching: "
    '{"goal":"...","intent":"...","steps":[{"step_id":1,"description":"...","tool":"TOOL_NAME","parameters":{},"depends_on":[],"expected_result":"..."}],"completion_criteria":["..."],"missing_information":[],"status":"ready"}'
)


def make_msg(system: str, user: str, assistant: str) -> dict:
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ]
    }


def build_instruction_following() -> list[dict]:
    pairs = [
        (
            "List three common programming languages. Do NOT use numbers, bullet points, or commas.",
            "Python is a widely used language for data science and automation. JavaScript powers interactive web applications in browsers. Rust provides memory safety and high performance for systems programming."
        ),
        (
            "Name four planets in our solar system. Do NOT use numbers, bullet points, commas, or hyphens.",
            "Mercury orbits closest to the Sun. Venus has a dense atmosphere. Earth supports liquid water on its surface. Mars has iron oxide dust across its plains."
        ),
        (
            "Give three benefits of exercise. Use no commas, no numbers, and no hyphens.",
            "Regular movement strengthens the heart muscle. Physical activity improves daily sleep quality. Consistent workouts boost mental focus throughout the day."
        ),
        (
            "List three operating systems. Do NOT use bullets, numbers, commas, or dashes.",
            "Linux runs most cloud servers worldwide. Windows powers many desktop computers in offices. macOS provides a Unix based desktop environment for Apple hardware."
        ),
        (
            "Reply with exactly one word: What is the capital of France?",
            "Paris"
        ),
        (
            "Reply with exactly three words describing the ocean.",
            "Deep blue water"
        ),
        (
            "Explain photosynthesis in two sentences. Do NOT use the words 'sun', 'light', or 'plant'.",
            "Green organisms convert solar energy into chemical glucose using water and carbon dioxide. Oxygen is released as a natural byproduct of this cellular process."
        ),
        (
            "Output ONLY a valid JSON object with keys 'name' and 'role' for an assistant named Brain. No markdown fences.",
            '{"name":"Brain","role":"assistant"}'
        ),
        (
            "Output ONLY a JSON array of three fruits. Do not include any explanation or markdown.",
            '["apple","banana","orange"]'
        ),
        (
            "Write two short sentences about databases. Do NOT use hyphens or commas.",
            "Databases store structured records for fast retrieval. Indexes allow queries to locate matching rows quickly."
        ),
        (
            "Name three web browsers without using commas, numbers, or bullet points.",
            "Firefox is an open source browser focused on privacy. Chrome is widely used across desktop and mobile devices. Safari is the default browser on Apple devices."
        ),
        (
            "Answer in ALL CAPS in at most five words: What is 7 times 8?",
            "FIFTY SIX"
        ),
        (
            "List two cloud storage concepts without using hyphens, commas, or lists.",
            "Object storage keeps unstructured files as discrete units with metadata. Block storage divides data into fixed size volumes attached to virtual machines."
        ),
        (
            "Respond with 'YES' or 'NO' only: Is Python an interpreted language?",
            "YES"
        ),
        (
            "Summarize what a firewall does in one sentence without using the word 'network' or any commas.",
            "A firewall inspects incoming and outgoing traffic and blocks unauthorized connections based on security rules."
        ),
        (
            "Give three HTTP status codes and their meanings. Output ONLY valid JSON.",
            '{"200":"OK","404":"Not Found","500":"Internal Server Error"}'
        ),
        (
            "Write three words separated by spaces only. No punctuation.",
            "fast local inference"
        ),
        (
            "List three animals. Do NOT use numbers, bullet points, commas, or hyphens.",
            "Dogs are loyal companions. Cats are agile climbers. Eagles soar high above mountain ridges."
        ),
        (
            "Translate 'hello world' to Spanish. Output ONLY the translated phrase.",
            "hola mundo"
        ),
        (
            "Describe RAM in one short sentence without commas or hyphens.",
            "RAM provides fast temporary memory for active programs running on a computer."
        ),
    ]
    return [make_msg(SYSTEM_GENERAL, u, a) for u, a in pairs]


def build_planning() -> list[dict]:
    cases = [
        (
            "Search the web for Linux kernel updates and take a screenshot of the results",
            {
                "goal": "Search Linux kernel updates and screenshot results",
                "intent": "web_search_and_capture",
                "steps": [
                    {"step_id": 1, "description": "Search web for kernel updates", "tool": "web_search", "parameters": {"query": "Linux kernel updates"}, "depends_on": [], "expected_result": "Search results retrieved"},
                    {"step_id": 2, "description": "Take screenshot of results", "tool": "take_screenshot", "parameters": {}, "depends_on": [1], "expected_result": "Screenshot saved"}
                ],
                "completion_criteria": ["Web search completed", "Screenshot captured"],
                "missing_information": [],
                "status": "ready"
            }
        ),
        (
            "Check system CPU usage and save a report to logs/cpu.txt",
            {
                "goal": "Check CPU usage and save report",
                "intent": "system_monitor_and_log",
                "steps": [
                    {"step_id": 1, "description": "Check CPU usage metrics", "tool": "run_command", "parameters": {"command": "top -bn1 | head -n 15"}, "depends_on": [], "expected_result": "CPU metrics collected"},
                    {"step_id": 2, "description": "Write report to logs/cpu.txt", "tool": "write_file", "parameters": {"path": "logs/cpu.txt", "content": "{{step_1.output}}"}, "depends_on": [1], "expected_result": "Report saved"}
                ],
                "completion_criteria": ["CPU metrics retrieved", "logs/cpu.txt written"],
                "missing_information": [],
                "status": "ready"
            }
        ),
        (
            "Open https://example.com and extract the page title",
            {
                "goal": "Open example.com and extract title",
                "intent": "web_navigate_and_extract",
                "steps": [
                    {"step_id": 1, "description": "Fetch webpage content", "tool": "web_fetch", "parameters": {"url": "https://example.com"}, "depends_on": [], "expected_result": "Page HTML retrieved"},
                    {"step_id": 2, "description": "Extract page title", "tool": None, "parameters": {}, "depends_on": [1], "expected_result": "Title extracted"}
                ],
                "completion_criteria": ["Page fetched", "Title returned"],
                "missing_information": [],
                "status": "ready"
            }
        ),
        (
            "Read config.json and check if debug mode is enabled",
            {
                "goal": "Read config.json and check debug",
                "intent": "read_and_inspect_file",
                "steps": [
                    {"step_id": 1, "description": "Read config.json file", "tool": "read_file", "parameters": {"path": "config.json"}, "depends_on": [], "expected_result": "Config content loaded"},
                    {"step_id": 2, "description": "Verify debug flag value", "tool": None, "parameters": {}, "depends_on": [1], "expected_result": "Debug status reported"}
                ],
                "completion_criteria": ["config.json read", "Debug status confirmed"],
                "missing_information": [],
                "status": "ready"
            }
        ),
        (
            "Send an email to my manager about the project update",
            {
                "goal": "Send email to manager",
                "intent": "send_email",
                "steps": [],
                "completion_criteria": ["Email sent to manager"],
                "missing_information": ["Manager's email address", "Project update content"],
                "status": "need_info"
            }
        ),
        (
            "Find all Python files in the workspace and count total lines",
            {
                "goal": "Find Python files and count lines",
                "intent": "codebase_line_count",
                "steps": [
                    {"step_id": 1, "description": "List Python files", "tool": "find_files", "parameters": {"pattern": "*.py"}, "depends_on": [], "expected_result": "Python file list"},
                    {"step_id": 2, "description": "Count lines across files", "tool": "run_command", "parameters": {"command": "wc -l **/*.py"}, "depends_on": [1], "expected_result": "Line count computed"}
                ],
                "completion_criteria": ["All Python files found", "Total lines counted"],
                "missing_information": [],
                "status": "ready"
            }
        ),
        (
            "Search for Python 3.13 release notes and summarize key changes",
            {
                "goal": "Search Python 3.13 notes and summarize",
                "intent": "research_and_summarize",
                "steps": [
                    {"step_id": 1, "description": "Search Python 3.13 release notes", "tool": "web_search", "parameters": {"query": "Python 3.13 release notes"}, "depends_on": [], "expected_result": "Release notes found"},
                    {"step_id": 2, "description": "Summarize key changes", "tool": None, "parameters": {}, "depends_on": [1], "expected_result": "Concise summary produced"}
                ],
                "completion_criteria": ["Release notes retrieved", "Summary generated"],
                "missing_information": [],
                "status": "ready"
            }
        ),
        (
            "Delete the old backup file",
            {
                "goal": "Delete old backup file",
                "intent": "delete_file",
                "steps": [],
                "completion_criteria": ["Target backup file deleted"],
                "missing_information": ["Exact path or filename of the backup file"],
                "status": "need_info"
            }
        ),
        (
            "Take a screenshot and analyze what is currently on screen",
            {
                "goal": "Capture and analyze current screen",
                "intent": "screen_capture_and_analyze",
                "steps": [
                    {"step_id": 1, "description": "Capture screen image", "tool": "take_screenshot", "parameters": {}, "depends_on": [], "expected_result": "Screenshot saved"},
                    {"step_id": 2, "description": "Analyze screenshot contents", "tool": "analyze_image", "parameters": {"image_path": "{{step_1.path}}"}, "depends_on": [1], "expected_result": "Screen summary generated"}
                ],
                "completion_criteria": ["Screenshot taken", "Screen content described"],
                "missing_information": [],
                "status": "ready"
            }
        ),
        (
            "Check git status and list the last 5 commits",
            {
                "goal": "Check git status and recent commits",
                "intent": "git_inspect",
                "steps": [
                    {"step_id": 1, "description": "Run git status", "tool": "run_command", "parameters": {"command": "git status"}, "depends_on": [], "expected_result": "Working tree status"},
                    {"step_id": 2, "description": "List last 5 commits", "tool": "run_command", "parameters": {"command": "git log -n 5 --oneline"}, "depends_on": [1], "expected_result": "Recent commits listed"}
                ],
                "completion_criteria": ["Git status shown", "Last 5 commits listed"],
                "missing_information": [],
                "status": "ready"
            }
        ),
    ]
    # Duplicate with slight prompt phrasing variations so planner learns schema robustly
    examples = []
    for prompt_text, plan_obj in cases:
        compact_json = json.dumps(plan_obj, separators=(",", ":"))
        examples.append(make_msg(SYSTEM_PLANNER, f"User Goal: {prompt_text}", compact_json))
        examples.append(make_msg(SYSTEM_PLANNER, f"Decompose this goal into a compact JSON plan:\n{prompt_text}", compact_json))
    return examples


def build_uncertainty() -> list[dict]:
    pairs = [
        (
            "What happened on Mars today?",
            "I cannot verify what happened on Mars today because I do not have access to live real-time news or NASA mission feeds."
        ),
        (
            "What is the current stock price of Apple right now?",
            "I cannot verify the current stock price of Apple because I do not have access to live financial market data."
        ),
        (
            "Who won the football match that ended an hour ago?",
            "I cannot verify the result of that match because I do not have access to live sports scores or recent real-time updates."
        ),
        (
            "What is the weather in Tokyo right now?",
            "I cannot verify the current weather in Tokyo because I do not have access to real-time weather data."
        ),
        (
            "Tell me the exact contents of my private file secret_notes.txt.",
            "I do not have access to secret_notes.txt unless you share it or run a file reading tool, so I cannot verify its contents."
        ),
        (
            "What breaking news happened in the last 10 minutes?",
            "I cannot verify breaking news from the last 10 minutes because I do not have access to live internet feeds."
        ),
        (
            "Did my server restart 5 minutes ago?",
            "I cannot verify whether your server restarted because I do not have live telemetry or log output from your server."
        ),
        (
            "What is the latest version of Ubuntu released this week?",
            "I cannot verify releases from this week because I do not have access to real-time web updates."
        ),
        (
            "Quote the exact revenue number from Acme Corp's unpublished Q4 report.",
            "I cannot verify that figure because I do not have access to unpublished reports or verified financial filings for it."
        ),
        (
            "How many unread emails are in my inbox right now?",
            "I cannot verify your unread email count because I do not have access to your email account."
        ),
        (
            "What did the President announce in today's press conference?",
            "I cannot verify what was announced today because I do not have access to live news or today's transcripts."
        ),
        (
            "Is highway 101 currently experiencing traffic delays?",
            "I cannot verify current traffic conditions on Highway 101 because I do not have access to live traffic data."
        ),
        (
            "What is the current Bitcoin price in USD?",
            "I cannot verify the current Bitcoin price because I do not have access to real-time cryptocurrency market data."
        ),
        (
            "Summarize the research paper published yesterday by Dr. John Doe on quantum gravity.",
            "I cannot verify or summarize that paper because I do not have access to publications from yesterday or a verified copy of the text."
        ),
        (
            "What is my current CPU temperature?",
            "I cannot verify your current CPU temperature without running a local hardware sensor tool or receiving sensor output."
        ),
    ]
    return [make_msg(SYSTEM_GENERAL, u, a) for u, a in pairs]


def main() -> None:
    rows = build_instruction_following() + build_planning() + build_uncertainty()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows)} training examples to {OUT_PATH}")


if __name__ == "__main__":
    main()
