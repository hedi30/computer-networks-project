#!/usr/bin/env python3
"""
UDP Quiz Server
Demonstrates connectionless communication using UDP protocol
"""

import socket
import json
import threading
import time
from collections import defaultdict
from datetime import datetime
import random
import os

# Server configuration
HOST = '0.0.0.0'  # Listen on all interfaces
PORT = 8888
BUFFER_SIZE = 4096
QUESTION_TIME_LIMIT = 10  # seconds per question
REBROADCAST_INTERVAL = float(os.getenv('UDP_REBROADCAST_EVERY', '2.0'))  # seconds
# Heartbeat to illustrate connectionless nature (no state, periodic broadcast)
HEARTBEAT_INTERVAL = float(os.getenv('UDP_HEARTBEAT_EVERY', '2.0'))

class UDPQuizServer:
    def __init__(self):
        """Initialize UDP quiz server state and underlying socket."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((HOST, PORT))
        self.sock.settimeout(1.0)  # For graceful shutdown polling

        # Load and shuffle questions
        self.questions = self.load_questions()
        random.shuffle(self.questions)

        # Core game / client state
        self.clients = {}  # {address: {'name': str, 'score': int, 'answers': [], 'answer_times': []}}
        self.active_game = False
        self.current_question_index = 0
        self.question_start_time = None
        self.game_lock = threading.Lock()

        # Sequencing + rebroadcast support (UDP demo features)
        self.seq = 0  # monotonically increasing sequence number
        self._last_rebroadcast = 0.0  # seconds since question start at last rebroadcast
        self._last_heartbeat = 0.0

        print(f"UDP Quiz Server started on {HOST}:{PORT}")
        print(f"Loaded {len(self.questions)} questions")
    
    def load_questions(self):
        """Load questions from questions.txt"""
        import os
        questions = []
        try:
            # Look for questions.txt in parent directory
            questions_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'questions.txt')
            with open(questions_path, 'r') as f:
                content = f.read()
            
            question_blocks = content.strip().split('\n\n')
            for block in question_blocks:
                if not block.strip():
                    continue
                
                lines = block.strip().split('\n')
                question = lines[0]
                options = []
                answer = None
                
                for line in lines[1:]:
                    if line.startswith('ANSWER:'):
                        answer = line.split('ANSWER:')[1].strip()
                    elif line.strip():
                        options.append(line.strip())
                
                if question and options and answer:
                    questions.append({
                        'question': question,
                        'options': options,
                        'answer': answer
                    })
        except FileNotFoundError:
            print("Error: questions.txt not found!")
            return []
        
        return questions
    
    def _next_seq(self):
        self.seq += 1
        return self.seq

    def send_message(self, address, message_type, data):
        """Send a message to a client with sequence number"""
        message = {
            'type': message_type,
            'data': data,
            'timestamp': time.time(),
            'seq': self._next_seq()
        }
        try:
            payload = json.dumps(message).encode('utf-8')
            self.sock.sendto(payload, address)
        except Exception as e:
            print(f"Error sending to {address}: {e}")
    
    def broadcast_message(self, message_type, data, exclude_address=None):
        """Broadcast message to all clients"""
        for address in list(self.clients.keys()):
            if address != exclude_address:
                self.send_message(address, message_type, data)
    
    def handle_client_register(self, address, data):
        """Handle client registration"""
        with self.game_lock:
            if self.active_game:
                self.send_message(address, 'error', {'message': 'Game already in progress'})
                return
            
            player_name = data.get('name', f'Player_{address[1]}')
            self.clients[address] = {
                'name': player_name,
                'score': 0,
                'answers': [],
                'answer_times': []
            }
            print(f"Player {player_name} ({address}) registered")
            self.send_message(address, 'registered', {
                'message': f'Welcome {player_name}!',
                'player_count': len(self.clients)
            })
    
    def handle_client_answer(self, address, data):
        """Handle client answer submission"""
        with self.game_lock:
            if address not in self.clients:
                return
            
            if not self.active_game or self.current_question_index >= len(self.questions):
                return
            
            # Check if already answered this question
            client = self.clients[address]
            if len(client['answers']) > self.current_question_index:
                return  # Already answered
            
            answer = data.get('answer', '').upper().strip()
            question = self.questions[self.current_question_index]
            correct_answer = question['answer'].strip()
            
            is_correct = (answer == correct_answer)
            time_taken = time.time() - self.question_start_time
            
            client['answers'].append(answer)
            client['answer_times'].append(time_taken)
            
            if is_correct:
                # Points based on speed (30 seconds max)
                points = max(1, int((QUESTION_TIME_LIMIT - time_taken) / 5) + 1)
                client['score'] += points
            else:
                points = 0
            
            self.send_message(address, 'answer_result', {
                'correct': is_correct,
                'correct_answer': correct_answer,
                'points': points,
                'total_score': client['score'],
                'time_taken': round(time_taken, 2)
            })
    
    def start_game(self):
        """Start the quiz game"""
        with self.game_lock:
            if len(self.clients) == 0:
                print("No clients registered")
                return
            
            if self.active_game:
                return
            
            self.active_game = True
            self.current_question_index = 0
            
            # Reset all client scores
            for client in self.clients.values():
                client['score'] = 0
                client['answers'] = []
                client['answer_times'] = []
            
            print(f"Game started with {len(self.clients)} players")
            self.broadcast_message('game_start', {
                'message': 'Game starting!',
                'total_questions': len(self.questions)
            })
            
            # Start sending questions
            threading.Thread(target=self.game_loop, daemon=True).start()
    
    def game_loop(self):
        """Main game loop - send questions sequentially"""
        for i, question in enumerate(self.questions):
            if not self.active_game:
                break
            
            with self.game_lock:
                self.current_question_index = i
                self.question_start_time = time.time()
            
            # Send question to all clients
            question_data = {
                'question_number': i + 1,
                'total_questions': len(self.questions),
                'question': question['question'],
                'options': question['options'],
                'time_limit': QUESTION_TIME_LIMIT
            }
            self.broadcast_message('question', question_data)
            
            # Active question window with periodic rebroadcast to mitigate loss/late joins
            start = time.time()
            self._last_rebroadcast = 0.0
            while True:
                elapsed = time.time() - start
                if elapsed >= QUESTION_TIME_LIMIT:
                    break
                # Periodic rebroadcast
                if elapsed - self._last_rebroadcast >= REBROADCAST_INTERVAL:
                    print(f"[REBROADCAST] question {i+1}")
                    self.broadcast_message('question', question_data)
                    self._last_rebroadcast = elapsed
                time.sleep(0.2)
            
            # Send correct answer if game still active
            with self.game_lock:
                if self.active_game:
                    self.broadcast_message('question_end', {
                        'correct_answer': question['answer'],
                        'question_number': i + 1
                    })
            
            # Brief pause between questions
            if i < len(self.questions) - 1:
                time.sleep(2)
        
        # Game ended - send final leaderboard
        self.end_game()
    
    def end_game(self):
        """End the game and send final leaderboard"""
        with self.game_lock:
            self.active_game = False
            
            # Calculate leaderboard
            leaderboard = []
            for address, client in self.clients.items():
                leaderboard.append({
                    'name': client['name'],
                    'score': client['score'],
                    'address': f"{address[0]}:{address[1]}"
                })
            
            leaderboard.sort(key=lambda x: x['score'], reverse=True)
            
            print("\n=== Final Leaderboard ===")
            for i, entry in enumerate(leaderboard, 1):
                print(f"{i}. {entry['name']}: {entry['score']} points")
            print("========================\n")
            
            self.broadcast_message('game_end', {
                'leaderboard': leaderboard,
                'message': 'Game finished!'
            })
            
            # Reset for next game
            self.current_question_index = 0
    
    def handle_request_start_game(self, address):
        """Handle request to start game"""
        with self.game_lock:
            if address not in self.clients:
                self.send_message(address, 'error', {'message': 'Not registered'})
                return
            
            # Start game if not already active
            if not self.active_game and len(self.clients) > 0:
                threading.Thread(target=self.start_game, daemon=True).start()
            else:
                self.send_message(address, 'error', {'message': 'Cannot start game now'})
    
    def run(self):
        """Main server loop"""
        print("Server waiting for clients...")
        print("Clients on the same network can connect using this machine's IP address")
        
        try:
            while True:
                # Periodic heartbeat broadcast (even if no incoming data)
                now = time.time()
                if now - self._last_heartbeat >= HEARTBEAT_INTERVAL and self.clients:
                    self.broadcast_message('heartbeat', {'note': 'server heartbeat'})
                    self._last_heartbeat = now
                try:
                    data, address = self.sock.recvfrom(BUFFER_SIZE)
                    
                    try:
                        message = json.loads(data.decode('utf-8'))
                        msg_type = message.get('type')
                        msg_data = message.get('data', {})
                        
                        if msg_type == 'register':
                            self.handle_client_register(address, msg_data)
                        elif msg_type == 'answer':
                            self.handle_client_answer(address, msg_data)
                        elif msg_type == 'start_game':
                            self.handle_request_start_game(address)
                        elif msg_type == 'get_status':
                            self.send_message(address, 'status', {
                                'active_game': self.active_game,
                                'player_count': len(self.clients),
                                'current_question': self.current_question_index
                            })
                        else:
                            self.send_message(address, 'error', {'message': 'Unknown message type'})
                    
                    except json.JSONDecodeError:
                        self.send_message(address, 'error', {'message': 'Invalid JSON'})
                    except Exception as e:
                        print(f"Error handling message from {address}: {e}")
                        self.send_message(address, 'error', {'message': str(e)})
                
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"Server error: {e}")
                    break
        
        except KeyboardInterrupt:
            print("\nShutting down server...")
        finally:
            self.sock.close()

if __name__ == '__main__':
    server = UDPQuizServer()
    server.run()

