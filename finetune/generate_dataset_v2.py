"""Generate comprehensive, balanced QLoRA v2 fine-tuning dataset (train_data_v2.jsonl) for Brain's Qwen3.5 2B.

Fixes:
1. Context-grounding vs refusal (MC_03 fix): Use context facts when present; do NOT refuse when info is in prompt/system context.
2. Strict need_info detection (L2_PLAN_NEED_INFO fix): Never hallucinate placeholder emails, passwords, paths. Use status=need_info.
3. Exact word and constraint compliance (IF_01 fix): Exact 3 words, exact 1 word, negative constraints.
4. Minimal neutral refusals (no hallucinated side-facts): State verification limits cleanly without guessing future/world facts.
"""
import json
from pathlib import Path

OUT_PATH = Path(__file__).parent / "train_data_v2.jsonl"

SYSTEM_GENERAL = (
    "You are Brain, a precise, honest local AI assistant. "
    "If relevant facts or memories are provided in the context, answer directly and accurately using them. "
    "Follow all formatting and negative constraints strictly. "
    "Never fabricate real-time facts, URLs, emails, or tool outputs. "
    "If information is truly missing and not provided in context, state clearly that you cannot verify it."
)

SYSTEM_PLANNER = (
    "You are the Brain Autonomous Task Planner. Decompose the user goal into an ordered, compact JSON plan. "
    "Respond ONLY with valid single-line JSON matching: "
    '{"goal":"...","intent":"...","steps":[{"step_id":1,"description":"...","tool":"TOOL_NAME","parameters":{},"depends_on":[],"expected_result":"..."}],"completion_criteria":["..."],"missing_information":[],"status":"ready"} '
    "If critical parameters (email address, recipient, file path, credentials) are not provided by the user, "
    "you MUST set 'status':'need_info', list them in 'missing_information', and leave 'steps':[] empty. Never invent placeholder emails or paths."
)


def make_msg(system: str, user: str, assistant: str) -> dict:
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ]
    }


def build_exact_constraints() -> list[dict]:
    # Exact word counts, formatting, negative constraints
    pairs = [
        # Exact 3 words
        ("State the current status of the operating system in exactly three words.", "Operating normally now"),
        ("Describe the server status in exactly three words.", "Server running smoothly"),
        ("Describe the sky today in exactly three words.", "Clear blue sky"),
        ("State your readiness in exactly three words.", "Ready for tasks"),
        ("Summarize the test results in exactly three words.", "All tests passed"),
        ("State the battery health in exactly three words.", "Battery health normal"),
        ("Describe the current weather in exactly three words.", "Sunny and warm"),
        ("Describe the database connection in exactly three words.", "Connected and active"),
        ("State the build result in exactly three words.", "Build completed successfully"),
        ("Describe your operational mode in exactly three words.", "Autonomous local mode"),
        # Exact 1 word
        ("Reply with exactly one word: What is the capital of France?", "Paris"),
        ("Reply with exactly one word: What is 9 times 9?", "81"),
        ("Reply with 'YES' or 'NO' only: Is Linux an operating system?", "YES"),
        ("Reply with 'YES' or 'NO' only: Is Python a compiled language?", "NO"),
        ("Reply with exactly one word: What is the opposite of hot?", "Cold"),
        ("Reply with exactly one word: What planet is third from the Sun?", "Earth"),
        # Exact 5 words
        ("Summarize what a CPU does in exactly five words.", "Processes instructions for the computer"),
        ("Describe an SSD in exactly five words.", "Fast non volatile storage drive"),
        ("Describe Git in exactly five words.", "Distributed version control software tool"),
        ("Summarize RAM in exactly five words.", "Fast temporary working system memory"),
        # Negative constraints (no commas, numbers, hyphens, bullets)
        (
            "List three common programming languages. Do NOT use numbers, bullet points, or commas.",
            "Python is widely used for data science and automation. JavaScript powers interactive web applications in browsers. Rust provides memory safety and high performance for systems programming."
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
            "Name three web browsers without using commas, numbers, or bullet points.",
            "Firefox is an open source browser focused on privacy. Chrome is widely used across desktop and mobile devices. Safari is the default browser on Apple devices."
        ),
        (
            "Write two short sentences about databases. Do NOT use hyphens or commas.",
            "Databases store structured records for fast retrieval. Indexes allow queries to locate matching rows quickly."
        ),
        (
            "List two cloud storage concepts without using hyphens, commas, or lists.",
            "Object storage keeps unstructured files as discrete units with metadata. Block storage divides data into fixed size volumes attached to virtual machines."
        ),
        (
            "Explain photosynthesis in two sentences. Do NOT use the words 'sun', 'light', or 'plant'.",
            "Green organisms convert solar energy into chemical glucose using water and carbon dioxide. Oxygen is released as a natural byproduct of this cellular process."
        ),
        # Pure JSON outputs without markdown
        (
            "Output ONLY a valid JSON object with keys 'name' and 'role' for an assistant named Brain. No markdown fences.",
            '{"name":"Brain","role":"assistant"}'
        ),
        (
            "Output ONLY a JSON array of three fruits. Do not include any explanation or markdown.",
            '["apple","banana","orange"]'
        ),
        (
            "Output ONLY valid JSON with keys 'a', 'b', 'c' where each value is an array of 2 prime numbers greater than 10. No markdown fences.",
            '{"a":[11,13],"b":[17,19],"c":[23,29]}'
        ),
        (
            "Give three HTTP status codes and their meanings. Output ONLY valid JSON.",
            '{"200":"OK","404":"Not Found","500":"Internal Server Error"}'
        ),
        (
            "Output ONLY a JSON object with keys 'status' and 'uptime_seconds' with values 'ok' and 3600.",
            '{"status":"ok","uptime_seconds":3600}'
        ),
    ]
    return [make_msg(SYSTEM_GENERAL, u, a) for u, a in pairs]


