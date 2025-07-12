import React from "react";

const DOTS = [
  // [left %, top %, size px, color, opacity]
  [8, 10, 70, "#88aaff", 0.13],
  [22, 22, 36, "#ffb8b8", 0.12],
  [65, 16, 42, "#90e0ef", 0.10],
  [78, 27, 90, "#a5ffd6", 0.10],
  [55, 65, 60, "#ffd6a5", 0.12],
  [42, 40, 32, "#b8afff", 0.10],
  [80, 70, 75, "#ffe5ec", 0.11],
  [20, 70, 60, "#b8ffd6", 0.10],
  [70, 55, 35, "#ffb8e8", 0.09],
  [30, 55, 44, "#aaffaa", 0.10],
  [50, 80, 36, "#b8c6ff", 0.10],
  [90, 35, 28, "#ffaaff", 0.09],
  [5, 45, 42, "#b8e8ff", 0.10],
  // add more if you like!
];

export default function BackgroundDots() {
  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 0,
        pointerEvents: "none",
        background: "linear-gradient(120deg, #e9f3ff 0%, #d9ecff 100%)",
        overflow: "hidden"
      }}
    >
      {DOTS.map(([left, top, size, color, opacity], i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            left: `${left}%`,
            top: `${top}%`,
            width: size,
            height: size,
            borderRadius: "50%",
            background: color,
            opacity,
            pointerEvents: "none",
            filter: "blur(0.5px)",
            zIndex: 0,
            transform: "translate(-50%, -50%)"
          }}
        />
      ))}
    </div>
  );
}