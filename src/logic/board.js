// logic/board.js

import { BOARD_POSITIONS } from "./deck";

// Build an empty board: { A1: null, A2: null, ..., F6: null }
export function buildBoard() {
  const board = {};
  for (const pos of BOARD_POSITIONS) {
    board[pos] = null;
  }
  return board;
}

// Place a wild (yellow) at a random empty position
export function placeWild(board) {
  const empty = Object.entries(board)
    .filter(([_, cell]) => !cell || cell.color !== "wild")
    .map(([pos]) => pos);
  if (empty.length === 0) return null;
  const pos = empty[Math.floor(Math.random() * empty.length)];
  board[pos] = { color: "wild" };
  return pos;
}
