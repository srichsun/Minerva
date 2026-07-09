"""FastAPI entrypoint for the document Q&A assistant."""
from fastapi import FastAPI
from pydantic import BaseModel

from app import llm, rag

app = FastAPI(title="Doc AI Assistant")


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/search")
def search(q: str):
    """Return the most relevant chunks for a query (retrieval sanity check)."""
    return {"query": q, "hits": rag.retrieve(q)}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    hits = rag.retrieve(req.question)
    prompt = rag.build_prompt(req.question, hits)
    answer = llm.generate(prompt, system=rag.SYSTEM_PROMPT)
    return ChatResponse(answer=answer)
