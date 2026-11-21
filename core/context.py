import time
import re
from typing import Optional, List, Dict, Any

from core.identity import IdentityManager, default_identity
from core.memory import MemoryStore, default_memory, MemoryRecord
from core.world_state import WorldStateManager, default_world_state


class ConversationTurn:
    """Represents a single conversational interaction turn."""
    def __init__(
        self,
        user_text: str,
        agent_response: str,
        referenced_app: Optional[str] = None,
        referenced_query: Optional[str] = None,
        tool_used: Optional[str] = None,
        screen_summary: Optional[str] = None,
        timestamp: Optional[float] = None
    ):
        self.user_text = user_text
        self.agent_response = agent_response
        self.referenced_app = referenced_app
        self.referenced_query = referenced_query
        self.tool_used = tool_used
        self.screen_summary = screen_summary
        self.timestamp = timestamp or time.time()


class GoalFrame:
    """
    Formal Goal State Frame holding structured task slots across conversation turns:
    - intent: e.g. 'PLAY_MEDIA', 'SEARCH_WEB', 'OPEN_APP'
    - target: e.g. 'mr.beast videos', 'python documentation'
    - platform: e.g. 'youtube', 'brave', 'reddit'
    - completed: bool
    """
    def __init__(self, intent: str = "", target: str = "", platform: str = "", completed: bool = False):
        self.intent = intent
        self.target = target
        self.platform = platform
        self.completed = completed

    def is_active(self) -> bool:
        return bool(self.intent and self.target and not self.completed)

    def to_executable_query(self) -> str:
        plat = self.platform or ("youtube" if self.intent == "PLAY_MEDIA" else "brave")
        if self.intent == "PLAY_MEDIA":
            return f"play {self.target} in {plat}"
        elif self.intent == "SEARCH_WEB":
            return f"open {plat} and search {self.target}"
        return f"{self.target} in {plat}"


