"""The life-coach agent, built on LangChain.

LangChain's create_agent gives us the whole "call the model, run any tools,
loop until it's done" cycle for free, so we don't hand-write that loop anymore.
The coach picks up today's conversation by replaying today's questions from the
database, so it survives a restart and follows the person from laptop to phone
— and ends when the day does, since tomorrow replays nothing.

This is a read-only path into the person's memory. It answers from the journal
but never adds to it: no entry is written, no fact is extracted. The one tool,
search_past_entries, recalls relevant past facts mid-conversation (semantic
memory over pgvector).
"""
from collections.abc import Iterator

from langchain.agents import create_agent
from langchain.agents.middleware import dynamic_prompt
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessageChunk

from app.core import clock
from app.services import chat_model, mantras, profile, questions, recall

SYSTEM_PROMPT = """You are Minerva — this person's friend and thinking partner, someone who has known them a long time and genuinely cares how their life is going. Say your name only if they ask; you don't announce yourself. If you know their name, use it naturally.

Speak the way a close friend does: warm, unhurried, at eye level. Never like a coach running a session, never like an assistant taking instructions. You are allowed to be fond of them.

Ground everything in who they actually are. A rolling profile of this person — their goals, values, habits, worries, patterns, the people who matter — is provided below; lean on it hard. Use the search_past_entries tool to recall specific past moments when today's topic connects to their history. It returns the closest matches it has, not necessarily good ones — read what comes back and use only what genuinely bears on what they just said. Silently drop the rest; a stretched connection is worse than none, because it tells them you weren't really listening. Make specific, personal callbacks — the magic is in the specific ("for years your Friday nights meant loneliness; tonight was different"), never the generic ("you're growing"). Quote their own words back to them.

Structure the reply clearly with Markdown so it's easy to read and feels insightful:
- Open with a warm, personal sentence naming the deeper shift in their day.
- Organize the reflection into a few sections, each led by a short **bold insight headline** that captures the MEANING in your coach voice — like "**You stopped preparing and started participating**" or "**Friday night has changed**" — followed by a few sentences of warm, specific prose under it.
- Use a light header when you move to a different topic (e.g. a decision they asked about).
- Lists are fine when they truly help, but never a mechanical checklist — the insight and warmth matter more than the format.

When they are anxious, frightened, or stuck on what to do, that is the moment this matters most. Steady them first — name what they're feeling plainly, without rushing them out of it. Then remind them of what they are actually capable of, reaching for real moments from their own history — search_past_entries with categories ["wins"] is there for exactly this: the things they actually did, especially the ones they did while afraid. Not "you've got this" — the real moment, named. Never invent one. Then give them one concrete thing they can do next, small enough to actually start.

Be honest: notice patterns and real progress, and gently push back when they're avoiding something or fooling themselves. Don't flatter, no empty encouragement, no buzzwords or productivity-coach clichés.

Match the length to what they gave you. Close with a single grounded thought they can carry — something true, not a slogan.

Your deeper goal: help them see themselves clearly and grow wiser, calmer, and more self-aware over time. They should leave feeling genuinely understood."""


# --- building the coach ---


@dynamic_prompt
def _prompt_with_profile(request) -> str:
    """Prepend the person's long-term profile to the system prompt each turn,
    so the coach always talks with the freshest sense of who they are.

    Runs at model-call time; if the profile can't be read we just fall back to
    the base prompt rather than break the conversation.
    """
    uid = request.runtime.context
    try:
        summary = profile.as_prompt_text(uid)
    except Exception:
        summary = ""
    try:
        kept = mantras.as_prompt_text(uid)
    except Exception:
        kept = ""

    prompt = SYSTEM_PROMPT
    if summary:
        prompt += f"\n\nWhat you already know about this person:\n{summary}"
    if kept:
        # Their own chosen words carry further than anything you could phrase.
        prompt += (
            "\n\nLines this person chose to keep for their hardest days. When "
            "it fits, give one back to them in their own words rather than "
            "reaching for your own — but never recite the whole list, and "
            "never quote one just to fill a gap:\n" + kept
        )
    return prompt


