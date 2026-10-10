# Power Play

## Online: three powers, meaningful choices

Enable **Power Play** when creating a room or starting Practice. Regular-card play stays the default. The host can change this setting between rounds; changing it clears readiness. Everyone sees the selected rules in the lobby and at the table.

Power Play uses **144 regular cards plus 12 powers**: one Paint, Shift, and Refresh in each of the four regular colors (156 total). Powers are visible in your private hand and occupy normal card slots. Both regular cards and powers recycle when the deck empties.

| Card | Effect | Targets |
| --- | --- | --- |
| **✦ Paint** | Place a dot of the card’s color on any empty square. | One empty square |
| **↗ Shift** | Move a regular colored dot one square up, down, left, or right into an empty space. No diagonal moves. It keeps its original color; the power card’s color does not matter. Yellow cannot move. | Source dot, then empty orthogonal neighbor |
| **↻ Refresh** | Discard the power and your remaining hand, then draw up to five cards. No opponent’s hand is accessed. | None |

### Turn rules

- Roll first whenever the wild dice are required.
- Play **one power instead of your two regular cards**. A power cannot follow a regular card or be combined with another power.
- Tap a power to read its instructions. Paint and Shift mark legal targets on the board. Choose targets, inspect the preview, then confirm with the main action button.
- Cancel or choose targets again before confirming; nothing is spent until confirmation.
- Paint and Shift score completed lines under the existing game rules. Placing or moving a dot alone does not score, and powers cannot replace occupied destinations.
- If a power collects yellow, roll again before the next player starts. A winning power ends the round immediately instead.
- Draw back to five after using a power. If the deck runs out, actual discarded cards are shuffled back in; Refresh can draw cards you just discarded. It does not guarantee five different cards.
- If there is no valid target, keep the card and choose a regular card, another power, or pass.

### Why this set?

Paint creates opportunities, Shift rewards reading the board, and Refresh helps with an awkward hand. Each trades away a full turn. Online play deliberately leaves out score multipliers, hidden traps, hand theft, and unrestricted wild placement to keep turns clear and targeting comfortable on phones.

The computer understands the online card format and can use powers when it cannot select regular cards. Game goals, series scores, rotating starters, and saved seats work with either deck.

## Server and client contract

- Creation/practice accept a strict optional `power_cards` boolean. Public state includes `power_cards`; rematch state includes `next_power_cards`.
- Private hands represent a power as `{ "location": "PWR", "color": "red", "power": "paint" }`. Regular card coordinates are unchanged.
- `play_power` requires `game_id`, current integer `round_id`, the owned `card`, and `targets` (coordinate strings; an empty array for Refresh).
- The server validates membership, turn, round, ownership, full-turn availability, and every target before changing state. Regular `play_cards` requests cannot consume powers.
- Public `last_move` uses `kind: "power"`, the power key, placements, collections, actual score delta, and an optional `removed` source list for Shift. Opponents never receive private hands.
- Manual starts use the same supported deck as automatic starts. No network route silently enables desktop-only powers.
- Rematches recreate the selected deck, preserving room credentials and series state. Deck recycling never duplicates card objects or includes cards held in other hands.

## Desktop variant

The desktop GUI retains its separate existing implementation in [gui_game.py](gui_game.py): Swap, Remove, Wild Place, Double Score, Card Swap, and Landmine. This online update does **not** alter those desktop rules or replace their activation dialogs. The older name “Steal” referred to a different proposed mechanic; it is not part of online Power Play.

See [LANDMINE_FEATURE.md](LANDMINE_FEATURE.md) for the desktop landmine variant. Legacy network GUIs do not have the browser’s targeting interface; use the browser for Power Play.

## Validation

- Python Socket.IO regressions cover all three powers, invalid requests, card identity conservation, AI fallback, concurrent submissions, mandatory rolls, winning moves, and rematch options.
- `npm run test:replay --prefix tests` also runs [tests/browser_powers.cjs](tests/browser_powers.cjs) through real browser clicks against the isolated fixture server. It checks four-player targeting, previews/cancellation, keyboard selection, scoring, hand privacy, reconnection, full-turn costs, recycling, and host rule changes.
- Keep fixtures local. Production has no test setup endpoint.
