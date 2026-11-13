"""
Brain Desktop Application UI (Streamlit Native).
Modern, dark-themed, autonomous task execution and reasoning dashboard.
Strictly local intelligence and execution — no Yui or Aoi companion code.
"""

import os
import sys
import time
import streamlit as st
import psutil

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.app_backend import default_app_core
from tools.registry import default_registry
from core.math_logic import try_deterministic_math_or_logic

st.set_page_config(
    page_title="Brain — Autonomous AI Intelligence",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for modern styling
st.markdown("""
<style>
    .main { background-color: #0d1117; }
    .stButton>button {
        background: linear-gradient(90deg, #2563eb, #3b82f6);
        color: white;
        border-radius: 8px;
        border: none;
        padding: 8px 16px;
        font-weight: 600;
    }
    .metric-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 10px;
    }
    .badge-verified {
        background-color: #065f46;
        color: #34d399;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge-direct {
        background-color: #1e3a8a;
        color: #93c5fd;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge-assisted {
        background-color: #581c87;
        color: #d8b4fe;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "core" not in st.session_state:
    st.session_state.core = default_app_core

core = st.session_state.core

# --- SIDEBAR: Model Switch & Controls ---
st.sidebar.title("🧠 Brain Core")
st.sidebar.caption("Autonomous Local Execution & Reasoning Engine")

st.sidebar.subheader("Model Selection")
selected_model = st.sidebar.selectbox(
    "Active Model",
    options=core.available_models,
    index=core.available_models.index(core.active_model) if core.active_model in core.available_models else 0,
    help="Switches active local model with sequential memory safety (keep_alive: 0)."
)

if selected_model != core.active_model:
    with st.sidebar.spinner(f"Swapping to {selected_model}..."):
        swapped = core.switch_model(selected_model)
        if swapped:
            st.sidebar.success(f"Switched to {selected_model}")
        else:
            st.sidebar.error("Failed to switch model.")

st.sidebar.subheader("Execution Mode")
mode_options = ["AUTO", "DIRECT", "ASSISTED", "VERIFIED"]
selected_mode = st.sidebar.radio(
    "Reasoning Mode",
    options=mode_options,
    index=mode_options.index(core.current_mode),
    help="AUTO selects mode conditionally based on task classification."
)
core.set_execution_mode(selected_mode)

st.sidebar.divider()
st.sidebar.subheader("System Telemetry")
hw = core.get_hardware_status()
st.sidebar.metric("RAM Usage", f"{hw['ram_used_mb']} MB", f"{hw['ram_percent']}% of {hw['ram_total_mb']} MB")
st.sidebar.metric("CPU Utilization", f"{hw['cpu_percent']}%")
st.sidebar.caption("Hardware: AMD Ryzen 3 7320U | 8 GB RAM")

# --- MAIN NAVIGATION TABS ---
tab_chat, tab_math, tab_memory, tab_tools, tab_system = st.tabs([
    "💬 Task Execution & Reasoning",
    "⚡ AST Deterministic Solver",
    "📚 Adaptive Memory",
    "🛠️ Tool Registry",
    "📊 Hardware Monitor",
])

# --- TAB 1: Chat & Execution ---
with tab_chat:
    st.subheader("Autonomous Task Execution & Multi-Step Reasoning")
    st.caption(f"Active Model: **{core.active_model}** | Mode: **{core.current_mode}**")

    # Render chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if "metadata" in msg and msg["metadata"]:
                meta = msg["metadata"]
                badge_class = "badge-verified" if meta.get("mode") == "VERIFIED" else ("badge-assisted" if meta.get("mode") == "ASSISTED" else "badge-direct")
                st.markdown(f"""
                <span class="{badge_class}">{meta.get('mode', 'DIRECT')}</span>
                <span style="color: #8b949e; font-size: 12px; margin-left: 8px;">
                    Strategy: <b>{meta.get('strategy', 'N/A')}</b> |
                    Path: <b>{meta.get('execution_path', 'N/A')}</b> |
                    Duration: <b>{meta.get('duration_ms', 0)} ms</b> |
                    RAM: <b>{meta.get('ram_mb', 0)} MB</b>
                </span>
                """, unsafe_allow_html=True)

    # Chat input
    user_prompt = st.chat_input("Enter a reasoning question, calculation, or system task (e.g. 'Calculate 144 / 12 + 5', 'What caused the crash?')...")
    if user_prompt:
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.write(user_prompt)

        with st.chat_message("assistant"):
            with st.spinner("Executing with Brain reasoning engine..."):
                res = core.execute_task(user_prompt)
                st.write(res["text"])
                badge_class = "badge-verified" if res.get("mode") == "VERIFIED" else ("badge-assisted" if res.get("mode") == "ASSISTED" else "badge-direct")
                st.markdown(f"""
                <span class="{badge_class}">{res.get('mode', 'DIRECT')}</span>
                <span style="color: #8b949e; font-size: 12px; margin-left: 8px;">
                    Strategy: <b>{res.get('strategy', 'N/A')}</b> |
                    Path: <b>{res.get('execution_path', 'N/A')}</b> |
                    Duration: <b>{res.get('duration_ms', 0)} ms</b> |
                    RAM: <b>{res.get('ram_mb', 0)} MB</b>
                </span>
                """, unsafe_allow_html=True)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": res["text"],
                    "metadata": res,
                })

# --- TAB 2: AST Deterministic Solver ---
with tab_math:
    st.subheader("Sub-Millisecond Deterministic AST & Pattern Engine")
    st.write("Solves arithmetic, sequence recognition, percentages, and unit conversions in <1ms without LLM latency.")

    sample_expr = st.text_input("Enter expression to test deterministically:", value="Calculate (15 * 8) + 120 / 4")
    if st.button("Solve Deterministically"):
        t0 = time.perf_counter()
        det = try_deterministic_math_or_logic(sample_expr)
        dur = (time.perf_counter() - t0) * 1000.0

        if det and det.get("solved"):
            st.success(f"**Solved in {dur:.3f} ms!**")
            st.metric("Result", det["answer"], f"Method: {det['method']}")
        else:
            st.warning("Not solvable via pure deterministic AST; routes automatically to LLM.")

# --- TAB 3: Adaptive Memory ---
with tab_memory:
    st.subheader("Model-Isolated Adaptive Memory & Experience Store")
    st.caption(f"Showing recorded experiences partitioned for **{core.active_model}**")

    search_q = st.text_input("Search past task experiences:", "")
    experiences = core.memory_engine.search_experiences(search_q or "task", model_id=core.active_model, limit=10)

    if experiences:
        for exp in experiences:
            with st.expander(f"Task: {exp.user_request[:60]}... ({exp.outcome})"):
                st.write(f"**Category:** {exp.task_category} | **Strategy:** {exp.strategy_used}")
                st.write(f"**Duration:** {exp.duration_ms:.1f} ms | **Verification:** {exp.verification_outcome}")
                st.json(exp.plan_json)
    else:
        st.info("No recorded experiences matching query for this model yet.")

# --- TAB 4: Tool Registry ---
with tab_tools:
    st.subheader("Autonomous Tool Registry")
    tools = default_registry.list_tools()
    st.write(f"Total registered tools: **{len(tools)}**")

    search_tool = st.text_input("Search tools by name or description:", "")
    for t in tools:
        if not search_tool or search_tool.lower() in t["name"].lower() or search_tool.lower() in t["description"].lower():
            with st.expander(f"🔧 {t['name']}"):
                st.write(t["description"])
                st.code(f"Parameters: {t['parameters']}", language="json")

# --- TAB 5: Hardware Monitor ---
with tab_system:
    st.subheader("System Hardware & Telemetry")
    col1, col2, col3 = st.columns(3)
    vm = psutil.virtual_memory()
    col1.metric("Used RAM", f"{round(vm.used / 1024**2, 1)} MB")
    col2.metric("Available RAM", f"{round(vm.available / 1024**2, 1)} MB")
    col3.metric("RAM Usage %", f"{vm.percent}%")

    st.progress(vm.percent / 100.0)
    st.caption("RAM boundary strictly maintained under 8 GB total physical memory.")
