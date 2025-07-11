import React, { useState, useEffect } from "react";
import { io } from "socket.io-client";
import Board from "./components/Board";
import Hand from "./components/Hand";
import DiscardPiles from "./components/DiscardPiles";

export default function MultiplayerApp({ onBack }) {
  const [roomId, setRoomId] = useState("");
  const [joined, setJoined] = useState(false);
  const [connected, setConnected] = useState(false);
  const [board, setBoard] = useState({});
  const [hand, setHand] = useState([]);
  const [discardPiles, setDiscardPiles] = useState([]);
  const [score, setScore] = useState(0);
  const [colorTally, setColorTally] = useState({});
  const [wildPos, setWildPos] = useState(null);
  const [gameOver, setGameOver] = useState(false);

  const [socket] = useState(() => io("http://localhost:3001"));

  useEffect(() => {
    function handleConnect() { setConnected(true); }
    function handleDisconnect() { setConnected(false); }
    function handleGameState(gameState) {
      setBoard(gameState.board);
      setHand(gameState.hand);
      setDiscardPiles(gameState.discardPiles);
      setScore(gameState.score);
      setColorTally(gameState.colorTally);
      setWildPos(gameState.wildPos);
      setGameOver(gameState.gameOver);
    }
    socket.on("connect", handleConnect);
    socket.on("disconnect", handleDisconnect);
    socket.on("game-state", handleGameState);

    return () => {
      socket.off("connect", handleConnect);
      socket.off("disconnect", handleDisconnect);
      socket.off("game-state", handleGameState);
      socket.disconnect();
    };
  }, [socket]);

  function joinRoom() {
    if (!roomId) return;
    socket.emit("join-room", roomId);
    setJoined(true);
  }

  function handlePlayCard(card) {
    if (!roomId) return;
    socket.emit("play-card", roomId, card);
  }

  if (!joined) {
    return (
      <div style={{
        width: "100vw",
        height: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexDirection: "column"
      }}>
        <button onClick={onBack} style={{ position: "absolute", left: 16, top: 16 }}>Back</button>
        <h2>Multiplayer: Join Room</h2>
        <input
          value={roomId}
          onChange={e => setRoomId(e.target.value)}
          placeholder="Room ID"
          style={{ padding: "10px 16px", fontSize: "1.1em", borderRadius: 8, border: "1px solid #ccc", marginRight: 10 }}
        />
        <button onClick={joinRoom} disabled={!roomId} style={{ padding: "10px 24px", fontSize: "1em", borderRadius: 8, background: "#3498db", color: "#fff", border: "none", cursor: (!roomId) ? "not-allowed" : "pointer" }}>
          Join Room
        </button>
        <div style={{ color: connected ? "green" : "red", fontWeight: 600 }}>
          {connected ? "Connected" : "Disconnected"}
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: 24, position: "relative" }}>
      <button onClick={onBack} style={{ position: "absolute", left: 16, top: 16 }}>Back</button>
      <h2>Multiplayer Room: {roomId}</h2>
      <div>Score: {score}</div>
      <div>
        Color tally: {Object.keys(colorTally).map(c => (
          <span key={c} style={{ color: c, marginRight: 12 }}>{c}: {colorTally[c]}</span>
        ))}
      </div>
      <Board board={board} onPlay={handlePlayCard} />
      <Hand hand={hand} onPlay={handlePlayCard} />
      <DiscardPiles cards={discardPiles} />
      {gameOver && (
        <div style={{ color: "green", fontWeight: 700, marginTop: 18 }}>
          Game Over!
        </div>
      )}
      <div style={{ color: connected ? "green" : "red", fontWeight: 600, marginTop: 12 }}>
        {connected ? "Connected" : "Disconnected"}
      </div>
    </div>
  );
}
