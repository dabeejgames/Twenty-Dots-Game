// src/components/DiscardPiles.jsx

import React from "react";

// Reuse your SVG card art for consistency
function getCardColor(card) {
  if (card.color === "purple") return "#b26de6";
  if (card.color === "blue") return "#164aff";
  if (card.color === "red") return "#ff2727";
  if (card.color === "green") return "#2ecc40";
  if (card.color === "wild") return "#ffd700";
  return "#888";
}

function MiniCardSVG({ card }) {
  const color = getCardColor(card);
  const rowLabel = card.position[0];
  const colLabel = card.position.slice(1);

  return (
    <svg
      width={50}
      height={75}
      viewBox="0 0 100 150"
      style={{ display: "block" }}
    >
      {/* Card border */}
      <rect
        x={0}
        y={0}
        width={100}
        height={150}
        rx={16}
        fill="#fff"
        stroke={color}
        strokeWidth={4}
      />
      {/* Center circle */}
      <circle
        cx={50}
        cy={75}
        r={23}
        fill="#fff"
        stroke={color}
        strokeWidth={3.5}
      />
      {/* Center labels */}
      <text
        x={50}
        y={72}
        textAnchor="middle"
        fontFamily="'Orbitron', Arial, sans-serif"
        fontWeight="bold"
        fontSize={18}
        fill={color}
        stroke="#fff"
        strokeWidth={0.8}
        style={{ paintOrder: "stroke", dominantBaseline: "middle" }}
      >
        {rowLabel}
      </text>
      <text
        x={50}
        y={92}
        textAnchor="middle"
        fontFamily="'Orbitron', Arial, sans-serif"
        fontWeight="bold"
        fontSize={18}
        fill={color}
        stroke="#fff"
        strokeWidth={0.8}
        style={{ paintOrder: "stroke", dominantBaseline: "middle" }}
      >
        {colLabel}
      </text>
      {/* Corner labels */}
      <text
        x={15}
        y={32}
        textAnchor="start"
        fontFamily="'Orbitron', Arial, sans-serif"
        fontWeight="bold"
        fontSize={12}
        fill={color}
        stroke="#fff"
        strokeWidth={0.6}
        style={{ paintOrder: "stroke" }}
      >
        {card.position}
      </text>
      <text
        x={85}
        y={138}
        textAnchor="end"
        fontFamily="'Orbitron', Arial, sans-serif"
        fontWeight="bold"
        fontSize={12}
        fill={color}
        stroke="#fff"
        strokeWidth={0.6}
        style={{ paintOrder: "stroke" }}
      >
        {card.position}
      </text>
    </svg>
  );
}

export default function DiscardPiles({ cards }) {
  if (!cards || cards.length === 0) return null;
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        margin: "12px 0",
      }}
    >
      <span
        style={{
          marginRight: 10,
          color: "#888",
          fontWeight: 600,
          fontFamily: "'Orbitron', Arial, sans-serif",
          fontSize: "1.05em",
        }}
      >
        Discards:
      </span>
      <div style={{ display: "flex", alignItems: "center" }}>
        {cards.map((card, idx) => (
          <div
            key={idx}
            style={{
              marginLeft: idx === 0 ? 0 : -22,
              zIndex: cards.length - idx,
              filter: idx === 0 ? "none" : "brightness(0.92)",
              boxShadow: "0 2px 8px #0001",
              borderRadius: 12,
              background: "none",
            }}
            title={`Last played: ${card.color} on ${card.position}`}
          >
            <MiniCardSVG card={card} />
          </div>
        ))}
      </div>
    </div>
  );
}
