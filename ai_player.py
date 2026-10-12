import random
from typing import List, Tuple

SIZE = 6
ROWS = 'ABCDEF'
COLUMNS = '123456'
COLORS = ('red', 'blue', 'purple', 'green')
DIRECTIONS = ((1, 0), (0, 1), (1, 1), (1, -1))
WIN_BONUS = 1000
HAND_SIZE = 5
DECK_SIZE = 144  # 36 locations x 4 regular colors; power cards never land as dots.


# --- Board simulation -------------------------------------------------------
# A board is a 6x6 list of color strings (or None), indexed board[row][col].
# These mirror TwentyDots.check_line_match/collect_dots and GameSession's
# apply_cards/apply_power without the logging, so the AI can search quickly.

def find_match(board, row, col, color):
    """Positions (x, y) collected by a dot of `color` at (row, col), and the match color."""
    def line_through(test_color, dx, dy):
        line = []
        for sign in (-1, 1):
            x, y = col + sign * dx, row + sign * dy
            while 0 <= x < SIZE and 0 <= y < SIZE and board[y][x] in (test_color, 'yellow'):
                line.append((x, y))
                x, y = x + sign * dx, y + sign * dy
        return line + [(col, row)]

    if color == 'yellow':
        adjacent = {board[row + sy * dy][col + sx * dx]
                    for dx, dy in DIRECTIONS for sx, sy in ((1, 1), (-1, -1))
                    if 0 <= col + sx * dx < SIZE and 0 <= row + sy * dy < SIZE}
        best, best_len = [], 0
        for test_color in sorted(adjacent - {None, 'yellow'}):
            found = [p for dx, dy in DIRECTIONS
                     for line in [line_through(test_color, dx, dy)] if len(line) >= 3
                     for p in line]
            if len(found) > best_len:
                best, best_len, color = found, len(found), test_color
        matches = best
    else:
        matches = [p for dx, dy in DIRECTIONS
                   for line in [line_through(color, dx, dy)] if len(line) >= 3 for p in line]
    return list(dict.fromkeys(matches)), color


def empty_gains():
    return {'total': 0, 'yellow': 0, **dict.fromkeys(COLORS, 0)}


def collect(board, positions, gains):
    """Remove matched dots, crediting each actual color. Returns True if a wild was collected."""
    wild = False
    for x, y in positions:
        dot = board[y][x]
        if dot is None:
            continue
        gains[dot] += 1
        if dot == 'yellow':
            wild = True
        else:
            gains['total'] += 1
        board[y][x] = None
    return wild


def place(board, row, col, color, gains):
    """Play one card in place. Returns True if the wild was replaced or collected."""
    replaced = board[row][col]
    board[row][col] = color
    if replaced is not None:
        gains[replaced] += 1
        gains['total'] += 1
    match, _ = find_match(board, row, col, color)
    wild = collect(board, match, gains) if match else False
    return replaced == 'yellow' or wild


def simulate_cards(board, cards):
    """Play (location, color) cards in order on a copy. Returns (board, gains, touched_wild)."""
    board = [row[:] for row in board]
    gains, wild = empty_gains(), False
    for location, color in cards:
        wild |= place(board, ROWS.index(location[0]), COLUMNS.index(location[1]), color, gains)
    return board, gains, wild


def simulate_power(board, power, color, cells):
    """Apply a validated power with (row, col) target cells on a copy."""
    board = [row[:] for row in board]
    gains, wild = empty_gains(), False
    if power == 'swap':
        (ra, ca), (rb, cb) = cells
        board[ra][ca], board[rb][cb] = board[rb][cb], board[ra][ca]
        matches = [find_match(board, r, c, board[r][c])[0] for r, c in cells]
        for match in matches:
            wild |= collect(board, match, gains)
    else:
        if power == 'shift':
            (sr, sc), (row, col) = cells
            color, board[sr][sc] = board[sr][sc], None
        else:
            (row, col), = cells
        board[row][col] = color
        match, _ = find_match(board, row, col, color)
        if match:
            wild = collect(board, match, gains)
    return board, gains, wild


