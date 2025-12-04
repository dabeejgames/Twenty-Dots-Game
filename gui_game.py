import sys
import os
import random
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QGridLayout, QPushButton, QLabel, QFrame, QScrollArea, QDialog,
                             QInputDialog, QMessageBox)
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPixmap, QPainter, QPen, QBrush
from twenty_dots import TwentyDots, Card, Dot
from ai_player import AIPlayer


class PowerCardDialog(QDialog):
    """Custom styled dialog for power card messages."""
    
    def __init__(self, parent, title, message, icon_emoji="⚡"):
        super().__init__(parent)
        self.setWindowTitle("Power Card")
        self.setModal(True)
        self.setFixedSize(400, 180)
        
        # Styling
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a1a2e, stop:1 #0f0f1e);
                border: 3px solid #FFD700;
                border-radius: 15px;
            }
            QLabel {
                color: #FFFFFF;
                background-color: transparent;
            }
            QPushButton {
                background-color: #FFD700;
                color: #000000;
                border: none;
                padding: 12px 30px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #FFC700;
            }
            QPushButton:pressed {
                background-color: #FFB700;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Icon and title
        header_layout = QHBoxLayout()
        icon_label = QLabel(icon_emoji)
        icon_label.setFont(QFont("Arial", 48))
        icon_label.setStyleSheet("color: #FFD700;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #FFD700;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title_label)
        
        layout.addLayout(header_layout)
        
        # Message
        message_label = QLabel(message)
        message_label.setFont(QFont("Arial", 12))
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setWordWrap(True)
        layout.addWidget(message_label)
        
        # OK button
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        ok_button.setFixedWidth(120)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)


class DotWidget(QFrame):
    """Custom widget to display a single dot position on the grid."""
    
    def __init__(self, col_idx, row_idx, parent=None):
        super().__init__(parent)
        self.col_idx = col_idx
        self.row_idx = row_idx
        self.dot = None
        self.is_highlighted = False
        self.setFixedSize(65, 65)
        self.setStyleSheet("border: 1px solid #444; background-color: #1a1a2e;")
    
    def set_dot(self, dot):
        """Set the dot at this position."""
        self.dot = dot
        self.update()
    
    def clear_dot(self):
        """Clear the dot at this position."""
        self.dot = None
        self.update()
    
    def set_highlighted(self, highlighted):
        """Highlight this dot widget for selection."""
        self.is_highlighted = highlighted
        if highlighted:
            self.setStyleSheet("border: 3px solid #FFD700; background-color: #2a2a3e;")
        else:
            self.setStyleSheet("border: 1px solid #444; background-color: #1a1a2e;")
        self.update()
    
    def paintEvent(self, event):
        """Paint the dot if one exists."""
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
            
            color = color_map.get(self.dot.color, QColor(255, 255, 255))
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(Qt.PenStyle.NoPen))
            painter.drawEllipse(12, 12, 40, 40)


class GameSetupDialog(QDialog):
    """Dialog for game setup."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.num_players = None
        self.difficulty = None
        self.game_mode = None
        self.ai_difficulties = {}
        self.ai_difficulty_level = 'medium'  # Default AI difficulty
        self.power_cards = True  # Default enabled
        self.timer_seconds = 0  # Default: no timer
        self.init_ui()
    
    def init_ui(self):
        """Initialize the UI with modern styling."""
        self.setWindowTitle("Twenty Dots - Game Setup")
        self.setFixedSize(900, 950)
        
        # Modern gradient background
        stylesheet = """
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a1a2e, stop:0.5 #16213e, stop:1 #0f3460);
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                color: white;
                border: 2px solid rgba(255, 255, 255, 0.3);
                padding: 8px 15px;
                border-radius: 12px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.2);
                border: 2px solid rgba(255, 255, 255, 0.5);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.3);
            }
            QPushButton.selected {
                background-color: #FFD700;
                color: #000;
                border: 2px solid #FFC700;
            }
            QLabel {
                color: #ffffff;
                font-size: 16px;
            }
            QCheckBox {
                color: #FFD700;
                font-size: 20px;
                font-weight: bold;
                spacing: 10px;
            }
            QCheckBox::indicator {
                width: 24px;
                height: 24px;
                border-radius: 4px;
                border: 2px solid #FFD700;
            }
            QCheckBox::indicator:checked {
                background-color: #FFD700;
            }
        """
        self.setStyleSheet(stylesheet)
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(30, 20, 30, 20)
        
        # Logo
        logo_path = "Twenty Dots Logo.png"
        if os.path.exists(logo_path):
            from PyQt6.QtGui import QPixmap
            logo_label = QLabel()
            pixmap = QPixmap(logo_path)
            # Scale logo to reasonable size while maintaining aspect ratio
            # Use wider dimensions to accommodate the full logo
            scaled_pixmap = pixmap.scaled(350, 190, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            main_layout.addWidget(logo_label)
        
        # Add separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: rgba(255, 215, 0, 0.3); margin: 10px 0px;")
        main_layout.addWidget(separator)
        
        # Game Mode Section
        mode_label = QLabel("⚔️ Game Mode")
        mode_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        mode_label.setStyleSheet("color: #FFD700; margin-top: 8px; margin-bottom: 3px;")
        main_layout.addWidget(mode_label)
        
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(15)
        mode_layout.addStretch()
        
        self.multiplayer_btn = QPushButton("👥 Multiplayer\nLocal Co-op")
        self.multiplayer_btn.setFixedSize(150, 60)
        self.multiplayer_btn.clicked.connect(lambda: self.set_game_mode('multiplayer'))
        mode_layout.addWidget(self.multiplayer_btn)
        
        self.single_btn = QPushButton("🤖 vs AI\nSingle Player")
        self.single_btn.setFixedSize(150, 60)
        self.single_btn.clicked.connect(lambda: self.set_game_mode('single_player'))
        mode_layout.addWidget(self.single_btn)
        
        mode_layout.addStretch()
        main_layout.addLayout(mode_layout)
        
        # Number of Players Section
        players_label = QLabel("👤 Number of Players")
        players_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        players_label.setStyleSheet("color: #FFD700; margin-top: 8px; margin-bottom: 3px;")
        main_layout.addWidget(players_label)
        
        players_layout = QHBoxLayout()
        players_layout.setSpacing(15)
        players_layout.addStretch()
        self.player_buttons = []
        for i in range(2, 5):
            btn = QPushButton(f"{i}\nPlayers")
            btn.setFixedSize(135, 55)
            btn.clicked.connect(lambda checked, p=i: self.set_players(p))
            players_layout.addWidget(btn)
            self.player_buttons.append(btn)
        
        players_layout.addStretch()
        main_layout.addLayout(players_layout)
        
        # AI Difficulty Section (shown only in single player mode)
        self.ai_difficulty_label = QLabel("🎯 AI Difficulty")
        self.ai_difficulty_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        self.ai_difficulty_label.setStyleSheet("color: #FFD700; margin-top: 8px; margin-bottom: 3px;")
        self.ai_difficulty_label.setVisible(False)
        main_layout.addWidget(self.ai_difficulty_label)
        
        ai_diff_layout = QHBoxLayout()
        ai_diff_layout.setSpacing(15)
        ai_diff_layout.addStretch()
        self.ai_diff_buttons = []
        
        self.easy_ai_btn = QPushButton("😊 Easy\nRelaxed")
        self.easy_ai_btn.setFixedSize(155, 75)
        self.easy_ai_btn.clicked.connect(lambda: self.set_ai_difficulty('easy'))
        self.easy_ai_btn.setVisible(False)
        ai_diff_layout.addWidget(self.easy_ai_btn)
        self.ai_diff_buttons.append(self.easy_ai_btn)
        
        self.medium_ai_btn = QPushButton("🎯 Medium\nBalanced")
        self.medium_ai_btn.setFixedSize(140, 75)
        self.medium_ai_btn.clicked.connect(lambda: self.set_ai_difficulty('medium'))
        self.medium_ai_btn.setVisible(False)
        self.medium_ai_btn.setProperty('class', 'selected')
        ai_diff_layout.addWidget(self.medium_ai_btn)
        self.ai_diff_buttons.append(self.medium_ai_btn)
        
        self.hard_ai_btn = QPushButton("🔥 Hard\nChallenge")
        self.hard_ai_btn.setFixedSize(155, 75)
        self.hard_ai_btn.clicked.connect(lambda: self.set_ai_difficulty('hard'))
        self.hard_ai_btn.setVisible(False)
        ai_diff_layout.addWidget(self.hard_ai_btn)
        self.ai_diff_buttons.append(self.hard_ai_btn)
        
        ai_diff_layout.addStretch()
        main_layout.addLayout(ai_diff_layout)
        
        # Win Condition Section
        difficulty_label = QLabel("🏆 Win Condition")
        difficulty_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        difficulty_label.setStyleSheet("color: #FFD700; margin-top: 8px; margin-bottom: 3px;")
        main_layout.addWidget(difficulty_label)
        
        difficulty_layout = QHBoxLayout()
        difficulty_layout.setSpacing(15)
        difficulty_layout.addStretch()
        self.difficulty_buttons = []
        
        self.easy_btn = QPushButton("🌟 Standard\n20 Dots Total")
        self.easy_btn.setFixedSize(165, 55)
        self.easy_btn.clicked.connect(lambda: self.set_difficulty("easy"))
        difficulty_layout.addWidget(self.easy_btn)
        self.difficulty_buttons.append(self.easy_btn)
        
        self.hard_btn = QPushButton("💎 Expert\n5 of Each Color")
        self.hard_btn.setFixedSize(165, 55)
        self.hard_btn.clicked.connect(lambda: self.set_difficulty("hard"))
        difficulty_layout.addWidget(self.hard_btn)
        self.difficulty_buttons.append(self.hard_btn)
        
        difficulty_layout.addStretch()
        main_layout.addLayout(difficulty_layout)
        
        # Timer Section
        timer_label = QLabel("⏱️ Turn Timer")
        timer_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        timer_label.setStyleSheet("color: #FFD700; margin-top: 8px; margin-bottom: 3px;")
        main_layout.addWidget(timer_label)
        
        timer_layout = QHBoxLayout()
        timer_layout.setSpacing(15)
        timer_layout.addStretch()
        self.timer_buttons = []
        
        self.no_timer_btn = QPushButton("∞ No Timer\nUnlimited")
        self.no_timer_btn.setFixedSize(135, 55)
        self.no_timer_btn.clicked.connect(lambda: self.set_timer(0))
        timer_layout.addWidget(self.no_timer_btn)
        self.timer_buttons.append(self.no_timer_btn)
        
        self.timer_30_btn = QPushButton("⏱️ 30 Seconds\nRelaxed")
        self.timer_30_btn.setFixedSize(135, 55)
        self.timer_30_btn.clicked.connect(lambda: self.set_timer(30))
        timer_layout.addWidget(self.timer_30_btn)
        self.timer_buttons.append(self.timer_30_btn)
        
        self.timer_15_btn = QPushButton("⚡ 15 Seconds\nFast-Paced")
        self.timer_15_btn.setFixedSize(135, 55)
        self.timer_15_btn.clicked.connect(lambda: self.set_timer(15))
        timer_layout.addWidget(self.timer_15_btn)
        self.timer_buttons.append(self.timer_15_btn)
        
        timer_layout.addStretch()
        main_layout.addLayout(timer_layout)
        
        # Power cards checkbox
        from PyQt6.QtWidgets import QCheckBox
        power_cards_layout = QHBoxLayout()
        power_cards_layout.addStretch()
        self.power_cards_check = QCheckBox("⚡ Enable Power Cards (Recommended)")
        self.power_cards_check.setChecked(True)
        power_cards_layout.addWidget(self.power_cards_check)
        power_cards_layout.addStretch()
        power_cards_layout.setContentsMargins(0, 10, 0, 5)
        main_layout.addLayout(power_cards_layout)
        
        # Start Game button
        start_button_layout = QHBoxLayout()
        start_button_layout.addStretch()
        self.start_btn = QPushButton("🎮 Start Game")
        self.start_btn.setFixedSize(200, 60)
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start_game_clicked)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(76, 175, 80, 0.3);
                color: #aaa;
                border: 2px solid rgba(76, 175, 80, 0.3);
                padding: 15px;
                border-radius: 12px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:enabled {
                background-color: #4CAF50;
                color: white;
                border: 2px solid #45a049;
            }
            QPushButton:enabled:hover {
                background-color: #45a049;
            }
        """)
        start_button_layout.addWidget(self.start_btn)
        start_button_layout.addStretch()
        main_layout.addLayout(start_button_layout)
        
        main_layout.addStretch()
        self.setLayout(main_layout)
    
    def set_game_mode(self, mode):
        self.game_mode = mode
        
        # Base style for unselected buttons
        base_style = """
            background-color: rgba(255, 255, 255, 0.1);
            color: white;
            border: 2px solid rgba(255, 255, 255, 0.3);
            padding: 8px 15px;
            border-radius: 12px;
            font-weight: bold;
            font-size: 14px;
        """
        
        # Update button selection styling
        self.multiplayer_btn.setStyleSheet(base_style if mode != 'multiplayer' else base_style + "background-color: #4CAF50; border: 2px solid #45a049; color: white;")
        self.single_btn.setStyleSheet(base_style if mode != 'single_player' else base_style + "background-color: #2196F3; border: 2px solid #0b7dda; color: white;")
        
        # Show/hide AI difficulty section
        is_single = mode == 'single_player'
        self.ai_difficulty_label.setVisible(is_single)
        for btn in self.ai_diff_buttons:
            btn.setVisible(is_single)
        
        self.check_all_set()
    
    def set_players(self, num):
        self.num_players = num
        
        # Base style for unselected buttons
        base_style = """
            background-color: rgba(255, 255, 255, 0.1);
            color: white;
            border: 2px solid rgba(255, 255, 255, 0.3);
            padding: 8px 15px;
            border-radius: 12px;
            font-weight: bold;
            font-size: 14px;
        """
        
        # Update button selection styling - reset all first, then select one
        for i, btn in enumerate(self.player_buttons):
            if i + 2 == num:
                btn.setStyleSheet(base_style + "background-color: #FF6B6B; border: 2px solid #FF5252; color: white;")
            else:
                btn.setStyleSheet(base_style)
        
        self.check_all_set()
    
    def set_ai_difficulty(self, level):
        """Set AI difficulty level."""
        self.ai_difficulty_level = level
        
        # Base style for unselected buttons
        base_style = """
            background-color: rgba(255, 255, 255, 0.1);
            color: white;
            border: 2px solid rgba(255, 255, 255, 0.3);
            padding: 8px 15px;
            border-radius: 12px;
            font-weight: bold;
            font-size: 14px;
        """
        
        # Reset all buttons to default style first
        self.easy_ai_btn.setStyleSheet(base_style)
        self.medium_ai_btn.setStyleSheet(base_style)
        self.hard_ai_btn.setStyleSheet(base_style)
        
        # Update selected button styling
        if level == 'easy':
            self.easy_ai_btn.setStyleSheet(base_style + "background-color: #4CAF50; border: 2px solid #45a049; color: white;")
        elif level == 'medium':
            self.medium_ai_btn.setStyleSheet(base_style + "background-color: #FFA726; border: 2px solid #FB8C00; color: white;")
        elif level == 'hard':
            self.hard_ai_btn.setStyleSheet(base_style + "background-color: #EF5350; border: 2px solid #E53935; color: white;")
        
        self.check_all_set()
    
    def set_timer(self, seconds):
        """Set turn timer duration."""
        self.timer_seconds = seconds
        
        # Base style for unselected buttons
        base_style = """
            background-color: rgba(255, 255, 255, 0.1);
            color: white;
            border: 2px solid rgba(255, 255, 255, 0.3);
            padding: 8px 15px;
            border-radius: 12px;
            font-weight: bold;
            font-size: 14px;
        """
        
        # Reset all timer buttons
        for btn in self.timer_buttons:
            btn.setStyleSheet(base_style)
        
        # Highlight selected
        if seconds == 0:
            self.no_timer_btn.setStyleSheet(base_style + "background-color: #4CAF50; border: 2px solid #45a049; color: white;")
        elif seconds == 30:
            self.timer_30_btn.setStyleSheet(base_style + "background-color: #FFA726; border: 2px solid #FB8C00; color: white;")
        elif seconds == 15:
            self.timer_15_btn.setStyleSheet(base_style + "background-color: #EF5350; border: 2px solid #E53935; color: white;")
        
        self.check_all_set()
    
    def set_difficulty(self, difficulty):
        self.difficulty = difficulty
        
        # Base style for unselected buttons
        base_style = """
            background-color: rgba(255, 255, 255, 0.1);
            color: white;
            border: 2px solid rgba(255, 255, 255, 0.3);
            padding: 8px 15px;
            border-radius: 12px;
            font-weight: bold;
            font-size: 14px;
        """
        
        # Update button selection styling - reset all first, then select one
        for i, btn in enumerate(self.difficulty_buttons):
            if (i == 0 and difficulty == 'easy') or (i == 1 and difficulty == 'hard'):
                btn.setStyleSheet(base_style + "background-color: #9C27B0; border: 2px solid #7B1FA2; color: white;")
            else:
                btn.setStyleSheet(base_style)
        
        # Set AI difficulties for all AI players based on selected level
        if self.game_mode == 'single_player' and self.num_players:
            self.ai_difficulties = {}
            for i in range(2, self.num_players + 1):
                self.ai_difficulties[f"Player {i}"] = self.ai_difficulty_level
        
        self.check_all_set()
    
    def check_all_set(self):
        # Enable start button if all required fields are set
        all_set = bool(self.game_mode and self.num_players and self.difficulty and self.timer_seconds is not None)
        self.start_btn.setEnabled(all_set)
    
    def start_game_clicked(self):
        """Handle start game button click."""
        # For single player, set AI difficulties
        if self.game_mode == 'single_player':
            self.ai_difficulties = {}
            for i in range(2, self.num_players + 1):
                self.ai_difficulties[f"Player {i}"] = self.ai_difficulty_level
        
        self.power_cards = self.power_cards_check.isChecked()
        self.accept()


