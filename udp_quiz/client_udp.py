#!/usr/bin/env python3
"""
UDP Quiz Client
Demonstrates connectionless communication using UDP protocol
"""

import socket
import json
import threading
import time
import sys

BUFFER_SIZE = 4096

class UDPQuizClient:
    def __init__(self, server_host, server_port, player_name):
        self.server_address = (server_host, server_port)
        self.player_name = player_name
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(1.0)
        
        self.registered = False
        self.game_active = False
        self.current_question = None
        self.question_start_time = None
        self.running = True
        
    def send_message(self, message_type, data):
        """Send a message to the server"""
        message = {
            'type': message_type,
            'data': data
        }
        try:
            self.sock.sendto(json.dumps(message).encode('utf-8'), self.server_address)
        except Exception as e:
            print(f"Error sending message: {e}")
    
    def receive_messages(self):
        """Receive and handle messages from server"""
        while self.running:
            try:
                data, address = self.sock.recvfrom(BUFFER_SIZE)
                
                if address != self.server_address:
                    continue  # Ignore messages from other addresses
                
                try:
                    message = json.loads(data.decode('utf-8'))
                    self.handle_message(message)
                except json.JSONDecodeError:
                    print("Received invalid JSON message")
                except Exception as e:
                    print(f"Error handling message: {e}")
            
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Receive error: {e}")
    
    def handle_message(self, message):
        """Handle incoming messages from server"""
        msg_type = message.get('type')
        msg_data = message.get('data', {})
        
        if msg_type == 'registered':
            self.registered = True
            print(f"\n✓ {msg_data.get('message')}")
            print(f"Players connected: {msg_data.get('player_count')}")
            print("\nType 'start' to begin the game when all players are ready!")
        
        elif msg_type == 'game_start':
            self.game_active = True
            print(f"\n{'='*50}")
            print(f"🎮 GAME STARTING!")
            print(f"Total questions: {msg_data.get('total_questions')}")
            print(f"{'='*50}\n")
        
        elif msg_type == 'question':
            self.current_question = msg_data
            self.question_start_time = time.time()
            
            print(f"\n{'='*50}")
            print(f"Question {msg_data['question_number']}/{msg_data['total_questions']}")
            print(f"{'='*50}")
            print(f"{msg_data['question']}")
            print()
            
            for option in msg_data['options']:
                print(f"  {option}")
            
            time_left = msg_data.get('time_limit', 30)
            print(f"\n⏱ Time limit: {time_left} seconds")
            print("Enter your answer (A, B, C, or D): ", end='', flush=True)
        
        elif msg_type == 'answer_result':
            correct = msg_data.get('correct', False)
            points = msg_data.get('points', 0)
            total_score = msg_data.get('total_score', 0)
            time_taken = msg_data.get('time_taken', 0)
            
            print()  # New line after answer input
            if correct:
                print(f"✓ Correct! You earned {points} points ({time_taken:.1f}s)")
            else:
                correct_answer = msg_data.get('correct_answer', '')
                print(f"✗ Incorrect. Correct answer was {correct_answer}")
            print(f"Your total score: {total_score} points\n")
        
        elif msg_type == 'question_end':
            # Question time ended
            if self.current_question:
                print(f"\n⏱ Time's up! Correct answer: {msg_data.get('correct_answer')}")
                print(f"You didn't answer in time.\n")
        
        elif msg_type == 'game_end':
            leaderboard = msg_data.get('leaderboard', [])
            print(f"\n{'='*50}")
            print("🏆 FINAL LEADERBOARD 🏆")
            print(f"{'='*50}")
            for i, entry in enumerate(leaderboard, 1):
                medal = ""
                if i == 1:
                    medal = "🥇"
                elif i == 2:
                    medal = "🥈"
                elif i == 3:
                    medal = "🥉"
                
                print(f"{medal} {i}. {entry['name']}: {entry['score']} points")
            print(f"{'='*50}\n")
            
            self.game_active = False
            self.current_question = None
            print("Game finished! You can start a new game by typing 'start'")
        
        elif msg_type == 'error':
            print(f"\n❌ Error: {msg_data.get('message')}\n")
        
        elif msg_type == 'status':
            print(f"\nStatus: Active game={msg_data.get('active_game')}, "
                  f"Players={msg_data.get('player_count')}\n")
    
    def submit_answer(self, answer):
        """Submit an answer to the current question"""
        if not self.game_active or not self.current_question:
            print("No active question!")
            return
        
        # Check if time limit exceeded
        if self.question_start_time:
            elapsed = time.time() - self.question_start_time
            time_limit = self.current_question.get('time_limit', 30)
            if elapsed > time_limit:
                print("Time limit exceeded!")
                return
        
        self.send_message('answer', {'answer': answer.upper().strip()})
        self.current_question = None  # Clear to prevent double answering
    
    def start(self):
        """Start the client"""
        print(f"Connecting to server at {self.server_address[0]}:{self.server_address[1]}...")
        
        # Register with server
        self.send_message('register', {'name': self.player_name})
        
        # Start receiver thread
        receiver_thread = threading.Thread(target=self.receive_messages, daemon=True)
        receiver_thread.start()
        
        # Wait for registration
        time.sleep(0.5)
        if not self.registered:
            print("Failed to register with server. Make sure the server is running.")
            return
        
        # Main input loop
        print("\n" + "="*50)
        print("UDP Quiz Game Client")
        print("="*50)
        print("Commands:")
        print("  start  - Start the game (when all players ready)")
        print("  status - Check game status")
        print("  quit   - Exit the client")
        print("="*50 + "\n")
        
        try:
            while self.running:
                try:
                    user_input = input().strip().lower()
                    
                    if user_input == 'quit':
                        break
                    elif user_input == 'start':
                        if self.registered:
                            self.send_message('start_game', {})
                        else:
                            print("Not registered with server!")
                    elif user_input == 'status':
                        self.send_message('get_status', {})
                    elif user_input and user_input.upper() in ['A', 'B', 'C', 'D']:
                        if self.game_active:
                            self.submit_answer(user_input)
                        else:
                            print("No active game! Type 'start' to begin.")
                    elif user_input:
                        print("Invalid command or answer. Enter A, B, C, or D for answers.")
                
                except EOFError:
                    break
                except KeyboardInterrupt:
                    break
        
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
            self.sock.close()
            print("\nDisconnected from server.")

def main():
    if len(sys.argv) < 2:
        print("Usage: python client_udp.py <server_ip> [player_name]")
        print("Example: python client_udp.py 192.168.1.100 Player1")
        sys.exit(1)
    
    server_host = sys.argv[1]
    server_port = 8888
    player_name = sys.argv[2] if len(sys.argv) > 2 else f"Player_{time.time()}"
    
    client = UDPQuizClient(server_host, server_port, player_name)
    client.start()

if __name__ == '__main__':
    main()

