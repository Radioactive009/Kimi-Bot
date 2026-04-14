import React, { useEffect, useMemo, useState } from "react";
import "./index.css";

const SASSY_IDLE = [
  "Ready to slay?",
  "Waiting for your vibes...",
  "Do not be shy, let us go.",
  "Manifesting a productivity boost.",
  "Locked and loaded?",
];

const SASSY_ACTIVE = [
  "Main character energy activated.",
  "I am listening.",
  "We are so back.",
  "Slaying the task list.",
  "Locked in.",
];

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
const SERVER_TOKEN = import.meta.env.VITE_KIMI_SERVER_TOKEN || "";

function App() {
  const [isActive, setIsActive] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [phrase, setPhrase] = useState(SASSY_IDLE[0]);

  const requestHeaders = useMemo(() => {
    const headers = { "Content-Type": "application/json" };
    if (SERVER_TOKEN) {
      headers["X-Kimi-Token"] = SERVER_TOKEN;
    }
    return headers;
  }, []);

  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const list = isActive ? SASSY_ACTIVE : SASSY_IDLE;
    setPhrase(list[Math.floor(Math.random() * list.length)]);
  }, [isActive]);

  const checkStatus = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/status`);
      if (!res.ok) {
        throw new Error(`Status request failed: ${res.status}`);
      }
      const data = await res.json();
      setIsActive(Boolean(data.active));
    } catch (err) {
      console.error("Backend not reached", err);
    }
  };

  const handleToggle = async () => {
    if (isLoading) return;
    setIsLoading(true);
    try {
      await new Promise((r) => setTimeout(r, 350));
      const res = await fetch(`${API_BASE_URL}/toggle`, {
        method: "POST",
        headers: requestHeaders,
      });
      if (!res.ok) {
        throw new Error(`Toggle request failed: ${res.status}`);
      }
      await checkStatus();
    } catch (err) {
      alert("Backend is unreachable or token is invalid.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app-container">
      <div className="background-blobs">
        <div className="blob blob-1"></div>
        <div className="blob blob-2"></div>
      </div>

      <div className="dashboard">
        <h1 className="title">KIMI</h1>

        <div className={`status-badge ${isActive ? "active" : "inactive"}`}>
          {isActive ? "Online and Running" : "Sleeping"}
        </div>

        <div className="dial-container">
          <button
            className={`dial-button ${isActive ? "active" : "inactive"} ${isLoading ? "loading" : ""}`}
            onClick={handleToggle}
            disabled={isLoading}
          >
            {isActive ? (
              <svg className="btn-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M6 18V6H10V18H6ZM14 18V6H18V18H14Z" fill="white" />
              </svg>
            ) : (
              <svg className="btn-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M8 5V19L19 12L8 5Z" fill="white" />
              </svg>
            )}
          </button>
        </div>

        <div className="text-container">
          <p className="status-text">
            {isActive ? "Kimi is active and waiting for your commands, boss." : "Kimi is currently idle. Tap to start."}
          </p>
          <p className="sassy-phrase">{isLoading ? "Switching..." : phrase}</p>
        </div>
      </div>
    </div>
  );
}

export default App;
