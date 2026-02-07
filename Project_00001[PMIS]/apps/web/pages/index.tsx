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
        <p>
          Logged in as: <strong>{user.name}</strong>
        </p>
        <p>
          Roles: <strong>{user.roles.join(", ")}</strong>
        </p>
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
            <li>
              <strong>admin:</strong> Approve/reject requests, view all
            </li>
            <li>
              <strong>analyst:</strong> Create tasks, propose patches
            </li>
            <li>
              <strong>operator:</strong> Create tasks, view details
            </li>
            <li>
              <strong>viewer:</strong> Read-only access
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
