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


class ShortTermMemory:
    """
    Maintains a bounded sliding window of recent conversation turns.
    Provides pronoun and referential context resolution ("it", "that", "the previous one").
    """
    def __init__(self, max_turns: int = 6):
        self.max_turns = max_turns
        self.turns: List[ConversationTurn] = []

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
        self.turns.append(turn)
        if len(self.turns) > self.max_turns:
            self.turns.pop(0)
        return turn

    def clear(self):
        """Clears short-term conversational context."""
        self.turns.clear()

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

    def build_system_context(self, user_request: str) -> str:
        """
        Builds the consolidated contextual header containing Identity,
        relevant persistent memories, verified world state, and recent conversation.
        """
        sections: List[str] = []

        # 1. Identity Snippet (2-3 concise lines)
        identity_snip = self.identity_mgr.get_identity_prompt_snippet()
        sections.append(identity_snip)

        # 2. Verified World State
        world_snip = self.world_state_mgr.get_state_prompt_snippet()
        sections.append(world_snip)

        # 3. Short-Term Conversation Context
        short_term_snip = self.short_term_mem.get_context_snippet()
        if short_term_snip:
            sections.append(short_term_snip)

        # 4. Relevant Memories (Relevance-filtered from user request)
        if user_request:
            memories: List[MemoryRecord] = self.memory_store.search_memories(user_request, limit=3)
            if memories:
                mem_lines = ["RELEVANT MEMORIES:"]
                for m in memories:
                    mem_lines.append(f"- [{m.memory_type}] {m.key}: {m.value}")
                sections.append("\n".join(mem_lines))

        return "\n\n".join(sections)


default_context_builder = ContextBuilder()
