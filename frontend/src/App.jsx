import { useState, useRef, useEffect } from "react";
import "./App.css";

// Where the FastAPI backend runs.
const API = "http://127.0.0.1:8000";

// One random id per browser, saved so it survives page reloads.
function getSessionId() {
  let id = localStorage.getItem("session_id");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("session_id", id);
  }
  return id;
}

export default function App() {
  // --- state: the three things that change over time ---
  const [messages, setMessages] = useState([]); // [{ role, text }]
  const [input, setInput] = useState("");        // what's typed in the box
  const [loading, setLoading] = useState(false); // waiting for a reply?

  // Auto-scroll to the newest message whenever the list changes.
  const bottom = useRef(null);
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Send the question to the backend, then add both messages to the list.
  async function send() {
    const question = input.trim();
    if (!question || loading) return;

    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API}/agent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, session_id: getSessionId() }),
      });
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: data.answer,
          tools: data.tools_used,   // which tools the agent chose
          sources: data.sources,    // which documents it searched
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: "Sorry — I couldn't reach the assistant." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header className="head">
        <h1>Doc AI Assistant</h1>
        <p>Ask about plans, returns, warranty, or an order.</p>
      </header>

      <main className="chat">
        {messages.length === 0 && (
          <p className="empty">Ask a question to begin.</p>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.text}

            {/* Show tools + sources under an assistant answer, if any. */}
            {(m.tools?.length > 0 || m.sources?.length > 0) && (
              <div className="meta">
                {m.tools?.map((t, j) => (
                  <span key={j} className="tag tool">tool · {t}</span>
                ))}
                {m.sources?.map((s, j) => (
                  <span key={j} className="tag src">doc · {s}</span>
                ))}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="msg assistant typing">
            <span></span><span></span><span></span>
          </div>
        )}

        <div ref={bottom} />
      </main>

      <form
        className="bar"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your question…"
        />
        <button disabled={loading}>Send</button>
      </form>
    </div>
  );
}
