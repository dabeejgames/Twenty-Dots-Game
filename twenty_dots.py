class Card:
    """Represents a single card in the Twenty Dots deck."""
    
    COLORS = ['red', 'blue', 'purple', 'green']
    POWER_TYPES = ['swap', 'remove', 'wild_place', 'double_score', 'card_swap', 'landmine']
    
    def __init__(self, location: str, color: str, power: str = None):
        """
        Initialize a card.
        
        Args:
            location: Grid position (e.g., "A1", "B4") or tuple like ('A', '1')
            color: Card color (red, blue, purple, green)
            power: Optional special power (swap, remove, wild_place, double_score, steal)
        """
        if isinstance(location, tuple):
            self.location = location
        else:
            self.location = location
        self.color = color
        self.power = power
    
    def is_power_card(self):
        """Check if this is a power card."""
        return self.power is not None
    
    def get_power_description(self):
        """Get description of the power."""
        descriptions = {
            'swap': '↔️ Dot Swap',
            'remove': '💣 Remove',
            'wild_place': '⭐ Wild Place',
            'double_score': '×2 Double',
            'card_swap': '🔄 Card Swap',
            'landmine': '💥 Land Mine'
        }
        return descriptions.get(self.power, '')
    
    def display_front(self):
        """Display the front of the card."""
        if self.power:
            power_symbol = {
                'swap': '↔️',
                'remove': '💣',
                'wild_place': '⭐',
                'double_score': '×2',
                'card_swap': '🔄',
                'landmine': '💥'
            }.get(self.power, '✨')
            return (
                f"┌─────────────┐\n"
                f"│{self.location:<11}│\n"
                f"│   {power_symbol} POWER  │\n"
                f"│    {self.location}      │\n"
                f"│             │\n"
                f"│{self.location:>11}│\n"
                f"└─────────────┘"
            )
        return (
            f"┌─────────────┐\n"
            f"│{self.location:<11}│\n"
            f"│             │\n"
            f"│    {self.location}      │\n"
            f"│             │\n"
            f"│{self.location:>11}│\n"
            f"└─────────────┘"
        )
    
    def display_back(self):
        """Display the back of the card with 20 dots."""
        dots = "● " * 20
        return (
            f"┌─────────────┐\n"
            f"│ {dots[:12]}│\n"
            f"│ {dots[12:24]}│\n"
            f"│ {dots[24:]}│\n"
            f"└─────────────┘"
        )
    
    def __str__(self):
        power_str = f" [{self.power}]" if self.power else ""
        return f"{self.location}-{self.color}{power_str}"
    
    def __repr__(self):
        return f"Card({self.location}, {self.color}, {self.power})"


class Dot:
    """Represents a dot on the game board."""
    
    DOT_COLORS = ['red', 'blue', 'purple', 'green', 'yellow']
    
    def __init__(self, color: str):
        if color not in self.DOT_COLORS:
            raise ValueError(f"Invalid dot color: {color}")
        self.color = color
    
    def __str__(self):
        color_symbol = {
            'red': '🔴',
            'blue': '🔵',
            'purple': '🟣',
            'green': '🟢',
            'yellow': '🟡'
        }
        return color_symbol.get(self.color, '●')
    
    def __repr__(self):
        return f"Dot({self.color})"