def response_gains(board, row, col, color):
    """Gains from one card placed on `board`, without copying it."""
    replaced = board[row][col]
    board[row][col] = color
    match, _ = find_match(board, row, col, color)
    gains = empty_gains()
    if replaced is not None:
        gains[replaced] += 1
        gains['total'] += 1
    for x, y in match:
        dot = board[y][x]
        gains[dot] += 1
        if dot != 'yellow':
            gains['total'] += 1
    board[row][col] = replaced
    return gains


def roll_gains(board, row, col):
    """Gains from the wild roll landing on (row, col); the covered dot earns nothing."""
    covered = board[row][col]
    board[row][col] = 'yellow'
    match, _ = find_match(board, row, col, 'yellow')
    gains = empty_gains()
    for x, y in match:
        dot = board[y][x]
        gains[dot] += 1
        if dot != 'yellow':
            gains['total'] += 1
    board[row][col] = covered
    return gains


# --- Goal scoring -------------------------------------------------------------

def goal_value(gains, stats, mode):
    """How much `gains` advances a player with `stats` toward this round's goal."""
    if mode == 'twenty_dots':
        value = gains['total']
        won = stats['total_dots'] + gains['total'] >= 20
    else:
        needs = {c: max(0, 5 - stats['score'].get(c, 0)) for c in COLORS}
        if mode == 'five_with_yellow':
            needs['yellow'] = max(0, 5 - stats.get('yellow_dots', 0))
        # Dots a player still needs are worth full value; surplus barely counts.
        value = sum(min(gains[c], need) + 0.2 * max(0, gains[c] - need)
                    for c, need in needs.items())
        if mode != 'five_with_yellow':
            value += 0.1 * gains['yellow']
        won = all(gains[c] >= need for c, need in needs.items())
    return value + (WIN_BONUS if won else 0)


def expected_top_two(values, pool):
    """Expected sum of the best two of a random HAND_SIZE-card hand drawn from `pool` cards,
    where `values` lists the cards worth anything (the rest are worth nothing)."""
    chance = HAND_SIZE / pool
    miss = 1 - chance
    expected = 0.0
    # A card counts when it is held and at most one better card is also held.
    for better, value in enumerate(sorted(values, reverse=True)):
        expected += value * chance * (miss ** better + better * chance * miss ** max(better - 1, 0))
    return expected


def best_play(board, cards, stats, mode):
    """A greedy player's best use of up to two (location, color) cards: (value, board)."""
    best_value, best_board = 0.0, board
    for i, first in enumerate(cards):
        once, gains, _ = simulate_cards(board, [first])
        value = goal_value(gains, stats, mode)
        if value > best_value:
            best_value, best_board = value, once
        for j, second in enumerate(cards):
            if j == i or second[0] == first[0]:
                continue
            twice, more, _ = simulate_cards(once, [second])
            total = {key: gains[key] + more[key] for key in gains}
            value = goal_value(total, stats, mode)
            if value > best_value:
                best_value, best_board = value, twice
    return best_value, best_board


def add_gains(stats, gains):
    return {'total_dots': stats['total_dots'] + gains['total'],
            'yellow_dots': stats.get('yellow_dots', 0) + gains['yellow'],
            'score': {c: stats['score'].get(c, 0) + gains[c] for c in COLORS}}


