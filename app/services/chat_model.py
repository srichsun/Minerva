"""The coach's chat model, chosen by config.LLM_PROVIDER.

Because everything runs through LangChain, swapping the "brain" between ChatGPT
and Claude is just picking a different wrapper here — no other code changes.
Kept in its own module so both the agent and the profile condenser share one
factory without importing each other.
"""
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from app.core import config


def build_chat_model():
    """Build the configured chat model (needs the matching API key)."""
    if config.LLM_PROVIDER == "openai":
        return ChatOpenAI(
            model=config.OPENAI_CHAT_MODEL,
            api_key=config.OPENAI_API_KEY,
            max_tokens=config.MAX_TOKENS,
            timeout=30.0,
        )
    return ChatAnthropic(
        model_name=config.CHAT_MODEL,
        api_key=config.ANTHROPIC_API_KEY,
        max_tokens=config.MAX_TOKENS,
        timeout=30.0,
    )
