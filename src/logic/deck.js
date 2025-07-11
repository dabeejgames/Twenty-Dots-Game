// logic/deck.js

export const COLORS = ["red", "blue", "green", "purple"];
export const ROWS = ["A", "B", "C", "D", "E", "F"];
export const COLS = [1, 2, 3, 4, 5, 6];

// Generate all board positions (e.g., "A1", "B2", ...)
export const BOARD_POSITIONS = ROWS.flatMap(r => COLS.map(c => `${r}${c}`));

// Build a full deck: one card for each color/position combo
export function buildDeck() {
  const deck = [];
  for (const color of COLORS) {
    for (const pos of BOARD_POSITIONS) {
      deck.push({ color, position: pos });
    }
  }
  return deck;
}

// Shuffle a deck (Fisher-Yates)
export function shuffle(deck) {
  const arr = [...deck];
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}
