# Power Play

## Online: six powers, meaningful choices

Enable **Power Play** when creating a room or starting Practice. Regular-card play stays the default. The host can change this setting between rounds; changing it clears readiness. Everyone sees the selected rules in the lobby and at the table.

Power Play uses **144 regular cards plus 24 powers**: one Paint, Shift, Swap, Block, Erase, and Tax in each of the four regular colors (168 total). Swap replaces Refresh. Powers are visible in your private hand and occupy normal card slots. Both regular cards and powers recycle when the deck empties.

| Card | Effect | Targets |
| --- | --- | --- |
| **✦ Paint** | Place a dot of the card’s color on any empty square. | One empty square |
| **↗ Shift** | Move a dot matching the card’s color one square up, down, left, or right into an empty space. No diagonal moves. Yellow cannot move. | Matching-color source dot, then empty orthogonal neighbor |
| **⇄ Swap** | Exchange any two regular dots anywhere on the board. Neither may be yellow. The card’s color does not matter; the dots may have the same or different colors. | Two distinct occupied, non-wild squares |
| **⛔ Block** | Block an empty square until your next turn begins. Nobody can play a regular card, Paint, or Shift there, and the wild dice re-roll if they land on it. The card’s color does not matter. | One empty, unblocked square |
| **✕ Erase** | Remove one dot matching the card’s color. Nobody scores it. | One dot of the card’s color |
| **¤ Tax** | Take up to two dots of the card’s color from an opponent tied for the most dots. Nobody gains them. You can’t tax anyone while you lead alone. | One opponent tied for the lead who holds that color |

### Turn rules

- Roll first whenever the wild dice are required.
- Play **one power instead of your two regular cards**. A power cannot follow a regular card or be combined with another power.
- Tap a power to read its instructions. All powers mark legal targets on the board. Choose targets, inspect the preview (both exchanged colors for Swap), then confirm with the main action button.
- Cancel or choose targets again before confirming; nothing is spent until confirmation.
- Paint, Shift, and Swap score completed lines under the existing game rules. Placing, moving, or swapping alone does not score. Block, Erase, and Tax never score for anyone. Paint and Shift need empty destinations; Swap exchanges two existing dots without replacement points.
- Swap checks both positions on the exchanged board before collecting. Overlapping lines collect each dot only once, including a shared yellow wildcard. A shared line is counted only once.
- If a power collects yellow, roll again before the next player starts. A winning power ends the round immediately instead.
- Keep your other cards and draw back to five after using a power. If the deck runs out, actual discarded cards are shuffled back in; a played power may be drawn again.
- If there is no valid target, keep the card and choose a regular card, another power, or pass.

### Why this set?

Paint creates opportunities, Shift makes a small adjustment with a matching color, and Swap rearranges two existing dots. Block, Erase, and Tax are the answers to them: hold a square someone needs, break up a line before it finishes, or slow down whoever is ahead. Each trades away a full turn. Tax only reaches the leader, so it can't be piled onto a player who is already behind.

Every effect is public: blocks show on everyone's board, and each erase or tax appears in the move summary. Online play deliberately leaves out score multipliers, hidden traps, hand theft, and unrestricted wild placement to keep turns clear and targeting comfortable on phones.

The computer understands the online card format and can use powers when it cannot select regular cards. Medium and Hard value Block and Erase by the lines they deny opponents, and Tax by the goal progress it takes from the leader. They never plan a card onto a blocked square. Game goals, series scores, rotating starters, and saved seats work with either deck.

## Server and client contract

- Creation/practice accept a strict optional `power_cards` boolean. Public state includes `power_cards`; rematch state includes `next_power_cards`.
- Private hands represent a power as `{ "location": "PWR", "color": "red", "power": "paint" }`. Regular card coordinates are unchanged.
- `play_power` requires `game_id`, current integer `round_id`, the owned `card`, and `targets` (one coordinate string for Paint, Block, or Erase; two for Shift or Swap; one opponent's player name for Tax). The retired `refresh` power is rejected.
- Public state includes `blocks: [{location, player}]`. A block is removed when its player's turn begins, saved with the room, and cleared by rematches. `play_cards` rejects a card on a blocked square without changing state.
- The server validates membership, turn, round, ownership, full-turn availability, and every target before changing state. Regular `play_cards` requests cannot consume powers.
- Public `last_move` uses `kind: "power"`, the power key, placements, collections, actual score delta, an optional `removed` list for Shift and Erase, `blocked` for Block, and `taxed: {player, color, count}` for Tax. Swap records both positions and their exchanged colors in `placements`. Opponents never receive private hands.
- Manual starts use the same supported deck as automatic starts. No network route silently enables desktop-only powers.
- Rematches recreate the selected deck, preserving room credentials and series state. Deck recycling never duplicates card objects or includes cards held in other hands.

## Desktop variant

The desktop GUI retains its separate existing implementation in [gui_game.py](gui_game.py): Swap, Remove, Wild Place, Double Score, Card Swap, and Landmine. This online update does **not** alter those desktop rules or replace their activation dialogs. The older name “Steal” referred to a different proposed mechanic; it is not part of online Power Play.

See [LANDMINE_FEATURE.md](LANDMINE_FEATURE.md) for the desktop landmine variant. Legacy network GUIs do not have the browser’s targeting interface; use the browser for Power Play.

## Validation

- Python Socket.IO regressions cover all six powers, invalid requests, card identity conservation, AI fallback, concurrent submissions, mandatory rolls, winning moves, and rematch options.
- `npm run test:replay --prefix tests` also runs [tests/browser_powers.cjs](tests/browser_powers.cjs) through real browser clicks against the isolated fixture server. It checks four-player targeting, previews/cancellation, keyboard selection, scoring, hand privacy, reconnection, full-turn costs, recycling, and host rule changes.
- Keep fixtures local. Production has no test setup endpoint.
