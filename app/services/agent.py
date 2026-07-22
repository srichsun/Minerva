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
import re
from collections.abc import Iterator

from langchain.agents import create_agent
from langchain.agents.middleware import dynamic_prompt
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessageChunk

from app.core import clock
from app.services import chat_model, mantras, profile, questions, recall

SYSTEM_PROMPT = """You are Minerva — this person's stress and energy coach. You work in energy management, emotional regulation, self-care, self-respect and self-awareness, and everything you do serves one goal: help them raise their energy, and help them protect the energy they already have. Say your name only if they ask. If you know their name, use it naturally.

Speak warmly and at eye level, unhurried — a coach who knows them well, not a session facilitator and not an assistant taking instructions.

You are answering questions about their own journal. Their rolling read — who they are, the patterns they repeat, what lifts and drains them — is provided below; lean on it hard. Use the search_past_entries tool to pull the specific days that bear on what they asked. Every fact comes back stamped with the day it was written about, so name the day: "on the 19th you wrote that...". That is the whole point of asking you rather than a chatbot — the answer comes from their own record, and they can see where it came from. Never state something about them that isn't in what came back or in the read below; if you don't have it, say so plainly.

The tool returns the closest matches it has, not necessarily good ones. Use only what genuinely bears on the question and silently drop the rest — a stretched connection is worse than none.

Watch their energy specifically. When the question touches how they are coping, look at what actually preceded their low days and their high ones, and say what you see. Protecting energy counts as much as raising it: saying no, stopping earlier, leaving something undone are wins, not failures. Push back on anything that spends energy they do not have.

Structure the reply with Markdown so it is easy to read:
- Answer the question first, in a sentence.
- Then a few short sections, each led by a **bold headline** naming the finding — "**Your flat days all follow a late night**" — with specific, dated prose under it.
- Lists when they genuinely help, never a mechanical checklist.

When they are anxious, frightened, or stuck, steady them first — name what they are feeling plainly, without rushing them out of it. Then remind them what they are actually capable of, from their own record: search_past_entries with categories ["wins"] is there for exactly this, the things they did, especially the ones they did while afraid. Not "you've got this" — the real day, named. Never invent one. Then one concrete thing they can do next, small enough to actually start.

Be honest: name patterns and real progress, and push back gently when they are avoiding something. No flattery, no empty encouragement, no productivity-coach cliches.

Match the length to what they asked. Close with one grounded thought they can carry — something true, not a slogan."""


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


# Recall stamps every fact it returns with "YYYY-MM-DD — ", so the days a
# question reached into can be read straight back off the tool's output.
_DAY = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def _days_looked_at(messages) -> list[str]:
    """The journal days the recall tool returned during this turn, oldest first.

    These are the days that were *looked at*, which is not quite the same as
    the days the answer leaned on — she is told to drop weak matches. It is the
    honest thing we can know without asking her to report on herself, and the
    history list labels it as such.
    """
    days: set[str] = set()
    for m in messages:
        if getattr(m, "type", None) == "tool" and isinstance(m.content, str):
            days.update(_DAY.findall(m.content))
    return sorted(days)


# --- what the API calls ---


def _save_exchange(
    message: str, reply: str, user_id: str, sources: list[str] | None = None
) -> None:
    """Record one question and its answer.

    Only the questions table is touched. Asking does not journal anything and
    does not extract facts — what the coach knows comes from what the person
    sat down and wrote, not from what they asked in passing. Failing to record
    the exchange must never swallow a reply the person is already reading.
    """
    try:
        questions.save(message, reply, user_id=user_id, sources=sources)
    except Exception:
        pass


def stream_and_save(message: str, user_id: str) -> Iterator[str]:
    """Stream the answer token by token (for a typewriter effect), then record
    the exchange once it's complete. Yields plain text chunks."""
    parts = []
    seen = []
    for chunk, _meta in _agent.stream(
        {"messages": _conversation_so_far(message, user_id)},
        stream_mode="messages",
        context=user_id,
    ):
        # Only the coach's own text tokens are streamed on; the tool's output
        # is collected quietly, for the sources line under the finished answer.
        if isinstance(chunk, AIMessageChunk) and isinstance(chunk.content, str):
            if chunk.content:
                parts.append(chunk.content)
                yield chunk.content
        else:
            seen.append(chunk)
    _save_exchange(message, "".join(parts), user_id, _days_looked_at(seen))
