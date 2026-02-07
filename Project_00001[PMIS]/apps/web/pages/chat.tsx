import React, { useState, useRef, useEffect } from "react";
import { useUser } from "../lib/useUser";
import { getApiClient } from "../lib/api";
import Layout from "../components/Layout";
import styles from "../styles/Chat.module.css";

interface Message {
  id: string;
  type: "user" | "bot";
  content: string;
  timestamp: Date;
}

export default function ChatPage() {
  const { user } = useUser();
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      type: "bot",
      content: "Hello! I'm the PMIS assistant. Ask me about packages, tasks, or request changes.",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (!user) {
    return (
      <Layout>
        <div className={styles.error}>Please log in first</div>
      </Layout>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    // Add user message
    const userMessage: Message = {
      id: Date.now().toString(),
      type: "user",
      content: input,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setError(null);
    setLoading(true);

    try {
      const api = getApiClient();
      const response = await api.chat(input);

      const botMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: "bot",
        content: response.response || "No response",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, botMessage]);

      // Show resource created info if applicable
      if (response.resource_created) {
        const infoMessage: Message = {
          id: (Date.now() + 2).toString(),
          type: "bot",
          content: `✓ Created ${response.resource_created.type} (${response.resource_created.id})`,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, infoMessage]);
      }
    } catch (err: any) {
      setError(err.message || "Failed to send message");
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: "bot",
        content: `❌ Error: ${err.message || "Request failed"}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className={styles.container}>
        <div className={styles.header}>
          <h1>Chat</h1>
          <p>Ask questions or request changes to packages</p>
        </div>

        <div className={styles.chatWindow}>
          <div className={styles.messages}>
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`${styles.message} ${styles[msg.type]}`}
              >
                <div className={styles.messageContent}>
                  <div className={styles.text}>{msg.content}</div>
                  <div className={styles.time}>
                    {msg.timestamp.toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </div>
                </div>
              </div>
            ))}
            {loading && (
              <div className={`${styles.message} ${styles.bot}`}>
                <div className={styles.messageContent}>
                  <div className={styles.typing}>
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <form onSubmit={handleSubmit} className={styles.inputForm}>
            {error && <div className={styles.errorBar}>{error}</div>}
            <div className={styles.inputGroup}>
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type a message..."
                disabled={loading}
                className={styles.input}
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className={styles.sendButton}
              >
                {loading ? "..." : "Send"}
              </button>
            </div>
          </form>
        </div>

        <div className={styles.help}>
          <h3>Try asking:</h3>
          <ul>
            <li>"What is the status of P-001?"</li>
            <li>"Mark P-001 as awarded"</li>
            <li>"Create a new task for P-001"</li>
            <li>"List overdue tasks"</li>
          </ul>
        </div>
      </div>
    </Layout>
  );
}
