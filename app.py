#!/usr/bin/env python3
import streamlit as st
import socket
import json
import threading
import time
import queue

BUFFER_SIZE = 4096

# Initialize session state
if 'sock' not in st.session_state:
    st.session_state.sock = None
if 'connected' not in st.session_state:
    st.session_state.connected = False
if 'registered' not in st.session_state:
    st.session_state.registered = False
if 'player_name' not in st.session_state:
    st.session_state.player_name = ""
if 'server_host' not in st.session_state:
    st.session_state.server_host = ""
if 'game_active' not in st.session_state:
    st.session_state.game_active = False
if 'current_question' not in st.session_state:
    st.session_state.current_question = None
if 'question_start_time' not in st.session_state:
    st.session_state.question_start_time = None
if 'score' not in st.session_state:
    st.session_state.score = 0
if 'message_queue' not in st.session_state:
    st.session_state.message_queue = queue.Queue()
if 'leaderboard' not in st.session_state:
    st.session_state.leaderboard = []
if 'player_count' not in st.session_state:
    st.session_state.player_count = 0
if 'receiver_thread' not in st.session_state:
    st.session_state.receiver_thread = None
if 'receiver_running' not in st.session_state:
    st.session_state.receiver_running = False
if 'rerun_counter' not in st.session_state:
    st.session_state.rerun_counter = 0
if 'timer_tick' not in st.session_state:
    st.session_state.timer_tick = 0
if 'waiting_for_result' not in st.session_state:
    st.session_state.waiting_for_result = False
if 'show_answer_form' not in st.session_state:
    st.session_state.show_answer_form = False

def send_message(message_type, data):
    """Send a message to the server"""
    if not st.session_state.connected or not st.session_state.sock:
        return False
    
    message = {
        'type': message_type,
        'data': data
    }
    try:
        print(f"[DEBUG] Sending message type: {message_type}, data: {data}")
        st.session_state.sock.sendall(json.dumps(message).encode('utf-8') + b'\n')
        return True
    except Exception as e:
        st.error(f"Error sending message: {e}")
        return False

def receive_messages(sock, message_queue, running_flag):
    """Receive and handle messages from server (runs in background thread)"""
    buffer = ""
    try:
        while running_flag[0] and sock:
            try:
                data = sock.recv(BUFFER_SIZE)
                if not data:
                    # Connection closed by server
                    message_queue.put({
                        'type': 'disconnected',
                        'data': {'message': 'Connection closed by server'}
                    })
                    break
                
                buffer += data.decode('utf-8')
                
                # Process complete messages (delimited by newline)
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if not line.strip():
                        continue
                    
                    try:
                        message = json.loads(line)
                        message_queue.put(message)
                    except json.JSONDecodeError:
                        pass
            
            except socket.error as e:
                # Connection error
                if running_flag[0]:
                    message_queue.put({
                        'type': 'error',
                        'data': {'message': f'Connection error: {e}'}
                    })
                break
            except Exception as e:
                # Other errors
                if running_flag[0]:
                    message_queue.put({
                        'type': 'error',
                        'data': {'message': f'Error: {e}'}
                    })
                break
    except Exception as e:
        message_queue.put({
            'type': 'error',
            'data': {'message': f'Receiver thread error: {e}'}
        })

