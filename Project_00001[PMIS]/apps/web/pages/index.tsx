import React, { useState } from "react";
import { useUser, User } from "../lib/useUser";
import styles from "../styles/Home.module.css";

// Demo users for testing
const DEMO_USERS: User[] = [
  {
    userId: "analyst-1",
    name: "Alice (Analyst)",
    roles: ["analyst"],
  },
  {
    userId: "operator-1",
    name: "Bob (Operator)",
    roles: ["operator"],
  },
  {
    userId: "admin-1",
    name: "Charlie (Admin)",
    roles: ["admin"],
  },
  {
    userId: "viewer-1",
    name: "Diana (Viewer)",
    roles: ["viewer"],
  },
];

export default function Home() {
  const { user, setUser } = useUser();
  const [selectedUserId, setSelectedUserId] = useState<string>(DEMO_USERS[0].userId);

  const handleLogin = () => {
    const selected = DEMO_USERS.find((u) => u.userId === selectedUserId);
    if (selected) {
      setUser(selected);
    }
  };

  if (user) {
    return (
      <div className={styles.welcome}>
        <h1>Welcome to PMIS</h1>
        <p>Logged in as: <strong>{user.name}</strong></p>
        <p>Roles: <strong>{user.roles.join(", ")}</strong></p>
        <div className={styles.links}>
          <a href="/chat">📝 Go to Chat</a>
          <a href="/packages">📦 View Packages</a>
          <a href="/approvals">✅ View Approvals</a>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.loginContainer}>
      <div className={styles.loginBox}>
        <h1>PMIS — Package Management System</h1>
        <p>Demo Login (no credentials needed)</p>
        
        <div className={styles.userSelect}>
          <label htmlFor="user-select">Select Demo User:</label>
          <select
            id="user-select"
            value={selectedUserId}
            onChange={(e) => setSelectedUserId(e.target.value)}
            className={styles.select}
          >
            {DEMO_USERS.map((u) => (
              <option key={u.userId} value={u.userId}>
                {u.name}
              </option>
            ))}
          </select>
        </div>

        <button onClick={handleLogin} className={styles.button}>
          Login
        </button>

        <div className={styles.roles}>
          <h3>User Roles:</h3>
          <ul>
            <li><strong>admin:</strong> Approve/reject requests, view all</li>
            <li><strong>analyst:</strong> Create tasks, propose patches</li>
            <li><strong>operator:</strong> Create tasks, view details</li>
            <li><strong>viewer:</strong> Read-only access</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
  };

  const checkStatus = async () => {
    if (!taskId.trim()) {
      alert("Please enter a task ID");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(
        `http://localhost:8000/api/tasks/${taskId}`
      );
      const data = await res.json();
      setTaskStatus(data);
    } catch (err) {
      console.error("Error checking status:", err);
      alert("Failed to check task status");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main style={{ padding: 24, fontFamily: "Arial, sans-serif", maxWidth: 800 }}>
      <h1>PMIS Web — Task Queue Demo</h1>
      <p>Submit tasks to the API and track their progress via the Celery worker.</p>

      <section style={{ marginBottom: 24 }}>
        <h2>Submit Task</h2>
        <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
          <input
            type="text"
            placeholder="Task name (e.g., 'process_user')"
            value={taskName}
            onChange={(e) => setTaskName(e.target.value)}
            disabled={loading}
            style={{ flex: 1, padding: 8 }}
          />
          <button
            onClick={submitTask}
            disabled={loading}
            style={{ padding: "8px 16px", cursor: "pointer" }}
          >
            {loading ? "Submitting..." : "Submit"}
          </button>
        </div>
        {taskId && (
          <div style={{ padding: 12, backgroundColor: "#e8f5e9", borderRadius: 4 }}>
            <strong>Task ID:</strong> <code>{taskId}</code>
          </div>
        )}
      </section>

      <section>
        <h2>Check Status</h2>
        <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
          <input
            type="text"
            placeholder="Task ID"
            value={taskId}
            onChange={(e) => setTaskId(e.target.value)}
            disabled={loading}
            style={{ flex: 1, padding: 8 }}
          />
          <button
            onClick={checkStatus}
            disabled={loading}
            style={{ padding: "8px 16px", cursor: "pointer" }}
          >
            {loading ? "Checking..." : "Check"}
          </button>
        </div>
        {taskStatus && (
          <div style={{ padding: 12, backgroundColor: "#f5f5f5", borderRadius: 4 }}>
            <pre>{JSON.stringify(taskStatus, null, 2)}</pre>
          </div>
        )}
      </section>

      <section style={{ marginTop: 24, padding: 12, backgroundColor: "#fff3e0", borderRadius: 4 }}>
        <h3>Development Notes</h3>
        <ul>
          <li>API runs on <code>http://localhost:8000</code></li>
          <li>Worker processes tasks from Redis queue</li>
          <li>Check worker logs: <code>docker compose logs worker -f</code></li>
        </ul>
      </section>
    </main>
  );
}
