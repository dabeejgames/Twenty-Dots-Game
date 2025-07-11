import React from "react";
import { ROWS, COLS } from "../logic/deck";

// Board expects a board object: { A1: { color }, A2: { color }, ... }
// Optionally, you can pass a prop `onPlay` for clickable cells.

export default function Board({ board, onPlay }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateRows: `repeat(${ROWS.length}, 42px)`,
        gridTemplateColumns: `repeat(${COLS.length}, 42px)`,
        gap: 4,
        background: "#e0e6ef",
        borderRadius: 12,
        padding: 10,
        margin: "24px auto",
        boxShadow: "0 2px 8px #0002",
        width: "max-content"
      }}
    >
      {ROWS.map(r =>
        COLS.map(c => {
          const pos = `${r}${c}`;
          const cell = board[pos];
          const color = cell?.color || "lightgray";
          const isWild = color === "wild";
          return (
            <button
              key={pos}
              onClick={() => onPlay && onPlay({ position: pos, color: cell?.color })}
              style={{
                width: 40,
                height: 40,
                borderRadius: "50%",
                border: "2px solid #b0b8c9",
                background: isWild ? "gold" : color,
                color: "#222",
                fontWeight: 700,
                cursor: onPlay ? "pointer" : "default",
                outline: "none",
                boxShadow: isWild ? "0 0 10px 2px #ffd70099" : undefined,
                transition: "background 0.18s"
              }}
              title={pos}
              disabled={!onPlay}
            >
              {isWild ? "★" : ""}
            </button>
          );
        })
      )}
    </div>
  );
}
