import React from "react";

// DiscardPiles expects an array of cards: [{ color, position }, ...]
export default function DiscardPiles({ cards }) {
  if (!cards || cards.length === 0) return null;
  return (
    <div style={{
      display: "flex",
      justifyContent: "center",
      alignItems: "center",
      margin: "12px 0"
    }}>
      <span style={{ marginRight: 10, color: "#888" }}>Discards:</span>
      {cards.map((card, idx) => (
        <div
          key={idx}
          style={{
            margin: "0 6px",
            padding: "8px 12px",
            borderRadius: 8,
            border: `2px solid ${card.color}`,
            background: "#f6f7fa",
            color: card.color,
            fontWeight: 600,
            fontSize: "1em",
            minWidth: 52,
            textAlign: "center"
          }}
          title={`Last played: ${card.color} on ${card.position}`}
        >
          {card.color.charAt(0).toUpperCase() + card.color.slice(1)}<br />
          <span style={{ fontSize: "0.98em" }}>{card.position}</span>
        </div>
      ))}
    </div>
  );
}
