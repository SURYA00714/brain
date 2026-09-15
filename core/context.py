from typing import Optional, List, Dict, Any

from core.identity import IdentityManager, default_identity
from core.memory import MemoryStore, default_memory, MemoryRecord
from core.world_state import WorldStateManager, default_world_state


class ContextBuilder:
    """
    Synthesizes minimal, targeted context for cognitive model reasoning.
    Combines:
      - System Identity (persona & core rules)
      - Relevant Memories (top 3-5 query-relevant records)
      - Verified World State (active apps, focused window, staleness flag)
      - Task State & Observations
    Prevents prompt bloat and guarantees FastRouter tasks remain zero-overhead.
    """
    def __init__(
        self,
        identity_mgr: Optional[IdentityManager] = None,
        memory_store: Optional[MemoryStore] = None,
        world_state_mgr: Optional[WorldStateManager] = None
    ):
        self.identity_mgr = identity_mgr or default_identity
        self.memory_store = memory_store or default_memory
        self.world_state_mgr = world_state_mgr or default_world_state

    def build_system_context(self, user_request: str) -> str:
        """
        Builds the consolidated contextual header containing Identity,
        relevant persistent memories, and verified world state.
        """
        sections: List[str] = []

        # 1. Identity Snippet (2-3 concise lines)
        identity_snip = self.identity_mgr.get_identity_prompt_snippet()
        sections.append(identity_snip)

        # 2. Verified World State
        world_snip = self.world_state_mgr.get_state_prompt_snippet()
        sections.append(world_snip)

        # 3. Relevant Memories (Relevance-filtered from user request)
        if user_request:
            memories: List[MemoryRecord] = self.memory_store.search_memories(user_request, limit=3)
            if memories:
                mem_lines = ["RELEVANT MEMORIES:"]
                for m in memories:
                    mem_lines.append(f"- [{m.memory_type}] {m.key}: {m.value}")
                sections.append("\n".join(mem_lines))

        return "\n\n".join(sections)


default_context_builder = ContextBuilder()
