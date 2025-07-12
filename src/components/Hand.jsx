// src/components/Hand.jsx

import React from "react";

// Utility: get color HEX for a color name, with improved green
function getCardColor(card) {
  if (card.color === "purple") return "#b26de6";
  if (card.color === "blue") return "#164aff";
  if (card.color === "red") return "#ff2727";
  if (card.color === "green") return "#2ecc40"; // vibrant green
  if (card.color === "wild") return "#ffd700";
  return "#888";
}

// SVG Card Art: Only the outside border is shown, no inner border, fully centered
function CardSVG({ card }) {
  const color = getCardColor(card);

  // Extract row (A-F) and column (1-6)
  const rowLabel = card.position[0];
  const colLabel = card.position.slice(1);

  return (
    <svg
      width={100}
      height={150}
      viewBox="0 0 100 150"
      style={{ display: "block", margin: "0 auto" }}
    >
      {/* Card background with only the outside border */}
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

      {/* Center circle ring */}
      <circle
        cx={50}
        cy={75}
        r={23}
        fill="#fff"
        stroke={color}
        strokeWidth={3.5}
      />

      {/* Center labels: Row (A-F) above, Number (1-6) below */}
      <text
        x={50}
        y={72}
        textAnchor="middle"
        fontFamily="'Orbitron', Arial, sans-serif"
        fontWeight="bold"
        fontSize={28}
        fill={color}
        stroke="#fff"
        strokeWidth={1.2}
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
        fontSize={28}
        fill={color}
        stroke="#fff"
        strokeWidth={1.2}
        style={{ paintOrder: "stroke", dominantBaseline: "middle" }}
      >
        {colLabel}
      </text>

      {/* Corner board position labels (e.g., "B1") */}
      <text
        x={13}
        y={28}
        textAnchor="start"
        fontFamily="'Orbitron', Arial, sans-serif"
        fontWeight="bold"
        fontSize={20}
        fill={color}
        stroke="#fff"
        strokeWidth={1}
        style={{ paintOrder: "stroke" }}
      >
        {card.position}
      </text>
      <text
        x={87}
        y={142}
        textAnchor="end"
        fontFamily="'Orbitron', Arial, sans-serif"
        fontWeight="bold"
        fontSize={20}
        fill={color}
        stroke="#fff"
        strokeWidth={1}
        style={{ paintOrder: "stroke" }}
      >
        {card.position}
      </text>
    </svg>
  );
}

export default function Hand({ hand, onPlay, selectedIdx }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "flex-end",
        margin: "28px 0 10px 0",
        gap: 18,
        flexWrap: "wrap",
        minHeight: 160,
      }}
    >
      {hand.map((card, idx) => {
        const color = getCardColor(card);
        const isSelected = selectedIdx === idx;
        return (
          <button
            key={idx}
            onClick={() => onPlay && onPlay(card)}
            style={{
              margin: 0,
              padding: 0,
              borderRadius: 16,
              border: isSelected ? `3.5px solid #6a88d7` : `2.5px solid ${color}`,
              background: "none",
              boxShadow: isSelected
                ? "0 0 0 4px #6a88d755, 0 8px 24px #5b94fa22"
                : "0 8px 28px #0002, 0 2px 8px #0001",
              cursor: onPlay ? "pointer" : "default",
              transform: isSelected ? "scale(1.08)" : "scale(1)",
              transition: "box-shadow 0.22s, transform 0.13s, border 0.13s",
              outline: "none",
              position: "relative",
              zIndex: isSelected ? 2 : 1,
              minWidth: 110,
              minHeight: 160,
              width: 110,
              height: 160,
              overflow: "visible",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
            title={`Play ${card.color} on ${card.position}`}
            disabled={!onPlay}
            tabIndex={0}
            aria-label={`Play card ${card.position}`}
            onMouseOver={e => (e.currentTarget.style.transform = "scale(1.09)")}
            onMouseOut={e =>
              (e.currentTarget.style.transform = isSelected
                ? "scale(1.08)"
                : "scale(1)")
            }
          >
            <CardSVG card={card} />
          </button>
        );
      })}
    </div>
  );
}
