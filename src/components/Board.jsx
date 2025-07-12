import React from "react";
import { ROWS, COLS } from "../logic/deck";

// Improved label style for column/row headers
const labelStyle = {
  fontFamily: "'Orbitron', Arial, sans-serif",
  fontWeight: 700,
  color: "#6a88d7",
  fontSize: "1.3em",
  letterSpacing: "2px",
  textShadow: "0 2px 8px #b8d1ff44",
  textTransform: "uppercase",
  userSelect: "none"
};

// New styles for the board container
const boardContainerStyle = {
  display: "inline-block",
  position: "relative",
  background: "rgba(255,255,255,0.22)",
  backdropFilter: "blur(16px)",
  borderRadius: 24,
  boxShadow: "0 8px 32px #0002",
  padding: 24,
  margin: "32px auto",
  border: "1.5px solid #e3eafe",
  minWidth: 384,
  minHeight: 384,
  transition: "box-shadow 0.18s"
};

// Style for the column label row
const columnLabelRowStyle = {
  display: "grid",
  gridTemplateColumns: `48px repeat(${COLS.length}, 56px)`,
  alignItems: "center",
  marginBottom: 8
};

// Style for each board row
const boardRowStyle = {
  display: "grid",
  gridTemplateColumns: `48px repeat(${COLS.length}, 56px)`,
  alignItems: "center"
};

// Style for the square cells
const squareCellStyle = {
  width: 48,
  height: 48,
  margin: 4,
  borderRadius: 12,
  border: "2.5px solid #b0b8c9",
  background: "radial-gradient(circle at 60% 40%, #e3eafe 65%, #fff 100%)",
  color: "#222",
  fontWeight: 700,
  cursor: "pointer",
  outline: "none",
  boxShadow: "0 2px 8px #0001",
  transition: "background 0.18s, box-shadow 0.18s, border 0.18s"
};

// Highlight style for selected or special cells
const highlightStyle = {
  border: "2.5px solid #ffd700",
  boxShadow: "0 0 16px 4px #ffd70066, 0 2px 8px #0001"
};

// Subtle hover effect for playable cells
const hoverCellStyle = {
  filter: "brightness(1.07) drop-shadow(0 2px 6px #b8d1ff33)"
};

// Slight shadow for wild
const wildCellStyle = {
  background: "radial-gradient(circle at 60% 40%, #ffe066 75%, #fffbe9 100%)",
  boxShadow: "0 0 20px 2px #ffd70055, 0 2px 8px #0001"
};

// Consistent color mapping for board cells
function getBoardCellColor(color) {
  if (color === "purple") return "#b26de6";
  if (color === "blue") return "#164aff";
  if (color === "red") return "#ff2727";
  if (color === "green") return "#2ecc40";
  if (color === "wild") return "wild";
  return "#bfc7d3";
}

export default function Board({ board, onPlay, lastMove }) {
  return (
    <div style={boardContainerStyle}>
      {/* Column labels (1-6), aligned with squares */}
      <div style={columnLabelRowStyle}>
        <div /> {/* Spacer for row label */}
        {COLS.map((c) => (
          <div
            key={c}
            style={{
              ...labelStyle,
              textAlign: "center",
              width: 56
            }}
          >
            {c}
          </div>
        ))}
      </div>
      {/* Board rows with row labels (A-F) */}
      {ROWS.map((r) => (
        <div key={r} style={boardRowStyle}>
          <div
            style={{
              ...labelStyle,
              textAlign: "center",
              width: 48
            }}
          >
            {r}
          </div>
          {COLS.map((c) => {
            const pos = `${r}${c}`;
            const cell = board[pos];
            const cellColor = getBoardCellColor(cell?.color);
            const isWild = cell?.color === "wild";
            const isLast = lastMove && lastMove.position === pos;

            // Determine cell background
            let cellBackground;
            if (isWild) {
              cellBackground = wildCellStyle.background;
            } else if (cell?.color) {
              cellBackground = `radial-gradient(circle at 60% 40%, ${cellColor} 70%, #f8fafd 100%)`;
            } else {
              cellBackground = squareCellStyle.background;
            }

            return (
              <button
                key={pos}
                onClick={() => onPlay && onPlay({ position: pos, color: cell?.color })}
                style={{
                  ...squareCellStyle,
                  background: cellBackground,
                  cursor: onPlay ? "pointer" : "default",
                  ...(isWild ? wildCellStyle : {}),
                  ...(isLast ? highlightStyle : {}),
                  ...(onPlay && !cell?.color ? hoverCellStyle : {}),
                  border: isLast
                    ? highlightStyle.border
                    : squareCellStyle.border
                }}
                title={pos}
                disabled={!onPlay}
                tabIndex={0}
                aria-label={`Cell ${pos}${isWild ? " (wild)" : ""}`}
              >
                {isWild ? (
                  <span
                    style={{
                      fontSize: 28,
                      color: "#ffd700",
                      textShadow: "0 0 8px #fff"
                    }}
                  >
                    ★
                  </span>
                ) : ""}
              </button>
            );
          })}
        </div>
      ))}
    </div>
  );
}
