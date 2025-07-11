// logic/gameRules.js

import { COLORS, ROWS, COLS } from "./deck";

// Check if a move is valid (no double-target in a turn)
export function isValidMove(playedPositions, newCard) {
  return !playedPositions.includes(newCard.position);
}

// Update color tally when a dot is removed
export function updateColorTally(tally, color) {
  if (!COLORS.includes(color)) return tally;
  return { ...tally, [color]: (tally[color] || 0) + 1 };
}

// Check for 3+ in a row (horizontal, vertical, diagonal) at a given position
export function checkChains(board, pos) {
  const directions = [
    [0, 1], [1, 0], [1, 1], [1, -1]
  ];
  const [row, col] = [ROWS.indexOf(pos[0]), COLS.indexOf(Number(pos.slice(1)))];
  const color = board[pos]?.color;
  if (!color || color === "wild") return [];

  let chains = [];

  for (const [dr, dc] of directions) {
    let count = 1;
    let chain = [pos];

    // Check forward
    for (let step = 1; step < 6; step++) {
      const r = row + dr * step, c = col + dc * step;
      if (r < 0 || r >= ROWS.length || c < 0 || c >= COLS.length) break;
      const p = `${ROWS[r]}${COLS[c]}`;
      if (board[p]?.color === color) {
        count++;
        chain.push(p);
      } else break;
    }
    // Check backward
    for (let step = 1; step < 6; step++) {
      const r = row - dr * step, c = col - dc * step;
      if (r < 0 || r >= ROWS.length || c < 0 || c >= COLS.length) break;
      const p = `${ROWS[r]}${COLS[c]}`;
      if (board[p]?.color === color) {
        count++;
        chain.push(p);
      } else break;
    }
    if (count >= 3) chains = [...chains, ...chain];
  }
  // Remove duplicates
  return [...new Set(chains)];
}

// Check win condition for easy mode (20 points)
export function checkWinByScore(score) {
  return score >= 20;
}

// Check win condition for hard mode (5 of each color)
export function checkWinByColors(tally) {
  return COLORS.every(color => (tally[color] || 0) >= 5);
}
