#!/usr/bin/env python3
"""
TCP Quiz Server
Demonstrates connection-oriented communication using TCP protocol
"""

import socket
import json
import threading
import time
from collections import defaultdict
from datetime import datetime
import random

# Server configuration
HOST = '0.0.0.0'  # Listen on all interfaces
PORT = 8889
BUFFER_SIZE = 4096
QUESTION_TIME_LIMIT = 10  # seconds per question (reduced from 30)

class TCPQuizServer:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((HOST, PORT))
        self.sock.listen(10)  # Allow up to 10 pending connections
        
        # Load questions
        self.questions = self.load_questions()
        random.shuffle(self.questions)
        
        # Client management (connection_id -> client data)
        self.clients = {}  # {connection_id: {'conn': socket, 'addr': tuple, 'name': str, 'score': int}}
        self.connection_counter = 0
        self.active_game = False
        self.current_question_index = 0
        self.question_start_time = None
        self.game_lock = threading.Lock()
        self.host_conn_id = None  # connection id of the host (first client)
        
        print(f"TCP Quiz Server started on {HOST}:{PORT}")
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
    
    def send_message(self, conn, message_type, data):
        """Send a message to a client connection"""
        message = {
            'type': message_type,
            'data': data,
            'timestamp': time.time()
        }
        try:
            conn.sendall(json.dumps(message).encode('utf-8') + b'\n')
        except Exception as e:
            print(f"Error sending message: {e}")
    
    def broadcast_message(self, message_type, data, exclude_conn_id=None):
        """Broadcast message to all connected clients"""
        disconnected = []
        for conn_id, client in list(self.clients.items()):
            if conn_id != exclude_conn_id:
                try:
                    self.send_message(client['conn'], message_type, data)
                except Exception as e:
                    print(f"Error broadcasting to {client['name']}: {e}")
                    disconnected.append(conn_id)
        
        # Remove disconnected clients
        for conn_id in disconnected:
            self.remove_client(conn_id)
    
    def remove_client(self, conn_id):
        """Remove a client from the game"""
        if conn_id in self.clients:
            client = self.clients[conn_id]
            print(f"Player {client['name']} disconnected")
            try:
                client['conn'].close()
            except:
                pass
            del self.clients[conn_id]
            # Reassign host if needed
            if self.host_conn_id == conn_id:
                if self.clients:
                    new_host_id = sorted(self.clients.keys())[0]
                    self.host_conn_id = new_host_id
                    new_host = self.clients[new_host_id]
                    # Notify all clients about new host
                    self.broadcast_message('host_update', {
                        'host_name': new_host.get('name')
                    })
                else:
                    self.host_conn_id = None
    
    def handle_client_register(self, conn_id, conn, data):
        """Handle client registration"""
        with self.game_lock:
            if self.active_game:
                self.send_message(conn, 'error', {'message': 'Game already in progress'})
                return
            
            player_name = data.get('name', f'Player_{conn_id}')
            self.clients[conn_id]['name'] = player_name
            self.clients[conn_id]['score'] = 0
            self.clients[conn_id]['answers'] = []
            self.clients[conn_id]['answer_times'] = []
            
            print(f"Player {player_name} ({self.clients[conn_id]['addr']}) registered")
            self.send_message(conn, 'registered', {
                'message': f'Welcome {player_name}!',
                'player_count': len(self.clients),
                'is_host': (conn_id == self.host_conn_id)
            })
            
            # Notify other clients
            self.broadcast_message('player_joined', {
                'player_name': player_name,
                'total_players': len(self.clients)
            }, exclude_conn_id=conn_id)
    
    def handle_client_answer(self, conn_id, conn, data):
        """Handle client answer submission"""
        with self.game_lock:
            if conn_id not in self.clients:
                print(f"[DEBUG] Client {conn_id} not found")
                return
            
            if not self.active_game or self.current_question_index >= len(self.questions):
                print(f"[DEBUG] Game not active or question index out of bounds")
                return
            
            # Check if already answered this question
            client = self.clients[conn_id]
            if len(client['answers']) > self.current_question_index:
                print(f"[DEBUG] Client {client['name']} already answered question {self.current_question_index}")
                return  # Already answered
            
            answer = data.get('answer', '').upper().strip()
            question = self.questions[self.current_question_index]
            correct_answer = question['answer'].strip()
            
            print(f"[DEBUG] Client {client['name']} answered '{answer}' for question {self.current_question_index}, correct: {correct_answer}")
            
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
            
            print(f"[DEBUG] Sending answer_result to {client['name']}: correct={is_correct}, points={points}")
            self.send_message(conn, 'answer_result', {
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
                print("No clients connected")
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
            
            # Wait for time limit
            time.sleep(QUESTION_TIME_LIMIT)
            
            # Send correct answer if game still active
            with self.game_lock:
                if self.active_game:
                    self.broadcast_message('question_end', {
                        'correct_answer': question['answer'],
                        'question_number': i + 1
                    })
                    # After each question, send a mid-game leaderboard update
                    leaderboard = []
                    for _cid, _client in self.clients.items():
                        leaderboard.append({'name': _client['name'], 'score': _client['score']})
                    leaderboard.sort(key=lambda x: x['score'], reverse=True)
                    self.broadcast_message('leaderboard', {
                        'leaderboard': leaderboard,
                        'round': i + 1,
                        'total_rounds': len(self.questions)
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
            for conn_id, client in self.clients.items():
                leaderboard.append({
                    'name': client['name'],
                    'score': client['score']
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
    
    def handle_request_start_game(self, conn_id, conn):
        """Handle request to start game"""
        with self.game_lock:
            # Only host can start the game
            if self.host_conn_id is None or conn_id != self.host_conn_id:
                self.send_message(conn, 'error', {'message': 'Only the host can start the game'})
                return
            if conn_id not in self.clients:
                self.send_message(conn, 'error', {'message': 'Not registered'})
                return
            
            # Start game if not already active
            if not self.active_game and len(self.clients) > 0:
                threading.Thread(target=self.start_game, daemon=True).start()
            else:
                self.send_message(conn, 'error', {'message': 'Cannot start game now'})
    
    def handle_client(self, conn, addr):
        """Handle a client connection"""
        conn_id = self.connection_counter
        self.connection_counter += 1
        
        print(f"New connection from {addr}")
        
        with self.game_lock:
            self.clients[conn_id] = {
                'conn': conn,
                'addr': addr,
                'name': None,
                'score': 0,
                'answers': [],
                'answer_times': []
            }
            # Assign host to the first connected client
            if self.host_conn_id is None:
                self.host_conn_id = conn_id
        
        try:
            buffer = ""
            while True:
                data = conn.recv(BUFFER_SIZE)
                if not data:
                    break
                
                buffer += data.decode('utf-8')
                
                # Process complete messages (delimited by newline)
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if not line.strip():
                        continue
                    
                    try:
                        message = json.loads(line)
                        msg_type = message.get('type')
                        msg_data = message.get('data', {})
                        
                        if msg_type == 'register':
                            self.handle_client_register(conn_id, conn, msg_data)
                        elif msg_type == 'answer':
                            self.handle_client_answer(conn_id, conn, msg_data)
                        elif msg_type == 'start_game':
                            self.handle_request_start_game(conn_id, conn)
                        elif msg_type == 'get_status':
                            with self.game_lock:
                                self.send_message(conn, 'status', {
                                    'active_game': self.active_game,
                                    'player_count': len(self.clients),
                                    'current_question': self.current_question_index
                                })
                        else:
                            self.send_message(conn, 'error', {'message': 'Unknown message type'})
                    
                    except json.JSONDecodeError:
                        self.send_message(conn, 'error', {'message': 'Invalid JSON'})
                    except Exception as e:
                        print(f"Error handling message from {addr}: {e}")
        
        except Exception as e:
            print(f"Error with client {addr}: {e}")
        finally:
            self.remove_client(conn_id)
    
    def run(self):
        """Main server loop"""
        print("Server waiting for clients...")
        print("Clients on the same network can connect using this machine's IP address")
        
        try:
            while True:
                conn, addr = self.sock.accept()
                # Handle each client in a separate thread
                threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()
        
        except KeyboardInterrupt:
            print("\nShutting down server...")
        finally:
            self.sock.close()
            # Close all client connections
            for client in list(self.clients.values()):
                try:
                    client['conn'].close()
                except:
                    pass

if __name__ == '__main__':
    server = TCPQuizServer()
    server.run()

