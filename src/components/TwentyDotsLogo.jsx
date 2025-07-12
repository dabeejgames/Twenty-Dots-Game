import React from "react";

export default function TwentyDotsLogo({ style }) {
  return (
    <div style={{ textAlign: "center", margin: "10px auto 0 auto", ...style }}>
      <div style={{
        // Use normal font
        fontFamily: "Arial, Helvetica, 'Segoe UI', 'Liberation Sans', sans-serif",
        fontSize: "2.0em", fontWeight: 900,
        letterSpacing: "0.04em", color: "#191919",
        textShadow: "2px 1px 0 #0003", lineHeight: 1.08, userSelect: "none",
      }}>
        TWENTY
      </div>
      <div style={{ display: "flex", justifyContent: "center", gap: 5, marginTop: "-0.12em" }}>
        {["d", "o", "t", "s"].map((ch, i) => (
          <span key={i} style={{
            display: "inline-block",
            width: 22, height: 22,
            borderRadius: "50%",
            background: ["#f03c3c", "#4bd247", "#a259d9", "#3498db"][i],
            color: "#fff",
            fontFamily: "Arial, Helvetica, 'Segoe UI', 'Liberation Sans', sans-serif",
            fontSize: "1em",
            textAlign: "center",
            lineHeight: "22px",
            marginRight: 1,
            boxShadow: "1px 1px 4px #0002"
          }}>{ch}</span>
        ))}
      </div>
    </div>
  );
}