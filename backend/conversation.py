"""
conversation.py — Conversation memory manager for BIS Sahayak.

Manages multi-turn conversation state so the chatbot can
understand follow-up questions like "What about testing?"
or "How much does it cost?" in the context of a previous
BIS-related discussion.

Storage: in-memory (dict). Auto-cleanup after 1 hour.
"""

import time
import uuid
from typing import Optional


class ConversationManager:

    def __init__(self, max_history: int = 20, ttl_seconds: int = 3600):
        """
        Args:
            max_history: Maximum messages to keep per conversation.
            ttl_seconds: Time-to-live for conversations (default 1 hour).
        """
        self._conversations: dict = {}
        self._max_history = max_history
        self._ttl = ttl_seconds

    # ---------------------------------------------------------
    # Create
    # ---------------------------------------------------------

    def create(self) -> str:
        """Create a new conversation and return its ID."""
        cid = str(uuid.uuid4())
        self._conversations[cid] = {
            "messages": [],
            "created_at": time.time(),
            "updated_at": time.time(),
            "entities": {},   # extracted context entities
        }
        self._cleanup()
        return cid

    # ---------------------------------------------------------
    # Get or create
    # ---------------------------------------------------------

    def get_or_create(self, conversation_id: Optional[str] = None) -> str:
        """Return existing conversation_id or create a new one."""
        if conversation_id and conversation_id in self._conversations:
            return conversation_id
        return self.create()

    # ---------------------------------------------------------
    # Add message
    # ---------------------------------------------------------

    def add_message(self, conversation_id: str, role: str, content: str):
        """
        Add a message to the conversation.

        Args:
            conversation_id: The conversation ID.
            role: 'user' or 'assistant'.
            content: The message text.
        """
        if conversation_id not in self._conversations:
            return

        conv = self._conversations[conversation_id]
        conv["messages"].append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
        })
        conv["updated_at"] = time.time()

        # Trim to max history
        if len(conv["messages"]) > self._max_history:
            conv["messages"] = conv["messages"][-self._max_history:]

    # ---------------------------------------------------------
    # Get history
    # ---------------------------------------------------------

    def get_history(
        self,
        conversation_id: str,
        max_messages: int = 10
    ) -> list:
        """Return recent messages for a conversation."""
        if conversation_id not in self._conversations:
            return []

        messages = self._conversations[conversation_id]["messages"]
        return messages[-max_messages:]

    # ---------------------------------------------------------
    # Get context summary (for Gemini prompt)
    # ---------------------------------------------------------

    def get_context_for_prompt(
        self,
        conversation_id: str,
        max_turns: int = 6
    ) -> str:
        """
        Build a concise conversation context string for
        the Gemini system prompt.

        Returns the last N turns formatted as:
            User: ...
            Assistant: ...
        """
        history = self.get_history(conversation_id, max_turns * 2)

        if not history:
            return ""

        lines = []
        for msg in history:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            # Truncate long messages for context
            content = msg["content"][:500]
            lines.append(f"{role_label}: {content}")

        return "\n".join(lines)

    # ---------------------------------------------------------
    # Update entities (product, category, user type, etc.)
    # ---------------------------------------------------------

    def update_entities(self, conversation_id: str, entities: dict):
        """Merge extracted entities into conversation state."""
        if conversation_id not in self._conversations:
            return

        self._conversations[conversation_id]["entities"].update(entities)

    def get_entities(self, conversation_id: str) -> dict:
        """Get extracted entities for a conversation."""
        if conversation_id not in self._conversations:
            return {}
        return self._conversations[conversation_id].get("entities", {})

    # ---------------------------------------------------------
    # Clear conversation
    # ---------------------------------------------------------

    def clear(self, conversation_id: str):
        """Clear a conversation's history."""
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]

    # ---------------------------------------------------------
    # Cleanup stale conversations
    # ---------------------------------------------------------

    def _cleanup(self):
        """Remove conversations older than TTL."""
        now = time.time()
        stale = [
            cid for cid, conv in self._conversations.items()
            if now - conv["updated_at"] > self._ttl
        ]
        for cid in stale:
            del self._conversations[cid]

    # ---------------------------------------------------------
    # Stats
    # ---------------------------------------------------------

    def active_count(self) -> int:
        """Number of active conversations."""
        self._cleanup()
        return len(self._conversations)