def process_messages():
    """Process messages from the queue"""
    messages_processed = False
    should_rerun = False
    
    while not st.session_state.message_queue.empty():
        try:
            message = st.session_state.message_queue.get_nowait()
            msg_type = message.get('type')
            msg_data = message.get('data', {})
            messages_processed = True
            
            # Debug: Log received message type
            print(f"[DEBUG] Received message type: {msg_type}")
            
            if msg_type == 'registered':
                st.session_state.registered = True
                st.session_state.player_count = msg_data.get('player_count', 0)
                should_rerun = True
            
            elif msg_type == 'player_joined':
                st.session_state.player_count = msg_data.get('total_players', 0)
                should_rerun = True
            
            elif msg_type == 'game_start':
                st.session_state.game_active = True
                st.session_state.score = 0
                should_rerun = True
            
            elif msg_type == 'question':
                # Initialize new question (make sure to reset answered flag)
                msg_data['answered'] = False
                msg_data['answer_feedback'] = None  # Clear any old feedback
                st.session_state.current_question = msg_data
                st.session_state.question_start_time = time.time()
                # Reset any waiting counters when a fresh question arrives
                st.session_state.rerun_counter = 0
                st.session_state.timer_tick = 0
                st.session_state.waiting_for_result = False
                st.session_state.show_answer_form = True
                print(f"[DEBUG] New question received: Q{msg_data.get('question_number')}")
                should_rerun = True
            
            elif msg_type == 'answer_result':
                correct = msg_data.get('correct', False)
                points = msg_data.get('points', 0)
                st.session_state.score = msg_data.get('total_score', 0)
                # Store answer result but don't clear question yet
                # The question will be cleared when next question arrives or question_end
                if st.session_state.current_question:
                    st.session_state.current_question['answer_feedback'] = {
                        'correct': correct,
                        'points': points,
                        'correct_answer': msg_data.get('correct_answer', '')
                    }
                # Result arrived; no longer waiting
                st.session_state.waiting_for_result = False
                st.session_state.show_answer_form = False
                should_rerun = True
            
            elif msg_type == 'question_end':
                st.session_state.current_question = None
                correct_answer = msg_data.get('correct_answer', '')
                st.info(f"⏱ Time's up! Correct answer: {correct_answer}")
                # Reset counter so waiting loop can begin cleanly
                st.session_state.rerun_counter = 0
                st.session_state.waiting_for_result = False
                st.session_state.show_answer_form = False
                should_rerun = True
            
            elif msg_type == 'game_end':
                st.session_state.game_active = False
                st.session_state.current_question = None
                st.session_state.leaderboard = msg_data.get('leaderboard', [])
                st.session_state.waiting_for_result = False
                st.session_state.show_answer_form = False
                should_rerun = True
            
            elif msg_type == 'error':
                st.error(f"❌ {msg_data.get('message')}")
            
            elif msg_type == 'disconnected':
                st.session_state.connected = False
                st.session_state.registered = False
                st.error(f"❌ {msg_data.get('message')}")
                should_rerun = True
            
            elif msg_type == 'status':
                st.session_state.game_active = msg_data.get('active_game', False)
                st.session_state.player_count = msg_data.get('player_count', 0)
        
        except queue.Empty:
            break
    
    # Return whether a rerun is needed instead of calling st.rerun() here
    return messages_processed, should_rerun

