# Power Cards Feature

## Overview
Special power cards have been added to Twenty Dots to add strategic depth and exciting gameplay moments!

## Power Card Types

### 1. ↔️ Swap (swap)
- **Effect**: Swap the positions of any two dots on the board
- **Strategy**: Move dots to create matches or disrupt opponent setups
- **Activation**: Select two grid positions when prompted

### 2. 💣 Remove (remove)
- **Effect**: Remove any single dot from the board
- **Strategy**: Clear blocking dots or prepare the board for future matches
- **Activation**: Select one grid position to remove

### 3. ⭐ Wild Place (wild_place)
- **Effect**: Place a yellow wild dot at any location on the board
- **Strategy**: Create instant match opportunities or block opponent strategies
- **Activation**: Select where to place the wild dot

### 4. ×2 Double Score (double_score)
- **Effect**: Your next match will score double points (2x)
- **Strategy**: Save for a big match to maximize scoring
- **Activation**: Automatic - your next match gets 2x multiplier

### 5. 🔀 Steal (steal)
- **Effect**: Steal a random card from another player's hand
- **Strategy**: Weaken opponents while strengthening your own position
- **Activation**: Select which player to steal from

## How Power Cards Work

### In the Deck
- **Total Power Cards**: 12 (3 per color)
- **Distribution**: Randomly assigned from the 5 power types
- **Regular Cards**: 132 (36 per color)

### Visual Indicators
Power cards are displayed with special badges:
- Golden ⚡ lightning bolt icon
- Power type description with emoji symbol
- Gold border with semi-transparent background

### Playing Power Cards
1. Select a power card from your hand (shows power badge)
2. Click "Play Selected Cards"
3. Follow the activation prompt for that power type
4. The power effect takes place immediately
5. The card is discarded after use

### Important Notes
- Power cards count toward your 2-card-per-turn limit
- Power cards are activated before being placed on the board
- Double Score effect applies to your very next match only
- Steal can fail if target player has no cards
- Wild Place can trigger matches at the placement location

## Technical Implementation

### Card Class Changes
```python
Card(location, color, power=None)
- is_power_card() -> bool
- get_power_description() -> str
```

### Player State
Each player now has a `double_next_match` flag that tracks the Double Score power effect.

### Power Activation Flow
1. Card selected and played
2. `activate_power_card()` called
3. Dialog shown for user input (if needed)
4. Power effect applied to game state
5. Board and scores updated

## Strategy Tips
- **Swap**: Save for critical moments when you need to complete a match
- **Remove**: Clear yellow wilds that benefit opponents
- **Wild Place**: Combine with existing dots for instant 3-of-a-kind
- **Double Score**: Use before playing multiple matching cards
- **Steal**: Target players with large hands to disrupt their plans

Enjoy the enhanced gameplay with power cards!
