import random
from typing import List, Tuple


class AIPlayer:
    """AI player that makes strategic decisions."""
    
    def __init__(self, difficulty: str = 'medium'):
        """
        Initialize AI player.
        
        Args:
            difficulty: 'easy', 'medium', or 'hard'
        """
        self.difficulty = difficulty
    
    def choose_cards(self, hand: List) -> List[int]:
        """
        Choose 2 cards to play from the hand.
        
        Args:
            hand: List of Card objects
        
        Returns:
            List of 2 indices to play
        """
        if self.difficulty == 'easy':
            return self._choose_cards_easy(hand)
        elif self.difficulty == 'medium':
            return self._choose_cards_medium(hand)
        else:
            return self._choose_cards_hard(hand)
    
    def _choose_cards_easy(self, hand: List) -> List[int]:
        """Easy AI - random selection."""
        if len(hand) < 2:
            return list(range(len(hand)))
        indices = list(range(len(hand)))
        random.shuffle(indices)
        return indices[:2]
    
    def _choose_cards_medium(self, hand: List) -> List[int]:
        """Medium AI - simple strategy (prefer same colors)."""
        if len(hand) < 2:
            return list(range(len(hand)))
        
        # Group cards by color
        color_groups = {}
        for i, card in enumerate(hand):
            if card.color not in color_groups:
                color_groups[card.color] = []
            color_groups[card.color].append(i)
        
        # Prefer cards of the same color
        for color, indices in color_groups.items():
            if len(indices) >= 2:
                return indices[:2]
        
        # Otherwise pick randomly
        indices = list(range(len(hand)))
        random.shuffle(indices)
        return indices[:2]
    
    def _choose_cards_hard(self, hand: List) -> List[int]:
        """Hard AI - advanced strategy with board awareness."""
        if len(hand) < 2:
            return list(range(len(hand)))
        
        # Try to maximize potential line matches
        best_score = -1
        best_combination = None
        
        for i in range(len(hand)):
            for j in range(i + 1, len(hand)):
                # Score based on same color (higher priority for line matching)
                score = 0
                if hand[i].color == hand[j].color:
                    score += 100
                
                # Additional strategy: prefer cards that aren't duplicated
                if hand[i].location != hand[j].location:
                    score += 50
                
                if score > best_score:
                    best_score = score
                    best_combination = [i, j]
        
        # Ensure we always return a valid combination
        if best_combination is None or len(best_combination) < 2:
            return [0, 1] if len(hand) >= 2 else list(range(len(hand)))
        
        return best_combination
    
    def make_move(self, game_state: dict) -> Tuple[List[int], str]:
        """
        Make a complete turn decision.
        
        Args:
            game_state: Dictionary with game information
        
        Returns:
            Tuple of (card_indices, move_description)
        """
        hand = game_state.get('hand', [])
        cards_to_play = self.choose_cards(hand)
        
        description = f"AI plays {len(cards_to_play)} cards"
        
        return cards_to_play, description
