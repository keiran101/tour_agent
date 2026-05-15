"""Chat message ORM model for conversation history persistence."""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class ChatMessage(SQLModel, table=True):
    """Stores each message in a conversation session.

    Preserves enough structure to reconstruct OpenAI-format messages:
    - user/assistant/system: role + content
    - assistant with tool_calls: role + content (nullable) + tool_calls_json
    - tool response: role + content + tool_call_id
    """

    __tablename__ = "chat_message"

    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="session.id", index=True)
    role: str = Field(max_length=20)
    content: str | None = Field(default=None)
    tool_calls_json: str | None = Field(default=None)
    tool_call_id: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_openai_message(self) -> dict:
        """Reconstruct an OpenAI-format message dict."""
        import json

        msg: dict = {"role": self.role}
        if self.content is not None:
            msg["content"] = self.content
        if self.tool_calls_json:
            msg["tool_calls"] = json.loads(self.tool_calls_json)
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        return msg

    @classmethod
    def from_openai_message(cls, session_id: str, msg: dict) -> "ChatMessage":
        """Create a ChatMessage from an OpenAI-format message dict."""
        import json

        tool_calls_json = None
        if "tool_calls" in msg:
            tool_calls_json = json.dumps(msg["tool_calls"], ensure_ascii=False)

        return cls(
            session_id=session_id,
            role=msg["role"],
            content=msg.get("content"),
            tool_calls_json=tool_calls_json,
            tool_call_id=msg.get("tool_call_id"),
        )
