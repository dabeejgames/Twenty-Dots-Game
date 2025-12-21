"""
Network-enabled GUI for Twenty Dots
Displays game state received from server and sends actions to server
"""
import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QGridLayout, QPushButton, QLabel, QFrame, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from twenty_dots import Card

class DotWidget(QFrame):
    """Widget to display a single dot on the grid"""
    
    def __init__(self, col_idx, row_idx, parent=None):
        super().__init__(parent)
        self.col_idx = col_idx
        self.row_idx = row_idx
        self.dot = None
        self.setFixedSize(65, 65)
        self.setStyleSheet("border: 1px solid #444; background-color: #1a1a2e;")
    
    def set_dot(self, dot_data):
        """Set dot from server data"""
        self.dot = dot_data
        self.update()
    
    def clear_dot(self):
        self.dot = None
        self.update()
    
    def paintEvent(self, event):
        super().paintEvent(event)
        
        if self.dot:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            color_map = {
                'red': QColor(255, 71, 87),
                'blue': QColor(54, 162, 235),
                'purple': QColor(156, 39, 176),
                'green': QColor(76, 175, 80),
                'yellow': QColor(255, 235, 59)
            }
            
            color = color_map.get(self.dot['color'], QColor(255, 255, 255))
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(Qt.PenStyle.NoPen))
            painter.drawEllipse(12, 12, 40, 40)


class CardWidget(QFrame):
    """Widget to display a card"""
    
    def __init__(self, card_data, parent=None):
        super().__init__(parent)
        self.card_data = card_data
        self.is_selected = False
        self.setFixedSize(120, 80)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Card location and color
        color_map = {
            'red': '#FF4757',
            'blue': '#36A2EB',
            'purple': '#9C27B0',
            'green': '#4CAF50',
            'yellow': '#FFEB3B'
        }
        
        bg_color = color_map.get(self.card_data['color'], '#FFFFFF')
        
        location_str = f"{self.card_data['location'][0]}{self.card_data['location'][1]}"
        
        # Create label layout
        label_layout = QHBoxLayout()
        left_label = QLabel(location_str)
        left_label.setStyleSheet("color: white; font-weight: bold; font-size: 10px;")
        label_layout.addWidget(left_label)
        
        center_label = QLabel(f"{location_str}\n{self.card_data['color'].upper()[:3]}")
        center_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_label.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        
        right_label = QLabel(location_str)
        right_label.setStyleSheet("color: white; font-weight: bold; font-size: 10px;")
        label_layout.addWidget(right_label)
        
        layout.addLayout(label_layout)
        layout.addWidget(center_label)
        
        self.setLayout(layout)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 2px solid {'#FFD700' if self.is_selected else '#FFFFFF'};
                border-radius: 8px;
            }}
        """)
    
    def toggle_selection(self):
        self.is_selected = not self.is_selected
        self.update_style()
    
    def update_style(self):
        color_map = {
            'red': '#FF4757',
            'blue': '#36A2EB',
            'purple': '#9C27B0',
            'green': '#4CAF50',
            'yellow': '#FFEB3B'
        }
        bg_color = color_map.get(self.card_data['color'], '#FFFFFF')
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 3px solid {'#FFD700' if self.is_selected else '#FFFFFF'};
                border-radius: 8px;
            }}
        """)
    
    def mousePressEvent(self, event):
        self.toggle_selection()
        super().mousePressEvent(event)