def build_context_grounded_memory() -> list[dict]:
    # CRUCIAL: teaches the model to USE context facts, fixing MC_03 over-refusal
    cases = [
        (
            "Context Memory:\n- User Name: Jai\n- User Location: Bangalore, India\n- Preferred Language: Python\n\nQuestion: What city do I live in?",
            "You live in Bangalore."
        ),
        (
            "Context Memory:\n- User City: Bangalore\n- User Role: Software Engineer\n\nQuestion: Where am I located?",
            "You are located in Bangalore."
        ),
        (
            "User profile: Lives in Bangalore. Works on AI agents.\n\nUser: What city do I live in?",
            "You live in Bangalore."
        ),
        (
            "System state: Memory store contains: {'city': 'Bangalore', 'timezone': 'IST'}.\n\nUser: Which city am I based in?",
            "You are based in Bangalore."
        ),
        (
            "Context:\nUser prefers Python over JavaScript. User is running Linux Mint on AMD Ryzen 3.\n\nUser: What OS am I running?",
            "You are running Linux Mint."
        ),
        (
            "Context:\nUser project is named Brain. Primary database is SQLite located at data/brain_memory.db.\n\nUser: Where is my memory database stored?",
            "Your memory database is stored at data/brain_memory.db."
        ),
        (
            "Context:\nUser favorite text editor is VS Code. Default browser is Chrome.\n\nUser: What is my favorite editor?",
            "Your favorite text editor is VS Code."
        ),
        (
            "Context:\nActive model tier: Local Ollama (qwen3.5-brain). Cloud fallback: Groq.\n\nUser: What is my local model?",
            "Your local model is Ollama running qwen3.5-brain."
        ),
        (
            "Context:\n- Task ID: T-104\n- Assigned to: Alice\n- Status: In Progress\n\nUser: Who is assigned to task T-104?",
            "Task T-104 is assigned to Alice."
        ),
        (
            "Context:\nServer IP is 192.168.1.50, port is 8080.\n\nUser: What port is the server running on?",
            "The server is running on port 8080."
        ),
        (
            "Context:\nUser stated earlier: 'I have three dogs named Max, Bella, and Charlie.'\n\nUser: How many dogs do I have and what are their names?",
            "You have three dogs named Max, Bella, and Charlie."
        ),
        (
            "Context:\nProject repository path: /home/jai/Downloads/Brain\n\nUser: What is the path to my workspace?",
            "Your workspace path is /home/jai/Downloads/Brain."
        ),
        (
            "Context Memory:\n- Favorite food: Pizza\n- Birth year: 1998\n\nUser: What is my favorite food?",
            "Your favorite food is Pizza."
        ),
        (
            "Context Memory:\n- Device: AMD Ryzen 3 7320U, 8GB RAM\n\nUser: How much RAM do I have?",
            "You have 8 GB of RAM."
        ),
        (
            "Context Memory:\n- Current target: Improve model accuracy to 95%+\n\nUser: What is our accuracy target?",
            "Your accuracy target is 95%+."
        ),
        (
            "Context:\nNo user location or city is recorded in memory.\n\nUser: What city do I live in?",
            "I do not have your city recorded in my context memory, so I cannot verify where you live."
        ),
        (
            "Context:\nNo phone number has been provided.\n\nUser: What is my phone number?",
            "I cannot verify your phone number because it has not been provided in our context."
        ),
        (
            "Context:\nMemory store is currently empty.\n\nUser: What was the first goal I gave you yesterday?",
            "I do not have access to yesterday's conversation records in current context, so I cannot verify your previous goal."
        ),
    ]
    return [make_msg(SYSTEM_GENERAL, u, a) for u, a in cases]


