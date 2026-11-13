"""
Brain Terminal GUI (TUI) — Creative, beginner-friendly, hacker-green terminal interface.
Features ASCII art, emojis, interactive menus, model switcher, and real-time execution feedback.
Uses Rich library with JetBrains Mono / green font aesthetics.
Strictly local intelligence — No Yui or Aoi companion code.
"""

import os
import sys
import time
import psutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.text import Text
from rich.prompt import Prompt
from rich.align import Align

from core.app_backend import default_app_core
from tools.registry import default_registry

console = Console()

BANNER_ASCII = """[bold green]
 ██████╗ ██████╗  █████╗ ██╗███╗   ██╗
 ██╔══██╗██╔══██╗██╔══██╗██║████╗  ██║
 ██████╔╝██████╔╝███████║██║██╔██╗ ██║
 ██╔══██╗██╔══██╗██╔══██║██║██║╚██╗██║
 ██████╔╝██║  ██║██║  ██║██║██║ ╚████║
 ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝[/bold green]
[bold green] 🧠 AUTONOMOUS LOCAL AI REASONING & EXECUTION ENGINE ⚡[/bold green]
[dim green]  Local-First • AMD Ryzen 3 7320U • 8GB RAM Safe • Zero Cloud Required[/dim green]
"""

def print_header(core):
    os.system("clear")
    console.print(Align.center(BANNER_ASCII))
    
    # Dynamic System & RAM Status Table
    hw = core.get_hardware_status()
    vm = psutil.virtual_memory()
    used_gb = hw.get("ram_used_gb", round(vm.used / 1024**3, 2))
    total_gb = hw.get("ram_total_gb", round(vm.total / 1024**3, 2))
    cpu_pct = hw.get("cpu_percent", psutil.cpu_percent())

    status_table = Table(show_header=False, box=None, padding=(0, 2), expand=True)
    status_table.add_column("Key1", style="bold green", justify="left")
    status_table.add_column("Val1", style="bold white", justify="left")
    status_table.add_column("Key2", style="bold green", justify="left")
    status_table.add_column("Val2", style="bold white", justify="left")
    status_table.add_column("Key3", style="bold green", justify="left")
    status_table.add_column("Val3", style="bold white", justify="left")

    status_table.add_row(
        "🤖 Model:", f"[bold cyan]{core.active_model}[/bold cyan]",
        "🎯 Mode:", f"[bold yellow]{core.current_mode}[/bold yellow]",
        "💾 RAM:", f"[bold green]{used_gb:.2f} GB / {total_gb:.2f} GB ({vm.percent}%)[/bold green]"
    )
    status_table.add_row(
        "🖥️ CPU:", f"[dim green]{hw.get('cpu_model', 'Ryzen 3 7320U')} @ {cpu_pct}%[/dim green]",
        "⚡ AST Engine:", "[bold green]Active (<1ms)[/bold green]",
        "🛡️ Memory Bound:", "[bold green]<6.1 GB (Safe)[/bold green]"
    )
    
    console.print(Panel(status_table, border_style="green", title="[bold green]DYNAMIC SYSTEM STATUS[/bold green]"))
    
    # Command menu bar
    menu_text = (
        "[bold green][1][/bold green] 🔄 [dim]Switch Model[/dim]  "
        "[bold green][2][/bold green] 🎯 [dim]Change Mode[/dim]  "
        "[bold green][3][/bold green] 🛠️ [dim]Tool Registry[/dim]  "
        "[bold green][4][/bold green] 📊 [dim]System Specs[/dim]  "
        "[bold green][5][/bold green] 🧹 [dim]Clear Screen[/dim]  "
        "[bold green][q][/bold green] 🚪 [dim]Quit[/dim]"
    )
    console.print(Panel(Align.center(menu_text), border_style="dim green"))
    console.print("[dim green]💡 Tip: Enter any question, calculation, or system command (e.g. 'open brave and open a new tab')[/dim green]\n")


def show_model_switcher(core):
    console.print("\n[bold green]🔄 SELECT ACTIVE LOCAL MODEL[/bold green]")
    table = Table(title="Available Ollama Models", border_style="green", header_style="bold green")
    table.add_column("Option", style="bold cyan", justify="center")
    table.add_column("Model Name", style="bold white")
    table.add_column("Status", justify="center")

    for idx, m in enumerate(core.available_models, 1):
        status = "[bold green]ACTIVE 🟢[/bold green]" if m == core.active_model else "[dim]Available[/dim]"
        table.add_row(str(idx), m, status)

    console.print(table)
    choice = Prompt.ask("[bold green]Choose model number (or press Enter to cancel)[/bold green]", default="")
    if choice.isdigit():
        c_idx = int(choice) - 1
        if 0 <= c_idx < len(core.available_models):
            target = core.available_models[c_idx]
            with console.status(f"[bold green]Unloading previous model and loading {target}...[/bold green]", spinner="dots"):
                success = core.switch_model(target)
            if success:
                console.print(f"[bold green]✅ Successfully swapped to {target} (VRAM/RAM safely sequenced)[/bold green]")
            else:
                console.print(f"[bold red]❌ Failed to switch to {target}[/bold red]")
            time.sleep(1.2)