class ShortTermMemory:
    """
    Maintains a bounded sliding window of recent conversation turns and an unbounded session history.
    Provides pronoun, referential, elliptical goal slot resolution, and ordinal turn recall.
    """
    def __init__(self, max_turns: int = 6):
        self.max_turns = max_turns
        self.turns: List[ConversationTurn] = []
        self.session_history: List[ConversationTurn] = []
        self.active_goal_frame: Optional[GoalFrame] = None

    def add_turn(
        self,
        user_text: str,
        agent_response: str,
        referenced_app: Optional[str] = None,
        referenced_query: Optional[str] = None,
        tool_used: Optional[str] = None,
        screen_summary: Optional[str] = None
    ) -> ConversationTurn:
        turn = ConversationTurn(
            user_text=user_text,
            agent_response=agent_response,
            referenced_app=referenced_app,
            referenced_query=referenced_query,
            tool_used=tool_used,
            screen_summary=screen_summary
        )
        self.session_history.append(turn)
        self.turns.append(turn)
        if len(self.turns) > self.max_turns:
            self.turns.pop(0)

        # Track or update GoalFrame from user_text
        lowered = user_text.lower().strip(".?!")
        m_play = re.match(r"^(?:can you\s+|could you\s+|please\s+)?(?:play|watch|listen to)\s+(.+?)(?:\s+(?:in|on)\s+([a-zA-Z0-9_\-\.]+))?$", lowered)
        if m_play:
            q_target = m_play.group(1).strip()
            q_plat = self.normalize_platform_name(m_play.group(2).strip()) if m_play.group(2) else "youtube"
            self.active_goal_frame = GoalFrame(intent="PLAY_MEDIA", target=q_target, platform=q_plat)
        elif self.active_goal_frame and ("opened" in agent_response.lower() or "playing" in agent_response.lower() or "searched" in agent_response.lower()):
            self.active_goal_frame.completed = True

        return turn

    def get_turn_by_ordinal(self, ordinal: int) -> Optional[ConversationTurn]:
        """Returns turn by 1-based index (e.g. 1 for first input, 2 for second input)."""
        idx = ordinal - 1
        if 0 <= idx < len(self.session_history):
            return self.session_history[idx]
        return None

    def get_first_turn(self) -> Optional[ConversationTurn]:
        """Returns the very first turn of this session."""
        return self.session_history[0] if self.session_history else None

    def get_last_turn(self, offset: int = 0) -> Optional[ConversationTurn]:
        """Returns turn relative to the end (0 = latest, 1 = previous to latest)."""
        idx = -(1 + offset)
        if abs(idx) <= len(self.session_history):
            return self.session_history[idx]
        return None

    def clear(self):
        """Clears short-term conversational context."""
        self.turns.clear()
        self.session_history.clear()
        self.active_goal_frame = None

    def get_last_substantive_request(self) -> Optional[str]:
        """Finds the most recent non-elliptical user request string."""
        for turn in reversed(self.turns):
            txt = turn.user_text.strip().lower()
            if not re.match(r"^(?:in|on|using|through|with)\s+", txt):
                return turn.user_text
        return None

    def get_last_user_request(self) -> Optional[str]:
        """Finds the most recent user request string."""
        if self.turns:
            return self.turns[-1].user_text
        return None

    @staticmethod
    def normalize_platform_name(name: str) -> str:
        clean = name.strip().lower()
        if clean in ("youtubr", "yt", "yutube", "you tube", "yotube", "youtube"):
            return "youtube"
        elif clean in ("browser", "browsr", "brave", "brave browser", "web"):
            return "brave"
        elif clean in ("wikipidia", "wiki", "wikipedia"):
            return "wikipedia"
        elif clean in ("git hub", "gh", "github"):
            return "github"
        elif clean in ("reddit", "reddt"):
            return "reddit"
        elif clean in ("terminal", "term", "bash", "console"):
            return "terminal"
        return clean

    def get_last_app(self) -> Optional[str]:
        """Finds the most recently referenced application in conversation or active state."""
        for turn in reversed(self.turns):
            if turn.referenced_app:
                return turn.referenced_app
        # Fallback to current world state active window / focused app
        return default_world_state.get_focused_app()

    def get_last_query(self) -> Optional[str]:
        """Finds the most recently discussed search query or topic."""
        for turn in reversed(self.turns):
            if turn.referenced_query:
                return turn.referenced_query
        return None

    def resolve_references(self, user_text: str) -> str:
        """
        Resolves pronouns and contextual references in user request:
        - "close it" -> "close brave" (if brave was recently referenced)
        - "focus it" / "switch to it" -> "focus brave"
        - "open it" -> "open brave"
        - "search that" -> "search <last_query>"
        """
        if not user_text or not isinstance(user_text, str):
            return user_text

        text = user_text.strip()
        lowered = text.lower().strip(".?!")

        # 1. Close references: "close it", "close this", "close that", "close the page", "close the browser"
        close_patterns = [
            r"^(?:please\s+)?(?:can\s+you\s+)?(?:close|quit|exit|kill)\s+(?:it|this|that|the page|the browser|window)$"
        ]
        if any(re.match(p, lowered) for p in close_patterns):
            last_app = self.get_last_app()
            if last_app:
                return f"close {last_app}"

        # 2. Focus references: "switch to it", "focus it", "focus the browser"
        focus_patterns = [
            r"^(?:please\s+)?(?:can\s+you\s+)?(?:switch\s+to|focus)\s+(?:it|this|that|the page|the browser)$",
            r"^(?:please\s+)?(?:can\s+you\s+)?bring\s+(?:it|this|that)\s+to\s+front$"
        ]
        if any(re.match(p, lowered) for p in focus_patterns):
            last_app = self.get_last_app()
            if last_app:
                return f"focus {last_app}"

        # 3. Open references: "open it", "launch it", "open this"
        open_patterns = [
            r"^(?:please\s+)?(?:can\s+you\s+)?(?:open|launch|start)\s+(?:it|this|that)$"
        ]
        if any(re.match(p, lowered) for p in open_patterns):
            last_app = self.get_last_app()
            if last_app:
                return f"open {last_app}"

        # 4. Search result references: "open the first result", "click the first result"
        first_res_patterns = [
            r"^(?:please\s+)?(?:can\s+you\s+)?(?:open|click)\s+(?:the\s+)?first\s+result$",
            r"^(?:please\s+)?(?:can\s+you\s+)?open\s+(?:the\s+)?first\s+link$"
        ]
        if any(re.match(p, lowered) for p in first_res_patterns):
            last_q = self.get_last_query()
            return f"open first search result for {last_q}" if last_q else "open brave"

        # 5. Search query references: "search that", "search that on the web", "look that up"
        search_patterns = [
            r"^(?:please\s+)?(?:can\s+you\s+)?search\s+(?:that|it)(?:\s+on\s+the\s+web)?$",
            r"^(?:please\s+)?(?:can\s+you\s+)?look\s+(?:that|it)\s+up$"
        ]
        if any(re.match(p, lowered) for p in search_patterns):
            last_q = self.get_last_query()
            if last_q:
                return f"search the web for {last_q}"

        # 6. Stage 6H Task Continuity keywords: "continue", "try again", "what happened?", "stop"
        if lowered in ["continue", "resume", "keep going"]:
            last_app = self.get_last_app()
            last_q = self.get_last_query()
            if last_q:
                return f"continue search for {last_q}"
            elif last_app:
                return f"focus {last_app}"
        elif lowered in ["try again", "retry"]:
            if self.turns:
                return self.turns[-1].user_text
        elif lowered in ["stop", "cancel"]:
            from core.companion_state import default_interruption_controller
            default_interruption_controller.request_interruption("user_stop_command")
            return "stop current action"

        # 7. Elliptical prepositional / platform refinement: "in youtube", "in youtubr", "in browser", "on reddit"
        m_prep = re.match(r"^(?:please\s+)?(?:in|on|using|through|with)\s+([a-zA-Z0-9_\-\.\s]+)$", lowered)
        if m_prep:
            raw_plat = m_prep.group(1).strip()
            norm_plat = self.normalize_platform_name(raw_plat)
            if self.active_goal_frame and self.active_goal_frame.target:
                self.active_goal_frame.platform = norm_plat
                self.active_goal_frame.completed = False
                return self.active_goal_frame.to_executable_query()

            last_sub = self.get_last_substantive_request()
            if last_sub:
                clean_prev = re.sub(r"\s+(?:in|on)\s+[a-zA-Z0-9_\-\.\s]+$", "", last_sub, flags=re.IGNORECASE).strip()
                return f"{clean_prev} in {norm_plat}"

        return user_text


    def get_context_snippet(self) -> str:
        """Formats the short-term dialogue window for inclusion in cognitive prompt."""
        if not self.turns:
            return ""
        lines = ["RECENT CONVERSATION CONTEXT:"]
        for idx, t in enumerate(self.turns[-4:], 1):
            ref_info = []
            if t.referenced_app:
                ref_info.append(f"app={t.referenced_app}")
            if t.referenced_query:
                ref_info.append(f"query={t.referenced_query}")
            meta_str = f" ({', '.join(ref_info)})" if ref_info else ""
            lines.append(f"User: {t.user_text}")
            lines.append(f"Brain{meta_str}: {t.agent_response[:120]}")
        return "\n".join(lines)


