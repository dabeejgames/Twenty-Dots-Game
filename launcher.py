"""
Twenty Dots - Game Launcher
Choose to play local game, host a networked game, or join a networked game
"""
import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                             QListWidget, QMessageBox, QDialog, QSpinBox,
                             QComboBox, QGroupBox)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from network_client import NetworkClient
import subprocess

class GameLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Twenty Dots - Game Launcher")
        self.setGeometry(100, 100, 600, 500)
        self.setStyleSheet("background-color: #1a1a2e;")
        
        self.network_client = None
        self.is_host = False
        
        self.init_ui()
    
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # Title
        title = QLabel("Twenty Dots")
        title.setFont(QFont('Arial', 36, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffd700;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        subtitle = QLabel("Choose Game Mode")
        subtitle.setFont(QFont('Arial', 16))
        subtitle.setStyleSheet("color: #ffffff;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        
        layout.addSpacing(30)
        
        # Buttons
        btn_style = """
            QPushButton {
                background-color: #6c5ce7;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 20px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5f4dd1;
            }
            QPushButton:pressed {
                background-color: #4d3db8;
            }
        """
        
        # Local game button
        self.local_btn = QPushButton("🎮 Play Local Game")
        self.local_btn.setStyleSheet(btn_style)
        self.local_btn.clicked.connect(self.start_local_game)
        layout.addWidget(self.local_btn)
        
        # Host game button
        self.host_btn = QPushButton("🌐 Host Network Game")
        self.host_btn.setStyleSheet(btn_style)
        self.host_btn.clicked.connect(self.show_host_dialog)
        layout.addWidget(self.host_btn)
        
        # Join game button
        self.join_btn = QPushButton("🔗 Join Network Game")
        self.join_btn.setStyleSheet(btn_style)
        self.join_btn.clicked.connect(self.show_join_dialog)
        layout.addWidget(self.join_btn)
        
        layout.addStretch()
        
        # Instructions
        instructions = QLabel("Local: Play on this device with AI players\n"
                            "Host: Create a game that others can join\n"
                            "Join: Connect to someone else's game")
        instructions.setFont(QFont('Arial', 11))
        instructions.setStyleSheet("color: #a0a0a0;")
        instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(instructions)
        
        central_widget.setLayout(layout)
    
    def start_local_game(self):
        """Launch local game with AI players"""
        from gui_game import TwentyDotsGUI
        self.game_window = TwentyDotsGUI()
        self.game_window.show()
        self.close()
    
    def show_host_dialog(self):
        """Show dialog to configure and host a game"""
        dialog = HostGameDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            game_id, player_name, num_ai = dialog.get_values()
            self.host_network_game(game_id, player_name, num_ai)
    
    def show_join_dialog(self):
        """Show dialog to join a game"""
        dialog = JoinGameDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            server_ip, game_id, player_name = dialog.get_values()
            self.join_network_game(server_ip, game_id, player_name)
    
    def host_network_game(self, game_id, player_name, num_ai):
        """Host a network game"""
        # Start the server in a subprocess
        try:
            # Get the directory where this script is located
            script_dir = os.path.dirname(os.path.abspath(__file__))
            server_path = os.path.join(script_dir, "game_server.py")
            
            self.server_process = subprocess.Popen(
                [sys.executable, server_path],
                cwd=script_dir,
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
            )
            print("Game server started")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start server: {str(e)}")
            return
        
        # Give server time to start
        QTimer.singleShot(4000, lambda: self._connect_as_host(game_id, player_name, num_ai))
    
    def _connect_as_host(self, game_id, player_name, num_ai):
        """Connect to the server as host"""
        self.is_host = True
        self.network_client = NetworkClient('http://localhost:5000')
        
        # Connect signals
        self.network_client.connected.connect(lambda: self._on_connected_as_host(game_id, player_name, num_ai))
        self.network_client.error_occurred.connect(self.show_error)
        self.network_client.game_created.connect(self.show_lobby)
        
        try:
            if not self.network_client.connect_to_server():
                QMessageBox.critical(self, "Error", "Failed to connect to server. Please wait a few seconds and try again.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection error: {str(e)}\n\nThe server is starting. Please wait a few seconds and try clicking 'Host Network Game' again.")
    
    def _on_connected_as_host(self, game_id, player_name, num_ai):
        """Called when connected as host"""
        self.network_client.create_game(game_id, player_name)
        self.num_ai_to_add = num_ai
    
    def join_network_game(self, server_ip, game_id, player_name):
        """Join an existing network game"""
        self.is_host = False
        server_url = f'http://{server_ip}:5000'
        self.network_client = NetworkClient(server_url)
        
        # Connect signals
        self.network_client.connected.connect(lambda: self._request_game_list(game_id, player_name))
        self.network_client.error_occurred.connect(self.show_error)
        self.network_client.game_joined.connect(self.show_lobby)
        
        if not self.network_client.connect_to_server():
            QMessageBox.critical(self, "Error", f"Failed to connect to {server_url}")
    
    def _request_game_list(self, game_id, player_name):
        """Join the specified game"""
        self.network_client.join_game(game_id, player_name)
    
    def show_lobby(self, data):
        """Show the game lobby while waiting for players"""
        lobby = GameLobby(self, self.network_client, data, self.is_host, 
                         getattr(self, 'num_ai_to_add', 0))
        lobby.show()
        self.hide()
    
    def show_error(self, message):
        """Show error message"""
        QMessageBox.critical(self, "Error", message)


class HostGameDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Host Network Game")
        self.setModal(True)
        self.setStyleSheet("background-color: #1a1a2e; color: white;")
        
        layout = QVBoxLayout()
        
        # Game ID
        layout.addWidget(QLabel("Game ID:"))
        self.game_id_input = QLineEdit()
        self.game_id_input.setText("game_001")
        self.game_id_input.setStyleSheet("padding: 8px; background: #2d2d44; border: 1px solid #6c5ce7;")
        layout.addWidget(self.game_id_input)
        
        # Player name
        layout.addWidget(QLabel("Your Name:"))
        self.name_input = QLineEdit()
        self.name_input.setText("Player 1")
        self.name_input.setStyleSheet("padding: 8px; background: #2d2d44; border: 1px solid #6c5ce7;")
        layout.addWidget(self.name_input)
        
        # Number of AI players
        layout.addWidget(QLabel("Number of AI Players (0-3):"))
        self.ai_spin = QSpinBox()
        self.ai_spin.setRange(0, 3)
        self.ai_spin.setValue(2)
        self.ai_spin.setStyleSheet("padding: 8px; background: #2d2d44; border: 1px solid #6c5ce7;")
        layout.addWidget(self.ai_spin)
        
        # Buttons
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("Create Game")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setStyleSheet("background: #6c5ce7; padding: 10px; border-radius: 5px;")
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("background: #e74c3c; padding: 10px; border-radius: 5px;")
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def get_values(self):
        return (self.game_id_input.text(), 
                self.name_input.text(), 
                self.ai_spin.value())


class JoinGameDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Join Network Game")
        self.setModal(True)
        self.setStyleSheet("background-color: #1a1a2e; color: white;")
        
        layout = QVBoxLayout()
        
        # Server IP
        layout.addWidget(QLabel("Server IP Address:"))
        self.server_input = QLineEdit()
        self.server_input.setText("localhost")
        self.server_input.setPlaceholderText("e.g., 192.168.1.100 or localhost")
        self.server_input.setStyleSheet("padding: 8px; background: #2d2d44; border: 1px solid #6c5ce7;")
        layout.addWidget(self.server_input)
        
        # Game ID
        layout.addWidget(QLabel("Game ID:"))
        self.game_id_input = QLineEdit()
        self.game_id_input.setText("game_001")
        self.game_id_input.setStyleSheet("padding: 8px; background: #2d2d44; border: 1px solid #6c5ce7;")
        layout.addWidget(self.game_id_input)
        
        # Player name
        layout.addWidget(QLabel("Your Name:"))
        self.name_input = QLineEdit()
        self.name_input.setText("Player 2")
        self.name_input.setStyleSheet("padding: 8px; background: #2d2d44; border: 1px solid #6c5ce7;")
        layout.addWidget(self.name_input)
        
        # Buttons
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("Join Game")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setStyleSheet("background: #6c5ce7; padding: 10px; border-radius: 5px;")
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("background: #e74c3c; padding: 10px; border-radius: 5px;")
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def get_values(self):
        return (self.server_input.text(),
                self.game_id_input.text(), 
                self.name_input.text())


class GameLobby(QMainWindow):
    def __init__(self, parent, network_client, game_data, is_host, num_ai):
        super().__init__(parent)
        self.network_client = network_client
        self.game_data = game_data
        self.is_host = is_host
        self.num_ai = num_ai
        
        self.setWindowTitle(f"Game Lobby - {game_data.get('game_id', 'Unknown')}")
        self.setGeometry(150, 150, 500, 400)
        self.setStyleSheet("background-color: #1a1a2e;")
        
        # Connect signals
        self.network_client.player_joined.connect(self.on_player_joined)
        self.network_client.game_started.connect(self.on_game_started)
        
        self.init_ui()
        
        # Add AI players if host
        if self.is_host and self.num_ai > 0:
            QTimer.singleShot(500, self.add_ai_players)
    
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Title
        title = QLabel(f"Game: {self.game_data.get('game_id', 'Unknown')}")
        title.setFont(QFont('Arial', 24, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffd700;")
        layout.addWidget(title)
        
        # Show IP address for host
        if self.is_host:
            import socket
            try:
                # Get local IP address
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
            except:
                local_ip = "Unable to detect"
            
            ip_info = QGroupBox("Connection Info")
            ip_info.setStyleSheet("""
                QGroupBox {
                    background: #2d2d44;
                    color: #4CAF50;
                    border: 2px solid #4CAF50;
                    border-radius: 5px;
                    padding: 15px;
                    margin-top: 10px;
                    font-weight: bold;
                }
                QGroupBox::title {
                    color: #4CAF50;
                }
            """)
            ip_layout = QVBoxLayout()
            
            ip_label = QLabel(f"Share this IP with other players:\n{local_ip}")
            ip_label.setFont(QFont('Arial', 14, QFont.Weight.Bold))
            ip_label.setStyleSheet("color: #4CAF50; padding: 5px;")
            ip_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ip_layout.addWidget(ip_label)
            
            game_id_label = QLabel(f"Game ID: {self.game_data.get('game_id', 'Unknown')}")
            game_id_label.setFont(QFont('Arial', 12))
            game_id_label.setStyleSheet("color: white; padding: 5px;")
            game_id_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ip_layout.addWidget(game_id_label)
            
            ip_info.setLayout(ip_layout)
            layout.addWidget(ip_info)
        
        # Players list
        players_label = QLabel("Players:")
        players_label.setFont(QFont('Arial', 16))
        players_label.setStyleSheet("color: white;")
        layout.addWidget(players_label)
        
        self.players_list = QListWidget()
        self.players_list.setStyleSheet("""
            QListWidget {
                background: #2d2d44;
                color: white;
                border: 2px solid #6c5ce7;
                border-radius: 5px;
                padding: 10px;
                font-size: 14px;
            }
        """)
        layout.addWidget(self.players_list)
        
        # Update players list
        self.update_players_list()
        
        # Start button (host only)
        if self.is_host:
            self.start_btn = QPushButton("Start Game")
            self.start_btn.setStyleSheet("""
                QPushButton {
                    background: #27ae60;
                    color: white;
                    padding: 15px;
                    font-size: 16px;
                    font-weight: bold;
                    border-radius: 5px;
                }
                QPushButton:hover { background: #229954; }
            """)
            self.start_btn.clicked.connect(self.start_game)
            layout.addWidget(self.start_btn)
        else:
            waiting_label = QLabel("Waiting for host to start game...")
            waiting_label.setStyleSheet("color: #a0a0a0; font-style: italic;")
            waiting_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(waiting_label)
        
        central_widget.setLayout(layout)
    
    def update_players_list(self):
        """Update the players list display"""
        self.players_list.clear()
        players = self.game_data.get('players', [])
        for player in players:
            self.players_list.addItem(f"👤 {player}")
    
    def add_ai_players(self):
        """Add AI players to the game"""
        for i in range(self.num_ai):
            ai_name = f"AI Player {i+1}"
            self.network_client.add_ai_player(ai_name, 'medium')
    
    def on_player_joined(self, data):
        """Handle when a new player joins"""
        self.game_data['players'] = data.get('players', [])
        self.update_players_list()
    
    def start_game(self):
        """Start the game (host only)"""
        if len(self.game_data.get('players', [])) < 2:
            QMessageBox.warning(self, "Not Enough Players", 
                              "Need at least 2 players to start!")
            return
        
        self.network_client.start_game()
    
    def on_game_started(self, game_state):
        """Handle when game starts"""
        from gui_game_network import TwentyDotsNetworkGUI
        self.game_window = TwentyDotsNetworkGUI(self.network_client, game_state)
        self.game_window.show()
        self.close()
        self.parent().close()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    launcher = GameLauncher()
    launcher.show()
    sys.exit(app.exec())