class AIPlayer:
    """AI player that makes strategic decisions."""

    # Hard-mode weights, tuned by self-play (see tests/test_ai_player.py).
    FUTURE_WEIGHT = 0.25   # Value of the best follow-up plays still in hand.
    DRAW_WEIGHT = 0.3      # Value of a fresh card drawn to replace one played.
    THREAT_WEIGHT = 1.0    # Expected value handed to opponents by the resulting board.
    STOP_EARLY = True      # Hard may end a turn after one card rather than feed opponents.
    FINALISTS = 6          # Plans hard plays out against sampled opponent hands.
    SAMPLES = 32           # Sampled opponent hands (and our draws) per decision.

    def __init__(self, difficulty: str = 'medium'):
        """
        Initialize AI player.

        Args:
            difficulty: 'easy', 'medium', or 'hard'
        """
        self.difficulty = difficulty
        self.rng = random.Random()

    def choose_cards(self, hand: List, context: dict = None) -> List[int]:
        """
        Choose cards to play from the hand.

        Without `context` (the desktop game) this uses card-only heuristics. With the
        board `context` from the online server, it returns the indices to play now:
        fewer than `context['cards_left']` ends the turn early, and an empty list on a
        fresh turn asks the server to use the best power card instead.
        """
        if context is not None:
            return self._choose_with_board(hand, context)
        if self.difficulty == 'easy':
            return self._choose_cards_easy(hand)
        elif self.difficulty == 'medium':
            return self._choose_cards_medium(hand)
        else:
            return self._choose_cards_hard(hand)

    def choose_power(self, options: List, context: dict):
        """Index of the power option to play, from (card, power, color, cells) options."""
        if not options:
            return None
        if self.difficulty == 'easy':
            return 0
        plans = [self._power_plan(i, option, context) for i, option in enumerate(options)]
        return self._best(plans, context)['power']

    # --- Board-aware play -----------------------------------------------------

    def _choose_with_board(self, hand, context):
        cards = [(''.join(card.location), card.color) for card in hand]
        if not cards:
            return []
        if self.difficulty == 'easy' and self.rng.random() < 0.7:
            # Mostly random play, but an obvious line still gets taken now and then.
            return self._choose_cards_easy(hand)[:context['cards_left']]
        plans = self._card_plans(cards, context)
        if self.difficulty != 'easy' and context['cards_left'] == 2 and context.get('power_options'):
            plans += [self._power_plan(i, option, context)
                      for i, option in enumerate(context['power_options'])]
        best = self._best(plans, context)
        return [] if best['power'] is not None else list(best['cards'])

    def _card_plans(self, cards, context):
        """Every distinct-location ordering of up to cards_left cards."""
        allowed = context['cards_left']
        sequences = [(i,) for i in range(len(cards))]
        if allowed >= 2:
            sequences += [(i, j) for i in range(len(cards)) for j in range(len(cards))
                          if i != j and cards[i][0] != cards[j][0]]
        if self.difficulty == 'hard' and self.STOP_EARLY and allowed < 2:
            sequences.append(())  # Stop after one card instead of feeding the board.
        elif self.difficulty != 'hard':
            # Easy and medium always use the whole turn when they can.
            longest = max(len(s) for s in sequences)
            sequences = [s for s in sequences if len(s) == longest]
        plans = []
        for sequence in sequences:
            board, gains, wild = simulate_cards(context['board'], [cards[i] for i in sequence])
            plans.append({'cards': sequence, 'power': None, 'board': board, 'gains': gains,
                          'wild': wild, 'played': len(sequence),
                          'hand': [card for i, card in enumerate(cards) if i not in sequence]})
        return plans

    def _power_plan(self, index, option, context):
        _, power, color, cells = option
        board, gains, wild = simulate_power(context['board'], power, color, cells)
        hand = [(''.join(c.location), c.color) for c in context.get('regular_hand', [])]
        return {'cards': (), 'power': index, 'board': board, 'gains': gains,
                'wild': wild, 'played': 1, 'hand': hand}

    def _best(self, plans, context):
        """Highest-valued plan; ties keep the earliest so choices stay predictable."""
        me = context['players'][context['me']]
        mode = context['mode']
        for plan in plans:
            plan['value'] = goal_value(plan['gains'], me, mode)
        if self.difficulty != 'hard':
            top = max(plan['value'] for plan in plans)
            return next(plan for plan in plans if plan['value'] == top)
        # Look ahead only for the strongest immediate options; powers can have hundreds.
        shortlist = sorted(range(len(plans)), key=lambda i: -plans[i]['value'])[:24]
        immediate = {i: plans[i]['value'] for i in shortlist}
        for i in shortlist:
            if plans[i]['value'] < WIN_BONUS:
                plans[i]['value'] += self._lookahead(plans[i], context)
        # Then play the finalists out against the same sampled hands, so luck cancels.
        finalists = sorted(shortlist, key=lambda i: -plans[i]['value'])[:self.FINALISTS]
        if len(finalists) > 1 and plans[finalists[0]]['value'] < WIN_BONUS:
            samples = self._sample_hands(context)
            for i in finalists:
                plans[i]['value'] = (immediate[i] + self._roll_value(plans[i], context)
                                     + self._rollout(plans[i], context, samples))
        return plans[max(finalists, key=lambda i: (plans[i]['value'], -i))]

    def _sample_hands(self, context):
        """(next opponent's hand, our next draws) pairs from cards we can't see."""
        mine = {(''.join(c.location), c.color) for c in context.get('regular_hand', [])}
        pool = [(r + c, color) for r in ROWS for c in COLUMNS for color in COLORS
                if (r + c, color) not in mine]
        draws = [self.rng.sample(pool, HAND_SIZE + 2) for _ in range(self.SAMPLES)]
        return [(cards[:HAND_SIZE], cards[HAND_SIZE:]) for cards in draws]

    def _rollout(self, plan, context, samples):
        """Average of (our best next turn - next opponent's best reply) over sampled hands."""
        mode, order = context['mode'], context['order']
        me = add_gains(context['players'][context['me']], plan['gains'])
        rival = context['players'][order[(order.index(context['me']) + 1) % len(order)]]
        total = 0.0
        for rival_hand, draws in samples:
            threat, board = best_play(plan['board'], rival_hand, rival, mode)
            follow_up, _ = best_play(board, plan['hand'] + draws[:plan['played']], me, mode)
            total += follow_up - threat
        return total / len(samples)

    def _roll_value(self, plan, context):
        """Touching the wild means rolling it somewhere new before the turn ends."""
        if not plan['wild']:
            return 0.0
        me = add_gains(context['players'][context['me']], plan['gains'])
        return sum(goal_value(roll_gains(plan['board'], r, c), me, context['mode'])
                   for r in range(SIZE) for c in range(SIZE)) / (SIZE * SIZE)

    def _lookahead(self, plan, context):
        """Own follow-ups and draws, minus what the board offers the opponents."""
        board, mode = plan['board'], context['mode']
        me = add_gains(context['players'][context['me']], plan['gains'])
        order = context['order']
        seat = order.index(context['me'])
        opponents = [order[(seat + k) % len(order)] for k in range(1, len(order))]

        mine, own_total = [], 0.0
        offered = {name: [] for name in opponents}  # Values of cards opponents might hold.
        for row in range(SIZE):
            for col in range(SIZE):
                for color in COLORS:
                    gains = response_gains(board, row, col, color)
                    mine_value = goal_value(gains, me, mode)
                    if (ROWS[row] + COLUMNS[col], color) in plan['hand']:
                        mine.append(mine_value)
                        continue  # Opponents cannot hold cards in our hand.
                    own_total += mine_value
                    if gains['total'] or gains['yellow']:
                        for name in opponents:
                            offered[name].append(goal_value(gains, context['players'][name], mode))
        unknown = SIZE * SIZE * len(COLORS) - len(plan['hand'])
        threat = sum((1.0 if k == 0 else 0.5) * expected_top_two(offered[name], unknown)
                     for k, name in enumerate(opponents))
        mine.sort(reverse=True)
        value = self.FUTURE_WEIGHT * sum(mine[:2])
        value += self.DRAW_WEIGHT * plan['played'] * own_total / unknown
        value -= self.THREAT_WEIGHT * threat
        return value + self._roll_value(plan, context)

    # --- Card-only heuristics (desktop game) --------------------------------------

    def _choose_cards_easy(self, hand: List) -> List[int]:
        """Easy AI - random selection."""
        if len(hand) < 2:
            return list(range(len(hand)))
        indices = list(range(len(hand)))
        self.rng.shuffle(indices)
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
        self.rng.shuffle(indices)
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