class TwentyDotsGUI(QMainWindow):
    """Main game GUI window."""
    
    def __init__(self):
        super().__init__()
        self.game = None
        self.dot_widgets = {}
        self.selected_cards = []
        self.ai_players = {}
        self.game_mode = 'multiplayer'
        self.player_discard_piles = {}
        self.player_stats = {}  # Track wins/losses for each player
        self.cards_played_this_turn = 0
        self.yellow_collected_by_power = False  # Track if power card collected yellow
        self.locations_played_this_turn = []  # Track locations played in current turn
        self.scored_this_turn = False
        self.landmine_waiting_for_sacrifice = None  # Track when landmine needs a sacrifice card
        self.waiting_for_dice_roll = False
        self.selecting_board_dots = False  # Power card board selection mode
        self.selected_board_positions = []  # Positions selected on board
        self.board_selection_callback = None  # Callback when selection complete
        self.landmine_widgets = {}  # Track landmine display widgets
        self.ai_timer = QTimer()
        self.ai_timer.timeout.connect(self.execute_ai_turn)
        self.pulse_timer = QTimer()
        self.pulse_timer.timeout.connect(self.pulse_dice_button)
        self.pulse_state = 0
        self.turn_timer = QTimer()
        self.turn_timer.timeout.connect(self.update_timer_display)
        self.timer_seconds = 0  # 0 = no timer
        self.time_remaining = 0
        self.timer_label = None
        self.timeout_counts = {}  # Track consecutive timeouts per player
        self.init_ui()
        self.show_setup_dialog()
    
    def init_ui(self):
        """Initialize the main UI."""
        self.setWindowTitle("Twenty Dots")
        
        # Set window icon
        icon_path = "twenty_dots_icon.png"
        if os.path.exists(icon_path):
            from PyQt6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))
        
        self.setGeometry(0, 0, 1400, 900)
        
        stylesheet = "QMainWindow { background-color: #0f0f1e; color: #ffffff; } QLabel { color: #ffffff; } QPushButton { background-color: #ff6b6b; color: white; border: none; padding: 10px; border-radius: 6px; font-weight: bold; } QPushButton:hover { background-color: #ff5252; } QPushButton:pressed { background-color: #e63946; } QFrame { background-color: #0f0f1e; border-radius: 8px; } QScrollArea { background-color: #0f0f1e; border: none; }"
        self.setStyleSheet(stylesheet)
        
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        
        # Center panel with grid and player boxes
        center_panel = QWidget()
        center_layout = QVBoxLayout()
        center_layout.setSpacing(5)
        
        # Grid with player boxes in corners and logo/board in center
        grid_container = QWidget()
        grid_outer_layout = QGridLayout()
        grid_outer_layout.setSpacing(5)
        grid_outer_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create player info boxes (will be populated later)
        self.player_boxes = {}
        for i in range(4):
            player_box = QFrame()
            player_box.setFixedSize(250, 200)
            player_box.setStyleSheet("background-color: #1a1a2e; border-radius: 8px; border: 2px solid #444;")
            box_layout = QVBoxLayout()
            box_layout.setContentsMargins(8, 8, 8, 8)
            
            name_label = QLabel(f"Player {i+1}")
            name_label.setFont(QFont("Arial", 13, QFont.Weight.Bold))
            name_label.setStyleSheet("color: #FFD700;")
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box_layout.addWidget(name_label)
            
            # Win/Loss record
            record_label = QLabel("W: 0 | L: 0")
            record_label.setFont(QFont("Arial", 9))
            record_label.setStyleSheet("color: #888888;")
            record_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box_layout.addWidget(record_label)
            
            score_label = QLabel("Score: 0/0/0/0")
            score_label.setFont(QFont("Courier", 14, QFont.Weight.Bold))
            score_label.setStyleSheet("color: #4CAF50;")
            score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box_layout.addWidget(score_label)
            
            discard_label = QLabel("Discard: 0 cards")
            discard_label.setFont(QFont("Arial", 9))
            discard_label.setStyleSheet("color: #aaaaaa;")
            discard_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box_layout.addWidget(discard_label)
            
            # Container for discard cards (side by side)
            discard_container = QWidget()
            discard_layout = QHBoxLayout()
            discard_layout.setSpacing(4)
            discard_layout.setContentsMargins(0, 0, 0, 0)
            discard_container.setLayout(discard_layout)
            discard_container.setFixedHeight(70)
            box_layout.addWidget(discard_container)
            
            player_box.setLayout(box_layout)
            self.player_boxes[i] = {
                'frame': player_box,
                'name': name_label,
                'record': record_label,
                'score': score_label,
                'discard_count': discard_label,
                'discard_layout': discard_layout
            }
        
        # Position player boxes - top row has Player 1 and Player 2
        grid_outer_layout.addWidget(self.player_boxes[0]['frame'], 0, 0)
        grid_outer_layout.addWidget(self.player_boxes[1]['frame'], 0, 3)
        
        # Logo in middle row, left position
        logo_path = "Twenty Dots Logo.png"
        if os.path.exists(logo_path):
            from PyQt6.QtGui import QPixmap
            logo_label = QLabel()
            pixmap = QPixmap(logo_path)
            scaled_pixmap = pixmap.scaled(250, 250, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_label.setMinimumSize(250, 200)
            grid_outer_layout.addWidget(logo_label, 1, 0)
        
        # Board in center
        board_frame = QFrame()
        board_frame.setFixedSize(450, 450)  # Fixed size to prevent stretching
        board_layout = QGridLayout()
        board_layout.setSpacing(0)
        board_layout.setContentsMargins(2, 2, 2, 2)
        
        columns = ['1', '2', '3', '4', '5', '6']
        rows = ['A', 'B', 'C', 'D', 'E', 'F']
        
        for col_idx, col in enumerate(columns):
            label = QLabel(col)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            label.setStyleSheet("color: #ff6b6b;")
            board_layout.addWidget(label, 0, col_idx + 1)
        
        for row_idx, row in enumerate(rows):
            label = QLabel(row)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            label.setStyleSheet("color: #ff6b6b;")
            board_layout.addWidget(label, row_idx + 1, 0)
            
            for col_idx in range(len(columns)):
                widget = DotWidget(col_idx, row_idx)
                widget.mousePressEvent = lambda event, c=col_idx, r=row_idx: self.on_dot_clicked(c, r)
                widget.setCursor(Qt.CursorShape.PointingHandCursor)
                self.dot_widgets[(col_idx, row_idx)] = widget
                board_layout.addWidget(widget, row_idx + 1, col_idx + 1)
        
        board_frame.setLayout(board_layout)
        # Board spans middle row center and right
        grid_outer_layout.addWidget(board_frame, 1, 1, 1, 2)
        
        # Landmines display area (above the grid)
        landmine_frame = QFrame()
        landmine_frame.setStyleSheet("background-color: transparent; border: none;")
        landmine_layout = QHBoxLayout()
        landmine_layout.setContentsMargins(0, 0, 0, 5)
        
        landmine_title = QLabel("💥 Active Land Mines:")
        landmine_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        landmine_title.setStyleSheet("color: #FF4757;")
        landmine_layout.addWidget(landmine_title)
        
        self.landmine_display = QHBoxLayout()
        landmine_layout.addLayout(self.landmine_display)
        landmine_layout.addStretch()
        
        landmine_frame.setLayout(landmine_layout)
        grid_outer_layout.addWidget(landmine_frame, 0, 1)
        
        # Bottom player boxes
        grid_outer_layout.addWidget(self.player_boxes[2]['frame'], 2, 0)
        grid_outer_layout.addWidget(self.player_boxes[3]['frame'], 2, 3)
        
        grid_container.setLayout(grid_outer_layout)
        
        # Add stretches to center the grid horizontally and vertically
        center_layout.addStretch(1)
        
        # Wrap grid in horizontal layout for centering
        grid_h_container = QWidget()
        grid_h_layout = QHBoxLayout()
        grid_h_layout.addStretch(1)
        grid_h_layout.addWidget(grid_container)
        grid_h_layout.addStretch(1)
        grid_h_container.setLayout(grid_h_layout)
        
        center_layout.addWidget(grid_h_container)
        center_layout.addStretch(1)
        
        self.current_player_label = QLabel()
        self.current_player_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.current_player_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(self.current_player_label)
        
        center_panel.setLayout(center_layout)
        main_layout.addWidget(center_panel, 3)
        
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        
        # Timer display at top of right panel
        self.timer_label = QLabel()
        self.timer_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_label.setVisible(False)
        self.timer_label.setFixedHeight(40)
        right_layout.addWidget(self.timer_label)
        
        hand_frame = QFrame()
        hand_layout = QVBoxLayout()
        hand_title = QLabel("Your Hand")
        hand_title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        hand_layout.addWidget(hand_title)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background-color: #1a1a2e;")
        self.hand_layout = QVBoxLayout()
        scroll_widget.setLayout(self.hand_layout)
        scroll.setWidget(scroll_widget)
        hand_layout.addWidget(scroll)
        
        hand_frame.setLayout(hand_layout)
        right_layout.addWidget(hand_frame)
        
        button_frame = QFrame()
        button_layout = QVBoxLayout()
        
        self.roll_dice_btn = QPushButton("🎲 Roll Wild Dice")
        self.roll_dice_btn.setFixedHeight(50)
        self.roll_dice_btn.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.roll_dice_base_style = "QPushButton { background-color: #FFD700; color: #000000; border: 3px solid #FFD700; } QPushButton:hover { background-color: #FFC700; }"
        self.roll_dice_btn.setStyleSheet(self.roll_dice_base_style)
        self.roll_dice_btn.clicked.connect(self.roll_wild_dice)
        self.roll_dice_btn.setEnabled(False)
        button_layout.addWidget(self.roll_dice_btn)
        
        self.play_btn = QPushButton("Play Selected Card(s)")
        self.play_btn.setFixedHeight(50)
        self.play_btn.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        play_style = "QPushButton { background-color: #4CAF50; } QPushButton:hover { background-color: #45a049; }"
        self.play_btn.setStyleSheet(play_style)
        self.play_btn.clicked.connect(self.play_selected_cards)
        button_layout.addWidget(self.play_btn)
        
        clear_btn = QPushButton("Clear Selection")
        clear_btn.setFixedHeight(40)
        clear_btn.setFont(QFont("Arial", 11))
        clear_btn.clicked.connect(self.clear_selection)
        button_layout.addWidget(clear_btn)
        
        instructions_btn = QPushButton("📖 How to Play")
        instructions_btn.setFixedHeight(40)
        instructions_btn.setFont(QFont("Arial", 11))
        instructions_style = "QPushButton { background-color: #9C27B0; } QPushButton:hover { background-color: #7B1FA2; }"
        instructions_btn.setStyleSheet(instructions_style)
        instructions_btn.clicked.connect(self.show_instructions)
        button_layout.addWidget(instructions_btn)
        
        lobby_btn = QPushButton("🏠 Return to Lobby")
        lobby_btn.setFixedHeight(40)
        lobby_btn.setFont(QFont("Arial", 11))
        lobby_style = "QPushButton { background-color: #FF9800; color: #FFFFFF; } QPushButton:hover { background-color: #F57C00; }"
        lobby_btn.setStyleSheet(lobby_style)
        lobby_btn.clicked.connect(self.return_to_lobby)
        button_layout.addWidget(lobby_btn)
        
        button_frame.setLayout(button_layout)
        right_layout.addWidget(button_frame)
        
        right_panel.setLayout(right_layout)
        main_layout.addWidget(right_panel, 1)
        
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
    
    def show_setup_dialog(self):
        """Show the game setup dialog."""
        dialog = GameSetupDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.game_mode = dialog.game_mode
            self.timer_seconds = dialog.timer_seconds
            self.start_game(dialog.num_players, dialog.difficulty, dialog.ai_difficulties, dialog.power_cards)
    
    def start_game(self, num_players, difficulty, ai_difficulties=None, power_cards=True):
        """Start a new game."""
        self.game = TwentyDots(num_players, difficulty, ai_opponents=ai_difficulties or {}, power_cards=power_cards)
        self.game.shuffle_deck()
        self.game.deal_cards(cards_per_player=5)
        
        # Initialize discard piles for each player
        self.player_discard_piles = {f"Player {i+1}": [] for i in range(num_players)}
        
        # Initialize timeout counters for each player
        self.timeout_counts = {f"Player {i+1}": 0 for i in range(num_players)}
        
        # Initialize player stats if not already tracked
        for i in range(num_players):
            player_name = f"Player {i+1}"
            if player_name not in self.player_stats:
                self.player_stats[player_name] = {'wins': 0, 'losses': 0}
        
        self.ai_players = {}
        if ai_difficulties:
            for player_name, ai_difficulty in ai_difficulties.items():
                self.ai_players[player_name] = AIPlayer(difficulty=ai_difficulty)
        
        # Don't auto-place yellow dot - let first player roll
        # col, row = self.game.roll_dice()
        # self.game.place_yellow_dot(col, row)
        
        # Update display
        self.update_board()
        self.update_scores()
        self.update_discard_piles()
        self.update_landmine_display()
        self.update_hand()
        self.update_current_player()
        
        # Show/hide timer label based on timer setting
        if self.timer_seconds > 0:
            self.timer_label.setVisible(True)
        
        # Enable roll dice button for first player
        if not self.is_current_player_ai():
            self.waiting_for_dice_roll = True
            self.roll_dice_btn.setEnabled(True)
            self.start_pulse_animation()
            self.play_btn.setEnabled(False)
            self.current_player_label.setText("🎲 Roll the Wild Dice to begin!")
            self.start_turn_timer()
        else:
            # If first player is AI, auto-roll for them
            row, col = self.game.roll_dice()
            result = self.game.place_wild_at_location(row, col)
            defused = result[2] if len(result) > 2 else False
            if defused:
                print(f"Initial wild defused landmine at {row}{col}")
                self.update_landmine_display()
            self.update_board()
            self.ai_timer.start(2000)
    
    def update_board(self):
        """Update the game board display."""
        for (col_idx, row_idx), widget in self.dot_widgets.items():
            dot = self.game.grid[row_idx][col_idx]
            if dot:
                widget.set_dot(dot)
            else:
                widget.clear_dot()
    
    def update_landmine_display(self):
        """Update the landmine display area above the grid."""
        # Clear existing landmine widgets
        while self.landmine_display.count():
            item = self.landmine_display.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Display each active landmine
        for mine in self.game.landmines:
            mine_widget = QFrame()
            mine_widget.setFixedSize(60, 60)
            mine_widget.setStyleSheet("""
                background-color: #2a2a3e;
                border: 2px solid #FF4757;
                border-radius: 8px;
            """)
            
            mine_layout = QVBoxLayout()
            mine_layout.setContentsMargins(5, 5, 5, 5)
            
            # Location (face down - hidden)
            location_label = QLabel("💥")
            location_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
            location_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            location_label.setStyleSheet("color: #FF4757; background-color: transparent; border: none;")
            mine_layout.addWidget(location_label)
            
            # Small label showing it's hidden
            hidden_label = QLabel("???")
            hidden_label.setFont(QFont("Arial", 8))
            hidden_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hidden_label.setStyleSheet("color: #888; background-color: transparent; border: none;")
            mine_layout.addWidget(hidden_label)
            
            mine_widget.setLayout(mine_layout)
            self.landmine_display.addWidget(mine_widget)
    
    def update_scores(self):
        """Update the scores display."""
        for idx, (player_name, data) in enumerate(self.game.players.items()):
            if idx >= 4:  # Only show first 4 players in boxes
                break
            
            box = self.player_boxes[idx]
            
            # Update name
            box['name'].setText(player_name)
            
            # Update win/loss record
            if player_name in self.player_stats:
                wins = self.player_stats[player_name]['wins']
                losses = self.player_stats[player_name]['losses']
                box['record'].setText(f"W: {wins} | L: {losses}")
            
            # Update score with colored letters
            if self.game.difficulty == 'easy':
                score_text = f"Total: {data['total_dots']} dots"
                box['score'].setText(score_text)
                box['score'].setStyleSheet("color: #4CAF50;")
            else:
                # Create HTML for colored score letters with white numbers
                score_html = f"""<span style='color: #FF4757;'>R</span> <span style='color: #FFFFFF;'>{data['score']['red']}</span> 
                                 <span style='color: #36A2EB;'>B</span> <span style='color: #FFFFFF;'>{data['score']['blue']}</span> 
                                 <span style='color: #9C27B0;'>P</span> <span style='color: #FFFFFF;'>{data['score']['purple']}</span> 
                                 <span style='color: #4CAF50;'>G</span> <span style='color: #FFFFFF;'>{data['score']['green']}</span>"""
                box['score'].setText(score_html)
            
            # Highlight current player
            if player_name == self.game.get_current_player():
                box['frame'].setStyleSheet("background-color: #2a2a4e; border-radius: 8px; border: 3px solid #FFD700;")
            else:
                box['frame'].setStyleSheet("background-color: #1a1a2e; border-radius: 8px; border: 2px solid #444;")
    
    def update_discard_piles(self):
        """Update the discard piles display in player boxes."""
        color_map = {
            'red': '#FF4757',
            'blue': '#36A2EB',
            'purple': '#9C27B0',
            'green': '#4CAF50'
        }
        
        for idx, (player_name, pile) in enumerate(self.player_discard_piles.items()):
            if idx >= 4:  # Only show first 4 players
                break
            
            box = self.player_boxes[idx]
            discard_layout = box['discard_layout']
            
            # Clear existing widgets completely
            for i in reversed(range(discard_layout.count())):
                item = discard_layout.itemAt(i)
                if item.widget():
                    widget = item.widget()
                    discard_layout.removeWidget(widget)
                    widget.deleteLater()
                elif item.spacerItem():
                    discard_layout.removeItem(item)
            
            # Update discard count
            box['discard_count'].setText(f"Discard: {len(pile)} cards")
            
            # Show last 2 cards side by side
            if pile:
                last_cards = pile[-2:] if len(pile) >= 2 else pile
                for card in last_cards:
                    card_widget = QFrame()
                    card_widget.setFixedSize(110, 60)
                    bg_color = color_map.get(card.color, '#2a2a3e')
                    card_widget.setStyleSheet(f"background-color: {bg_color}; border-radius: 4px; border: 1px solid #444;")
                    
                    card_layout = QVBoxLayout()
                    card_layout.setContentsMargins(4, 4, 4, 4)
                    card_layout.setSpacing(2)
                    
                    # Top location (white text, left aligned)
                    top_label = QLabel(card.location)
                    top_label.setFont(QFont("Arial", 9, QFont.Weight.Bold))
                    top_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
                    top_label.setStyleSheet(f"color: #FFFFFF; background-color: transparent; border: none;")
                    card_layout.addWidget(top_label)
                    
                    # Center color (white text)
                    color_label = QLabel(card.color.upper())
                    color_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                    color_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    color_label.setStyleSheet(f"color: #FFFFFF; background-color: transparent; border: none;")
                    card_layout.addWidget(color_label)
                    
                    # Bottom location (white text, right aligned)
                    bottom_label = QLabel(card.location)
                    bottom_label.setFont(QFont("Arial", 9, QFont.Weight.Bold))
                    bottom_label.setAlignment(Qt.AlignmentFlag.AlignRight)
                    bottom_label.setStyleSheet(f"color: #FFFFFF; background-color: transparent; border: none;")
                    card_layout.addWidget(bottom_label)
                    
                    card_widget.setLayout(card_layout)
                    discard_layout.addWidget(card_widget)
                
                # Add spacer to push cards to the left
                discard_layout.addStretch()
    
    def update_hand(self):
        """Update the player's hand display."""
        while self.hand_layout.count():
            self.hand_layout.takeAt(0).widget().deleteLater()
        
        player = self.game.get_current_player()
        hand = self.game.get_player_hand(player)
        
        # Clear selections when hand updates
        self.selected_cards = []
        
        if self.is_current_player_ai():
            ai_label = QLabel("🤖 AI is thinking...")
            ai_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            ai_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ai_label.setStyleSheet("color: #FFD700;")
            self.hand_layout.addWidget(ai_label)
            self.play_btn.setEnabled(False)
            self.roll_dice_btn.setEnabled(False)
            return
        
        self.play_btn.setEnabled(True)
        
        color_map = {
            'red': '#FF4757',
            'blue': '#36A2EB',
            'purple': '#9C27B0',
            'green': '#4CAF50'
        }
        
        for i, card in enumerate(hand):
            # Create card widget with colored background
            card_widget = QFrame()
            card_widget.setFixedHeight(100)
            bg_color = color_map.get(card.color, '#2a2a3e')
            
            # Enhanced styling with gradient effect and power card glow
            if card.is_power_card():
                card_widget.setStyleSheet(f"""
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 {bg_color}, stop:1 #1a1a2e);
                    border-radius: 10px;
                    border: 3px solid #FFD700;
                """)
            else:
                card_widget.setStyleSheet(f"""
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 {bg_color}, stop:0.5 {bg_color}, stop:1 #1a1a2e);
                    border-radius: 10px;
                    border: 2px solid rgba(255, 255, 255, 0.2);
                """)
            
            card_layout = QVBoxLayout()
            card_layout.setContentsMargins(10, 6, 10, 6)
            card_layout.setSpacing(2)
            
            # Top row - location and power indicator
            top_row = QHBoxLayout()
            top_row.setContentsMargins(0, 0, 0, 0)
            
            # Show location or "PWR" for power cards
            display_location = "⚡" if card.is_power_card() else card.location
            top_left = QLabel(display_location)
            top_left.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            if card.is_power_card():
                top_left.setStyleSheet("color: #FFD700; background-color: transparent; border: none;")
            else:
                top_left.setStyleSheet("color: #FFFFFF; background-color: transparent; border: none;")
            top_row.addWidget(top_left)
            
            top_row.addStretch()
            
            # Power indicator on top right
            if card.is_power_card():
                power_icon = QLabel("⚡")
                power_icon.setFont(QFont("Arial", 12, QFont.Weight.Bold))
                power_icon.setStyleSheet("color: #FFD700; background-color: transparent; border: none;")
                top_row.addWidget(power_icon)
            else:
                top_right = QLabel(card.location)
                top_right.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                top_right.setStyleSheet("color: #FFFFFF; background-color: transparent; border: none;")
                top_row.addWidget(top_right)
            
            card_layout.addLayout(top_row)
            
            # Center - large location or "POWER"
            if card.is_power_card():
                location_label = QLabel("POWER")
                location_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
            else:
                location_label = QLabel(card.location)
                location_label.setFont(QFont("Arial", 32, QFont.Weight.Bold))
            location_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            location_label.setStyleSheet("color: #FFFFFF; background-color: transparent; border: none;")
            card_layout.addWidget(location_label)
            
            # Bottom row - color name and power description
            bottom_row = QHBoxLayout()
            bottom_row.setContentsMargins(0, 0, 0, 0)
            
            if card.is_power_card():
                # Power description on bottom left
                power_desc = QLabel(card.get_power_description())
                power_desc.setFont(QFont("Arial", 9, QFont.Weight.Bold))
                power_desc.setStyleSheet("color: #FFD700; background-color: transparent; border: none;")
                bottom_row.addWidget(power_desc)
                
                bottom_row.addStretch()
                
                # Power icon on bottom right
                bottom_power = QLabel("⚡")
                bottom_power.setFont(QFont("Arial", 9, QFont.Weight.Bold))
                bottom_power.setStyleSheet("color: #FFD700; background-color: transparent; border: none;")
                bottom_row.addWidget(bottom_power)
            else:
                # Regular card - color name
                bottom_left = QLabel(card.color.upper())
                bottom_left.setFont(QFont("Arial", 9, QFont.Weight.Bold))
                bottom_left.setStyleSheet("color: rgba(255, 255, 255, 0.8); background-color: transparent; border: none;")
                bottom_row.addWidget(bottom_left)
                
                bottom_row.addStretch()
                
                bottom_right = QLabel(card.location)
                bottom_right.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                bottom_right.setStyleSheet("color: #FFFFFF; background-color: transparent; border: none;")
                bottom_row.addWidget(bottom_right)
            
            card_layout.addLayout(bottom_row)
            
            card_widget.setLayout(card_layout)
            
            # Make it clickable
            card_widget.mousePressEvent = lambda event, idx=i: self.toggle_card_selection(idx)
            card_widget.setCursor(Qt.CursorShape.PointingHandCursor)
            
            # Highlight if selected with enhanced glow effect
            if i in self.selected_cards:
                if card.is_power_card():
                    card_widget.setStyleSheet(f"""
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 {bg_color}, stop:1 #1a1a2e);
                        border-radius: 10px;
                        border: 4px solid #FFD700;
                        background-color: rgba(255, 215, 0, 0.15);
                    """)
                else:
                    card_widget.setStyleSheet(f"""
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 {bg_color}, stop:0.5 {bg_color}, stop:1 #FFD700);
                        border-radius: 10px;
                        border: 4px solid #FFD700;
                    """)
            
            self.hand_layout.addWidget(card_widget)
        
        # Ensure selected_cards is empty at end
        self.selected_cards = []
    
    def toggle_card_selection(self, card_idx):
        """Toggle card selection."""
        if card_idx in self.selected_cards:
            self.selected_cards.remove(card_idx)
        else:
            # Limit selection based on cards already played this turn
            max_selectable = 2 - self.cards_played_this_turn
            if len(self.selected_cards) < max_selectable:
                self.selected_cards.append(card_idx)
        
        # Refresh hand display to show selection
        player = self.game.get_current_player()
        hand = self.game.get_player_hand(player)
        
        if self.is_current_player_ai():
            return
        
        # Update only the visual selection without clearing everything
        color_map = {
            'red': '#FF4757',
            'blue': '#36A2EB',
            'purple': '#9C27B0',
            'green': '#4CAF50'
        }
        
        for i in range(self.hand_layout.count()):
            widget = self.hand_layout.itemAt(i).widget()
            if isinstance(widget, QFrame) and i < len(hand):
                card = hand[i]
                bg_color = color_map.get(card.color, '#2a2a3e')
                if i in self.selected_cards:
                    widget.setStyleSheet(f"background-color: {bg_color}; border-radius: 8px; border: 3px solid #FFD700;")
                else:
                    widget.setStyleSheet(f"background-color: {bg_color}; border-radius: 8px; border: 2px solid #444;")
    
    def clear_selection(self):
        """Clear card selection."""
        self.selected_cards = []
        self.update_hand()
    
    def show_instructions(self):
        """Show game instructions dialog."""
        from PyQt6.QtWidgets import QMessageBox
        
        instructions = QMessageBox(self)
        instructions.setWindowTitle("🎲 Twenty Dots - How to Play")
        instructions.setStyleSheet("QMessageBox { background-color: #1a1a2e; color: #ffffff; } QLabel { color: #ffffff; } QPushButton { background-color: #4CAF50; color: white; padding: 8px 16px; border-radius: 4px; }")
        
        text = """<html><head><style>
        body { font-family: Arial; color: #ffffff; }
        h2 { color: #FFD700; }
        h3 { color: #4CAF50; }
        .important { color: #FF6B6B; }
        .power { color: #FFA500; }
        </style></head><body>
        
        <h2>🎯 OBJECTIVE</h2>
        <p><b>Easy Mode:</b> First player to collect 20 dots wins!</p>
        <p><b>Hard Mode:</b> First player to collect 5 dots of each color wins!</p>
        
        <h2>🎴 SETUP</h2>
        <p>• Each player starts with 5 cards</p>
        <p>• One wild (yellow) dot is placed on the board</p>
        
        <h2>🎮 GAMEPLAY</h2>
        <p><b>1. Roll Wild Dice</b> - At game start and when wild dot is collected/replaced</p>
        <p><b>2. Play Cards</b> - Play 1-2 cards per turn (click to select)</p>
        <p class="important"><b>Important:</b> Cannot play 2 cards with the same location!</p>
        <p><b>3. Match & Collect</b> - Get 3+ dots in a row (horizontal/vertical/diagonal)</p>
        <p>• Wild dots act as any color to complete matches</p>
        <p>• Collect all dots in the matching line</p>
        
        <h2>⚡ POWER CARDS</h2>
        <p class="power"><b>Power Card Rules:</b></p>
        <p class="important">• Must be played ALONE (cannot play with other cards)</p>
        <p class="important">• Cannot be played AFTER regular cards (must play first)</p>
        <p class="important">• Takes your FULL TURN (counts as 2 cards played)</p>
        <p class="important">• Only ONE power card per turn</p>
        
        <p class="power"><b>Available Power Cards:</b></p>
        <p>↔️ <b>Dot Swap:</b> Swap any 2 dots on the board - matches score!</p>
        <p>💣 <b>Remove:</b> Remove any colored dot from the board</p>
        <p>⭐ <b>Wild Place:</b> Place a yellow wild dot anywhere - matches score!</p>
        <p>×2 <b>Double Score:</b> Next match awards double points!</p>
        <p>🔄 <b>Card Swap:</b> Swap 2 of your cards with 2 from another player</p>
        <p>💥 <b>Land Mine:</b> Sacrifice a card to plant a mine - detonates 3x3 area!</p>
        
        <h2>⭐ SPECIAL RULES</h2>
        <p>• <b>Wild Dot Replacement:</b> Playing a card on the wild dot location replaces it</p>
        <p>• <b>Wild Match:</b> If wild dot completes a 3+ match, collect it and roll again!</p>
        <p>• <b>Chain Matches:</b> Keep rolling if wild dot keeps making matches!</p>
        <p>• <b>Dot Replacement Bonus:</b> Replace an opponent's colored dot to steal 1 point of that color!</p>
        <p class="important">Note: Replacing the yellow wild dot does NOT award points</p>
        
        <h2>🏆 WINNING</h2>
        <p>Be the first to reach your goal and claim victory!</p>
        
        </body></html>"""
        
        instructions.setText(text)
        instructions.setTextFormat(Qt.TextFormat.RichText)
        instructions.exec()
    
    def return_to_lobby(self):
        """Return to the game setup lobby."""
        from PyQt6.QtWidgets import QMessageBox
        
        # Confirm the user wants to return to lobby
        msg = QMessageBox(self)
        msg.setWindowTitle("Return to Lobby")
        msg.setText("Are you sure you want to return to the lobby?")
        msg.setInformativeText("The current game will be lost.")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #1a1a2e;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        result = msg.exec()
        
        if result == QMessageBox.StandardButton.Yes:
            # Stop any timers
            if self.ai_timer.isActive():
                self.ai_timer.stop()
            if self.pulse_timer.isActive():
                self.pulse_timer.stop()
            
            # Reset game state
            self.game = None
            self.selected_cards = []
            self.cards_played_this_turn = 0
            self.waiting_for_dice_roll = False
            self.scored_this_turn = False
            
            # Show setup dialog again
            self.show_setup_dialog()
    
    def roll_wild_dice(self):
        """Manually roll the dice to place wild yellow dot."""
        print("DEBUG: roll_wild_dice called")
        row, col = self.game.roll_dice()
        print(f"DEBUG: Rolled {row}{col}, placing wild dot...")
        result = self.game.place_wild_at_location(row, col)
        defused = result[2] if len(result) > 2 else False
        if defused:
            self.current_player_label.setText(f"✨ Wild defused a landmine at {row}{col}!")
            self.update_landmine_display()
        self.update_board()
        print(f"DEBUG: Wild dot placed, checking for matches...")
        
        # Check if yellow dot placement creates a match
        player = self.game.get_current_player()
        print(f"DEBUG: Current player is {player}, calling check_yellow_match...")
        yellow_match = self.check_yellow_match(row, col)
        print(f"DEBUG: check_yellow_match returned: {yellow_match}")
        
        if yellow_match:
            # Yellow created a match! Let player collect it
            self.waiting_for_dice_roll = True
            self.start_pulse_animation()
            self.current_player_label.setText("💥 WILD MATCH! Roll again for another chance!")
        else:
            self.roll_dice_btn.setEnabled(False)
            self.waiting_for_dice_roll = False
            self.play_btn.setEnabled(True)
            self.stop_pulse_animation()
            # Start timer after rolling dice
            self.start_turn_timer()
        
        # After rolling, either continue turn or move to next player
        if not yellow_match and self.cards_played_this_turn >= 2:
            # Turn complete, move to next player
            player = self.game.get_current_player()
            hand = self.game.get_player_hand(player)
            
            # Draw new cards to refill hand
            while len(hand) < 5 and self.game.deck:
                self.game.draw_card(player)
            
            # Reset turn counters
            self.cards_played_this_turn = 0
            self.locations_played_this_turn = []
            self.scored_this_turn = False
            
            # Check win after completing turn
            if self.game.check_win():
                self.show_winner(player)
                return
            
            self.game.next_player()
            self.update_scores()  # Update to highlight the new current player
            self.update_hand()
            self.update_current_player()
            
            if self.is_current_player_ai():
                self.ai_timer.start(2000)
        elif not yellow_match:
            # Can continue playing cards
            player = self.game.get_current_player()
            cards_left = 2 - self.cards_played_this_turn
            self.current_player_label.setText(f"🎮 {player}'s Turn - {cards_left} card(s) left")
    
    def play_selected_cards(self):
        """Play the selected cards."""
        # Don't allow playing cards if waiting for dice roll
        if self.waiting_for_dice_roll:
            return
        
        if len(self.selected_cards) == 0:
            return
        
        player = self.game.get_current_player()
        
        # Reset timeout counter on successful play
        if player in self.timeout_counts:
            self.timeout_counts[player] = 0
        
        hand = self.game.get_player_hand(player)
        
        # Check if any selected card is a power card
        has_power_card = False
        has_landmine = False
        for idx in self.selected_cards:
            if idx < len(hand) and hand[idx].is_power_card():
                has_power_card = True
                if hand[idx].power == 'landmine':
                    has_landmine = True
                break
        
        # Power card rules:
        # 1. Cannot play power card if cards already played this turn
        # 2. Cannot play power card with other cards (EXCEPTION: landmine needs sacrifice card)
        # 3. Cannot play more than 1 power card at once
        if has_power_card:
            if self.cards_played_this_turn > 0:
                self.current_player_label.setText("❌ Power cards must be played first - cannot play after regular cards!")
                QTimer.singleShot(2000, self.update_current_player)
                return
            
            # Special case: Landmine can be played with 1 regular card (sacrifice)
            if has_landmine:
                if len(self.selected_cards) == 2:
                    # Check that the other card is a regular card
                    other_card = None
                    for idx in self.selected_cards:
                        if idx < len(hand) and not hand[idx].is_power_card():
                            other_card = hand[idx]
                            break
                    if not other_card:
                        self.current_player_label.setText("❌ Landmine must be played with 1 regular card to sacrifice!")
                        QTimer.singleShot(2000, self.update_current_player)
                        return
                    # Valid landmine + sacrifice combination, allow it
                elif len(self.selected_cards) == 1:
                    self.current_player_label.setText("❌ Landmine requires a regular card to sacrifice!")
                    QTimer.singleShot(2000, self.update_current_player)
                    return
                else:
                    self.current_player_label.setText("❌ Landmine must be played with exactly 1 regular card!")
                    QTimer.singleShot(2000, self.update_current_player)
                    return
            else:
                # Other power cards must be played alone (exactly 1 card)
                if len(self.selected_cards) > 1:
                    self.current_player_label.setText("❌ Can only play 1 power card at a time - it takes your full turn!")
                    QTimer.singleShot(2000, self.update_current_player)
                    return
        
        # Check if playing too many cards this turn
        cards_to_play = len(self.selected_cards)
        if self.cards_played_this_turn + cards_to_play > 2:
            self.current_player_label.setText(f"❌ Only {2 - self.cards_played_this_turn} card(s) left to play this turn!")
            QTimer.singleShot(2000, self.update_current_player)
            return
        
        # Allow 1 or 2 cards
        if len(self.selected_cards) > 2:
            return
        
        # Check if any selected card location was already played this turn
        for idx in self.selected_cards:
            if idx < len(hand):
                card = hand[idx]
                print(f"DEBUG: Checking card {card.location}, already played: {self.locations_played_this_turn}")
                if not card.is_power_card() and card.location in self.locations_played_this_turn:
                    self.current_player_label.setText("❌ Cannot play 2 cards at the same location in one turn!")
                    QTimer.singleShot(2000, self.update_current_player)
                    return
        
        # Check if 2 cards with same location (when playing simultaneously)
        if len(self.selected_cards) == 2:
            card1 = hand[self.selected_cards[0]]
            card2 = hand[self.selected_cards[1]]
            print(f"DEBUG: Comparing cards - card1.location='{card1.location}' ({type(card1.location)}), card2.location='{card2.location}' ({type(card2.location)})")
            print(f"DEBUG: card1.is_power={card1.is_power_card()}, card2.is_power={card2.is_power_card()}")
            print(f"DEBUG: Locations equal? {card1.location == card2.location}")
            if not card1.is_power_card() and not card2.is_power_card() and card1.location == card2.location:
                self.current_player_label.setText("❌ Cannot play 2 cards with the same location!")
                QTimer.singleShot(2000, self.update_current_player)
                return
            
        self.execute_turn(self.selected_cards)
    
    def on_dot_clicked(self, col_idx, row_idx):
        """Handle clicking on a dot on the board (for power card selection)."""
        if not self.selecting_board_dots:
            return
        
        # Get the widget and check if it has a dot
        widget = self.dot_widgets[(col_idx, row_idx)]
        if not widget.dot:
            return  # Can't select empty positions
        
        # Convert indices to row/col strings
        row = self.game.rows[row_idx]
        col = self.game.columns[col_idx]
        position = (row_idx, col_idx)
        
        # Check if already selected
        if position in self.selected_board_positions:
            # Deselect
            self.selected_board_positions.remove(position)
            widget.set_highlighted(False)
        else:
            # Select
            self.selected_board_positions.append(position)
            widget.set_highlighted(True)
            
            # If we have enough selections, complete the action
            if self.board_selection_callback:
                required_count = getattr(self, 'required_selections', 2)
                if len(self.selected_board_positions) >= required_count:
                    # Call the callback with selected positions
                    self.board_selection_callback(self.selected_board_positions[:required_count])
    
    def select_dots_on_board(self, count, message):
        """Enable board selection mode to pick dots by clicking."""
        from PyQt6.QtWidgets import QMessageBox
        
        # Show instruction message
        msg = QMessageBox(self)
        msg.setWindowTitle("⚡ Power Card")
        msg.setText(message)
        msg.setInformativeText(f"Click {count} dot(s) on the board")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #1a1a2e;
            }
            QLabel {
                color: #FFD700;
                font-size: 14px;
            }
            QPushButton {
                background-color: #FFD700;
                color: #000000;
                border: none;
                padding: 8px 20px;
                border-radius: 5px;
                font-weight: bold;
                min-width: 80px;
            }
        """)
        msg.exec()
        
        # Enable selection mode
        self.selecting_board_dots = True
        self.selected_board_positions = []
        self.required_selections = count
        self.current_player_label.setText(f"⚡ Click {count} dots on the board...")
        
        # Wait for selections (will be handled by on_dot_clicked)
        # Return a promise-like pattern using a loop
        from PyQt6.QtCore import QEventLoop
        self.selection_loop = QEventLoop()
        
        def on_selection_complete(positions):
            self.selecting_board_dots = False
            # Clear highlights
            for pos in self.selected_board_positions:
                widget = self.dot_widgets[pos]
                widget.set_highlighted(False)
            self.selected_board_positions = []
            self.board_selection_callback = None
            self.update_current_player()
            self.selection_loop.quit()
            # Convert positions to (row, col) tuples
            result = []
            for row_idx, col_idx in positions:
                result.append((row_idx, col_idx))
            self.selection_result = result
        
        self.board_selection_callback = on_selection_complete
        self.selection_loop.exec()
        
        return getattr(self, 'selection_result', None)
    
    def activate_power_card(self, card, player):
        """Activate a power card's special ability."""
        power = card.power
        is_ai = player in self.ai_players
        
        if power == 'swap':
            # Get two grid positions to swap
            if is_ai:
                # AI randomly picks two positions with dots
                import random
                positions_with_dots = []
                for row_idx in range(6):
                    for col_idx in range(6):
                        if self.game.grid[row_idx][col_idx]:
                            positions_with_dots.append((row_idx, col_idx))
                if len(positions_with_dots) >= 2:
                    pos1, pos2 = random.sample(positions_with_dots, 2)
                    self.game.swap_dots(pos1, pos2)
                    self.update_board()
                    
                    # Check for matches at both swapped positions
                    for pos in [pos1, pos2]:
                        dot = self.game.grid[pos[0]][pos[1]]
                        if dot and dot.color != 'yellow':
                            row = self.game.rows[pos[0]]
                            col = self.game.columns[pos[1]]
                            match_result = self.game.check_line_match(row, col, dot.color)
                            if match_result:
                                line_match, match_color = match_result
                                # Check if yellow is in the match
                                for match_pos in line_match:
                                    match_dot = self.game.grid[match_pos[1]][match_pos[0]]
                                    if match_dot and match_dot.color == 'yellow':
                                        self.yellow_collected_by_power = True
                                        break
                                self.game.collect_dots(line_match, player, dot.color)
                                self.update_board()
                                self.update_scores()
                    
                    return True
            else:
                positions = self.select_dots_on_board(2, "Swap two dots")
                if positions and len(positions) == 2:
                    self.game.swap_dots(positions[0], positions[1])
                    self.update_board()
                    
                    # Check for matches at both swapped positions
                    for pos in positions:
                        dot = self.game.grid[pos[0]][pos[1]]
                        if dot and dot.color != 'yellow':
                            row = self.game.rows[pos[0]]
                            col = self.game.columns[pos[1]]
                            match_result = self.game.check_line_match(row, col, dot.color)
                            if match_result:
                                line_match, match_color = match_result
                                # Check if yellow is in the match
                                for match_pos in line_match:
                                    match_dot = self.game.grid[match_pos[1]][match_pos[0]]
                                    if match_dot and match_dot.color == 'yellow':
                                        self.yellow_collected_by_power = True
                                        break
                                self.game.collect_dots(line_match, player, dot.color)
                                self.update_board()
                                self.update_scores()
                    
                    # Clear highlights from all dot widgets after swap
                    for widget in self.dot_widgets.values():
                        widget.set_highlighted(False)
                    
                    PowerCardDialog(self, "Dot Swap", "Dots swapped!", "↔️").exec()
                    return True
        
        elif power == 'remove':
            # Select a dot to remove (excluding wild dot)
            if is_ai:
                # AI randomly picks a colored dot to remove
                import random
                colored_dots = []
                for row_idx in range(6):
                    for col_idx in range(6):
                        dot = self.game.grid[row_idx][col_idx]
                        if dot and dot.color != 'yellow':
                            colored_dots.append((row_idx, col_idx))
                if colored_dots:
                    row_idx, col_idx = random.choice(colored_dots)
                    self.game.remove_dot(row_idx, col_idx)
                    self.update_board()
                    return True
            else:
                position = self.select_grid_position("Select a colored dot to remove (NOT the wild)")
                if position:
                    row_idx = self.game.rows.index(position[0])
                    col_idx = self.game.columns.index(position[1])
                    
                    # Check if this is the yellow wild dot
                    dot = self.game.grid[row_idx][col_idx]
                    if dot and dot.color == 'yellow':
                        QMessageBox.warning(self, "Power Card", "Cannot remove the wild dot! Choose a colored dot instead.")
                        return False
                    
                    # Check if there's actually a dot to remove
                    if not dot:
                        QMessageBox.warning(self, "Power Card", "No dot at that position!")
                        return False
                    
                    self.game.remove_dot(row_idx, col_idx)
                    self.update_board()
                    PowerCardDialog(self, "Remove", f"Removed {dot.color} dot!", "💣").exec()
                    return True
        
        elif power == 'wild_place':
            # Select where to place a new yellow wild dot
            print("DEBUG: wild_place power activated")
            if is_ai:
                # AI randomly picks an empty position
                import random
                empty_positions = []
                for row_idx in range(6):
                    for col_idx in range(6):
                        if not self.game.grid[row_idx][col_idx]:
                            empty_positions.append((self.game.rows[row_idx], self.game.columns[col_idx]))
                if empty_positions:
                    row, col = random.choice(empty_positions)
                    result = self.game.place_wild_at_location(row, col)
                    row_col_tuple = result[:2] if len(result) > 2 else result
                    defused = result[2] if len(result) > 2 else False
                    if defused:
                        print(f"AI wild_place defused landmine at {row}{col}")
                        self.update_landmine_display()
                    self.update_board()
                    
                    # Check for matches at the new wild dot position - check ALL directions
                    row_idx = self.game.rows.index(row)
                    col_idx = self.game.columns.index(col)
                    all_match_positions = []
                    match_colors = []
                    
                    # Check all 4 directions for matches
                    directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
                    
                    for dx, dy in directions:
                        line = []
                        colors_in_line = set()
                        
                        # Check backwards
                        x, y = col_idx - dx, row_idx - dy
                        while 0 <= x < 6 and 0 <= y < 6:
                            dot = self.game.grid[y][x]
                            if dot:
                                line.append((x, y))
                                colors_in_line.add(dot.color)
                                x -= dx
                                y -= dy
                            else:
                                break
                        
                        line.reverse()
                        line.append((col_idx, row_idx))  # Add yellow dot position
                        colors_in_line.add('yellow')
                        
                        # Check forwards
                        x, y = col_idx + dx, row_idx + dy
                        while 0 <= x < 6 and 0 <= y < 6:
                            dot = self.game.grid[y][x]
                            if dot:
                                line.append((x, y))
                                colors_in_line.add(dot.color)
                                x += dx
                                y += dy
                            else:
                                break
                        
                        # If we found a line of 3 or more with exactly one non-yellow color
                        non_yellow_colors = colors_in_line - {'yellow'}
                        if len(line) >= 3 and len(non_yellow_colors) == 1:
                            match_color = list(non_yellow_colors)[0]
                            all_match_positions.extend(line)
                            match_colors.append(match_color)
                    
                    # Now collect all matches at once
                    if all_match_positions:
                        # Remove duplicates
                        unique_positions = []
                        seen = set()
                        for pos in all_match_positions:
                            if pos not in seen:
                                seen.add(pos)
                                unique_positions.append(pos)
                        
                        # Group positions by color and collect
                        color_groups = {}
                        for i, match_color in enumerate(match_colors):
                            if match_color not in color_groups:
                                color_groups[match_color] = []
                        
                        for pos in unique_positions:
                            dot = self.game.grid[pos[1]][pos[0]]
                            if dot:
                                if dot.color == 'yellow':
                                    if match_colors:
                                        color_groups[match_colors[0]].append(pos)
                                else:
                                    if dot.color in color_groups:
                                        color_groups[dot.color].append(pos)
                                    else:
                                        color_groups[dot.color] = [pos]
                        
                        for match_color, positions in color_groups.items():
                            if positions:
                                self.game.collect_dots(positions, player, match_color)
                        
                        # Check if yellow was collected
                        if self.game.grid[row_idx][col_idx] is None:
                            self.yellow_collected_by_power = True
                    
                    self.update_board()
                    self.update_scores()
                    return True
            else:
                position = self.select_grid_position("Select where to place wild dot")
                if position:
                    row = position[0]
                    col = position[1]
                    result = self.game.place_wild_at_location(row, col)
                    row_col_tuple = result[:2] if len(result) > 2 else result
                    defused = result[2] if len(result) > 2 else False
                    if defused:
                        self.current_player_label.setText(f"✨ Wild defused a landmine at {row}{col}!")
                        self.update_landmine_display()
                    self.update_board()
                    
                    # Check for matches at the new wild dot position - check ALL directions
                    row_idx = self.game.rows.index(row)
                    col_idx = self.game.columns.index(col)
                    all_match_positions = []
                    match_colors = []
                    
                    print(f"DEBUG wild_place: Checking matches at {row}{col} (row_idx={row_idx}, col_idx={col_idx})")
                    
                    # Check all 4 directions for matches
                    directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
                    
                    for dx, dy in directions:
                        line = []
                        colors_in_line = set()
                        
                        # Check backwards
                        x, y = col_idx - dx, row_idx - dy
                        while 0 <= x < 6 and 0 <= y < 6:
                            dot = self.game.grid[y][x]
                            if dot:
                                line.append((x, y))
                                colors_in_line.add(dot.color)
                                x -= dx
                                y -= dy
                            else:
                                break
                        
                        line.reverse()
                        line.append((col_idx, row_idx))  # Add yellow dot position
                        colors_in_line.add('yellow')
                        
                        # Check forwards
                        x, y = col_idx + dx, row_idx + dy
                        while 0 <= x < 6 and 0 <= y < 6:
                            dot = self.game.grid[y][x]
                            if dot:
                                line.append((x, y))
                                colors_in_line.add(dot.color)
                                x += dx
                                y += dy
                            else:
                                break
                        
                        # If we found a line of 3 or more with exactly one non-yellow color
                        non_yellow_colors = colors_in_line - {'yellow'}
                        print(f"DEBUG wild_place: Direction ({dx},{dy}) - line length: {len(line)}, colors: {colors_in_line}, non-yellow: {non_yellow_colors}")
                        if len(line) >= 3 and len(non_yellow_colors) == 1:
                            match_color = list(non_yellow_colors)[0]
                            print(f"DEBUG wild_place: MATCH FOUND! Color: {match_color}, adding {len(line)} dots to collection")
                            all_match_positions.extend(line)
                            match_colors.append(match_color)
                    
                    # Now collect all matches at once
                    if all_match_positions:
                        # Remove duplicates (yellow dot will appear in multiple matches)
                        unique_positions = []
                        seen = set()
                        for pos in all_match_positions:
                            if pos not in seen:
                                seen.add(pos)
                                unique_positions.append(pos)
                        
                        # Collect all dots - use the first match color (they should all be the same when yellow is wild)
                        # Actually, we need to collect by color groups
                        color_groups = {}
                        for i, match_color in enumerate(match_colors):
                            if match_color not in color_groups:
                                color_groups[match_color] = []
                        
                        # Group positions by their actual color (not the match color)
                        for pos in unique_positions:
                            dot = self.game.grid[pos[1]][pos[0]]
                            if dot:
                                if dot.color == 'yellow':
                                    # Yellow gets counted in first match color
                                    if match_colors:
                                        color_groups[match_colors[0]].append(pos)
                                else:
                                    if dot.color in color_groups:
                                        color_groups[dot.color].append(pos)
                                    else:
                                        color_groups[dot.color] = [pos]
                        
                        # Collect each color group
                        total_collected = 0
                        for match_color, positions in color_groups.items():
                            if positions:
                                self.game.collect_dots(positions, player, match_color)
                                total_collected += len(positions)
                        
                        self.update_board()
                        self.update_scores()
                        
                        # Check if yellow dot was collected
                        yellow_collected = self.game.grid[row_idx][col_idx] is None
                        
                        colors_str = ", ".join(set(match_colors))
                        PowerCardDialog(self, "Wild Place", f"Wild dot placed and matched {total_collected} dots!\nColors: {colors_str}", "⭐").exec()
                        
                        # If yellow was collected, trigger dice roll
                        if yellow_collected:
                            self.yellow_collected_by_power = True
                    else:
                        PowerCardDialog(self, "Wild Place", "Wild dot placed!", "⭐").exec()
                    
                    return True
        
        elif power == 'double_score':
            # Set flag for next match to score double
            self.game.players[player]['double_next_match'] = True
            if not is_ai:
                PowerCardDialog(self, "Double Score", "Next match will score 2x points!", "×2").exec()
            return True
        
        elif power == 'card_swap':
            # Swap 2 cards from your hand with 2 cards from another player's hand
            other_players = [p for p in self.game.players.keys() if p != player]
            if not other_players:
                if not is_ai:
                    QMessageBox.warning(self, "Power Card", "No other players to swap cards with!")
                return False
            
            player_hand = self.game.get_player_hand(player)
            if len(player_hand) < 2:
                if not is_ai:
                    QMessageBox.warning(self, "Power Card", "You need at least 2 cards in your hand to swap!")
                return False
            
            if is_ai:
                # AI randomly picks a player with at least 2 cards and swaps 2 random cards
                import random
                players_with_cards = [p for p in other_players if len(self.game.get_player_hand(p)) >= 2]
                if players_with_cards:
                    target_player = random.choice(players_with_cards)
                    target_hand = self.game.get_player_hand(target_player)
                    
                    # Pick 2 random cards from each hand
                    my_cards = random.sample(player_hand, 2)
                    their_cards = random.sample(target_hand, 2)
                    
                    # Perform the swap
                    for card in my_cards:
                        player_hand.remove(card)
                        target_hand.append(card)
                    for card in their_cards:
                        target_hand.remove(card)
                        player_hand.append(card)
                    
                    return True
                return False
            else:
                # Human player selects target player
                items = [f"{p} ({len(self.game.get_player_hand(p))} cards)" for p in other_players]
                
                dialog = QInputDialog(self)
                dialog.setWindowTitle("🔄 Card Swap")
                dialog.setLabelText("Select player to swap cards with:")
                dialog.setComboBoxItems(items)
                dialog.setStyleSheet("""
                    QInputDialog {
                        background-color: #1a1a2e;
                        color: #FFFFFF;
                    }
                    QLabel {
                        color: #FFD700;
                        font-size: 14px;
                        font-weight: bold;
                    }
                    QComboBox {
                        background-color: #2a2a3e;
                        color: #FFFFFF;
                        border: 2px solid #FFD700;
                        border-radius: 5px;
                        padding: 8px;
                        font-size: 14px;
                    }
                    QComboBox:hover {
                        border: 2px solid #FFC700;
                    }
                    QComboBox QAbstractItemView {
                        background-color: #2a2a3e;
                        color: #FFFFFF;
                        selection-background-color: #FFD700;
                        selection-color: #000000;
                    }
                    QPushButton {
                        background-color: #FFD700;
                        color: #000000;
                        border: none;
                        padding: 8px 20px;
                        border-radius: 5px;
                        font-weight: bold;
                        min-width: 80px;
                    }
                    QPushButton:hover {
                        background-color: #FFC700;
                    }
                """)
                
                ok = dialog.exec()
                target = dialog.textValue()
                
                if ok and target:
                    target_player = other_players[items.index(target)]
                    target_hand = self.game.get_player_hand(target_player)
                    
                    if len(target_hand) < 2:
                        QMessageBox.warning(self, "Power Card", f"{target_player} doesn't have enough cards!")
                        return False
                    
                    # Let player select 2 cards from their hand to swap (exclude the card swap power card being played)
                    exclude = [card for card in player_hand if card.is_power_card() and card.power == 'card_swap']
                    selected_indices = self.select_cards_from_hand(player_hand, 2, f"Select 2 cards from YOUR hand to swap with {target_player}", exclude_cards=exclude)
                    if not selected_indices or len(selected_indices) != 2:
                        QMessageBox.warning(self, "Card Swap", "You must select exactly 2 cards!")
                        return False
                    
                    # Let player select 2 cards from target's hand
                    target_indices = self.select_cards_from_hand(target_hand, 2, f"Select 2 cards from {target_player}'s hand to receive", show_face_down=True)
                    if not target_indices or len(target_indices) != 2:
                        QMessageBox.warning(self, "Card Swap", "You must select exactly 2 cards!")
                        return False
                    
                    # Get the actual card objects
                    my_cards = [player_hand[i] for i in selected_indices]
                    their_cards = [target_hand[i] for i in target_indices]
                    
                    # Perform the swap
                    for card in my_cards:
                        player_hand.remove(card)
                        target_hand.append(card)
                    for card in their_cards:
                        target_hand.remove(card)
                        player_hand.append(card)
                    
                    self.update_hand()
                    PowerCardDialog(self, "Card Swap", f"Swapped 2 cards with {target_player}!", "🔄").exec()
                    return True
        
        elif power == 'landmine':
            # For human players, landmine requires selecting a second card
            # For AI, auto-select a random regular card
            hand = self.game.get_player_hand(player)
            regular_cards = [c for c in hand if not c.is_power_card()]
            
            print(f"DEBUG: Landmine activation - {player} has {len(regular_cards)} regular cards out of {len(hand)} total")
            
            if not regular_cards:
                if not is_ai:
                    QMessageBox.warning(self, "Power Card", "You need a regular card to place a land mine!")
                print(f"DEBUG: Landmine activation failed - no regular cards available for {player}")
                return False
            
            if is_ai:
                # AI randomly picks a regular card to sacrifice
                import random
                sacrificed_card = random.choice(regular_cards)
                hand.remove(sacrificed_card)
                success = self.game.place_landmine(sacrificed_card.location, sacrificed_card.color, player)
                if success:
                    self.update_landmine_display()
                    return True
                else:
                    # Failed to place landmine (space occupied), put card back
                    hand.append(sacrificed_card)
                    print(f"DEBUG: Landmine placement failed for {player} - space {sacrificed_card.location} is occupied")
                    return False
            else:
                # For human players, just mark that we're waiting for sacrifice card selection
                # This will be handled in execute_turn
                return 'waiting_for_sacrifice'
        
        return False
    
    def select_cards_from_hand(self, hand, count, message, show_face_down=False, exclude_cards=None):
        """Show dialog to select cards from a hand. Returns list of selected indices.
        
        Args:
            hand: List of cards to select from
            count: Number of cards to select
            message: Message to display
            show_face_down: Whether to hide card details
            exclude_cards: List of cards to exclude from selection (e.g., the power card being played)
        """
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
        from PyQt6.QtCore import Qt
        
        if exclude_cards is None:
            exclude_cards = []
        
        # Filter out excluded cards
        selectable_hand = [card for card in hand if card not in exclude_cards]
        # Create mapping from selectable indices to original hand indices
        index_mapping = {i: hand.index(card) for i, card in enumerate(selectable_hand)}
        
        dialog = QDialog(self)
        dialog.setWindowTitle("🔄 Card Swap")
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1a1a2e;
            }
        """)
        
        layout = QVBoxLayout()
        
        # Message label
        msg_label = QLabel(message)
        msg_label.setStyleSheet("""
            QLabel {
                color: #FFD700;
                font-size: 16px;
                font-weight: bold;
                padding: 10px;
            }
        """)
        msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(msg_label)
        
        # Cards display
        cards_layout = QHBoxLayout()
        selected = []
        card_buttons = []
        
        def toggle_card(idx):
            if idx in selected:
                selected.remove(idx)
                card_buttons[idx].setStyleSheet(get_button_style(idx, False))
            else:
                if len(selected) < count:
                    selected.append(idx)
                    card_buttons[idx].setStyleSheet(get_button_style(idx, True))
        
        def get_button_style(idx, is_selected):
            border = "4px solid #FFD700" if is_selected else "2px solid #555"
            return f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #3a3a4e, stop:1 #2a2a3e);
                    color: #FFFFFF;
                    border: {border};
                    border-radius: 10px;
                    padding: 15px;
                    font-size: 14px;
                    font-weight: bold;
                    min-width: 100px;
                    min-height: 80px;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #4a4a5e, stop:1 #3a3a4e);
                }}
            """
        
        for i, card in enumerate(selectable_hand):
            btn = QPushButton()
            if show_face_down:
                btn.setText("🎴\n???")
            else:
                location = card.location if hasattr(card, 'location') else '?'
                color = card.color if hasattr(card, 'color') else '?'
                if card.is_power_card():
                    btn.setText(f"{card.get_power_description()}\n{color.upper()}")
                else:
                    btn.setText(f"{location}\n{color.upper()}")
            
            btn.setStyleSheet(get_button_style(i, False))
            btn.clicked.connect(lambda checked, idx=i: toggle_card(idx))
            card_buttons.append(btn)
            cards_layout.addWidget(btn)
        
        layout.addLayout(cards_layout)
        
        # Confirm button
        confirm_btn = QPushButton(f"Confirm Selection ({count} cards)")
        confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFD700;
                color: #000000;
                border: none;
                padding: 12px 30px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 16px;
                margin: 10px;
            }
            QPushButton:hover {
                background-color: #FFC700;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """)
        confirm_btn.setEnabled(False)
        
        def update_confirm_button():
            confirm_btn.setEnabled(len(selected) == count)
            confirm_btn.setText(f"Confirm Selection ({len(selected)}/{count} cards)")
        
        def on_confirm():
            if len(selected) == count:
                dialog.accept()
        
        # Update button state whenever selection changes
        original_toggle = toggle_card
        def toggle_with_update(idx):
            original_toggle(idx)
            update_confirm_button()
        
        # Re-connect buttons with the updated toggle function
        for i, btn in enumerate(card_buttons):
            btn.clicked.disconnect()
            btn.clicked.connect(lambda checked, idx=i: toggle_with_update(idx))
        
        confirm_btn.clicked.connect(on_confirm)
        layout.addWidget(confirm_btn)
        
        dialog.setLayout(layout)
        result = dialog.exec()
        
        if result == QDialog.DialogCode.Accepted and len(selected) == count:
            # Map selected indices back to original hand indices
            return [index_mapping[i] for i in selected]
        return None
    
    def select_grid_position(self, message):
        """Show dialog to select a grid position."""
        rows = self.game.rows
        cols = self.game.columns
        
        # Create list of all positions
        positions = [f"{row}{col}" for row in rows for col in cols]
        
        # Create styled input dialog
        dialog = QInputDialog(self)
        dialog.setWindowTitle("⚡ Power Card")
        dialog.setLabelText(message)
        dialog.setComboBoxItems(positions)
        dialog.setStyleSheet("""
            QInputDialog {
                background-color: #1a1a2e;
                color: #FFFFFF;
            }
            QLabel {
                color: #FFD700;
                font-size: 14px;
                font-weight: bold;
            }
            QComboBox {
                background-color: #2a2a3e;
                color: #FFFFFF;
                border: 2px solid #FFD700;
                border-radius: 5px;
                padding: 8px;
                font-size: 14px;
            }
            QComboBox:hover {
                border: 2px solid #FFC700;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #2a2a3e;
                color: #FFFFFF;
                selection-background-color: #FFD700;
                selection-color: #000000;
            }
            QPushButton {
                background-color: #FFD700;
                color: #000000;
                border: none;
                padding: 8px 20px;
                border-radius: 5px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #FFC700;
            }
        """)
        
        ok = dialog.exec()
        position = dialog.textValue()
        
        if ok and position:
            return (position[0], position[1])
        return None
    
    def select_two_grid_positions(self, message):
        """Show dialog to select two grid positions."""
        pos1 = self.select_grid_position(f"{message} (First position)")
        if not pos1:
            return None
        
        pos2 = self.select_grid_position(f"{message} (Second position)")
        if not pos2:
            return None
        
        return [pos1, pos2]
    
    def execute_turn(self, card_indices):
        """Execute a player's turn with the given card indices."""
        # Stop the timer when cards are played
        self.stop_turn_timer()
        
        try:
            player = self.game.get_current_player()
            hand = self.game.get_player_hand(player)
            
            # Validate card indices
            if not card_indices or len(card_indices) == 0:
                print("Error: No cards selected")
                return
            
            # Filter valid indices only
            valid_indices = [i for i in card_indices if 0 <= i < len(hand)]
            if len(valid_indices) != len(card_indices):
                print(f"Warning: Some card indices were out of range. Hand size: {len(hand)}, Indices: {card_indices}")
            
            if not valid_indices:
                print("Error: No valid card indices")
                return
            
            # Clear selected cards to prevent reuse of old indices
            self.selected_cards = []
            
            # Sort indices in reverse order to safely remove from hand
            sorted_indices = sorted(valid_indices, reverse=True)
            cards = [hand[i] for i in sorted_indices]
        except Exception as e:
            print(f"Error in execute_turn setup: {e}")
            import traceback
            traceback.print_exc()
            return
        
        try:
            # Separate power cards from regular cards
            power_cards = [card for card in cards if card.is_power_card()]
            regular_cards = [card for card in cards if not card.is_power_card()]
            
            # Track which power cards were successfully activated
            activated_power_cards = []
            
            # Activate power cards first
            for power_card in power_cards:
                print(f"DEBUG: Activating power card: {power_card.power}")
                result = self.activate_power_card(power_card, player)
                print(f"DEBUG: Power card {power_card.power} returned: {result}")
                if result == 'waiting_for_sacrifice':
                    # Landmine needs a sacrifice card - check if one was selected
                    sacrifice_cards = [c for c in regular_cards if not c.is_power_card()]
                    if sacrifice_cards:
                        # Use the first selected regular card as sacrifice
                        sacrificed_card = sacrifice_cards[0]
                        
                        # Try to place the landmine - check if space is empty
                        success = self.game.place_landmine(sacrificed_card.location, sacrificed_card.color, player)
                        
                        if success:
                            regular_cards.remove(sacrificed_card)
                            hand.remove(sacrificed_card)
                            self.update_landmine_display()
                            # Add landmine power card to discard, but keep sacrifice card face-down (not in discard)
                            self.player_discard_piles[player].append(power_card)
                            # Note: sacrificed_card stays face-down on board, not added to discard pile
                            self.cards_played_this_turn += 2  # Count both landmine and sacrifice card
                            activated_power_cards.append(power_card)
                            # Show success message
                            if not player in self.ai_players:
                                PowerCardDialog(self, "Land Mine", f"Land mine armed at {sacrificed_card.location}!\nAny player who plays here will detonate it!", "💥").exec()
                        else:
                            # Space is occupied - can't place landmine
                            if not player in self.ai_players:
                                QMessageBox.warning(self, "Land Mine", f"Cannot place land mine at {sacrificed_card.location} - space is already occupied!\nPlease select a card with an empty location.")
                            cards.remove(power_card)
                    else:
                        # No sacrifice card selected - cancel landmine activation
                        print(f"DEBUG: Landmine activation cancelled - no regular card selected")
                        cards.remove(power_card)
                elif not result:
                    # If activation failed or was cancelled, don't discard the card
                    cards.remove(power_card)
                else:
                    # Power card activated successfully - add to discard
                    print(f"DEBUG: Power card {power_card.power} activated successfully, adding to discard")
                    self.player_discard_piles[player].append(power_card)
                    # Power cards take the full turn (count as 2 cards played)
                    self.cards_played_this_turn += 2
                    activated_power_cards.append(power_card)
            
            print(f"DEBUG: Activated power cards: {[pc.power for pc in activated_power_cards]}")
            print(f"DEBUG: Hand before removal: {len(hand)} cards")
            
            # Remove activated power cards from hand
            for power_card in activated_power_cards:
                if power_card in hand:
                    print(f"DEBUG: Removing {power_card.power} from hand")
                    hand.remove(power_card)
                else:
                    print(f"DEBUG: Warning - {power_card.power} not found in hand!")
            
            print(f"DEBUG: Hand after removal: {len(hand)} cards")
            
            # If no regular cards to play, we're done (but still need to end turn and draw cards)
            if not regular_cards:
                self.update_hand()
                self.update_discard_piles()
                
                # Check if yellow was collected by the power card and need dice roll
                if self.yellow_collected_by_power:
                    if not self.is_current_player_ai():
                        self.waiting_for_dice_roll = True
                        self.roll_dice_btn.setEnabled(True)
                        self.play_btn.setEnabled(False)
                        self.start_pulse_animation()
                        self.current_player_label.setText("⭐ 3 of a Kind! Wild dot collected - Roll for new position!")
                        # Reset flag after setting up dice roll
                        self.yellow_collected_by_power = False
                        self.update_hand()
                        return
                    else:
                        # AI auto-rolls
                        row, col = self.game.roll_dice()
                        result = self.game.place_wild_at_location(row, col)
                        defused = result[2] if len(result) > 2 else False
                        if defused:
                            print(f"AI wild defused landmine at {row}{col} after power card")
                            self.update_landmine_display()
                        self.update_board()
                        print(f"DEBUG: AI rolled wild to {row}{col} after power card match")
                        # Check if AI's roll creates another match - keep rolling until no match
                        while True:
                            yellow_match = self.check_yellow_match(row, col)
                            if yellow_match:
                                print(f"DEBUG: AI created yellow match! Rolling again for new wild...")
                                row, col = self.game.roll_dice()
                                result = self.game.place_wild_at_location(row, col)
                                defused = result[2] if len(result) > 2 else False
                                if defused:
                                    print(f"AI wild defused landmine at {row}{col}")
                                    self.update_landmine_display()
                                self.update_board()
                                print(f"DEBUG: AI rolled new wild to {row}{col}, checking again...")
                            else:
                                # No match, exit loop
                                print(f"DEBUG: No match at {row}{col}, continuing...")
                                break
                
                # Check if turn should end
                if self.cards_played_this_turn >= 2:
                    self.cards_played_this_turn = 0
                    self.locations_played_this_turn = []
                    self.scored_this_turn = False
                    self.yellow_collected_by_power = False
                    
                    # Draw new cards after turn is complete
                    print(f"DEBUG: End of turn (power card only) - Hand size before draw: {len(hand)}")
                    cards_drawn = 0
                    while len(hand) < 5 and self.game.deck:
                        self.game.draw_card(player)
                        cards_drawn += 1
                    print(f"DEBUG: Drew {cards_drawn} cards. Hand size now: {len(hand)}")
                    
                    # Check win
                    if self.game.check_win():
                        self.show_winner(player)
                        return
                    
                    self.game.next_player()
                    self.update_scores()
                    self.update_current_player()
                    self.update_hand()
                    if self.is_current_player_ai():
                        self.ai_timer.start(2000)
                return
            
            total_collected = []
            yellow_was_replaced = False
            yellow_was_collected = False
            
            # Add regular cards to player's discard pile
            print(f"DEBUG: Adding {len(regular_cards)} regular cards to {player}'s discard pile. Current pile size: {len(self.player_discard_piles[player])}")
            for card in regular_cards:
                self.player_discard_piles[player].append(card)
                # Track location played this turn
                self.locations_played_this_turn.append(card.location)
                print(f"DEBUG: Added {card} to discard. New pile size: {len(self.player_discard_piles[player])}")
            
            for i, card in enumerate(regular_cards):
                print(f"DEBUG: Placing card {i+1}/{len(regular_cards)}: {card}")
                # Check if placing on yellow dot location
                row = card.location[0]
                col = card.location[1]
                row_idx = self.game.rows.index(row)
                col_idx = self.game.columns.index(col)
                
                # Check for landmine at this location
                detonation = self.game.check_and_detonate_landmine(card.location, player)
                if detonation:
                    # Landmine detonated!
                    removed_count = len(detonation['removed_positions'])
                    print(f"💥 LANDMINE DETONATED at {detonation['location']}! Removed {removed_count} dots, penalty: -2 {detonation['color']}")
                    
                    # Only show dialog for human players
                    if player not in self.ai_players:
                        dialog = PowerCardDialog(
                            title="💥 LAND MINE DETONATED! 💥",
                            message=f"You triggered a land mine at {detonation['location']}!\n\n"
                                    f"💥 Removed {removed_count} dots in 3x3 area\n"
                                    f"⚠️ Penalty: -2 {detonation['color']} dots",
                            gradient_colors=("#FF4757", "#8B0000"),
                            parent=self
                        )
                        dialog.exec()
                    
                    # Update displays after detonation
                    self.update_board()
                    self.update_scores()
                    self.update_landmine_display()
                    # Don't place the dot - landmine destroyed it!
                    continue
                
                current_dot = self.game.grid[row_idx][col_idx]
                if current_dot and current_dot.color == 'yellow':
                    yellow_was_replaced = True
                
                success, replaced_color = self.game.place_card_dot(card)
                if success:
                    print(f"DEBUG: Successfully placed {card.color} dot at {card.location}")
                    print(f"DEBUG: Grid at {card.location}: {self.game.grid[row_idx][col_idx]}")
                    # Award point for replacing a colored dot
                    if replaced_color:
                        self.game.players[player]['score'][replaced_color] += 1
                        self.game.players[player]['total_dots'] += 1
                    
                    match_result = self.game.check_line_match(card.location[0], card.location[1], card.color)
                    if match_result:
                        line_match, match_color = match_result
                        print(f"DEBUG: check_line_match returned {len(line_match)} positions (color={match_color})")
                    else:
                        line_match = None
                        print(f"DEBUG: check_line_match returned no match")
                    
                    if line_match:
                        # Check if yellow dot is in the match
                        for pos in line_match:
                            dot = self.game.grid[pos[1]][pos[0]]
                            if dot and dot.color == 'yellow':
                                yellow_was_collected = True
                                break
                        
                        self.game.collect_dots(line_match, player, card.color)
                        total_collected.extend(line_match)
                        self.scored_this_turn = True
            
            # Remove regular cards from hand in reverse index order (so indices remain valid)
            regular_card_indices = sorted([hand.index(card) for card in regular_cards if card in hand], reverse=True)
            print(f"DEBUG: Removing regular cards at indices {regular_card_indices} from hand of size {len(hand)}")
            for idx in regular_card_indices:
                if idx < len(hand):
                    removed_card = hand.pop(idx)
                    print(f"DEBUG: Removed {removed_card} at index {idx}. Hand size now: {len(hand)}")
            
            # Track cards played this turn (regular cards only, power cards already tracked)
            self.cards_played_this_turn += len(regular_cards)
            
            # Update display
            self.update_board()
            self.update_scores()
            self.update_discard_piles()
            
        except Exception as e:
            print(f"Error during card processing: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # Only roll dice if yellow was replaced or collected (including by power cards)
        need_dice_roll = yellow_was_replaced or yellow_was_collected or self.yellow_collected_by_power
        
        if need_dice_roll and not self.is_current_player_ai():
            self.waiting_for_dice_roll = True
            self.roll_dice_btn.setEnabled(True)
            self.play_btn.setEnabled(False)
            self.start_pulse_animation()
            # Restart timer for dice roll
            self.start_turn_timer()
            if yellow_was_collected:
                self.current_player_label.setText("⭐ 3 of a Kind! Wild dot collected - Roll for new position!")
            else:
                self.current_player_label.setText("🎯 Wild dot replaced! Roll the dice!")
            # Update hand before returning
            self.update_hand()
            return
        
        # If AI needs dice roll, auto-roll
        if need_dice_roll and self.is_current_player_ai():
            row, col = self.game.roll_dice()
            result = self.game.place_wild_at_location(row, col)
            defused = result[2] if len(result) > 2 else False
            if defused:
                print(f"AI wild defused landmine at {row}{col}")
                self.update_landmine_display()
            self.update_board()
            # Check for yellow match after AI rolls - keep rolling until no match
            print(f"DEBUG: AI rolled wild to {row}{col}, checking for match...")
            while True:
                yellow_match = self.check_yellow_match(row, col)
                if yellow_match:
                    print(f"DEBUG: AI created yellow match! Rolling again for new wild...")
                    # The yellow was collected in the match, so we need to roll again
                    row, col = self.game.roll_dice()
                    result = self.game.place_wild_at_location(row, col)
                    defused = result[2] if len(result) > 2 else False
                    if defused:
                        print(f"AI wild defused landmine at {row}{col}")
                        self.update_landmine_display()
                    self.update_board()
                    print(f"DEBUG: AI rolled new wild to {row}{col}, checking again...")
                else:
                    # No match found, exit the loop
                    print(f"DEBUG: No match at {row}{col}, continuing with turn...")
                    break
        
        # Check if turn is complete (2 cards played)
        if self.cards_played_this_turn >= 2:
            # Reset turn counters and move to next player
            self.cards_played_this_turn = 0
            self.locations_played_this_turn = []  # Clear locations for next turn
            self.scored_this_turn = False
            self.yellow_collected_by_power = False  # Reset power card yellow flag
            
            try:
                # Draw new cards after turn is complete
                print(f"DEBUG: End of turn - Hand size before draw: {len(hand)}, cards_played_this_turn was: {2}")
                cards_drawn = 0
                while len(hand) < 5 and self.game.deck:
                    self.game.draw_card(player)
                    cards_drawn += 1
                print(f"DEBUG: Drew {cards_drawn} cards. Hand size now: {len(hand)}")
                
                # Check win
                if self.game.check_win():
                    self.show_winner(player)
                    return
                
                # Next player
                self.game.next_player()
                self.update_scores()  # Update to highlight the new current player
                self.update_hand()
                self.update_current_player()
                
                # Stop timer for previous player, start for new player if human
                self.stop_turn_timer()
                if not self.is_current_player_ai():
                    self.start_turn_timer()
                
                if self.is_current_player_ai():
                    self.ai_timer.start(2000)
            except Exception as e:
                print(f"Error in end of turn processing: {e}")
                import traceback
                traceback.print_exc()
        else:
            # Still have cards to play this turn
            self.update_hand()
            self.current_player_label.setText(f"🎮 {player}'s Turn - {2 - self.cards_played_this_turn} card(s) left")
            # Restart timer for remaining cards
            if not self.is_current_player_ai():
                self.start_turn_timer()
            else:
                # AI needs to continue playing
                self.ai_timer.start(2000)
    
    def is_current_player_ai(self) -> bool:
        """Check if current player is AI."""
        player = self.game.get_current_player()
        return player in self.ai_players
    
    def check_yellow_match(self, row: str, col: str) -> bool:
        """Check if yellow dot placement creates a match and collect if so."""
        row_idx = self.game.rows.index(row)
        col_idx = self.game.columns.index(col)
        
        print(f"DEBUG check_yellow_match: Checking yellow at {row}{col} (row_idx={row_idx}, col_idx={col_idx})")
        
        # Check all 4 directions for matches with yellow as wild
        # Format is (dx, dy) where dx is column change, dy is row change
        directions = [
            (1, 0),   # horizontal (right)
            (0, 1),   # vertical (down)
            (1, 1),   # diagonal down-right
            (1, -1)   # diagonal up-right
        ]
        
        for dx, dy in directions:
            print(f"DEBUG: Checking direction dx={dx}, dy={dy}")
            line = []
            colors_in_line = set()
            
            # Check backwards
            x, y = col_idx - dx, row_idx - dy
            while 0 <= x < self.game.grid_size and 0 <= y < self.game.grid_size:
                dot = self.game.grid[y][x]
                if dot:
                    line.append((x, y))
                    colors_in_line.add(dot.color)
                    x -= dx
                    y -= dy
                else:
                    break
            
            line.reverse()
            line.append((col_idx, row_idx))  # Add yellow dot position
            colors_in_line.add('yellow')
            
            # Check forwards
            x, y = col_idx + dx, row_idx + dy
            while 0 <= x < self.game.grid_size and 0 <= y < self.game.grid_size:
                dot = self.game.grid[y][x]
                if dot:
                    line.append((x, y))
                    colors_in_line.add(dot.color)
                    x += dx
                    y += dy
                else:
                    break
            
            # If we found a line of 3 or more, and there's at least one non-yellow color
            non_yellow_colors = colors_in_line - {'yellow'}
            print(f"DEBUG: Line length={len(line)}, colors={colors_in_line}, non_yellow={non_yellow_colors}")
            if len(line) >= 3 and len(non_yellow_colors) == 1:
                # Collect the match
                player = self.game.get_current_player()
                match_color = list(non_yellow_colors)[0]
                print(f"DEBUG: MATCH FOUND! Collecting {len(line)} dots of color {match_color} for {player}")
                self.game.collect_dots(line, player, match_color)
                self.update_board()
                self.update_scores()
                return True
        
        print(f"DEBUG: No match found for yellow at {row}{col}")
        return False
    
    def start_pulse_animation(self):
        """Start pulsing animation on dice button."""
        self.pulse_state = 0
        self.pulse_timer.start(100)
    
    def stop_pulse_animation(self):
        """Stop pulsing animation on dice button."""
        self.pulse_timer.stop()
        self.roll_dice_btn.setStyleSheet(self.roll_dice_base_style)
    
    def pulse_dice_button(self):
        """Animate the dice button with a pulsing effect."""
        self.pulse_state = (self.pulse_state + 1) % 20
        
        # Create pulsing effect by alternating border colors
        if self.pulse_state < 10:
            intensity = self.pulse_state / 10.0
            border_color = f"rgb({int(255 * intensity)}, {int(69 * intensity)}, {int(0 * intensity)})"
        else:
            intensity = (20 - self.pulse_state) / 10.0
            border_color = f"rgb({int(255 * intensity)}, {int(69 * intensity)}, {int(0 * intensity)})"
        
        pulse_style = f"QPushButton {{ background-color: #FFD700; color: #000000; border: 3px solid {border_color}; }} QPushButton:hover {{ background-color: #FFC700; }}"
        self.roll_dice_btn.setStyleSheet(pulse_style)
    
    def start_turn_timer(self):
        """Start the turn timer if enabled."""
        if self.timer_seconds > 0 and not self.is_current_player_ai():
            self.time_remaining = self.timer_seconds
            self.update_timer_display()
            self.turn_timer.start(1000)  # Update every second
    
    def stop_turn_timer(self):
        """Stop the turn timer."""
        if self.turn_timer.isActive():
            self.turn_timer.stop()
    
    def update_timer_display(self):
        """Update the timer display and handle timeout."""
        if self.time_remaining > 0:
            self.time_remaining -= 1
            
            # Color coding based on time remaining
            if self.time_remaining > 10:
                color = "#4CAF50"  # Green
            elif self.time_remaining > 5:
                color = "#FFA726"  # Orange
            else:
                color = "#EF5350"  # Red
            
            self.timer_label.setText(f"⏱️ Time: {self.time_remaining}s")
            self.timer_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        else:
            # Time's up! Handle timeout
            self.stop_turn_timer()
            self.timer_label.setText("⏱️ Time's Up!")
            self.timer_label.setStyleSheet("color: #EF5350; font-weight: bold;")
            
            player = self.game.get_current_player()
            
            # Track consecutive timeouts
            if player not in self.timeout_counts:
                self.timeout_counts[player] = 0
            self.timeout_counts[player] += 1
            
            # Check for forfeit (3 consecutive timeouts)
            if self.timeout_counts[player] >= 3:
                from PyQt6.QtWidgets import QMessageBox
                msg = QMessageBox(self)
                msg.setWindowTitle("Game Forfeited")
                msg.setText(f"{player} has forfeited the game!")
                msg.setInformativeText(f"{player} failed to play within the time limit 3 times in a row.")
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.setStyleSheet("""
                    QMessageBox {
                        background-color: #1a1a2e;
                        color: #ffffff;
                    }
                    QLabel {
                        color: #ffffff;
                    }
                    QPushButton {
                        background-color: #EF5350;
                        color: white;
                        padding: 8px 16px;
                        border-radius: 4px;
                        min-width: 80px;
                    }
                """)
                msg.exec()
                
                # End the game - find another player as winner
                other_players = [p for p in self.game.players.keys() if p != player]
                if other_players:
                    self.show_winner(other_players[0])
                return
            
            # Auto-play 2 non-power cards
            hand = self.game.get_player_hand(player)
            if hand:
                # Filter out power cards, get only regular cards
                regular_card_indices = [i for i, card in enumerate(hand) if not card.is_power_card()]
                
                if len(regular_card_indices) >= 2:
                    # Play first 2 regular cards
                    cards_to_play = regular_card_indices[:2]
                    print(f"DEBUG: {player} timed out! Auto-playing cards at indices {cards_to_play}")
                    
                    # Show timeout warning
                    if not player in self.ai_players:
                        from PyQt6.QtWidgets import QMessageBox
                        warning = QMessageBox(self)
                        warning.setWindowTitle("Timeout Warning")
                        warning.setText(f"Time's up! Auto-playing 2 cards.")
                        warning.setInformativeText(f"Consecutive timeouts: {self.timeout_counts[player]}/3\nOne more timeout will forfeit the game!")
                        warning.setIcon(QMessageBox.Icon.Warning)
                        warning.setStyleSheet("""
                            QMessageBox {
                                background-color: #1a1a2e;
                                color: #ffffff;
                            }
                            QLabel {
                                color: #FFD700;
                            }
                            QPushButton {
                                background-color: #FFA726;
                                color: white;
                                padding: 8px 16px;
                                border-radius: 4px;
                                min-width: 80px;
                            }
                        """)
                        warning.exec()
                    
                    self.execute_turn(cards_to_play)
                elif len(regular_card_indices) == 1:
                    # Only 1 regular card, play it
                    print(f"DEBUG: {player} timed out! Only 1 regular card, auto-playing it")
                    self.execute_turn([regular_card_indices[0]])
                else:
                    # No regular cards, skip turn
                    print(f"DEBUG: {player} timed out but has no regular cards to play")
                    self.game.next_player()
                    self.update_hand()
                    self.update_current_player()
                    self.stop_turn_timer()
                    if not self.is_current_player_ai():
                        self.start_turn_timer()
                    elif self.is_current_player_ai():
                        self.ai_timer.start(2000)
    
    def execute_ai_turn(self):
        """Execute AI player's turn."""
        self.ai_timer.stop()
        
        player = self.game.get_current_player()
        
        if player not in self.ai_players:
            return
        
        try:
            ai = self.ai_players[player]
            hand = self.game.get_player_hand(player)
            
            if not hand or len(hand) < 2:
                print(f"AI {player} doesn't have enough cards. Hand size: {len(hand) if hand else 0}")
                # Draw cards if needed
                while len(hand) < 5 and self.game.deck:
                    self.game.draw_card(player)
                    hand = self.game.get_player_hand(player)
                
                if len(hand) < 2:
                    print(f"AI {player} still doesn't have enough cards after drawing. Skipping turn.")
                    self.game.next_player()
                    self.update_hand()
                    self.update_current_player()
                    if self.is_current_player_ai():
                        self.ai_timer.start(2000)
                    return
            
            card_indices = ai.choose_cards(hand)
            
            if not card_indices or len(card_indices) == 0:
                print(f"AI {player} returned no card indices")
                return
            
            self.execute_turn(card_indices)
        except Exception as e:
            print(f"Error executing AI turn for {player}: {e}")
            import traceback
            traceback.print_exc()
            # Try to recover by moving to next player
            self.game.next_player()
            self.update_hand()
            self.update_current_player()
            if self.is_current_player_ai():
                self.ai_timer.start(2000)
    
    def update_current_player(self):
        """Update the current player label."""
        player = self.game.get_current_player()
        # Reset turn tracking variables for new turn
        self.cards_played_this_turn = 0
        self.locations_played_this_turn = []
        self.scored_this_turn = False
        print(f"DEBUG: New turn started for {player}, locations_played reset to: {self.locations_played_this_turn}")
        self.current_player_label.setText(f"🎮 {player}'s Turn")
        self.current_player_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")
    
    def show_winner(self, player):
        """Show the winner."""
        self.play_btn.setEnabled(False)
        self.ai_timer.stop()
        self.stop_turn_timer()
        
        # Update player stats
        for player_name in self.game.players.keys():
            if player_name == player:
                self.player_stats[player_name]['wins'] += 1
            else:
                self.player_stats[player_name]['losses'] += 1
        
        # Update the display to show new records
        self.update_scores()
        
        if player in self.ai_players:
            trophy = "🤖"
        else:
            trophy = "🏆"
        
        self.current_player_label.setText(f"{trophy} {player} WINS! {trophy}")
        self.current_player_label.setStyleSheet("color: #FFD700; font-weight: bold; font-size: 18px;")
        
        # Add Play Again and Exit buttons
        from PyQt6.QtWidgets import QMessageBox, QPushButton
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Game Over")
        msg_box.setText(f"{trophy} {player} WINS! {trophy}")
        msg_box.setInformativeText("What would you like to do?")
        msg_box.setStyleSheet("QMessageBox { background-color: #0f0f1e; color: #ffffff; } QPushButton { background-color: #4CAF50; color: white; padding: 10px 20px; border-radius: 5px; font-weight: bold; } QPushButton:hover { background-color: #45a049; }")
        
        play_again_btn = msg_box.addButton("Play Again", QMessageBox.ButtonRole.AcceptRole)
        exit_btn = msg_box.addButton("Exit to Menu", QMessageBox.ButtonRole.RejectRole)
        
        msg_box.exec()
        
        if msg_box.clickedButton() == play_again_btn:
            # Start a new game with same settings
            self.start_game(self.game.num_players, self.game.difficulty, 
                          {name: self.ai_players[name].difficulty for name in self.ai_players})
        else:
            # Return to setup dialog
            self.close()
            self.__init__()
            self.show()


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    window = TwentyDotsGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
