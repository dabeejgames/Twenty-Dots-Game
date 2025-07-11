import React from "react";

// Hand expects an array of cards: [{ color, position }, ...]
export default function Hand({ hand, onPlay }) {
  return (
    <div style={{
      display: "flex",
      justifyContent: "center",
      alignItems: "center",
      margin: "18px 0"
    }}>
      {hand.map((card, idx) => (
        <button
          key={idx}
          onClick={() => onPlay && onPlay(card)}
          style={{
            margin: "0 8px",
            padding: "10px 18px",
            borderRadius: 8,
            border: `2px solid ${card.color}`,
            background: "#fff",
            color: card.color,
            fontWeight: 700,
            fontSize: "1.08em",
            boxShadow: "0 2px 8px #0002",
            cursor: onPlay ? "pointer" : "default"
          }}
          title={`Play ${card.color} on ${card.position}`}
          disabled={!onPlay}
        >
          {card.color.charAt(0).toUpperCase() + card.color.slice(1)} <b>{card.position}</b>
        </button>
      ))}
    </div>
  );
}
