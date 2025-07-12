// src/App.jsx

import React, { useState } from "react";
import SinglePlayerApp from "./SinglePlayerApp";
import MultiplayerApp from "./MultiplayerApp";
import BackgroundDots from "./components/BackgroundDots";

export default function App() {
  const [screen, setScreen] = useState("menu");

  return (
    <div style={{ minHeight: "100vh", background: "#eaf0fa", position: "relative" }}>
      <BackgroundDots />
      {screen === "menu" && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            minHeight: "100vh",
            zIndex: 1,
            position: "relative"
          }}
        >
          <h1
            style={{
              fontFamily: "'Orbitron', Arial, sans-serif",
              fontWeight: 900,
              fontSize: "2.7em",
              color: "#2b71e7",
              textShadow: "0 4px 32px #b8d1ff33"
            }}
          >
            Twenty Dots Game
          </h1>
          <p style={{ color: "#5b6b8c", fontSize: "1.18em", marginBottom: 32 }}>
            A modern multiplayer and single-player strategy game.
          </p>
          <button
            style={{
              fontSize: 22,
              padding: "14px 44px",
              borderRadius: 16,
              background: "linear-gradient(120deg, #2b71e7 60%, #b26de6 100%)",
              color: "#fff",
              fontWeight: 700,
              border: "none",
              margin: "18px 0",
              boxShadow: "0 4px 20px #2b71e733",
              cursor: "pointer",
              letterSpacing: "1.2px"
            }}
            onClick={() => setScreen("single")}
          >
            Single Player
          </button>
          <button
            style={{
              fontSize: 22,
              padding: "14px 44px",
              borderRadius: 16,
              background: "linear-gradient(120deg, #b26de6 60%, #2b71e7 100%)",
              color: "#fff",
              fontWeight: 700,
              border: "none",
              margin: "18px 0",
              boxShadow: "0 4px 20px #b26de633",
              cursor: "pointer",
              letterSpacing: "1.2px"
            }}
            onClick={() => setScreen("multi")}
          >
            Multiplayer
          </button>
          <footer style={{ marginTop: 48, color: "#b0b8c9", fontSize: "1em" }}>
            &copy; {new Date().getFullYear()} Twenty Dots Game
          </footer>
        </div>
      )}
      {screen === "single" && (
        <SinglePlayerApp onBack={() => setScreen("menu")} />
      )}
      {screen === "multi" && (
        <MultiplayerApp onBack={() => setScreen("menu")} />
      )}
    </div>
  );
}