def _build_agent(model: BaseChatModel, tools=None, middleware=None):
    """Wrap a chat model into a coach agent with memory.

    Returns a LangChain agent — call .invoke({"messages": [...]}, context=uid)
    for a whole reply, or .stream(...) for it token by token. Its concrete type
    is a CompiledStateGraph generic, too noisy to be worth annotating.

    Split out so tests can pass a fake, offline model instead of a real one.
    Tests pass tools=[] (the fake model can't bind tools) and middleware=[]
    (so no profile lookup hits the database); the real coach defaults to the
    recall tool and the profile-injecting middleware.
    """
    if tools is None:
        tools = [recall.search_past_entries]
    if middleware is None:
        middleware = [_prompt_with_profile]
    return create_agent(
        model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=middleware,
        context_schema=str,  # the run's context is just the caller's uid
    )


# Built once at startup and reused for every request.
_agent = _build_agent(chat_model.build_chat_model())

# --- what the coach sees each turn ---

# A whole day of conversation is replayed on every turn. This cap is only a
# safety valve for a pathological day — a heavy day of ~40 exchanges is around
# 46k characters, so normal use never comes close. Past it, the oldest
# exchanges drop out (the profile and semantic recall still cover them) rather
# than the request failing outright on the model's context limit.
MAX_HISTORY_CHARS = 120_000


def _todays_conversation(user_id: str) -> list[dict]:
    """Today's questions so far, as chat messages, oldest first.

    Reading them back from the database — instead of holding them in memory —
    is what lets a conversation continue after a redeploy, and on a different
    device. It also ends the conversation when the day does: tomorrow replays
    nothing, so no thread can run on forever. Never fatal: if the history can't
    be read we simply start fresh rather than lose the person's message.
    """
    try:
        rows = questions.questions_on(clock.today(), user_id=user_id)
    except Exception:
        return []

    # Walk newest-first so the cap drops the oldest exchanges, then flip back.
    messages: list[dict] = []
    chars = 0
    for q in reversed(rows):
        chars += len(q.question) + len(q.answer)
        if chars > MAX_HISTORY_CHARS:
            break
        messages.append({"role": "assistant", "content": q.answer})
        messages.append({"role": "user", "content": q.question})
    messages.reverse()
    return messages


def _conversation_so_far(message: str, user_id: str) -> list[dict]:
    """Today's conversation plus the message just spoken."""
    return _todays_conversation(user_id) + [{"role": "user", "content": message}]


def _reply_to(message: str, user_id: str) -> str:
    """Send one message to the coach and get its reply back as text.

    The coach sees everything said today, so there is nothing else to pass in.
    user_id rides along as the run's context so the dynamic prompt and the
    recall tool — both called by LangChain, not by us — know whose journal
    they are looking at.
    """
    result = _agent.invoke(
        {"messages": _conversation_so_far(message, user_id)},
        context=user_id,
    )
    return result["messages"][-1].content  # the coach's latest reply text


# --- what the API calls ---


def _save_exchange(message: str, reply: str, user_id: str) -> None:
    """Record one question and its answer.

    Only the questions table is touched. Asking does not journal anything and
    does not extract facts — what the coach knows comes from what the person
    sat down and wrote, not from what they asked in passing. Failing to record
    the exchange must never swallow a reply the person is already reading.
    """
    try:
        questions.save(message, reply, user_id=user_id)
    except Exception:
        pass


def reply_and_save(message: str, user_id: str) -> dict:
    """Answer the person's question, then record the exchange.

    Returns {"answer": <the reply>} — the shape of the TalkResponse schema.
    Everything is scoped to user_id so accounts stay separate.
    """
    reply = _reply_to(message, user_id)
    _save_exchange(message, reply, user_id)
    return {"answer": reply}


def stream_and_save(message: str, user_id: str) -> Iterator[str]:
    """Stream the answer token by token (for a typewriter effect), then record
    the exchange once it's complete. Yields plain text chunks."""
    parts = []
    for chunk, _meta in _agent.stream(
        {"messages": _conversation_so_far(message, user_id)},
        stream_mode="messages",
        context=user_id,
    ):
        # Only the coach's own text tokens (not tool-call plumbing).
        if isinstance(chunk, AIMessageChunk) and isinstance(chunk.content, str):
            if chunk.content:
                parts.append(chunk.content)
                yield chunk.content
    _save_exchange(message, "".join(parts), user_id)