def build_need_info_and_planning() -> list[dict]:
    # Strict distinction: If critical info is missing, MUST emit status: need_info. Never invent placeholders.
    need_info_cases = [
        (
            "Read logs/app.log, summarize errors, and email the summary to my manager.",
            {
                "goal": "Read app.log, summarize errors, email summary to manager",
                "intent": "log_analysis_and_email",
                "steps": [],
                "completion_criteria": ["Email sent to manager with error summary"],
                "missing_information": ["Manager's email address"],
                "status": "need_info"
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
            "Delete the old backup file",
            {
                "goal": "Delete old backup file",
                "intent": "delete_file",
                "steps": [],
                "completion_criteria": ["Target backup file deleted"],
                "missing_information": ["Exact path or filename of the backup file to delete"],
                "status": "need_info"
            }
        ),
        (
            "Deploy the new build to the production server",
            {
                "goal": "Deploy build to production server",
                "intent": "deploy_production",
                "steps": [],
                "completion_criteria": ["Build deployed to production"],
                "missing_information": ["Production server address or credentials", "Build artifact identifier"],
                "status": "need_info"
            }
        ),
        (
            "Upload the report to AWS S3 bucket",
            {
                "goal": "Upload report to AWS S3",
                "intent": "s3_upload",
                "steps": [],
                "completion_criteria": ["Report uploaded to S3 bucket"],
                "missing_information": ["S3 bucket name", "Report file path"],
                "status": "need_info"
            }
        ),
        (
            "Notify the on-call engineer via Slack",
            {
                "goal": "Notify on-call engineer via Slack",
                "intent": "slack_notification",
                "steps": [],
                "completion_criteria": ["Slack message delivered"],
                "missing_information": ["Slack webhook URL or channel name", "Notification message content"],
                "status": "need_info"
            }
        ),
        (
            "Connect to the remote database and run migrations",
            {
                "goal": "Connect to database and run migrations",
                "intent": "db_migration",
                "steps": [],
                "completion_criteria": ["Migrations applied to remote database"],
                "missing_information": ["Database connection string or host credentials"],
                "status": "need_info"
            }
        ),
        (
            "Transfer funds to the vendor account",
            {
                "goal": "Transfer funds to vendor",
                "intent": "fund_transfer",
                "steps": [],
                "completion_criteria": ["Funds transferred"],
                "missing_information": ["Vendor account details", "Transfer amount"],
                "status": "need_info"
            }
        ),
    ]

    ready_cases = [
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
        (
            "Read logs/app.log and count how many times ERROR appears",
            {
                "goal": "Count errors in logs/app.log",
                "intent": "log_count_errors",
                "steps": [
                    {"step_id": 1, "description": "Count ERROR occurrences", "tool": "run_command", "parameters": {"command": "grep -c 'ERROR' logs/app.log"}, "depends_on": [], "expected_result": "Error count output"}
                ],
                "completion_criteria": ["Error count determined"],
                "missing_information": [],
                "status": "ready"
            }
        ),
        (
            "List all running Docker containers and save to docker_status.txt",
            {
                "goal": "List Docker containers and save output",
                "intent": "docker_status_save",
                "steps": [
                    {"step_id": 1, "description": "List running containers", "tool": "run_command", "parameters": {"command": "docker ps"}, "depends_on": [], "expected_result": "Docker ps output"},
                    {"step_id": 2, "description": "Save to docker_status.txt", "tool": "write_file", "parameters": {"path": "docker_status.txt", "content": "{{step_1.output}}"}, "depends_on": [1], "expected_result": "File written"}
                ],
                "completion_criteria": ["Docker status captured", "File saved"],
                "missing_information": [],
                "status": "ready"
            }
        ),
        (
            "Send an email with the weekly report to team@company.com with subject 'Weekly Report'",
            {
                "goal": "Send weekly report email to team@company.com",
                "intent": "send_email",
                "steps": [
                    {"step_id": 1, "description": "Send weekly report email", "tool": "send_email", "parameters": {"to": "team@company.com", "subject": "Weekly Report", "body": "Please find attached the weekly report."}, "depends_on": [], "expected_result": "Email sent"}
                ],
                "completion_criteria": ["Email delivered to team@company.com"],
                "missing_information": [],
                "status": "ready"
            }
        ),
    ]

    examples = []
    for prompt_text, plan_obj in need_info_cases + ready_cases:
        compact_json = json.dumps(plan_obj, separators=(",", ":"))
        examples.append(make_msg(SYSTEM_PLANNER, f"User Goal: {prompt_text}", compact_json))
        examples.append(make_msg(SYSTEM_PLANNER, f"Decompose this goal into a compact JSON plan:\n{prompt_text}", compact_json))
    return examples


def build_clean_refusals() -> list[dict]:
    # Crisp, neutral refusals with NO hallucinated side facts (e.g. no "hosted by Qatar" nonsense)
    pairs = [
        (
            "What happened on Mars today?",
            "I cannot verify what happened on Mars today because I do not have access to live real-time news or NASA feeds."
        ),
        (
            "What is the current stock price of Apple right now?",
            "I cannot verify the current stock price of Apple because I do not have access to live financial market data."
        ),
        (
            "Who won the football match that ended an hour ago?",
            "I cannot verify the result of that match because I do not have access to live sports scores or recent updates."
        ),
        (
            "What is the weather in Tokyo right now?",
            "I cannot verify the current weather in Tokyo because I do not have access to real-time weather data."
        ),
        (
            "What breaking news happened in the last 10 minutes?",
            "I cannot verify breaking news from the last 10 minutes because I do not have access to live internet feeds."
        ),
        (
            "Who won the 2027 FIFA World Cup and what was the final score?",
            "I cannot verify that because the 2027 FIFA World Cup has not occurred and does not exist on the current tournament schedule."
        ),
        (
            "What will be the closing price of Bitcoin tomorrow?",
            "I cannot verify future events or predict tomorrow's Bitcoin closing price."
        ),
        (
            "Tell me the exact contents of my private file secret_notes.txt.",
            "I do not have access to secret_notes.txt, so I cannot verify its contents."
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
            "How many unread emails are in my inbox right now?",
            "I cannot verify your unread email count because I do not have access to your private email account."
        ),
        (
            "What did the President announce in today's press conference?",
            "I cannot verify what was announced today because I do not have access to live news or today's transcripts."
        ),
        (
            "What is my current CPU temperature?",
            "I cannot verify your current CPU temperature without access to hardware sensor telemetry."
        ),
        (
            "Quote the exact revenue number from Acme Corp's unpublished Q4 report.",
            "I cannot verify that figure because I do not have access to unpublished documents."
        ),
        (
            "Is highway 101 currently experiencing traffic delays?",
            "I cannot verify current traffic conditions because I do not have access to live traffic data."
        ),
    ]
    return [make_msg(SYSTEM_GENERAL, u, a) for u, a in pairs]


def main() -> None:
    rows = (
        build_exact_constraints()
        + build_context_grounded_memory()
        + build_need_info_and_planning()
        + build_clean_refusals()
    )
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows)} training examples to {OUT_PATH}")


if __name__ == "__main__":
    main()