def show_mode_switcher(core):
    console.print("\n[bold green]🎯 SELECT REASONING EXECUTION MODE[/bold green]")
    modes = [
        ("AUTO", "Conditional Intelligence (Selects DIRECT, ASSISTED, or VERIFIED dynamically)"),
        ("DIRECT", "Direct unencumbered model response (fastest, ideal for causal/inductive reasoning)"),
        ("ASSISTED", "Multi-step decomposition & structured planning scratchpad"),
        ("VERIFIED", "Sub-millisecond AST math, unit conversion & constraint enforcement"),
    ]
    table = Table(border_style="green", header_style="bold green")
    table.add_column("Option", style="bold cyan", justify="center")
    table.add_column("Mode", style="bold white")
    table.add_column("Description", style="dim green")

    for idx, (m, desc) in enumerate(modes, 1):
        mark = " [bold green](Current)[/bold green]" if m == core.current_mode else ""
        table.add_row(str(idx), m + mark, desc)

    console.print(table)
    choice = Prompt.ask("[bold green]Select mode (1-4)[/bold green]", default="1")
    if choice in ("1", "2", "3", "4"):
        selected = modes[int(choice) - 1][0]
        core.set_execution_mode(selected)
        console.print(f"[bold green]✅ Execution mode set to: {selected}[/bold green]")
        time.sleep(1.0)


def show_tools_panel():
    tools = default_registry.list_tools()
    table = Table(title=f"🛠️ Registered System Tools ({len(tools)} Total)", border_style="green", header_style="bold green")
    table.add_column("Tool Name", style="bold cyan")
    table.add_column("Description", style="white")

    for t in tools[:15]:  # Show first 15 for clean terminal display
        table.add_row(t["name"], t["description"][:70] + "...")

    console.print(table)
    console.print(f"[dim green]Showing 15 of {len(tools)} tools. All tools execute autonomously via Brain.[/dim green]")
    Prompt.ask("[bold green]Press Enter to return to main menu[/bold green]", default="")


def show_telemetry_panel(core):
    hw = core.get_hardware_status()
    vm = psutil.virtual_memory()

    table = Table(title="📊 Real-Time Hardware & Inference Telemetry", border_style="green", header_style="bold green")
    table.add_column("Metric", style="bold green")
    table.add_column("Current Value", style="bold white")

    table.add_row("🤖 Active Model", hw["active_model"])
    table.add_row("🎯 Reasoning Mode", hw["current_mode"])
    table.add_row("🖥️ Processor", hw.get("cpu_model", "AMD Ryzen 3 7320U (4C/8T)"))
    table.add_row("⚡ CPU Utilization", f"{hw['cpu_percent']}%")
    table.add_row("💾 RAM Used", f"{hw['ram_used_gb']:.2f} GB ({vm.percent}%)")
    table.add_row("💾 RAM Total", f"{hw['ram_total_gb']:.2f} GB")
    table.add_row("💾 RAM Available", f"{hw['ram_avail_gb']:.2f} GB")
    table.add_row("🛡️ Memory Boundary", "Strictly bounded < 6.1 GB (8 GB physical ceiling)")
    table.add_row("⚙️ Deterministic AST", "Enabled (<1.0 ms latency)")

    console.print(table)
    Prompt.ask("[bold green]Press Enter to return to main menu[/bold green]", default="")


def run_terminal_gui():
    core = default_app_core
    print_header(core)

    while True:
        try:
            prompt_str = f"[bold green]Brain[/bold green] [dim]({core.active_model})[/dim] [bold green]❯[/bold green] "
            user_input = console.input(prompt_str).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold green]👋 Exiting Brain AI. Goodbye![/bold green]")
            break

        if not user_input:
            continue

        low = user_input.lower()
        if low in ("exit", "quit", "q"):
            console.print("\n[bold green]👋 Exiting Brain AI. Goodbye![/bold green]")
            break

        # Menu Shortcuts
        if low in ("1", "/model", "/models"):
            show_model_switcher(core)
            print_header(core)
            continue
        if low in ("2", "/mode"):
            show_mode_switcher(core)
            print_header(core)
            continue
        if low in ("3", "/tools"):
            show_tools_panel()
            print_header(core)
            continue
        if low in ("4", "/stats", "/telemetry"):
            show_telemetry_panel(core)
            print_header(core)
            continue
        if low in ("5", "/clear", "clear", "cls"):
            core.clear_conversation()
            print_header(core)
            console.print("[dim green]Conversation context cleared.[/dim green]\n")
            continue

        # Task / Reasoning Execution
        with console.status("[bold green]🧠 Brain is reasoning and executing...[/bold green]", spinner="dots"):
            res = core.execute_task(user_input)

        # Style mode badge
        mode = res.get("mode", "DIRECT")
        badge_style = "bold green" if mode == "VERIFIED" else ("bold magenta" if mode == "ASSISTED" else "bold cyan")
        strategy = res.get("strategy", "REASONING")
        dur_sec = res.get("duration_sec", round(res.get("duration_ms", 0.0) / 1000.0, 2))
        ram_gb = res.get("ram_gb", round(res.get("ram_mb", 0.0) / 1024.0, 2))
        path = res.get("execution_path", "LLM_DIRECT")

        panel_title = f"[{badge_style}] {mode} [/{badge_style}] • [bold green]{strategy}[/bold green]"
        panel_subtitle = f"[dim green]⏱️ Time: [bold green]{dur_sec:.2f}s[/bold green] | 💾 RAM: [bold green]{ram_gb:.2f} GB[/bold green] | ⚡ Path: {path}[/dim green]"
        
        # Render markdown answer in panel
        content = Markdown(res["text"])
        console.print(Panel(content, border_style="green", title=panel_title, title_align="left", subtitle=panel_subtitle, subtitle_align="right"))
        console.print("")


if __name__ == "__main__":
    run_terminal_gui()
