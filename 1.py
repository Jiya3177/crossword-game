#!/usr/bin/env python3
"""
DBMS Crossword - Backend Server
Python server without Flask - uses built-in http.server
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import sqlite3
from datetime import datetime
import os
from urllib.parse import parse_qs

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
            time_taken INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Create leaderboard view
    cursor.execute('''
        CREATE VIEW IF NOT EXISTS leaderboard_view AS
        SELECT 
            u.username,
            MAX(s.score) as best_score,
            MIN(s.time_taken) as best_time,
            COUNT(s.score_id) as games_played
        FROM users u
        LEFT JOIN scores s ON u.user_id = s.user_id
        GROUP BY u.user_id
        ORDER BY best_score DESC, best_time ASC
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
        if self.path == '/leaderboard':
            self.get_leaderboard()
        elif self.path == '/stats':
            self.get_stats()
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({'error': 'Not found'}).encode())
    
    def do_POST(self):
        """Handle POST requests"""
        if self.path == '/submit_score':
            self.submit_score()
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({'error': 'Not found'}).encode())
    
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
                    'time': row[2] if row[2] else 0,
                    'games': row[3]
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
                INSERT INTO scores (user_id, score, time_taken)
                VALUES (?, ?, ?)
            ''', (user_id, score, time_taken))
            
            conn.commit()
            conn.close()
            
            print(f"✓ Score submitted: {username} - {score} points in {time_taken}s")
            
            self._set_headers(201)
            self.wfile.write(json.dumps({
                'message': 'Score submitted successfully!',
                'score': score,
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
  GET  /leaderboard  - Get top 10 players
  GET  /stats        - Get game statistics
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
    
    # Start server
    run_server(port=5000)