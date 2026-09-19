import time


class PerformanceProfiler:
    """
    Structured Performance & Latency Truth Profiler for Brain.
    Uses high-resolution time.perf_counter() to measure end-to-end wall-clock latency
    and separate granular phase timings:
      - router_decision_ms
      - planner_request_ms
      - planner_generation_ms
      - tool_execution_ms
      - app_launch_ms
      - browser_action_ms
      - network_wait_ms
      - screenshot_ms
      - ocr_ms
      - verification_ms
      - final_response_ms
      - total_wall_clock_ms
    """
    def __init__(self, task_name="Task"):
        self.task_name = task_name
        self.start_counter = time.perf_counter()
        self.end_counter = None

        self.router_decision_ms = 0.0
        self.planner_request_ms = 0.0
        self.planner_generation_ms = 0.0
        self.tool_execution_ms = 0.0
        self.app_launch_ms = 0.0
        self.browser_action_ms = 0.0
        self.network_wait_ms = 0.0
        self.screenshot_ms = 0.0
        self.ocr_ms = 0.0
        self.verification_ms = 0.0
        self.final_response_ms = 0.0

        self.llm_call_count = 0
        self.tool_call_count = 0
        self.gui_action_count = 0
        self.history_char_count = 0
        self.estimated_prompt_tokens = 0
        self.router_used = False

    def start(self):
        self.start_counter = time.perf_counter()
        self.end_counter = None

    def record_router(self, duration_sec, matched=False, tool_name=""):
        self.router_decision_ms += (duration_sec * 1000.0)
        if matched:
            self.router_used = True
            self.task_name = f"FAST_ROUTER:{tool_name}" if tool_name else "FAST_ROUTER"

    def record_route(self, route_type, tool_name=""):
        self.router_used = True
        self.task_name = f"{route_type}:{tool_name}" if tool_name else route_type

    def record_llm_call(self, duration_sec, prompt_chars=0):
        self.llm_call_count += 1
        self.planner_generation_ms += (duration_sec * 1000.0)
        self.history_char_count = prompt_chars
        self.estimated_prompt_tokens = prompt_chars // 4

    def record_llm(self, duration_sec, prompt_chars=0):
        self.record_llm_call(duration_sec, prompt_chars)

    def record_tool_call(self, tool_name, duration_sec, is_gui=False):
        self.tool_call_count += 1
        dur_ms = (duration_sec * 1000.0)
        self.tool_execution_ms += dur_ms
        if is_gui:
            self.gui_action_count += 1

        tool_upper = str(tool_name).upper()
        if tool_upper in ("OPEN_APP", "CLOSE_APP", "FOCUS_APP"):
            self.app_launch_ms += dur_ms
        elif tool_upper in ("BROWSER_SEARCH", "BROWSER_NAVIGATE"):
            self.browser_action_ms += dur_ms
        elif tool_upper == "WEB_SEARCH":
            self.network_wait_ms += dur_ms

    def record_tool(self, tool_name, duration_sec, is_gui=False):
        self.record_tool_call(tool_name, duration_sec, is_gui)

    def record_ocr(self, duration_sec):
        self.ocr_ms += (duration_sec * 1000.0)

    def record_screenshot(self, duration_sec):
        self.screenshot_ms += (duration_sec * 1000.0)

    def record_verification(self, duration_sec):
        self.verification_ms += (duration_sec * 1000.0)

    def stop(self):
        self.end_counter = time.perf_counter()

    def record_total(self):
        self.stop()

    def get_total_wall_clock_ms(self):
        if self.end_counter is not None:
            return (self.end_counter - self.start_counter) * 1000.0
        return (time.perf_counter() - self.start_counter) * 1000.0

    def get_total_ms(self):
        return self.get_total_wall_clock_ms()

    def to_dict(self):
        total_ms = self.get_total_wall_clock_ms()
        return {
            "task_name": self.task_name,
            "strategy": "FAST_ROUTER" if self.router_used else "LLM_PLANNER",
            "router_decision_ms": round(self.router_decision_ms, 2),
            "planner_request_ms": round(self.planner_request_ms, 2),
            "planner_generation_ms": round(self.planner_generation_ms, 2),
            "tool_execution_ms": round(self.tool_execution_ms, 2),
            "app_launch_ms": round(self.app_launch_ms, 2),
            "browser_action_ms": round(self.browser_action_ms, 2),
            "network_wait_ms": round(self.network_wait_ms, 2),
            "screenshot_ms": round(self.screenshot_ms, 2),
            "ocr_ms": round(self.ocr_ms, 2),
            "verification_ms": round(self.verification_ms, 2),
            "final_response_ms": round(self.final_response_ms, 2),
            "total_wall_clock_ms": round(total_ms, 2),
            "llm_call_count": self.llm_call_count,
            "tool_call_count": self.tool_call_count,
            "gui_action_count": self.gui_action_count,
            "estimated_prompt_tokens": self.estimated_prompt_tokens,
            # Backward compatibility aliases
            "total_ms": round(total_ms, 2),
            "router_ms": round(self.router_decision_ms, 2),
            "llm_calls": self.llm_call_count,
            "tool_calls": self.tool_call_count,
            "gui_actions": self.gui_action_count,
            "llm_generation_ms": round(self.planner_generation_ms, 2),
            "estimated_tokens": self.estimated_prompt_tokens
        }

    def format_perf_log(self):
        d = self.to_dict()
        return (
            f"[PERF] task=\"{d['task_name']}\"\n"
            f"  strategy={d['strategy']}\n"
            f"  router_decision={d['router_decision_ms']:.2f}ms\n"
            f"  llm_generation={d['planner_generation_ms']:.2f}ms (calls={d['llm_call_count']})\n"
            f"  tool_execution={d['tool_execution_ms']:.2f}ms (calls={d['tool_call_count']})\n"
            f"  screenshot={d['screenshot_ms']:.2f}ms | ocr={d['ocr_ms']:.2f}ms | verification={d['verification_ms']:.2f}ms\n"
            f"  TOTAL_WALL_CLOCK={d['total_wall_clock_ms']:.2f}ms"
        )

    def log_summary(self, user_request="", mode="AUTO", status="SUCCESS"):
        if user_request:
            self.task_name = user_request
        d = self.to_dict()
        d["intent_route"] = f"FAST_ROUTER:{d['task_name']}" if self.router_used else "LLM_PLANNER"
        d["total_latency_ms"] = d["total_wall_clock_ms"]
        d["llm_latency_ms"] = d["planner_generation_ms"]
        d["tool_latency_ms"] = d["tool_execution_ms"]
        d["mode"] = mode
        d["status"] = status
        return d


