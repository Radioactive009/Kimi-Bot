import React, { useState, useEffect } from 'react';
import './index.css';

const SASSY_IDLE = [
  "Ready to slay?",
  "Waiting for your vibes...",
  "Don't be shy, let's go.",
  "Manifesting a productivity boost.",
  "Locked and loaded?"
];

const SASSY_ACTIVE = [
  "Main character energy activated.",
  "I'm literally listening.",
  "We are so back.",
  "Slaying the task list.",
  "Locked in. 🚀"
];

function App() {
  const [isActive, setIsActive] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [phrase, setPhrase] = useState(SASSY_IDLE[0]);

  // Sync status on mount and periodically
  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 2000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const list = isActive ? SASSY_ACTIVE : SASSY_IDLE;
    setPhrase(list[Math.floor(Math.random() * list.length)]);
  }, [isActive]);

  const checkStatus = async () => {
    try {
      const res = await fetch('http://localhost:8000/status');
      const data = await res.json();
      setIsActive(data.active);
    } catch (err) {
      console.error("Backend not reached");
    }
  };

  const handleToggle = async () => {
    if (isLoading) return;
    setIsLoading(true);
    try {
      // Small delay for dramatic effect
      await new Promise(r => setTimeout(r, 600)); 
      const res = await fetch('http://localhost:8000/toggle', { method: 'POST' });
      const data = await res.json();
      // Status will be synced by the interval
      checkStatus();
    } catch (err) {
      alert("Is the backend server running? 💀");
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
        
        <div className={`status-badge ${isActive ? 'active' : 'inactive'}`}>
          {isActive ? '● Online & Slashing' : '○ Sleeping'}
        </div>

        <div className="dial-container">
          <button 
            className={`dial-button ${isActive ? 'active' : 'inactive'} ${isLoading ? 'loading' : ''}`}
            onClick={handleToggle}
            disabled={isLoading}
          >
            {isActive ? (
              <svg className="btn-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M6 18V6H10V18H6ZM14 18V6H18V18H14Z" fill="white"/>
              </svg>
            ) : (
              <svg className="btn-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M8 5V19L19 12L8 5Z" fill="white"/>
              </svg>
            )}
          </button>
        </div>

        <div className="text-container">
          <p className="status-text">
            {isActive ? "Kimi is active and waiting for your commands, boss." : "Kimi is currently chilling. Tap to bring her back."}
          </p>
          <p className="sassy-phrase">
            {isLoading ? "Vibing..." : phrase}
          </p>
        </div>
      </div>
    </div>
  );
}

export default App;
