import { useEffect, useRef, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export default function App() {
  const [sessionId, setSessionId] = useState(null);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [geminiLoading, setGeminiLoading] = useState(false);
  const [summary, setSummary] = useState("");
  const [aiOk, setAiOk] = useState(null);
  const [geminiOn, setGeminiOn] = useState(true); // toggle if you want
  const chatEndRef = useRef(null);
  const inputRef = useRef(null);

  // auto-scroll on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Gemini health badge
  useEffect(() => {
    const tick = async () => {
      try {
        const r = await fetch(`${API_BASE}/ai/ping`);
        const j = await r.json();
        setAiOk(!!j.ok);
      } catch {
        setAiOk(false);
      }
    };
    tick();
    const id = setInterval(tick, 30000);
    return () => clearInterval(id);
  }, []);

  // Start a dynamic triage session
  useEffect(() => {
    const boot = async () => {
      try {
        const r = await fetch(`${API_BASE}/triage-dyn/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ initiator: "react-ui" }),
        });
        const data = await r.json();
        setSessionId(data.session_id);
        setMessages([
          {
            role: "assistant",
            text: data.question || "Hello! Let's begin dynamic triage.",
            context: data.context || {},
            step: data.step ?? 0,
          },
        ]);
      } catch (e) {
        setMessages([{ role: "system", text: `Failed to start: ${e}` }]);
      }
    };
    boot();
  }, []);

  const send = async () => {
    if (!sessionId || !input.trim()) return;
    const userText = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: userText }]);
    setLoading(true);

    try {
      // TRIAGE TURN
      const r = await fetch(`${API_BASE}/triage-dyn/${sessionId}/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answer: userText }),
      });
      const data = await r.json();
      const ctx = data.context || {};

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: data.question || "(no next question — AI triage complete)",
          context: ctx,
          step: data.step,
        },
      ]);

      // If triage flow is effectively done, pull summary
      if (!data.question || data.step > 8) {
        const s = await fetch(`${API_BASE}/triage-dyn/${sessionId}/summary`);
        const text = await s.text();
        setSummary(text);
      }

      // GEMINI TURN (free-form helper) — run AFTER triage turn
      if (geminiOn) {
        setGeminiLoading(true);
        try {
          const chatResp = await fetch(`${API_BASE}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              message: userText,
              // Pass triage context so Gemini can be helpful
              context: ctx,
              session_id: sessionId,
            }),
          });

          // Expect: { reply: "..." }
          const chatData = await chatResp.json();
          if (chatData?.reply) {
            setMessages((prev) => [
              ...prev,
              { role: "gemini", text: chatData.reply },
            ]);
          } else {
            setMessages((prev) => [
              ...prev,
              {
                role: "system",
                text:
                  "Gemini did not return a reply. Check your GEMINI_API_KEY and /chat handler.",
              },
            ]);
          }
        } catch (err) {
          setMessages((prev) => [
            ...prev,
            { role: "system", text: `Gemini error: ${err}` },
          ]);
        } finally {
          setGeminiLoading(false);
        }
      }
    } catch (e) {
      setMessages((prev) => [...prev, { role: "system", text: `Error: ${e}` }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const Hint = ({ context }) => {
    if (!context) return null;
    const { pof_timestamp, correlation_id, endpoint, pof_message, ai_label } =
      context;
    if (
      !pof_timestamp &&
      !correlation_id &&
      !endpoint &&
      !pof_message &&
      !ai_label
    )
      return null;
    return (
      <div style={{ marginTop: 6, fontSize: 12, opacity: 0.8 }}>
        {pof_timestamp && <div>POF: {pof_timestamp}</div>}
        {pof_message && <div>POF Message: {pof_message}</div>}
        {correlation_id && <div>CorrelationID: {correlation_id}</div>}
        {endpoint && <div>Endpoint: {endpoint}</div>}
        {ai_label && <div>AI Label: {ai_label}</div>}
      </div>
    );
  };

  const who = (role) =>
    role === "user"
      ? "You"
      : role === "system"
      ? "System"
      : role === "gemini"
      ? "Gemini"
      : "Triage AI";

  const whoColor = (role) =>
    role === "user" ? "#2563eb" : role === "system" ? "#ef4444" : role === "gemini" ? "#0c7" : "#111827";

  return (
    <div
      style={{
        maxWidth: 820,
        margin: "0 auto",
        padding: 16,
        fontFamily: "Inter, system-ui, sans-serif",
        position: "relative",
      }}
    >
      {/* Status + Gemini toggle */}
      <div
        style={{
          position: "absolute",
          top: 12,
          right: 16,
          display: "flex",
          gap: 12,
          fontSize: 12,
          alignItems: "center",
        }}
      >
        <span>
          Gemini:{" "}
          <span style={{ color: aiOk ? "green" : aiOk === false ? "red" : "#666" }}>
            {aiOk ? "connected" : aiOk === false ? "offline" : "checking..."}
          </span>
        </span>
        <label style={{ userSelect: "none", cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={geminiOn}
            onChange={(e) => setGeminiOn(e.target.checked)}
            style={{ marginRight: 6 }}
          />
          Ask Gemini
        </label>
      </div>

      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 12 }}>
        AI Dynamic Triage Chat
      </h1>

      <div
        style={{
          border: "1px solid #e5e7eb",
          borderRadius: 10,
          padding: 12,
          height: 480,
          overflowY: "auto",
          background: "#fafafa",
        }}
      >
        {messages.map((m, i) => (
          <div key={i} style={{ marginBottom: 12 }}>
            <div style={{ fontWeight: 600, color: whoColor(m.role) }}>
              {who(m.role)}
            </div>
            <div style={{ whiteSpace: "pre-wrap" }}>{m.text}</div>
            {m.role === "assistant" && <Hint context={m.context} />}
          </div>
        ))}
        {geminiLoading && (
          <div style={{ fontSize: 12, opacity: 0.7 }}>Gemini is thinking…</div>
        )}
        <div ref={chatEndRef} />
      </div>

      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <textarea
          ref={inputRef}
          rows={2}
          placeholder="Type your answer and press Enter…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          style={{
            flex: 1,
            border: "1px solid #e5e7eb",
            borderRadius: 8,
            padding: 10,
            fontSize: 14,
            resize: "vertical",
          }}
        />
        <button
          onClick={send}
          disabled={loading || !sessionId}
          style={{
            border: "1px solid #e5e7eb",
            borderRadius: 8,
            padding: "0 16px",
            fontWeight: 600,
            cursor: loading ? "not-allowed" : "pointer",
            background: loading ? "#e5e7eb" : "#111827",
            color: loading ? "#6b7280" : "#fff",
          }}
        >
          {loading ? "…" : "Send"}
        </button>
      </div>

      {summary && (
        <div
          style={{
            marginTop: 16,
            border: "1px solid #e5e7eb",
            borderRadius: 10,
            padding: 12,
            background: "#fff",
            whiteSpace: "pre-wrap",
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
            fontSize: 13,
          }}
        >
          {summary}
        </div>
      )}
    </div>
  );
}
