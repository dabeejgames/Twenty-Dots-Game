// src/SinglePlayerApp.jsx

import React, { useState, useEffect } from "react";
import Board from "./components/Board";
import Hand from "./components/Hand";
import DiscardPiles from "./components/DiscardPiles";
import { buildDeck, shuffle, COLORS, BOARD_POSITIONS, ROWS, COLS } from "./logic/deck";
import { buildBoard, placeWild } from "./logic/board";
import { updateColorTally, checkWinByScore, checkWinByColors } from "./logic/gameRules";

// --- Helper: Chain detection with wild support ---
function getChains(board, lastPos, wildPos) {
  const directions = [
    [0, 1],   // horizontal
    [1, 0],   // vertical
    [1, 1],   // diagonal down-right
    [1, -1],  // diagonal down-left
  ];
  const rowLetter = lastPos[0];
  const colNum = parseInt(lastPos.slice(1), 10);
  const rowIdx = ROWS.indexOf(rowLetter);
  const colIdx = COLS.indexOf(colNum);

  const color = board[lastPos]?.color;
  if (!color || color === "wild") return [];

  let foundChains = [];

  for (const [dr, dc] of directions) {
    let chain = [lastPos];

    // Forward
    for (let step = 1; step < 6; step++) {
      const r = rowIdx + dr * step;
      const c = colIdx + dc * step;
      if (r < 0 || r >= ROWS.length || c < 0 || c >= COLS.length) break;
      const pos = `${ROWS[r]}${COLS[c]}`;
      const cellColor = board[pos]?.color;
      if (cellColor === color || (pos === wildPos && cellColor === "wild")) {
        chain.push(pos);
      } else break;
    }
    // Backward
    for (let step = 1; step < 6; step++) {
      const r = rowIdx - dr * step;
      const c = colIdx - dc * step;
      if (r < 0 || r >= ROWS.length || c < 0 || c >= COLS.length) break;
      const pos = `${ROWS[r]}${COLS[c]}`;
      const cellColor = board[pos]?.color;
      if (cellColor === color || (pos === wildPos && cellColor === "wild")) {
        chain.push(pos);
      } else break;
    }
    if (chain.length >= 3 && chain.some(pos => pos === wildPos)) {
      foundChains.push(Array.from(new Set(chain)));
    } else if (chain.length >= 3 && !foundChains.some(arr => arr.includes(lastPos))) {
      foundChains.push(Array.from(new Set(chain)));
    }
  }
  // Remove duplicate chains
  const uniqueChains = [];
  foundChains.forEach(chain => {
    if (!uniqueChains.some(uc => uc.sort().join() === chain.sort().join())) {
      uniqueChains.push(chain);
    }
  });
  return uniqueChains;
}

const HAND_SIZE = 5;
const DISCARD_PILE_SIZE = 3;

function drawCards(deck, count) {
  return [deck.slice(0, count), deck.slice(count)];
}