def connect_to_server(host, port, name):
    """Connect to the server"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        
        st.session_state.sock = sock
        st.session_state.connected = True
        st.session_state.server_host = host
        
        # Create thread-safe flag and start receiver thread
        running_flag = [True]  # Use list so reference is shared
        st.session_state.receiver_running = running_flag
        receiver_thread = threading.Thread(
            target=receive_messages, 
            args=(sock, st.session_state.message_queue, running_flag),
            daemon=True
        )
        receiver_thread.start()
        st.session_state.receiver_thread = receiver_thread
        
        # Register with server
        time.sleep(0.2)
        send_message('register', {'name': name})
        
        return True
    except Exception as e:
        st.error(f"Error connecting to server: {e}")
        return False

def disconnect():
    """Disconnect from server"""
    # Stop receiver thread
    if st.session_state.receiver_running and isinstance(st.session_state.receiver_running, list):
        st.session_state.receiver_running[0] = False
    
    if st.session_state.sock:
        try:
            st.session_state.sock.close()
        except:
            pass
    
    st.session_state.sock = None
    st.session_state.connected = False
    st.session_state.registered = False
    st.session_state.game_active = False
    st.session_state.current_question = None
    st.session_state.score = 0
    st.session_state.leaderboard = []
    st.session_state.player_count = 0
    st.session_state.receiver_running = False

def render_leaderboard():
    """Render the final leaderboard UI"""
    st.header("🎉 Quiz Completed!")
    st.markdown("---")
    
    # Calculate player's position and score
    player_score = 0
    player_position = 0
    for i, entry in enumerate(st.session_state.leaderboard, 1):
        if entry['name'] == st.session_state.player_name:
            player_score = entry['score']
            player_position = i
            break
    
    total_players = len(st.session_state.leaderboard)
    if player_score > 0:
        st.write(f"✅ **Your Final Score: {player_score} points**")
        if player_position == 1:
            st.success("🏆 Perfect Score! You won!")
        elif player_position <= 3:
            st.success(f"🌟 Excellent! You finished #{player_position}!")
        else:
            st.info(f"👍 Good work! You finished #{player_position} out of {total_players}")
    
    st.markdown("---")
    st.header("🏆 Final Leaderboard")
    st.markdown("---")
    
    for i, entry in enumerate(st.session_state.leaderboard, 1):
        medal = ""
        if i == 1:
            medal = "🥇"
        elif i == 2:
            medal = "🥈"
        elif i == 3:
            medal = "🥉"
        
        # Highlight current player
        is_you = entry['name'] == st.session_state.player_name
        style = "border: 3px solid #1f77b4; padding: 15px; border-radius: 8px; background-color: #e6f3ff;"
        normal_style = "padding: 10px; border-radius: 5px;"
        
        st.markdown(f"""
        <div class="leaderboard-card hot-card" style="{style if is_you else normal_style}">
            <h3>{medal} {i}. {entry['name']}: {entry['score']} points</h3>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    if st.button("🔄 Start New Game", type="primary", use_container_width=True):
        send_message('start_game', {})
        st.session_state.leaderboard = []
        st.rerun()

# Main UI
st.set_page_config(page_title="TCP Quiz Game", page_icon="🎮", layout="wide")

