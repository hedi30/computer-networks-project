# Testing Guide - CS411 Lab 4 Quiz Game

## Quick Start Testing

### Step 1: Get Your IP Address

Run the helper script to get your local IP:
```bash
python get_ip.py
```

Or manually find it:
```bash
# Linux/Mac
hostname -I
# or
ip addr show | grep "inet "

# Windows
ipconfig
```

### Step 2: Test UDP Version (Connectionless)

**Terminal 1 - Start UDP Server:**
```bash
cd /home/xcoder/dev/computer-networks-project
python udp_quiz/server_udp.py
```

You should see:
```
UDP Quiz Server started on 0.0.0.0:8888
Loaded 15 questions
Server waiting for clients...
```

**Terminal 2 - Connect First Client:**
```bash
cd /home/xcoder/dev/computer-networks-project
python udp_quiz/client_udp.py localhost Player1
# OR from another machine:
python udp_quiz/client_udp.py <SERVER_IP> Player1
```

**Terminal 3 - Connect Second Client (Optional):**
```bash
python udp_quiz/client_udp.py localhost Player2
```

**In the client terminals:**
1. You'll see "✓ Welcome [PlayerName]!" message
2. Type `start` in any client terminal to begin the game
3. When a question appears, type A, B, C, or D to answer
4. Game will show results and final leaderboard

### Step 3: Test TCP Version (Connection-Oriented)

#### Option A: Using Streamlit GUI (Recommended)

**Terminal 1 - Start TCP Server:**
```bash
cd /home/xcoder/dev/computer-networks-project
python tcp_quiz/server_tcp.py
```

You should see:
```
TCP Quiz Server started on 0.0.0.0:8889
Loaded 15 questions
Server waiting for clients...
```

**Terminal 2 - Launch Streamlit App:**
```bash
cd /home/xcoder/dev/computer-networks-project
streamlit run app.py
```

The app will open in your browser (usually `http://localhost:8501`)

**In the Streamlit interface:**
1. Enter server IP (use `localhost` if testing locally)
2. Enter your name
3. Click "Connect"
4. Click "🚀 Start Game" when ready
5. Click answer buttons (A, B, C, D) to answer questions
6. View real-time score and leaderboard

**For multiplayer testing:**
- Open the Streamlit URL on multiple devices/browsers
- Or use: `streamlit run app.py --server.address 0.0.0.0` to allow network access
- Then access from other devices using: `http://<SERVER_IP>:8501`

#### Option B: Using Command-Line Client

**Terminal 1 - Start TCP Server:**
```bash
python tcp_quiz/server_tcp.py
```

**Terminal 2 - Connect First Client:**
```bash
python tcp_quiz/client_tcp.py localhost Player1
```

**Terminal 3 - Connect Second Client:**
```bash
python tcp_quiz/client_tcp.py localhost Player2
```

**In client terminals:**
1. Type `start` to begin
2. Type A, B, C, or D to answer questions
3. View results in real-time

## Testing Scenarios

### 1. Single Player Test
- Start server
- Connect one client
- Start game and answer all questions
- Verify score calculation works
- Check leaderboard shows correctly

### 2. Multiplayer Test (2+ Players)
- Start server
- Connect multiple clients
- Start game
- Verify all clients receive questions simultaneously
- Verify scores update correctly for each player
- Check leaderboard ranking

### 3. Network Testing (Different Machines)
- Find server IP using `python get_ip.py`
- On server machine: Start server
- On client machines: Connect using server's IP address
- Verify connections work across network

### 4. Protocol Comparison Test

**UDP (Connectionless):**
- Messages can be lost (test by disconnecting briefly)
- No connection establishment needed
- Fast but unreliable

**TCP (Connection-Oriented):**
- Reliable message delivery
- Connection must be established first
- Ordered message delivery

### 5. Timing Test
- Answer questions quickly to get more points
- Let time run out to see timeout handling
- Verify points decrease as time increases

### 6. Error Handling Test
- Try connecting with wrong IP address
- Try starting game with no players
- Try starting game when game already in progress
- Try disconnecting during game

## Expected Behavior

### UDP Version:
- ✓ Instant connection (no handshake)
- ✓ Fast message delivery
- ⚠️ Messages may be lost if network is unstable
- ✓ Server handles clients by IP:port pairs

### TCP Version:
- ✓ Connection establishment (handshake)
- ✓ Reliable message delivery
- ✓ Ordered message delivery
- ✓ Server maintains connection per client

### Common Features:
- ✓ Real-time question broadcasting
- ✓ Timer for each question (30 seconds)
- ✓ Score based on speed (faster = more points)
- ✓ Leaderboard at end of game
- ✓ Multiple players can play simultaneously

## Troubleshooting

### "Connection refused" error:
- Make sure server is running first
- Check IP address is correct
- Check firewall isn't blocking ports
- For UDP: Server must be running before clients connect
- For TCP: Server must be listening

### "Address already in use" error:
- Another process is using the port
- Kill existing server: `pkill -f server_udp.py` or `pkill -f server_tcp.py`
- Or change port in server code

### Questions not loading:
- Make sure `questions.txt` is in project root directory
- Check file has correct format

### Streamlit not opening:
- Check if port 8501 is available
- Try: `streamlit run app.py --server.port 8502`
- Access via: `http://localhost:8502`

### Multiple players can't connect:
- Verify all are on same network
- Check server IP is accessible
- For Streamlit: Use `--server.address 0.0.0.0` to allow network access

## Quick Test Commands

```bash
# Test UDP (all in one):
# Terminal 1
python udp_quiz/server_udp.py &

# Terminal 2
python udp_quiz/client_udp.py localhost TestPlayer1

# Test TCP Streamlit:
# Terminal 1
python tcp_quiz/server_tcp.py &

# Terminal 2
streamlit run app.py
```

## Performance Testing

- Test with 5+ simultaneous players
- Monitor server CPU/memory usage
- Test with slow network connections
- Verify questions are synchronized across all clients

