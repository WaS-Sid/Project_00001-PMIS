import React, { useState } from "react";

export default function Home() {
  const [taskName, setTaskName] = useState("");
  const [taskId, setTaskId] = useState("");
  const [taskStatus, setTaskStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  const submitTask = async () => {
    if (!taskName.trim()) {
      alert("Please enter a task name");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: taskName, data: { example: "data" } }),
      });
      const data = await res.json();
      setTaskId(data.task_id);
      setTaskName("");
    } catch (err) {
      console.error("Error submitting task:", err);
      alert("Failed to submit task");
    } finally {
      setLoading(false);
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
