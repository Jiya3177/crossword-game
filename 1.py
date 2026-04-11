#!/usr/bin/env python3
"""
DBMS Crossword - Backend Server
Python server without Flask - uses built-in http.server
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import sqlite3
import os
import sys

# Database setup
DB_NAME = 'crossword.db'

def init_database():
    """Initialize SQLite database with required tables"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create scores table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            score_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            score INTEGER NOT NULL,
            answered_cells INTEGER NOT NULL DEFAULT 0,
            total_cells INTEGER NOT NULL DEFAULT 0,
            time_taken INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    existing_columns = {
        row[1] for row in cursor.execute("PRAGMA table_info(scores)").fetchall()
    }
    if 'answered_cells' not in existing_columns:
        cursor.execute('ALTER TABLE scores ADD COLUMN answered_cells INTEGER NOT NULL DEFAULT 0')
    if 'total_cells' not in existing_columns:
        cursor.execute('ALTER TABLE scores ADD COLUMN total_cells INTEGER NOT NULL DEFAULT 0')

    cursor.execute('DROP VIEW IF EXISTS leaderboard_view')

    # Create leaderboard view
    cursor.execute('''
        CREATE VIEW leaderboard_view AS
        SELECT 
            u.username,
            best.score AS best_score,
            best.answered_cells AS best_answered_cells,
            best.total_cells AS best_total_cells,
            best.time_taken AS best_time,
            totals.games_played
        FROM users u
        JOIN (
            SELECT 
                s1.user_id,
                s1.score,
                s1.answered_cells,
                s1.total_cells,
                s1.time_taken,
                s1.score_id
            FROM scores s1
            WHERE s1.score_id = (
                SELECT s2.score_id
                FROM scores s2
                WHERE s2.user_id = s1.user_id
                ORDER BY s2.score DESC, s2.time_taken ASC, s2.score_id ASC
                LIMIT 1
            )
        ) best ON u.user_id = best.user_id
        JOIN (
            SELECT user_id, COUNT(*) AS games_played
            FROM scores
            GROUP BY user_id
        ) totals ON u.user_id = totals.user_id
        ORDER BY best.score DESC, best.time_taken ASC
        LIMIT 10
    ''')
    
    conn.commit()
    conn.close()
    print("✓ Database initialized successfully!")


class CrosswordHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler for Crossword Server"""
    
    def _set_headers(self, status=200, content_type='application/json'):
        """Set response headers"""
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS"""
        self._set_headers(204)
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/':
            self.serve_file('login.html', 'text/html; charset=utf-8')
        elif self.path == '/game':
            self.serve_file('1.htm', 'text/html; charset=utf-8')
        elif self.path.startswith('/game?'):
            self.serve_file('1.htm', 'text/html; charset=utf-8')
        elif self.path == '/login.html':
            self.serve_file('login.html', 'text/html; charset=utf-8')
        elif self.path == '/1.htm':
            self.serve_file('1.htm', 'text/html; charset=utf-8')
        elif self.path == '/1.css':
            self.serve_file('1.css', 'text/css; charset=utf-8')
        elif self.path == '/leaderboard':
            self.get_leaderboard()
        elif self.path == '/stats':
            self.get_stats()
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({'error': 'Not found'}).encode())
    
    def do_POST(self):
        """Handle POST requests"""
        if self.path == '/login':
            self.login_user()
        elif self.path == '/submit_score':
            self.submit_score()
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({'error': 'Not found'}).encode())

    def serve_file(self, file_name, content_type):
        """Serve a local file"""
        try:
            file_path = os.path.join(os.path.dirname(__file__), file_name)
            with open(file_path, 'rb') as file:
                data = file.read()
            self._set_headers(200, content_type)
            self.wfile.write(data)
        except FileNotFoundError:
            self._set_headers(404)
            self.wfile.write(json.dumps({'error': 'File not found'}).encode())

    def login_user(self):
        """Create or fetch a user by username"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode() or '{}')

            username = (data.get('username') or '').strip()
            if not username:
                self._set_headers(400)
                self.wfile.write(json.dumps({
                    'error': 'Username is required'
                }).encode())
                return

            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO users (username) VALUES (?)', (username,))
            cursor.execute('SELECT user_id, username FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()
            conn.commit()
            conn.close()

            self._set_headers(200)
            self.wfile.write(json.dumps({
                'message': 'Login successful',
                'user_id': user[0],
                'username': user[1]
            }).encode())

        except Exception as e:
            print(f"Error logging in user: {e}")
            self._set_headers(500)
            self.wfile.write(json.dumps({'error': str(e)}).encode())
    
    def get_leaderboard(self):
        """Get top 10 players from leaderboard"""
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT username, best_score, best_time, games_played
                FROM leaderboard_view
            ''')
            
            results = cursor.fetchall()
            conn.close()
            
            leaderboard = []
            for row in results:
                leaderboard.append({
                    'username': row[0],
                    'score': row[1] if row[1] else 0,
                    'answered_cells': row[2] if row[2] else 0,
                    'total_cells': row[3] if row[3] else 0,
                    'time': row[4] if row[4] else 0,
                    'games': row[5]
                })
            
            self._set_headers()
            self.wfile.write(json.dumps({
                'leaderboard': leaderboard
            }).encode())
            
        except Exception as e:
            print(f"Error getting leaderboard: {e}")
            self._set_headers(500)
            self.wfile.write(json.dumps({'error': str(e)}).encode())
    
    def get_stats(self):
        """Get overall game statistics"""
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM users')
            total_users = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM scores')
            total_games = cursor.fetchone()[0]
            
            cursor.execute('SELECT AVG(score) FROM scores')
            avg_score = cursor.fetchone()[0] or 0
            
            conn.close()
            
            self._set_headers()
            self.wfile.write(json.dumps({
                'total_users': total_users,
                'total_games': total_games,
                'average_score': round(avg_score, 2)
            }).encode())
            
        except Exception as e:
            print(f"Error getting stats: {e}")
            self._set_headers(500)
            self.wfile.write(json.dumps({'error': str(e)}).encode())
    
    def submit_score(self):
        """Submit a new score"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            username = data.get('username')
            score = data.get('score')
            answered_cells = data.get('answered_cells', 0)
            total_cells = data.get('total_cells', 0)
            time_taken = data.get('time')
            
            if not username or score is None or time_taken is None:
                self._set_headers(400)
                self.wfile.write(json.dumps({
                    'error': 'Missing required fields'
                }).encode())
                return
            
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            
            # Insert or get user
            cursor.execute('''
                INSERT OR IGNORE INTO users (username) VALUES (?)
            ''', (username,))
            
            cursor.execute('''
                SELECT user_id FROM users WHERE username = ?
            ''', (username,))
            user_id = cursor.fetchone()[0]
            
            # Insert score
            cursor.execute('''
                INSERT INTO scores (user_id, score, answered_cells, total_cells, time_taken)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, score, answered_cells, total_cells, time_taken))
            
            conn.commit()
            conn.close()
            
            print(f"✓ Score submitted: {username} - {score} points in {time_taken}s")
            
            self._set_headers(201)
            self.wfile.write(json.dumps({
                'message': 'Attempt submitted successfully!',
                'score': score,
                'answered_cells': answered_cells,
                'total_cells': total_cells,
                'time': time_taken
            }).encode())
            
        except Exception as e:
            print(f"Error submitting score: {e}")
            self._set_headers(500)
            self.wfile.write(json.dumps({'error': str(e)}).encode())
    
    def log_message(self, format, *args):
        """Custom log message format"""
        print(f"[{self.log_date_time_string()}] {format % args}")


def run_server(port=5000):
    """Start the HTTP server"""
    server_address = ('', port)
    httpd = HTTPServer(server_address, CrosswordHandler)
    
    print(f"""
╔══════════════════════════════════════════════════════════╗
║        DBMS Crossword Server - Running                   ║
╚══════════════════════════════════════════════════════════╝

✓ Server running on http://localhost:{port}
✓ Database: {DB_NAME}
✓ Ready to accept connections...

Available endpoints:
  GET  /            - Login page
  GET  /game        - Crossword game
  GET  /leaderboard  - Get top 10 players
  GET  /stats        - Get game statistics
  POST /login        - Login with username
  POST /submit_score - Submit a new score

Press Ctrl+C to stop the server
    """)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n✓ Server stopped gracefully")
        httpd.server_close()


if __name__ == '__main__':
    # Initialize database
    init_database()

    port = 5000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("Invalid port. Using default 5000.")

    run_server(port=port)
