# 💥 Land Mine Card Feature

## Overview
Land Mine cards add a tactical element to Twenty Dots, allowing players to set traps that detonate when opponents play on them.

## How It Works

### 1. Acquiring Land Mines
- The deck includes **3 Land Mine power cards** (when power cards are enabled)
- Land mines have the "PWR" location (not tied to any grid position)
- They can be drawn like any other card

### 2. Placing a Land Mine
When you play a Land Mine card:
1. A red-themed dialog prompts you to **select a regular card from your hand to sacrifice**
2. The sacrificed card determines:
   - **Location**: Where the mine will be placed (e.g., A1, C4, F6)
   - **Color**: What color penalty the mine will inflict (red, blue, green, purple)
3. The sacrificed card is removed from your hand permanently
4. The mine is placed at that location (face-down, hidden from other players)
5. A success message confirms the mine is armed

### 3. Mine Display
- Active mines are shown **above the game board** in a dedicated area
- Each mine appears as a face-down card showing:
  - 💥 explosion emoji
  - "???" to indicate hidden location
- Red border and dark styling indicate danger
- **Other players cannot see the exact location** (face-down)

### 4. Detonation
When **any player** (including you!) plays a card on a mined location:
1. **BOOM!** The mine detonates immediately
2. A dramatic red dialog shows:
   - "💥 LAND MINE DETONATED! 💥"
   - Number of dots removed in the blast
   - Penalty applied
3. **Blast Effect**: All dots in a **3x3 area** around the mine are removed from the board
4. **Penalty**: The triggering player loses **2 dots** of the mine's color
   - If they only have 1 dot of that color, they lose 1
   - If they have 0 dots of that color, no penalty
5. The mine is removed from the game after detonating
6. The triggering player's card is still placed normally after the blast

## Strategy Tips

### Offensive Use
- **Block high-traffic locations**: Place mines on commonly played spots (center positions, corners)
- **Target specific players**: Use colors that opponents are collecting
- **Protect your leads**: Mine locations opponents need for matches

### Defensive Considerations
- **Remember your mines!** You can trigger them yourself
- **Track played locations**: Avoid your own mines by remembering where you placed them
- **Sacrifice wisely**: Choose cards that are less useful for your current strategy

### Advanced Tactics
- **Bluff potential**: Opponents don't know exact mine locations, creating psychological pressure
- **Area denial**: A single mine can make opponents hesitant to play entire regions
- **Combo setup**: Clear opponent dots before they can score matches
- **Late-game disruption**: Deploy when opponents are close to winning

## Technical Details

### Card Properties
- **Type**: Power Card
- **Power**: 'landmine'
- **Location**: 'PWR' (not grid-based)
- **Symbol**: 💥

### Game State
- Active mines stored in `game.landmines` list
- Each entry contains:
  - `location`: Grid position (e.g., 'A1')
  - `color`: Penalty color (red/blue/green/purple)
  - `player`: Who placed the mine

### Detonation Mechanics
- **Blast radius**: 3x3 grid centered on mine location
- **Edge handling**: Blast correctly limited at board edges
- **Penalty calculation**: Safely handles cases where player has fewer dots than penalty
- **Removed positions**: All affected grid positions tracked and cleared

## Balancing
- **Limited quantity**: Only 3 mines in deck
- **Self-damage risk**: Placing mines creates strategic risk/reward
- **No targeted placement**: Must sacrifice a card, can't choose arbitrary locations
- **One-time use**: Mines are removed after detonating
- **Visible count**: Players can see total number of active mines (but not locations)

## Implementation Notes
- Mines integrate seamlessly with existing turn flow
- Detonation checked before dot placement
- GUI updates automatically after blast
- Compatible with all other power cards
- Network multiplayer support included