class TwentyDots:
    def __init__(self, num_players: int = 2, difficulty: str = 'easy', ai_opponents: dict = None, power_cards: bool = True):
        """Initialize a Twenty Dots game."""
        if num_players < 2 or num_players > 4:
            raise ValueError("Number of players must be between 2 and 4")
        if difficulty not in ['easy', 'hard']:
            raise ValueError("Difficulty must be 'easy' or 'hard'")
        
        self.num_players = num_players
        self.difficulty = difficulty
        self.power_cards_enabled = power_cards
        self.grid_size = 6
        self.grid = [[None for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        self.columns = ['1', '2', '3', '4', '5', '6']
        self.rows = ['A', 'B', 'C', 'D', 'E', 'F']
        self.colors = ['red', 'blue', 'purple', 'green']
        
        # Initialize deck
        self.deck = self._create_deck()
        
        # Player hands, scores, and AI status
        # ai_opponents: dict like {'Player 2': 'easy', 'Player 3': 'medium', 'Player 4': 'hard'}
        self.ai_opponents = ai_opponents or {}
        self.players = {f"Player {i+1}": {
            'hand': [], 
            'score': {color: 0 for color in self.colors}, 
            'total_dots': 0,
            'yellow_dots': 0,
            'is_ai': f"Player {i+1}" in self.ai_opponents,
            'double_next_match': False
        } for i in range(num_players)}
        self.current_player_idx = 0
        self.yellow_dot_position = None
        self.landmines = []  # List of landmines: [{'location': 'A1', 'color': 'red', 'player': 'Player 1'}, ...]
        
        # Win conditions
        if difficulty == 'easy':
            self.win_condition = lambda p: p['total_dots'] >= 20
        else:  # hard
            self.win_condition = lambda p: all(p['score'][color] >= 5 for color in self.colors)
    
    def display_grid(self):
        """Display the 6x6 grid with labels."""
        # Top column labels
        print("   " + " ".join(self.columns))
        print()
        
        # Grid with row labels
        for row_idx, row_num in enumerate(self.rows):
            row_display = row_num + "  "
            for col_idx in range(self.grid_size):
                dot = self.grid[row_idx][col_idx]
                if dot:
                    row_display += str(dot) + " "
                else:
                    row_display += "· "
            row_display += " " + row_num
            print(row_display)
        
        print()
        # Bottom column labels
        print("   " + " ".join(self.columns))
    
    def place_dot(self, col: str, row: str) -> bool:
        """
        Place a dot at the specified position.
        
        Args:
            col: Column letter (A-F)
            row: Row number (1-6)
        
        Returns:
            True if successful, False if invalid position or already occupied
        """
        if col not in self.columns or row not in self.rows:
            print(f"Invalid position: {col}{row}")
            return False
        
        col_idx = self.columns.index(col)
        row_idx = self.rows.index(row)
        
        if self.grid[row_idx][col_idx]:
            print(f"Position {col}{row} already occupied!")
            return False
        
        self.grid[row_idx][col_idx] = True
        return True
    
    def clear_dot(self, col: str, row: str) -> bool:
        """
        Clear a dot at the specified position.
        
        Args:
            col: Column letter (A-F)
            row: Row number (1-6)
        
        Returns:
            True if successful, False if invalid position or empty
        """
        if col not in self.columns or row not in self.rows:
            print(f"Invalid position: {col}{row}")
            return False
        
        col_idx = self.columns.index(col)
        row_idx = self.rows.index(row)
        
        if not self.grid[row_idx][col_idx]:
            print(f"Position {col}{row} is already empty!")
            return False
        
        self.grid[row_idx][col_idx] = False
        return True
    
    def count_dots(self) -> int:
        """Count total dots on the grid."""
        return sum(sum(1 for dot in row if dot) for row in self.grid)
    
    def _create_deck(self):
        """Create the full 144-card deck with optional special power cards added separately."""
        import random
        deck = []
        
        print("[DECK CREATION] Building new shuffled deck...")
        
        # Create 36 regular location cards for each color (144 total)
        all_locations = []
        for row in self.rows:
            for col in self.columns:
                all_locations.append(f"{row}{col}")
        
        for color in self.colors:
            for location in all_locations:
                deck.append(Card(location, color))
        
        print(f"[DECK CREATION] Created {len(deck)} cards across {len(self.colors)} colors")
        
        # Add power cards separately (not tied to specific locations)
        if self.power_cards_enabled:
            power_types = ['swap', 'remove', 'wild_place', 'double_score', 'card_swap']
            # Add 3 power cards per color (12 total)
            for color in self.colors:
                for _ in range(3):
                    power = random.choice(power_types)
                    # Power cards use 'PWR' as location to indicate they're special
                    deck.append(Card('PWR', color, power=power))
            
            # Add 3 landmine cards (neutral - no specific color for display, red for simplicity)
            for _ in range(3):
                deck.append(Card('PWR', 'red', power='landmine'))
        
        return deck
    
    def shuffle_deck(self):
        """Shuffle the deck."""
        import random
        random.shuffle(self.deck)
    
    def deal_cards(self, cards_per_player: int = 5):
        """
        Deal cards to all players.
        
        Args:
            cards_per_player: Number of cards each player receives
        """
        player_names = list(self.players.keys())
        card_idx = 0
        
        print(f"[DEAL_CARDS] Starting to deal {cards_per_player} cards to {len(player_names)} players")
        print(f"[DEAL_CARDS] First 10 cards in deck: {[(c.location, c.color) for c in self.deck[:10]]}")
        
        for _ in range(cards_per_player):
            for player in player_names:
                if card_idx < len(self.deck):
                    card = self.deck[card_idx]
                    print(f"[DEAL_CARDS] Dealing card {card_idx} to {player}: {card.location} {card.color}")
                    self.players[player]['hand'].append(card)
                    card_idx += 1
        
        # Remaining cards stay in deck for drawing
        self.deck = self.deck[card_idx:]
        print(f"[DEAL_CARDS] Dealing complete. {len(self.deck)} cards remaining in deck")
    
    def draw_card(self, player_name: str) -> Card:
        """Draw a card from the deck for a player."""
        if self.deck:
            card = self.deck.pop(0)
            self.players[player_name]['hand'].append(card)
            return card
        return None
    
    def roll_dice(self):
        """
        Roll both dice (letter and number).
        
        Returns:
            Tuple of (row, column) e.g., ('A', '1')
        """
        import random
        row = random.choice(self.rows)
        col = random.choice(self.columns)
        return row, col
    
    def place_wild_at_location(self, row: str, col: str) -> tuple:
        """Place yellow wild at specific location (power card ability). Returns (row, col) strings for match checking."""
        row_idx = self.rows.index(row)
        col_idx = self.columns.index(col)
        
        # Remove previous yellow dot if it exists
        if self.yellow_dot_position:
            old_row_idx, old_col_idx = self.yellow_dot_position
            self.grid[old_row_idx][old_col_idx] = None
        
        # Check if there's a landmine at this location - wild defuses it
        defused_landmine = False
        if hasattr(self, 'landmines') and (row, col) in self.landmines:
            del self.landmines[(row, col)]
            defused_landmine = True
        
        # Place new yellow dot
        self.grid[row_idx][col_idx] = Dot('yellow')
        self.yellow_dot_position = (row_idx, col_idx)
        # Return row, col, and whether a landmine was defused
        return (row, col, defused_landmine)
    
    def place_card_dot(self, card: Card) -> tuple:
        """Place a dot from a card on the board.
        Returns (success: bool, replaced_dot_color: str or None)
        """
        row = card.location[0]
        col = card.location[1]
        row_idx = self.rows.index(row)
        col_idx = self.columns.index(col)
        
        current = self.grid[row_idx][col_idx]
        
        # Check if position is empty
        if current is None:
            self.grid[row_idx][col_idx] = Dot(card.color)
            return (True, None)
        
        # If yellow dot is here, replace it and track it
        if current.color == 'yellow':
            self.grid[row_idx][col_idx] = Dot(card.color)
            self.yellow_dot_position = None
            return (True, 'yellow')
        
        # If a colored dot is here, replace it and award point
        if current.color in self.colors:
            replaced_color = current.color
            self.grid[row_idx][col_idx] = Dot(card.color)
            return (True, replaced_color)
        
        # Otherwise can't place
        return (False, None)
    
    def check_line_match(self, row: str, col: str, color: str) -> tuple:
        """
        Check for a line match (3 or more in a row) after placing a dot.
        Returns list of ALL dots that form lines with the newly placed dot (may include multiple matches).
        Yellow dots act as wildcards and match any color.
        """
        row_idx = self.rows.index(row)
        col_idx = self.columns.index(col)
        all_matches = []
        
        print(f"DEBUG check_line_match: Checking {row}{col} ({row_idx},{col_idx}) color={color}")
        
        # Directions: horizontal, vertical, diagonal-down, diagonal-up  
        # Format is (dx, dy) where dx is column change, dy is row change
        directions = [
            (1, 0),   # horizontal (right)
            (0, 1),   # vertical (down)
            (1, 1),   # diagonal down-right
            (1, -1)   # diagonal up-right  
        ]
        
        # When placing yellow wildcard, we need to check for matches with ALL adjacent colors
        # not just the first one we find, because yellow could form multiple matches
        if color == 'yellow':
            # Find all unique non-yellow colors adjacent to this position
            adjacent_colors = set()
            for dx, dy in directions:
                for direction in [-1, 1]:
                    x, y = col_idx + (dx * direction), row_idx + (dy * direction)
                    if 0 <= x < self.grid_size and 0 <= y < self.grid_size:
                        dot = self.grid[y][x]
                        if dot and dot.color != 'yellow':
                            adjacent_colors.add(dot.color)
            
            print(f"DEBUG: Yellow placed, found adjacent colors: {adjacent_colors}")
            
            # If no adjacent colors, no matches possible
            if not adjacent_colors:
                print(f"DEBUG: No adjacent colors for yellow, no matches possible")
                return [], 'yellow'
            
            # Try each adjacent color as a potential match target
            all_color_matches = {}
            for test_color in adjacent_colors:
                color_matches = []
                # Check all directions for this specific color
                for dx, dy in directions:
                    line = []
                    
                    # Check backwards (max 5 dots to prevent infinite loops)
                    x, y = col_idx - dx, row_idx - dy
                    safety_count = 0
                    while 0 <= x < self.grid_size and 0 <= y < self.grid_size and safety_count < 5:
                        dot = self.grid[y][x]
                        if dot and (dot.color == test_color or dot.color == 'yellow'):
                            line.append((x, y))
                            x -= dx
                            y -= dy
                            safety_count += 1
                        else:
                            break
                    
                    line.reverse()
                    line.append((col_idx, row_idx))  # Add the yellow dot
                    
                    # Check forwards (max 5 dots to prevent infinite loops)
                    x, y = col_idx + dx, row_idx + dy
                    safety_count = 0
                    while 0 <= x < self.grid_size and 0 <= y < self.grid_size and safety_count < 5:
                        dot = self.grid[y][x]
                        if dot and (dot.color == test_color or dot.color == 'yellow'):
                            line.append((x, y))
                            x += dx
                            y += dy
                            safety_count += 1
                        else:
                            break
                    
                    # If we found a line of 3 or more, save it
                    if len(line) >= 3:
                        color_matches.extend(line)
                
                if color_matches:
                    all_color_matches[test_color] = color_matches
            
            # Use the longest match found
            if all_color_matches:
                best_color = max(all_color_matches.keys(), key=lambda c: len(all_color_matches[c]))
                all_matches = all_color_matches[best_color]
                target_color = best_color
                print(f"DEBUG: Best match is {best_color} with {len(all_matches)} positions")
                
                # Remove duplicates and return
                seen = set()
                unique_matches = []
                for pos in all_matches:
                    if pos not in seen:
                        seen.add(pos)
                        unique_matches.append(pos)
                
                print(f"DEBUG: Returning {len(unique_matches)} unique matched positions: {unique_matches} (target_color={target_color})")
                return unique_matches, target_color
            else:
                print(f"DEBUG: No matches found for yellow")
                return [], 'yellow'
        else:
            # Regular colored dot - simpler logic
            target_color = color
            print(f"DEBUG: Regular color placed: {target_color}")
            
            # Check all directions and collect all matches for regular colored dots
            for dx, dy in directions:
                line = []
                
                # Check backwards
                x, y = col_idx - dx, row_idx - dy
                print(f"DEBUG: Checking direction ({dx},{dy}) backwards from ({col_idx},{row_idx})")
                while 0 <= x < self.grid_size and 0 <= y < self.grid_size:
                    dot = self.grid[y][x]
                    print(f"DEBUG: Checking backwards position ({x},{y}): dot={'None' if dot is None else dot.color}")
                    # Yellow dots act as wildcards
                    if dot and (dot.color == target_color or dot.color == 'yellow'):
                        print(f"DEBUG: Found {dot.color} at ({x},{y}) backwards")
                        line.append((x, y))
                        x -= dx
                        y -= dy
                    else:
                        print(f"DEBUG: Breaking backwards check at ({x},{y})")
                        break
                
                line.reverse()
                line.append((col_idx, row_idx))  # Add the newly placed dot
                
                # Check forwards
                x, y = col_idx + dx, row_idx + dy
                print(f"DEBUG: Checking direction ({dx},{dy}) forwards from ({col_idx},{row_idx})")
                while 0 <= x < self.grid_size and 0 <= y < self.grid_size:
                    dot = self.grid[y][x]
                    print(f"DEBUG: Checking forwards position ({x},{y}): dot={'None' if dot is None else dot.color}")
                    # Yellow dots act as wildcards
                    if dot and (dot.color == target_color or dot.color == 'yellow'):
                        print(f"DEBUG: Found {dot.color} at ({x},{y}) forwards")
                        line.append((x, y))
                        x += dx
                        y += dy
                    else:
                        print(f"DEBUG: Breaking forwards check at ({x},{y})")
                        break
                
                # If we found a line of 3 or more, add it to all matches
                print(f"DEBUG: Direction ({dx},{dy}) found line of length {len(line)}: {line}")
                if len(line) >= 3:
                    all_matches.extend(line)
        
        # Remove duplicates while preserving order (the placed dot might be in multiple matches)
        seen = set()
        unique_matches = []
        for pos in all_matches:
            if pos not in seen:
                seen.add(pos)
                unique_matches.append(pos)
        
        print(f"DEBUG: Returning {len(unique_matches)} unique matched positions: {unique_matches} (target_color={target_color})")
        return unique_matches, target_color
    
    def collect_dots(self, positions: list, player_name: str, color: str):
        """Collect dots from the board and add to player's score."""
        # Check if double score is active
        multiplier = 2 if self.players[player_name].get('double_next_match', False) else 1
        
        for col_idx, row_idx in positions:
            dot = self.grid[row_idx][col_idx]
            if dot:
                # If it's a yellow dot, track it separately
                if dot.color == 'yellow':
                    self.players[player_name]['yellow_dots'] += multiplier
                    print(f"[COLLECT_DOTS] {player_name} collected yellow dot! Total yellow: {self.players[player_name]['yellow_dots']}")
                else:
                    # Award points for the actual dot color collected
                    self.players[player_name]['score'][dot.color] += multiplier
                    self.players[player_name]['total_dots'] += multiplier
                self.grid[row_idx][col_idx] = None
        
        # Reset double score flag after use
        if self.players[player_name].get('double_next_match', False):
            self.players[player_name]['double_next_match'] = False
    
    def get_player_hand(self, player_name: str):
        """Get a player's current hand."""
        return self.players[player_name]['hand']
    
    def swap_dots(self, pos1: tuple, pos2: tuple) -> bool:
        """Swap two dots on the board. Returns True if successful."""
        r1, c1 = pos1
        r2, c2 = pos2
        
        if not (0 <= r1 < self.grid_size and 0 <= c1 < self.grid_size):
            return False
        if not (0 <= r2 < self.grid_size and 0 <= c2 < self.grid_size):
            return False
        
        # Swap the dots
        self.grid[r1][c1], self.grid[r2][c2] = self.grid[r2][c2], self.grid[r1][c1]
        return True
    
    def remove_dot(self, row_idx: int, col_idx: int) -> bool:
        """Remove a dot from the board. Returns True if there was a dot to remove."""
        if not (0 <= row_idx < self.grid_size and 0 <= col_idx < self.grid_size):
            return False
        
        if self.grid[row_idx][col_idx]:
            self.grid[row_idx][col_idx] = None
            return True
        return False
    
    def place_wild_at_location(self, row: str, col: str) -> tuple:
        """Place yellow wild at specific location (power card ability). Returns (row, col) for match checking."""
        row_idx = self.rows.index(row)
        col_idx = self.columns.index(col)
        
        # Remove previous yellow dot if it exists
        if self.yellow_dot_position:
            old_row_idx, old_col_idx = self.yellow_dot_position
            self.grid[old_row_idx][old_col_idx] = None
        
        # Place new yellow dot
        self.grid[row_idx][col_idx] = Dot('yellow')
        self.yellow_dot_position = (row_idx, col_idx)
        # Return row and col strings for check_line_match
        return (row, col)
    
    def steal_card(self, from_player: str, to_player: str) -> Card:
        """Steal a random card from one player's hand to another."""
        import random
        if not self.players[from_player]['hand']:
            return None
        
        stolen_card = random.choice(self.players[from_player]['hand'])
        self.players[from_player]['hand'].remove(stolen_card)
        self.players[to_player]['hand'].append(stolen_card)
        return stolen_card
    
    def place_landmine(self, location: str, color: str, player: str):
        """Place a landmine at a specific location with a color. Returns True if successful, False if space occupied."""
        # Check if the location is empty
        row = location[0]
        col = location[1]
        
        if row not in self.rows or col not in self.columns:
            return False
        
        row_idx = self.rows.index(row)
        col_idx = self.columns.index(col)
        
        # Check if space is empty (None means empty)
        if self.grid[row_idx][col_idx] is not None:
            return False
        
        self.landmines.append({
            'location': location,
            'color': color,
            'player': player
        })
        return True
    
    def check_and_detonate_landmine(self, location: str, player: str) -> dict:
        """Check if a landmine exists at location and detonate it. Returns landmine info or None."""
        for i, mine in enumerate(self.landmines):
            if mine['location'] == location:
                # Detonate! Remove the landmine from the list
                detonated = self.landmines.pop(i)
                
                # Get the position indices
                row_idx = self.rows.index(location[0])
                col_idx = self.columns.index(location[1])
                
                # Remove all dots within 1 square (3x3 area centered on landmine)
                removed_positions = []
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        r = row_idx + dr
                        c = col_idx + dc
                        if 0 <= r < self.grid_size and 0 <= c < self.grid_size:
                            if self.grid[r][c]:
                                removed_positions.append((c, r))
                                self.grid[r][c] = None
                
                # Penalize the player who triggered it (lose 2 dots of the mine's color)
                mine_color = detonated['color']
                if self.players[player]['score'][mine_color] >= 2:
                    self.players[player]['score'][mine_color] -= 2
                    self.players[player]['total_dots'] -= 2
                elif self.players[player]['score'][mine_color] == 1:
                    self.players[player]['score'][mine_color] = 0
                    self.players[player]['total_dots'] -= 1
                
                detonated['removed_positions'] = removed_positions
                return detonated
        
        return None
    
    def get_current_player(self) -> str:
        """Get the name of the current player."""
        player_names = list(self.players.keys())
        return player_names[self.current_player_idx]
    
    def next_player(self):
        """Move to the next player."""
        self.current_player_idx = (self.current_player_idx + 1) % self.num_players
    
    def check_win(self) -> bool:
        """Check if the current player has won."""
        player_name = self.get_current_player()
        return self.win_condition(self.players[player_name])
    
    def display_scores(self):
        """Display all player scores."""
        print("\n" + "=" * 50)
        print("SCORES")
        print("=" * 50)
        for player_name, data in self.players.items():
            total = data['total_dots']
            if self.difficulty == 'easy':
                print(f"{player_name}: {total} total dots")
            else:
                color_counts = ' | '.join([f"{c}: {data['score'][c]}" for c in self.colors])
                print(f"{player_name}: {color_counts} | Total: {total}")
    
    def display_deck_info(self):
        """Display information about the deck."""
        print(f"Cards in deck: {len(self.deck)}")
        print(f"\nPlayer hands:")
        for player, data in self.players.items():
            print(f"  {player}: {len(data['hand'])} cards")


def main():
    """Main game loop."""
    import random
    
    print("Welcome to Twenty Dots!")
    print("=" * 50)
    
    # Get number of players
    while True:
        try:
            num_players = int(input("\nHow many players? (2-4): "))
            if 2 <= num_players <= 4:
                break
            else:
                print("Please enter a number between 2 and 4.")
        except ValueError:
            print("Invalid input. Please enter a number.")
    
    # Get difficulty
    while True:
        difficulty = input("\nChoose difficulty (easy/hard): ").lower().strip()
        if difficulty in ['easy', 'hard']:
            break
        else:
            print("Please enter 'easy' or 'hard'.")
    
    game = TwentyDots(num_players, difficulty)
    
    # Shuffle and deal
    game.shuffle_deck()
    game.deal_cards(cards_per_player=5)
    
    print(f"\n✓ Game initialized with {num_players} players on {difficulty} mode!")
    print(f"✓ Win Condition: ", end="")
    if difficulty == 'easy':
        print("First to 20 total dots")
    else:
        print("First to get 5 of each color")
    
    # Roll for first yellow dot
    print("\n" + "=" * 50)
    print("INITIAL YELLOW DOT PLACEMENT")
    print("=" * 50)
    
    first_player = game.get_current_player()
    print(f"\n{first_player} rolls the dice...")
    input("Press Enter to roll...")
    
    col, row = game.roll_dice()
    print(f"\n🎲 Rolled: {col}{row}")
    game.place_yellow_dot(col, row)
    
    game.display_grid()
    game.display_scores()
    
    # Main game loop
    turn_number = 1
    
    while True:
        print("\n" + "=" * 50)
        print(f"TURN {turn_number} - {game.get_current_player()}'s Turn")
        print("=" * 50)
        
        current_player = game.get_current_player()
        hand = game.get_player_hand(current_player)
        
        print(f"\nYour hand ({len(hand)} cards):")
        for i, card in enumerate(hand, 1):
            print(f"  {i}. {card}")
        
        game.display_grid()
        
        # Player must play 2 cards
        cards_to_play = []
        
        for play_num in range(2):
            while True:
                try:
                    card_idx = int(input(f"\nPlay card {play_num + 1}/2 (enter number 1-{len(hand)}): ")) - 1
                    if 0 <= card_idx < len(hand) and card_idx not in cards_to_play:
                        cards_to_play.append(card_idx)
                        break
                    else:
                        print("Invalid selection or card already selected.")
                except ValueError:
                    print("Please enter a valid number.")
        
        # Execute card plays
        total_collected = []
        play_colors = []
        
        for card_idx in sorted(cards_to_play, reverse=True):
            card = hand[card_idx]
            play_colors.append(card.color)
            
            print(f"\nPlaying: {card}")
            
            if game.place_card_dot(card):
                print(f"✓ Placed {card.color} dot at {card.location}")
                
                # Check for line match
                line_match = game.check_line_match(card.location[0], card.location[1], card.color)
                if line_match:
                    print(f"✓✓✓ LINE MATCH! {len(line_match)} dots collected!")
                    game.collect_dots(line_match, current_player, card.color)
                    total_collected.extend(line_match)
            else:
                print(f"✗ Could not place card at {card.location}")
            
            hand.pop(card_idx)
        
        # Display grid after cards played
        game.display_grid()
        
        # Draw new cards to get back to 5 hand
        while len(hand) < 5 and game.deck:
            game.draw_card(current_player)
        
        # Roll for new yellow dot if line match occurred
        if total_collected:
            print(f"\n{current_player} rolling for new yellow dot placement...")
            input("Press Enter to roll...")
            col, row = game.roll_dice()
            print(f"🎲 Rolled: {col}{row}")
            game.place_yellow_dot(col, row)
        
        # Check if player won
        if game.check_win():
            print("\n" + "=" * 50)
            print(f"🎉 {current_player} WINS! 🎉")
            print("=" * 50)
            game.display_scores()
            break
        
        game.display_scores()
        
        # Next player
        game.next_player()
        turn_number += 1
        
        input("\nPress Enter for next player's turn...")


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
