import React, { useState, useEffect } from "react";
import Board from "./components/Board";
import Hand from "./components/Hand";
import DiscardPiles from "./components/DiscardPiles";
import { buildDeck, shuffle, COLORS, BOARD_POSITIONS } from "./logic/deck";
import { buildBoard, placeWild } from "./logic/board";
import { updateColorTally, checkWinByScore, checkWinByColors } from "./logic/gameRules";

const HAND_SIZE = 5;
const DISCARD_PILE_SIZE = 3;

function drawCards(deck, count) {
  return [deck.slice(0, count), deck.slice(count)];
}

export default function SinglePlayerApp({ onBack }) {
  const [deck, setDeck] = useState([]);
  const [board, setBoard] = useState({});
  const [hand, setHand] = useState([]);
  const [discardPiles, setDiscardPiles] = useState([]);
  const [score, setScore] = useState(0);
  const [colorTally, setColorTally] = useState({ red: 0, blue: 0, green: 0, purple: 0 });
  const [wildPos, setWildPos] = useState(null);
  const [gameOver, setGameOver] = useState(false);

  // Initialize game on mount
  useEffect(() => {
    let newDeck = shuffle(buildDeck());
    let [initialHand, restDeck] = drawCards(newDeck, HAND_SIZE);
    let newBoard = buildBoard();
    let wild = placeWild(newBoard);
    setDeck(restDeck);
    setHand(initialHand);
    setBoard(newBoard);
    setWildPos(wild);
    setDiscardPiles([]);
    setScore(0);
    setColorTally({ red: 0, blue: 0, green: 0, purple: 0 });
    setGameOver(false);
  }, []);

  function handlePlayCard(card) {
    if (gameOver) return;
    if (!hand.some(c => c.position === card.position && c.color === card.color)) return;

    const prev = board[card.position];
    let newScore = score;
    let newColorTally = { ...colorTally };
    let newBoard = { ...board };
    let newWildPos = wildPos;
    let wildCleared = false;

    if (prev && prev.color && prev.color !== "wild") {
      newColorTally = updateColorTally(newColorTally, prev.color);
      newScore += 1;
    }
    newBoard[card.position] = { color: card.color };

    if (card.position === wildPos || (prev && prev.color === "wild")) {
      wildCleared = true;
    }

    if (wildCleared) {
      const available = BOARD_POSITIONS.filter(pos => newBoard[pos]?.color !== "wild");
      if (available.length > 0) {
        newWildPos = available[Math.floor(Math.random() * available.length)];
        newBoard[newWildPos] = { color: "wild" };
      } else {
        newWildPos = null;
      }
    }

    let newDiscardPiles = [card, ...discardPiles].slice(0, DISCARD_PILE_SIZE);
    let newHand = hand.filter(c => !(c.position === card.position && c.color === card.color));
    let newDeck = [...deck];

    if (newHand.length < HAND_SIZE && newDeck.length > 0) {
      const [drawn, rest] = drawCards(newDeck, HAND_SIZE - newHand.length);
      newHand = [...newHand, ...drawn];
      newDeck = rest;
    }

    // Win detection (easy mode: 20 points; hard mode: 5 of each color)
    let finished = checkWinByScore(newScore) || checkWinByColors(newColorTally);

    setBoard(newBoard);
    setHand(newHand);
    setDeck(newDeck);
    setDiscardPiles(newDiscardPiles);
    setScore(newScore);
    setColorTally(newColorTally);
    setWildPos(newWildPos);
    setGameOver(finished);
  }

  return (
    <div style={{ padding: 24, position: "relative" }}>
      <button onClick={onBack} style={{ position: "absolute", left: 16, top: 16 }}>Back</button>
      <h2>Single Player</h2>
      <div>Score: {score}</div>
      <div>
        Color tally: {COLORS.map(c => (
          <span key={c} style={{ color: c, marginRight: 12 }}>{c}: {colorTally[c]}</span>
        ))}
      </div>
      <Board board={board} onPlay={handlePlayCard} />
      <Hand hand={hand} onPlay={handlePlayCard} />
      <DiscardPiles cards={discardPiles} />
      {gameOver && (
        <div style={{ color: "green", fontWeight: 700, marginTop: 18 }}>
          You win!
        </div>
      )}
    </div>
  );
}