class TwentyDotsNetworkGUI(QMainWindow):
    def __init__(self, network_client, initial_game_state):
        super().__init__()
        self.network_client = network_client
        self.game_state = initial_game_state
        self.player_name = network_client.player_name
        self.my_hand = []
        self.selected_cards = []
        self.card_widgets = []
        
        self.setWindowTitle(f"Twenty Dots - {self.player_name}")
        self.setGeometry(50, 50, 1400, 900)
        self.setStyleSheet("background-color: #0f0f1e;")
        
        # Connect network signals
        self.network_client.game_updated.connect(self.on_game_updated)
        self.network_client.your_hand.connect(self.on_hand_received)
        self.network_client.error_occurred.connect(self.show_error)
        
        self.init_ui()
        self.update_display()
    
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout()
        
        # Left side - board and players
        left_layout = QVBoxLayout()
        
        # Title
        title = QLabel("Twenty Dots")
        title.setFont(QFont('Arial', 32, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffd700;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(title)
        
        # Board
        board_frame = QFrame()
        board_frame.setFixedSize(450, 450)
        board_layout = QGridLayout()
        board_layout.setSpacing(0)
        board_layout.setContentsMargins(2, 2, 2, 2)
        
        # Column headers
        board_layout.addWidget(QLabel(""), 0, 0)
        for col_idx in range(6):
            col_label = QLabel(str(col_idx + 1))
            col_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col_label.setStyleSheet("color: #ff6b6b; font-weight: bold; font-size: 14px;")
            board_layout.addWidget(col_label, 0, col_idx + 1)
        
        # Grid cells with row headers
        self.grid_cells = []
        rows = ['A', 'B', 'C', 'D', 'E', 'F']
        for row_idx in range(6):
            row_label = QLabel(rows[row_idx])
            row_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row_label.setStyleSheet("color: #ff6b6b; font-weight: bold; font-size: 14px;")
            board_layout.addWidget(row_label, row_idx + 1, 0)
            
            row_cells = []
            for col_idx in range(6):
                dot_widget = DotWidget(col_idx, row_idx)
                board_layout.addWidget(dot_widget, row_idx + 1, col_idx + 1)
                row_cells.append(dot_widget)
            self.grid_cells.append(row_cells)
        
        board_frame.setLayout(board_layout)
        left_layout.addWidget(board_frame, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Player scores
        self.score_labels = {}
        scores_layout = QHBoxLayout()
        for player in self.game_state['players'].keys():
            player_label = QLabel(f"{player}: 0")
            player_label.setStyleSheet("color: white; font-size: 14px; padding: 10px;")
            scores_layout.addWidget(player_label)
            self.score_labels[player] = player_label
        left_layout.addLayout(scores_layout)
        
        main_layout.addLayout(left_layout)
        
        # Right side - hand and controls
        right_layout = QVBoxLayout()
        right_layout.setSpacing(20)
        
        hand_label = QLabel("Your Hand")
        hand_label.setFont(QFont('Arial', 20, QFont.Weight.Bold))
        hand_label.setStyleSheet("color: white;")
        right_layout.addWidget(hand_label)
        
        # Hand area
        self.hand_frame = QFrame()
        self.hand_layout = QVBoxLayout()
        self.hand_frame.setLayout(self.hand_layout)
        self.hand_frame.setStyleSheet("background-color: #1a1a2e; border-radius: 10px; padding: 10px;")
        right_layout.addWidget(self.hand_frame)
        
        # Turn info
        self.turn_label = QLabel("")
        self.turn_label.setFont(QFont('Arial', 16))
        self.turn_label.setStyleSheet("color: #ffd700; padding: 10px;")
        self.turn_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self.turn_label)
        
        # Control buttons
        self.play_btn = QPushButton("Play Selected Cards")
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 15px;
                font-size: 16px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #555; }
        """)
        self.play_btn.clicked.connect(self.play_selected_cards)
        right_layout.addWidget(self.play_btn)
        
        self.end_turn_btn = QPushButton("End Turn")
        self.end_turn_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff6b6b;
                color: white;
                padding: 15px;
                font-size: 16px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #ff5252; }
            QPushButton:disabled { background-color: #555; }
        """)
        self.end_turn_btn.clicked.connect(self.end_turn)
        right_layout.addWidget(self.end_turn_btn)
        
        right_layout.addStretch()
        
        main_layout.addLayout(right_layout)
        central_widget.setLayout(main_layout)
    
    def update_display(self):
        """Update the display with current game state"""
        # Update board
        board = self.game_state.get('board', [])
        for row_idx in range(6):
            for col_idx in range(6):
                if row_idx < len(board) and col_idx < len(board[row_idx]):
                    dot_data = board[row_idx][col_idx]
                    if dot_data:
                        self.grid_cells[row_idx][col_idx].set_dot(dot_data)
                    else:
                        self.grid_cells[row_idx][col_idx].clear_dot()
        
        # Update scores
        players = self.game_state.get('players', {})
        for player_name, player_data in players.items():
            total = player_data.get('total_dots', 0)
            if player_name in self.score_labels:
                self.score_labels[player_name].setText(f"{player_name}: {total}")
        
        # Update turn indicator
        current_turn = self.game_state.get('current_turn', '')
        is_my_turn = (current_turn == self.player_name)
        
        self.turn_label.setText(
            f"{'YOUR TURN' if is_my_turn else f'{current_turn}s Turn'}"
        )
        
        self.play_btn.setEnabled(is_my_turn)
        self.end_turn_btn.setEnabled(is_my_turn)
    
    def update_hand_display(self):
        """Update the hand display"""
        # Clear existing cards
        for widget in self.card_widgets:
            widget.deleteLater()
        self.card_widgets.clear()
        
        # Add new cards
        for card_data in self.my_hand:
            card_widget = CardWidget(card_data)
            self.hand_layout.addWidget(card_widget)
            self.card_widgets.append(card_widget)
    
    def play_selected_cards(self):
        """Play the selected cards"""
        selected = [w.card_data for w in self.card_widgets if w.is_selected]
        
        if not selected:
            QMessageBox.warning(self, "No Cards Selected", "Please select cards to play")
            return
        
        if len(selected) > 2:
            QMessageBox.warning(self, "Too Many Cards", "You can only play up to 2 cards per turn")
            return
        
        # Convert to Card objects
        cards = [Card(c['color'], tuple(c['location'])) for c in selected]
        
        # Send to server
        self.network_client.play_cards(cards)
    
    def end_turn(self):
        """End the current turn"""
        self.network_client.end_turn()
    
    @pyqtSlot(dict)
    def on_game_updated(self, game_state):
        """Handle game state update from server"""
        self.game_state = game_state
        self.update_display()
    
    @pyqtSlot(dict)
    def on_hand_received(self, data):
        """Handle hand update from server"""
        self.my_hand = data.get('hand', [])
        self.update_hand_display()
    
    def show_error(self, message):
        """Show error message"""
        QMessageBox.critical(self, "Error", message)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # This would normally be created by the launcher
    print("This should be launched from launcher.py")
    sys.exit(app.exec())
