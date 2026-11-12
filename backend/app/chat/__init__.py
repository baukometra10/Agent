"""Chat package — import ChatAgentService from app.chat.agent to avoid circular imports."""

__all__ = ["ChatAgentService"]


def __getattr__(name: str):
    if name == "ChatAgentService":
        from app.chat.agent import ChatAgentService

        return ChatAgentService
    raise AttributeError(name)