# Global styling (hotter UI)
st.markdown(
    """
    <style>
    :root {
        --primary: #ff3b7f; /* hot pink */
        --secondary: #8e2de2; /* purple */
        --accent: #f9a826; /* orange */
        --bg1: #0f2027;
        --bg2: #203a43;
        --bg3: #2c5364;
    }
    .stApp {
        background: linear-gradient(135deg, var(--bg1), var(--bg2), var(--bg3));
        color: #fff;
    }
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 1.2rem;
        max-width: 1100px;
    }
    h1, h2, h3, h4 { color: #fff !important; }
    .hot-card {
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 16px;
        padding: 18px;
        box-shadow: 0 6px 24px rgba(0,0,0,0.25), inset 0 0 0 1px rgba(255,255,255,0.04);
    }
    .question-card { border-left: 4px solid var(--primary); }
    .leaderboard-card { border-left: 4px solid var(--accent); }
    .stMetric {
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 12px;
        padding: 8px 12px;
    }
    .stProgress > div > div {
        background: linear-gradient(90deg, var(--primary), var(--accent)) !important;
    }
    .stAlert { border-radius: 12px; }
    hr, .stMarkdown hr {
        border: none; height: 1px;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.25), transparent);
    }
    /* Inputs on dark bg */
    .stTextInput input, .stNumberInput input, .st-radio label, .stSelectbox div[data-baseweb="select"] {
        color: #fff !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🎮 TCP Quiz Game Client")
st.markdown("**CS411 - Lab 4: Network Socket Programming**")

st.markdown("---")

# Process incoming messages (do this first to handle any queued messages)
# Process multiple times to catch rapid messages
for _ in range(3):  # Try processing multiple times
    _, needs_rerun = process_messages()
    if needs_rerun:
        st.rerun()
    if st.session_state.message_queue.empty():
        break
    time.sleep(0.05)  # Small delay to let messages arrive

# Connection Section
if not st.session_state.connected:
    st.header("🔌 Connect to Server")
    
    col1, col2 = st.columns(2)
    with col1:
        server_host = st.text_input("Server IP Address", value="localhost", 
                                     help="Enter the IP address of the quiz server (e.g., 192.168.1.100)")
    with col2:
        server_port = st.number_input("Server Port", value=8889, min_value=1, max_value=65535)
    
    player_name = st.text_input("Your Name", value=f"Player_{int(time.time()) % 10000}")
    
    if st.button("Connect", type="primary"):
        if connect_to_server(server_host, int(server_port), player_name):
            st.session_state.player_name = player_name
            st.success("Connecting...")
            time.sleep(0.5)
            st.rerun()

else:
    # Connected - Show game interface
    st.success(f"✓ Connected to {st.session_state.server_host}")
    
    # Top bar with metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Your Score", st.session_state.score)
    with col2:
        st.metric("Players", st.session_state.player_count)
    with col3:
        if st.session_state.game_active and st.session_state.current_question:
            question_num = st.session_state.current_question.get('question_number', 0)
            total_questions = st.session_state.current_question.get('total_questions', 0)
            st.metric("Progress", f"{question_num}/{total_questions}")
        else:
            st.metric("Status", "Waiting")
    with col4:
        if st.button("🔌 Disconnect", use_container_width=True):
            disconnect()
            st.rerun()
    
    st.markdown("---")
    
    # Game Status
    if not st.session_state.registered:
        st.info("Registering with server...")
    
    elif st.session_state.leaderboard:
        # Show final leaderboard regardless of game_active
        render_leaderboard()
    
    elif not st.session_state.game_active:
        # Lobby - waiting for game
        st.header("🏠 Game Lobby")
        
        if st.session_state.player_count > 0:
            st.info(f"Waiting in lobby... {st.session_state.player_count} player(s) connected")
            
            if st.button("🚀 Start Game", type="primary"):
                send_message('start_game', {})
                st.info("Starting game...")
                time.sleep(0.5)
                st.rerun()
        else:
            st.warning("No players connected")
    
    else:
        # Active Game
        if st.session_state.current_question:
            # Show current question with quiz app styling
            question = st.session_state.current_question
            time_limit = question.get('time_limit', 30)
            question_num = question.get('question_number', 0)
            total_questions = question.get('total_questions', 0)
            
            # Calculate time remaining
            if st.session_state.question_start_time:
                elapsed = time.time() - st.session_state.question_start_time
                time_remaining = max(0, time_limit - elapsed)
            else:
                time_remaining = time_limit
            
            # Progress bar for question number
            progress_col1, progress_col2 = st.columns([3, 1])
            with progress_col1:
                progress = question_num / total_questions if total_questions > 0 else 0
                st.progress(progress)
            with progress_col2:
                st.write(f"📊 **{question_num}/{total_questions}**")
            
            # Show current score if available
            if st.session_state.score > 0:
                accuracy_info = ""
                if question_num > 1:
                    # Estimate accuracy (rough calculation)
                    st.info(f"✅ **Current Score: {st.session_state.score} points**")
            
            st.subheader(f"❓ {question['question']}")
            
            # Numeric countdown only (no progress bar)
            st.metric("Time left", f"{time_remaining:.1f}s")
            
            # Auto-refresh when time runs out to catch server's question_end message (no waiting UI)
            if time_remaining <= 0:
                if st.session_state.rerun_counter < 10:  # Just a few times
                    st.session_state.rerun_counter += 1
                    time.sleep(0.3)
                    st.rerun()
            
            # Check current UI state flags
            question_answered = question.get('answered', False)
            answer_feedback = question.get('answer_feedback', None)
            # Derive a stable waiting state: once answered and before feedback, we're waiting
            waiting_for_result = st.session_state.waiting_for_result or (question_answered and not answer_feedback)
            # Persist the derived waiting state to avoid flicker between reruns
            st.session_state.waiting_for_result = waiting_for_result
            
            print(f"[DEBUG UI] Q{question_num}: answered={question_answered}, has_feedback={answer_feedback is not None}")
            
            if answer_feedback:
                # Show feedback from server
                if answer_feedback['correct']:
                    st.success(f"🎉 Correct! You earned {answer_feedback['points']} points")
                else:
                    st.error(f"❌ Incorrect. The correct answer was **{answer_feedback['correct_answer']}**")

                # Auto-refresh to catch next question quickly (no waiting UI)
                if st.session_state.rerun_counter < 150:  # 30 seconds max
                    st.session_state.rerun_counter += 1
                    time.sleep(0.2)
                    st.rerun()
                
            elif waiting_for_result:
                # Hide submit UI immediately; silently poll for server response
                if st.session_state.rerun_counter < 50:  # up to ~10s
                    st.session_state.rerun_counter += 1
                    time.sleep(0.2)
                    st.rerun()
                else:
                    st.session_state.rerun_counter = 0  # Reset for next question
            else:
                # Reset counter when showing question form
                st.session_state.rerun_counter = 0
                # Answer options using radio buttons (like quiz_app.py)
                selected_option = None
                if st.session_state.show_answer_form and not waiting_for_result and not answer_feedback:
                    selected_option = st.radio(
                        "Choose your answer:",
                        question['options'],
                        key=f"answer_{question_num}",
                        disabled=False
                    )
                
                # Extract answer letter from selected option
                answer_letter = None
                if selected_option:
                    # Option format: "A) Option text"
                    if len(selected_option) > 0 and selected_option[0].isalpha():
                        answer_letter = selected_option[0].upper()
                    # Or if it's just the letter
                    elif selected_option.upper() in ['A', 'B', 'C', 'D']:
                        answer_letter = selected_option.upper()
                
                # Submit Answer button
                if st.session_state.show_answer_form and not waiting_for_result and not answer_feedback and st.button("✅ Submit Answer", type="primary", use_container_width=True):
                    if answer_letter:
                        print(f"[DEBUG] Submitting answer: {answer_letter}")
                        # Immediately mark as answered so the button hides on next render
                        st.session_state.current_question['answered'] = True
                        st.session_state.current_question['selected_answer'] = answer_letter
                        st.session_state.waiting_for_result = True
                        st.session_state.show_answer_form = False
                        # Try to send the answer; if it fails, revert the flag
                        if not send_message('answer', {'answer': answer_letter}):
                            st.session_state.current_question['answered'] = False
                            st.session_state.waiting_for_result = False
                            st.session_state.show_answer_form = True
                            st.error("Failed to send answer to server")
                        # Trigger rerun to update UI (hide button)
                        st.rerun()
                    else:
                        st.warning("Please select an answer first")

            # Schedule countdown refresh AFTER rendering the UI so options are visible
            if not question.get('answered', False) and not waiting_for_result and not answer_feedback and time_remaining > 0:
                if st.session_state.timer_tick < 120:  # ~60 seconds at 0.5s steps
                    st.session_state.timer_tick += 1
                    time.sleep(0.5)
                    st.rerun()
        
        elif st.session_state.leaderboard:
            # Fallback (active game path) - show leaderboard
            render_leaderboard()
        
        else:
            # Waiting between questions or after answering (no waiting UI)
            # Auto-refresh while waiting for the server to push the next question
            if st.session_state.game_active:
                if st.session_state.rerun_counter < 120:  # ~36s total at 0.3s per tick
                    st.session_state.rerun_counter += 1
                    time.sleep(0.3)
                    st.rerun()
                else:
                    # Safety reset in case we somehow miss the next question
                    st.session_state.rerun_counter = 0

# Footer
st.markdown("---")
st.caption("**TCP Protocol Demo** - Connection-oriented, reliable, ordered delivery")

