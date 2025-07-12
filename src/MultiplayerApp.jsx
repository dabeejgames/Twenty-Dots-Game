// src/MultiplayerApp.jsx

import React, { useState, useEffect, useRef } from "react";
import io from "socket.io-client";
import Board from "./components/Board";
import Hand from "./components/Hand";
import DiscardPiles from "./components/DiscardPiles";
import { COLORS } from "./logic/deck";

// Adjust this URL to your backend server location
const SERVER_URL = "http://localhost:4000";

export default function MultiplayerApp({ onBack }) {
  const [socket, setSocket] = useState(null);
  const [room, setRoom] = useState("");
  const [playerId, setPlayerId] = useState("");
  const [gameState, setGameState] = useState(null);
  const [inputRoom, setInputRoom] = useState("");
  const [isReady, setIsReady] = useState(false);
  const [error, setError] = useState("");
  const [selectedIdx, setSelectedIdx] = useState(null);

  // Connect to server
  useEffect(() => {
    const sock = io(SERVER_URL);
    setSocket(sock);

    sock.on("connect", () => setPlayerId(sock.id));
    sock.on("roomJoined", (roomName) => setRoom(roomName));
    sock.on("gameState", (state) => {
      setGameState(state);
      setError("");
      setIsReady(false);
      setSelectedIdx(null);
    });
    sock.on("errorMsg", (msg) => setError(msg));
    sock.on("disconnect", () => {
      setRoom("");
      setGameState(null);
      setError("Disconnected from server.");
    });

    return () => sock.disconnect();
  }, []);

  // Join or create a room
  function handleJoinRoom(e) {
    e.preventDefault();
    if (inputRoom.trim()) {
      socket.emit("joinRoom", inputRoom.trim());
    }
  }

  // Ready up for game start
  function handleReady() {
    socket.emit("playerReady", room);
    setIsReady(true);
  }

  // Play a card
  function handlePlayCard(card) {
    if (!gameState || !gameState.myTurn) return;
    socket.emit("playCard", { room, card });
    setSelectedIdx(null);
  }

  // End turn (after 2 cards)
  function handleEndTurn() {
    socket.emit("endTurn", room);
  }

  // Leave room and reset
  function handleLeaveRoom() {
    socket.emit("leaveRoom", room);
    setRoom("");
    setGameState(null);
    setError("");
    setIsReady(false);
    setSelectedIdx(null);
  }

  // UI: Lobby screen
  if (!room) {
    return (
      <div style={{ padding: 32, maxWidth: 420, margin: "40px auto", textAlign: "center" }}>
        <h2>Multiplayer Lobby</h2>
        <form onSubmit={handleJoinRoom}>
          <input
            value={inputRoom}
            onChange={e => setInputRoom(e.target.value)}
            placeholder="Room code"
            style={{ fontSize: 18, padding: 8, borderRadius: 8, border: "1.5px solid #b0b8c9", marginRight: 10 }}
          />
          <button type="submit" style={{ fontSize: 18, padding: "8px 18px", borderRadius: 8, background: "#2b71e7", color: "#fff", border: "none", fontWeight: 700 }}>
            Join Room
          </button>
        </form>
        <div style={{ marginTop: 18, color: "#888" }}>
          Enter a code to create or join a room.<br />
          Share the code with your friend to play!
        </div>
        {error && <div style={{ color: "#e76a2b", marginTop: 16 }}>{error}</div>}
        <button onClick={onBack} style={{ marginTop: 36, fontSize: 16, borderRadius: 8, border: "1.5px solid #b0b8c9", background: "#fff", color: "#2b71e7", fontWeight: 700, padding: "8px 18px" }}>
          Back
        </button>
      </div>
    );
  }

  // UI: Waiting for opponent or game start
  if (!gameState) {
    return (
      <div style={{ padding: 32, maxWidth: 480, margin: "40px auto", textAlign: "center" }}>
        <h2>Room: <span style={{ color: "#2b71e7" }}>{room}</span></h2>
        <div style={{ marginTop: 18, color: "#888" }}>Waiting for another player to join...</div>
        <button onClick={handleLeaveRoom} style={{ marginTop: 36, fontSize: 16, borderRadius: 8, border: "1.5px solid #b0b8c9", background: "#fff", color: "#2b71e7", fontWeight: 700, padding: "8px 18px" }}>
          Leave Room
        </button>
        {error && <div style={{ color: "#e76a2b", marginTop: 16 }}>{error}</div>}
      </div>
    );
  }

  // UI: Game in progress
  const {
    board,
    hand,
    discardPiles,
    score,
    colorTally,
    opponentDiscardPiles,
    opponentScore,
    opponentColorTally,
    myTurn,
    gameOver,
    winner,
    lastMove,
    turnCount
  } = gameState;

  return (
    <div style={{ padding: 24, position: "relative" }}>
      <button onClick={handleLeaveRoom} style={{ position: "absolute", left: 16, top: 16 }}>Leave</button>
      <div style={{
        margin: "0 auto 18px auto",
        padding: "18px 30px",
        borderRadius: 18,
        background: "rgba(255,255,255,0.26)",
        backdropFilter: "blur(8px)",
        boxShadow: "0 2px 16px #0001",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: "1.18em",
        fontWeight: 600
      }}>
        <span style={{ color: "#2b71e7", marginRight: 18 }}>Your Score: {score}</span>
        <span style={{ color: "#e76a2b", marginRight: 18 }}>Opponent Score: {opponentScore}</span>
        <span style={{
          background: myTurn ? "#2b71e7" : "#e76a2b",
          color: "#fff",
          borderRadius: 8,
          padding: "4px 14px",
          marginLeft: 18,
          boxShadow: "0 1px 4px #0002",
          fontWeight: 700,
          letterSpacing: "0.5px"
        }}>
          {gameOver
            ? winner === "draw"
              ? "Draw!"
              : winner === playerId
                ? "You win!"
                : "Opponent wins!"
            : myTurn
              ? "Your Turn"
              : "Opponent's Turn"}
        </span>
      </div>
      <div>
        <strong>Your Colors:</strong>{" "}
        {COLORS.map(c => (
          <span key={c} style={{ color: c, marginRight: 12 }}>{c}: {colorTally[c]}</span>
        ))}
      </div>
      <div>
        <strong>Opponent Colors:</strong>{" "}
        {COLORS.map(c => (
          <span key={c} style={{ color: c, marginRight: 12 }}>{c}: {opponentColorTally[c]}</span>
        ))}
      </div>
      <div style={{ margin: "18px 0" }}>
        <Board board={board} onPlay={myTurn && !gameOver ? (card => handlePlayCard(card)) : undefined} lastMove={lastMove} />
      </div>
      <div>
        <strong>Your Hand:</strong>
        <Hand
          hand={hand}
          onPlay={myTurn && !gameOver
            ? (card) => handlePlayCard(card)
            : undefined}
        />
        <DiscardPiles cards={discardPiles} />
      </div>
      <div>
        <strong>Opponent Discards:</strong>
        <DiscardPiles cards={opponentDiscardPiles} />
      </div>
      {myTurn && !gameOver && (
        <button
          onClick={handleEndTurn}
          style={{
            marginTop: 16,
            fontSize: 18,
            borderRadius: 8,
            background: "#2b71e7",
            color: "#fff",
            border: "none",
            fontWeight: 700,
            padding: "10px 28px",
            boxShadow: "0 2px 8px #2b71e733",
            cursor: "pointer"
          }}
        >
          End Turn
        </button>
      )}
      {error && <div style={{ color: "#e76a2b", marginTop: 16 }}>{error}</div>}
      {gameOver && (
        <div style={{
          marginTop: 32,
          fontSize: "1.35em",
          fontWeight: 700,
          color: winner === playerId ? "#2ecc40" : winner === "draw" ? "#888" : "#e76a2b"
        }}>
          {winner === "draw"
            ? "It's a draw!"
            : winner === playerId
              ? "Congratulations, you win!"
              : "Opponent wins!"}
        </div>
      )}
    </div>
  );
}