default_short_term_memory = ShortTermMemory()


class ContextBuilder:
    """
    Synthesizes minimal, targeted context for cognitive model reasoning.
    Combines:
      - System Identity (persona & core rules)
      - Relevant Memories (top 3-5 query-relevant records)
      - Verified World State (active apps, focused window, staleness flag)
      - Recent Short-Term Conversation Context
    Prevents prompt bloat and guarantees FastRouter tasks remain zero-overhead.
    """
    def __init__(
        self,
        identity_mgr: Optional[IdentityManager] = None,
        memory_store: Optional[MemoryStore] = None,
        world_state_mgr: Optional[WorldStateManager] = None,
        short_term_mem: Optional[ShortTermMemory] = None
    ):
        self.identity_mgr = identity_mgr or default_identity
        self.memory_store = memory_store or default_memory
        self.world_state_mgr = world_state_mgr or default_world_state
        self.short_term_mem = short_term_mem or default_short_term_memory

    def build_system_context(self, user_request: str, max_chars: int = 1200) -> str:
        """
        Builds the consolidated contextual header containing Identity,
        relevant persistent memories, verified world state, and recent conversation.
        Bounded by `max_chars` to keep local 2K-context inference fast on 8 GB RAM.
        """
        sections: List[str] = []

        # 1. Identity Snippet (2-3 concise lines)
        identity_snip = self.identity_mgr.get_identity_prompt_snippet()
        sections.append(identity_snip)

        # 2. Verified World State (omit UNKNOWN state during pure conversational, creative, or educational prompts)
        is_conversational = any(kw in user_request.lower() for kw in (
            "joke", "meaning of life", "poem", "story", "riddle", "philosophy",
            "how are you", "who are you", "hello", "hi", "hey",
            "how can i train", "how to train", "teach me", "explain ", "how does ", "what is a "
        ))
        world_snip = self.world_state_mgr.get_state_prompt_snippet()
        if not is_conversational or "Active Application: none" not in world_snip:
            sections.append(world_snip)

        # 3. Short-Term Conversation Context
        short_term_snip = self.short_term_mem.get_context_snippet()
        if short_term_snip:
            sections.append(short_term_snip)

        # 4. Relevant Memories (Relevance-filtered, verified-first, deduplicated, conflict-checked)
        if user_request:
            memories: List[MemoryRecord] = self.memory_store.search_memories(user_request, limit=5)
            if memories:
                # Prioritize verified memories first, then relevance & recency
                memories.sort(key=lambda m: (bool(getattr(m, "verified", True)), getattr(m, "relevance_score", 0.0), m.updated_at), reverse=True)
                seen_pairs = set()
                key_values: Dict[str, set] = {}
                mem_lines = ["USER FACTS & STORED CONTEXT:"]
                for m in memories[:3]:
                    pair = (m.key.lower(), m.value.strip().lower())
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)
                    key_values.setdefault(m.key.lower(), set()).add(m.value.strip())
                    mem_lines.append(f"- The user previously told you {m.key}: {m.value}")
                for k, vals in key_values.items():
                    if len(vals) > 1:
                        mem_lines.append(f"- [CONFLICT] Multiple values for '{k}': {', '.join(sorted(vals))}")
                sections.append("\n".join(mem_lines))

        ctx = "\n\n".join(sections)
        if len(ctx) > max_chars:
            ctx = ctx[:max_chars].rsplit("\n", 1)[0]
        return ctx


default_context_builder = ContextBuilder()