function getRandomAIMove(aiHand, positionsPlayedThisTurn) {
  if (!aiHand || aiHand.length === 0) return null;
  const playable = aiHand.filter(card => !positionsPlayedThisTurn.includes(card.position));
  if (playable.length === 0) return null;
  return playable[Math.floor(Math.random() * playable.length)];
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

  const [aiHand, setAiHand] = useState([]);
  const [aiDiscardPiles, setAiDiscardPiles] = useState([]);
  const [aiScore, setAiScore] = useState(0);
  const [aiColorTally, setAiColorTally] = useState({ red: 0, blue: 0, green: 0, purple: 0 });

  const [playerTurn, setPlayerTurn] = useState(true);
  const [cardsPlayedThisTurn, setCardsPlayedThisTurn] = useState([]);
  const [aiCardsPlayedThisTurn, setAiCardsPlayedThisTurn] = useState([]);

  useEffect(() => {
    let newDeck = shuffle(buildDeck());
    let [playerHand, restDeck1] = drawCards(newDeck, HAND_SIZE);
    let [aiInitialHand, restDeck2] = drawCards(restDeck1, HAND_SIZE);
    let newBoard = buildBoard();
    let wild = placeWild(newBoard);
    setDeck(restDeck2);
    setHand(playerHand);
    setAiHand(aiInitialHand);
    setBoard(newBoard);
    setWildPos(wild);
    setDiscardPiles([]);
    setAiDiscardPiles([]);
    setScore(0);
    setAiScore(0);
    setColorTally({ red: 0, blue: 0, green: 0, purple: 0 });
    setAiColorTally({ red: 0, blue: 0, green: 0, purple: 0 });
    setGameOver(false);
    setPlayerTurn(true);
    setCardsPlayedThisTurn([]);
    setAiCardsPlayedThisTurn([]);
  }, []);

  function handlePlayCard(card) {
    if (gameOver || !playerTurn) return;
    if (!hand.some(c => c.position === card.position && c.color === card.color)) return;
    if (cardsPlayedThisTurn.includes(card.position)) return;

    let prev = board[card.position];
    let newScore = score;
    let newColorTally = { ...colorTally };
    let newBoard = { ...board };
    let newWildPos = wildPos;
    let wildCleared = false;
    let wildWasInChain = false;

    if (prev && prev.color && prev.color !== "wild") {
      newColorTally = updateColorTally(newColorTally, prev.color);
      newScore += 1;
    }
    newBoard[card.position] = { color: card.color };

    let chains = getChains(newBoard, card.position, wildPos);
    let positionsToClear = new Set();
    chains.forEach(chain => {
      chain.forEach(pos => positionsToClear.add(pos));
      if (chain.includes(wildPos)) wildWasInChain = true;
    });

    if (positionsToClear.size > 0) {
      positionsToClear.forEach(pos => {
        const chainColor = newBoard[pos]?.color;
        if (chainColor && chainColor !== "wild") {
          newColorTally = updateColorTally(newColorTally, chainColor);
          newScore += 1;
        }
        if (pos === wildPos) wildCleared = true;
        newBoard[pos] = null;
      });
    }

    if (card.position === wildPos || (prev && prev.color === "wild") || wildCleared || wildWasInChain) {
      const available = BOARD_POSITIONS.filter(pos => newBoard[pos]?.color !== "wild" && !newBoard[pos]);
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

    // Only replenish hand after 2 cards played
    let nextCardsPlayed = [...cardsPlayedThisTurn, card.position];
    if (nextCardsPlayed.length >= 2) {
      if (newHand.length < HAND_SIZE && newDeck.length > 0) {
        const [drawn, rest] = drawCards(newDeck, HAND_SIZE - newHand.length);
        newHand = [...newHand, ...drawn];
        newDeck = rest;
      }
      setHand(newHand);
      setDeck(newDeck);
      setCardsPlayedThisTurn([]);
      setPlayerTurn(false);
    } else {
      setHand(newHand);
      setCardsPlayedThisTurn(nextCardsPlayed);
    }

    let finished = checkWinByScore(newScore) || checkWinByColors(newColorTally);

    setBoard(newBoard);
    setDiscardPiles(newDiscardPiles);
    setScore(newScore);
    setColorTally(newColorTally);
    setWildPos(newWildPos);
    setGameOver(finished);
  }

  // AI move logic (simple random, never double-targets, always plays 2 cards per turn)
  useEffect(() => {
    if (!playerTurn && !gameOver) {
      if (aiCardsPlayedThisTurn.length < 2) {
        const aiMove = getRandomAIMove(aiHand, aiCardsPlayedThisTurn);
        if (aiMove) {
          setTimeout(() => {
            handleAIPlayCard(aiMove);
          }, 900);
        }
      } else {
        // Replenish AI hand after 2 cards
        let newHand = aiHand;
        let newDeck = deck;
        if (aiHand.length < HAND_SIZE && deck.length > 0) {
          const [drawn, rest] = drawCards(deck, HAND_SIZE - aiHand.length);
          newHand = [...aiHand, ...drawn];
          newDeck = rest;
        }
        setAiHand(newHand);
        setDeck(newDeck);
        setAiCardsPlayedThisTurn([]);
        setTimeout(() => setPlayerTurn(true), 700);
      }
    }
    // eslint-disable-next-line
  }, [playerTurn, aiHand, aiCardsPlayedThisTurn, gameOver]);

  function handleAIPlayCard(card) {
    if (gameOver || playerTurn) return;
    if (!aiHand.some(c => c.position === card.position && c.color === card.color)) return;
    if (aiCardsPlayedThisTurn.includes(card.position)) return;

    let prev = board[card.position];
    let newScore = aiScore;
    let newColorTally = { ...aiColorTally };
    let newBoard = { ...board };
    let newWildPos = wildPos;
    let wildCleared = false;
    let wildWasInChain = false;

    if (prev && prev.color && prev.color !== "wild") {
      newColorTally = updateColorTally(newColorTally, prev.color);
      newScore += 1;
    }
    newBoard[card.position] = { color: card.color };

    let chains = getChains(newBoard, card.position, wildPos);
    let positionsToClear = new Set();
    chains.forEach(chain => {
      chain.forEach(pos => positionsToClear.add(pos));
      if (chain.includes(wildPos)) wildWasInChain = true;
    });

    if (positionsToClear.size > 0) {
      positionsToClear.forEach(pos => {
        const chainColor = newBoard[pos]?.color;
        if (chainColor && chainColor !== "wild") {
          newColorTally = updateColorTally(newColorTally, chainColor);
          newScore += 1;
        }
        if (pos === wildPos) wildCleared = true;
        newBoard[pos] = null;
      });
    }

    if (card.position === wildPos || (prev && prev.color === "wild") || wildCleared || wildWasInChain) {
      const available = BOARD_POSITIONS.filter(pos => newBoard[pos]?.color !== "wild" && !newBoard[pos]);
      if (available.length > 0) {
        newWildPos = available[Math.floor(Math.random() * available.length)];
        newBoard[newWildPos] = { color: "wild" };
      } else {
        newWildPos = null;
      }
    }

    let newDiscardPiles = [card, ...aiDiscardPiles].slice(0, DISCARD_PILE_SIZE);
    let newHand = aiHand.filter(c => !(c.position === card.position && c.color === card.color));
    let newDeck = [...deck];

    setAiHand(newHand);
    setAiDiscardPiles(newDiscardPiles);
    setBoard(newBoard);
    setAiScore(newScore);
    setAiColorTally(newColorTally);
    setWildPos(newWildPos);
    setGameOver(checkWinByScore(newScore) || checkWinByColors(newColorTally));
    setDeck(newDeck);
    setAiCardsPlayedThisTurn([...aiCardsPlayedThisTurn, card.position]);
  }

  return (
    <div style={{ padding: 24, position: "relative" }}>
      <button onClick={onBack} style={{ position: "absolute", left: 16, top: 16 }}>Back</button>
      <div style={{
        margin: "0 auto 18px auto",
        padding: "18px 30px",
        borderRadius: 18,
        background: "rgba(255,255,255,0.26)",
        backdropFilter: "blur(8px)",
        boxShadow: "0 2px 16px #0001",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: "1.18em",
        fontWeight: 600
      }}>
        <span style={{ color: "#2b71e7", marginRight: 18 }}>Your Score: {score}</span>
        <span style={{ color: "#e76a2b", marginRight: 18 }}>AI Score: {aiScore}</span>
        <span style={{
          background: playerTurn ? "#2b71e7" : "#e76a2b",
          color: "#fff",
          borderRadius: 8,
          padding: "4px 14px",
          marginLeft: 18,
          boxShadow: "0 1px 4px #0002",
          fontWeight: 700,
          letterSpacing: "0.5px"
        }}>
          {gameOver ? (score > aiScore ? "You win!" : "AI wins!") : playerTurn ? "Your Turn" : "AI Thinking..."}
        </span>
      </div>
      <div>
        <strong>Your Colors:</strong>{" "}
        {COLORS.map(c => (
          <span key={c} style={{ color: c, marginRight: 12 }}>{c}: {colorTally[c]}</span>
        ))}
      </div>
      <div>
        <strong>AI Colors:</strong>{" "}
        {COLORS.map(c => (
          <span key={c} style={{ color: c, marginRight: 12 }}>{c}: {aiColorTally[c]}</span>
        ))}
      </div>
      <div style={{ margin: "18px 0" }}>
        <Board board={board} onPlay={playerTurn && !gameOver ? (card => handlePlayCard(card)) : undefined} />
      </div>
      <div>
        <strong>Your Hand:</strong>
        <Hand
          hand={hand}
          onPlay={playerTurn && !gameOver
            ? (card) => {
                if (!cardsPlayedThisTurn.includes(card.position)) handlePlayCard(card);
              }
            : undefined}
        />
        <DiscardPiles cards={discardPiles} />
      </div>
      <div>
        <strong>AI Discards:</strong>
        <DiscardPiles cards={aiDiscardPiles} />
      </div>
    </div>
  );
}
