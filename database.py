#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database management module for ChatAI application
"""
import pyodbc
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from logger_config import app_logger

class Config:
    def __init__(self):
        # Ưu tiên lấy link PostgreSQL từ Render
        self.database_url = os.environ.get('DATABASE_URL')
        
        # Thông số dự phòng cho SQL Server (máy nhà)
        self.db_driver = os.environ.get('DB_DRIVER', 'ODBC Driver 17 for SQL Server')
        self.db_server = os.environ.get('DB_SERVER', 'IAMIOT')
        self.db_name = os.environ.get('DB_NAME', 'DNU_ChatApp')
        self.db_trusted = os.environ.get('DB_TRUSTED_CONNECTION', 'true').lower() in ['true', '1', 'yes']
        self.db_user = os.environ.get('DB_USER', '')
        self.db_password = os.environ.get('DB_PASSWORD', '')

        self.conn_str = f"DRIVER={{{self.db_driver}}};SERVER={self.db_server};DATABASE={self.db_name};"
        if self.db_trusted:
            self.conn_str += "Trusted_Connection=yes;"
        else:
            self.conn_str += f"UID={self.db_user};PWD={self.db_password};"
        self.conn_str += "Encrypt=yes;TrustServerCertificate=yes;"

config = Config()

class DatabaseManager:
    @staticmethod
    def get_db_connection():
        try:
            # Nếu có DATABASE_URL -> Dùng PostgreSQL (Render)
            if config.database_url:
                return psycopg2.connect(config.database_url)
            # Nếu không -> Dùng SQL Server (Máy nhà)
            return pyodbc.connect(config.conn_str)
        except Exception as e:
            app_logger.error(f"Database connection error: {e}")
            raise

    @staticmethod
    def execute_query(query, params=None, fetch_one=False, fetch_all=False):
        try:
            conn = DatabaseManager.get_db_connection()
            # PostgreSQL dùng %s thay vì ?, ta cần xử lý nếu đang ở Render
            if config.database_url:
                query = query.replace('?', '%s').replace('GETDATE()', 'CURRENT_TIMESTAMP')
                query = query.replace('SCOPE_IDENTITY()', 'LASTVAL()') # PostgreSQL tương đương

            cursor = conn.cursor()
            cursor.execute(query, params) if params else cursor.execute(query)
            
            result = None
            if fetch_one:
                result = cursor.fetchone()
            elif fetch_all:
                result = cursor.fetchall()
            else:
                conn.commit()
                result = cursor.rowcount
            
            conn.close()
            return result
        except Exception as e:
            app_logger.error(f"Query execution error: {e}")
            raise
    
    @staticmethod
    def create_user(username, password, full_name, email=None):
        """Create new user"""
        try:
            query = """
                INSERT INTO Users (Username, Password, FullName, Email, Status, CreatedAt)
                VALUES (?, ?, ?, ?, 'Offline', GETDATE())
            """
            params = (username, generate_password_hash(password), full_name, email)
            return DatabaseManager.execute_query(query, params)
        except Exception as e:
            app_logger.error(f"User creation error: {e}")
            raise
    
    @staticmethod
    def get_user_by_username(username):
        """Get user by username"""
        try:
            query = "SELECT UserID, Username, Password, FullName, Email, Status FROM Users WHERE Username = ?"
            return DatabaseManager.execute_query(query, (username,), fetch_one=True)
        except Exception as e:
            app_logger.error(f"Get user by username error: {e}")
            return None
    
    @staticmethod
    def save_message(user_id, content, msg_type='Text', room_id=1, reply_to_message_id=None):
        """Save message to database"""
        try:
            DatabaseManager.ensure_reply_column()
            if reply_to_message_id:
                query = """
                    INSERT INTO Messages (RoomID, SenderID, Content, MessageType, IsRead, SentAt, ReplyToMessageID)
                    VALUES (?, ?, ?, ?, 0, GETDATE(), ?)
                """
                params = (room_id, user_id, content, msg_type, reply_to_message_id)
            else:
                query = """
                    INSERT INTO Messages (RoomID, SenderID, Content, MessageType, IsRead, SentAt)
                    VALUES (?, ?, ?, ?, 0, GETDATE())
                """
                params = (room_id, user_id, content, msg_type)
            return DatabaseManager.execute_query(query, params)
        except Exception as e:
            app_logger.error(f"Save message error: {e}")
            raise
    
    @staticmethod
    def get_room_messages(room_id, limit=50):
        """Get messages for a room"""
        try:
            DatabaseManager.ensure_reply_column()
            query = """
                SELECT TOP {} m.MessageID, m.Content, m.MessageType, m.SentAt, m.IsRead,
                       u.Username as SenderName, u.UserID as SenderID, m.ReplyToMessageID
                FROM Messages m
                JOIN Users u ON m.SenderID = u.UserID
                WHERE m.RoomID = ? AND m.IsDeleted = 0
                ORDER BY m.SentAt DESC
            """.format(limit)
            messages = DatabaseManager.execute_query(query, (room_id,), fetch_all=True)
            return messages
        except Exception as e:
            app_logger.error(f"Get room messages error: {e}")
            return []
    
    @staticmethod
    def get_analytics_data(export_type):
        """Get analytics data for export"""
        try:
            if export_type == 'users':
                query = """
                    SELECT UserID, Username, FullName, Email, Status, CreatedAt
                    FROM Users
                    ORDER BY CreatedAt DESC
                """
            elif export_type == 'messages':
                query = """
                    SELECT m.MessageID, m.Content, m.MessageType, m.SentAt,
                           u.Username as SenderName
                    FROM Messages m
                    JOIN Users u ON m.SenderID = u.UserID
                    ORDER BY m.SentAt DESC
                """
            elif export_type == 'rooms':
                query = """
                    SELECT RoomID, RoomName, IsGroup, CreatedAt
                    FROM Rooms
                    ORDER BY CreatedAt DESC
                """
            elif export_type == 'files':
                query = """
                    SELECT FileID, FileName, FileType, FileSize, UploadedAt,
                           u.Username as UploaderName
                    FROM Files f
                    JOIN Users u ON f.UploadedBy = u.UserID
                    ORDER BY f.UploadedAt DESC
                """
            else:
                return None
            
            return DatabaseManager.execute_query(query, fetch_all=True)
        except Exception as e:
            app_logger.error(f"Get analytics data error: {e}")
            return None
    
    @staticmethod
    def ensure_room_participants_table():
        """Ensure RoomParticipants table exists"""
        try:
            app_logger.info(f"Checking/creating RoomParticipants table")
            query = """
                IF OBJECT_ID('RoomParticipants', 'U') IS NULL
                BEGIN
                    CREATE TABLE RoomParticipants (
                        RoomID INT NOT NULL,
                        UserID INT NOT NULL,
                        JoinedAt DATETIME DEFAULT GETDATE(),
                        PRIMARY KEY (RoomID, UserID),
                        FOREIGN KEY (RoomID) REFERENCES Rooms(RoomID),
                        FOREIGN KEY (UserID) REFERENCES Users(UserID)
                    )
                END
            """
            DatabaseManager.execute_query(query)
            app_logger.info(f"RoomParticipants table checked/created successfully")
        except Exception as e:
            app_logger.error(f"RoomParticipants table creation error: {e}")
    
    @staticmethod
    def ensure_user_auth_columns():
        """Ensure user authentication columns exist"""
        try:
            app_logger.info(f"Connecting to database server: {config.db_server}")
            conn = DatabaseManager.get_db_connection()
            cursor = conn.cursor()
            
            columns_to_add = [
                ('Email', "ALTER TABLE Users ADD Email NVARCHAR(255) NULL"),
                ('IsVerified', "ALTER TABLE Users ADD IsVerified BIT NOT NULL DEFAULT 0"),
                ('VerificationToken', "ALTER TABLE Users ADD VerificationToken NVARCHAR(255) NULL"),
                ('OAuthProvider', "ALTER TABLE Users ADD OAuthProvider NVARCHAR(50) NULL"),
                ('OAuthId', "ALTER TABLE Users ADD OAuthId NVARCHAR(255) NULL"),
                ('ResetToken', "ALTER TABLE Users ADD ResetToken NVARCHAR(255) NULL"),
                ('ResetTokenExpiresAt', "ALTER TABLE Users ADD ResetTokenExpiresAt DATETIME NULL")
            ]
            
            message_columns_to_add = [
                ('EditedAt', "ALTER TABLE Messages ADD EditedAt DATETIME NULL")
            ]
            
            for column_name, sql in columns_to_add:
                if not DatabaseManager.column_exists('Users', column_name):
                    cursor.execute(sql)
                    app_logger.info(f"Added column {column_name} to Users table")
            
            for column_name, sql in message_columns_to_add:
                if not DatabaseManager.column_exists('Messages', column_name):
                    cursor.execute(sql)
                    app_logger.info(f"Added column {column_name} to Messages table")
            
            conn.commit()
            conn.close()
        except Exception as e:
            app_logger.error(f"Column check error: {e}")
    
    @staticmethod
    def column_exists(table, column):
        """Check if column exists in table"""
        try:
            conn = DatabaseManager.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ? AND COLUMN_NAME = ?", (table, column))
            exists = cursor.fetchone() is not None
            conn.close()
            return exists
        except Exception as e:
            app_logger.error(f"Column check error: {e}")
            return False
    
    @staticmethod
    def ensure_last_seen_column():
        """Ensure LastSeenAt column exists in Users table"""
        try:
            if not DatabaseManager.column_exists('Users', 'LastSeenAt'):
                query = "ALTER TABLE Users ADD LastSeenAt DATETIME NULL"
                DatabaseManager.execute_query(query)
                app_logger.info("Added LastSeenAt column to Users table")
        except Exception as e:
            app_logger.error(f"Error adding LastSeenAt column: {e}")

    @staticmethod
    def ensure_user_status_message_column():
        """Ensure UserStatusMessage column exists in Users table"""
        try:
            if not DatabaseManager.column_exists('Users', 'UserStatusMessage'):
                query = "ALTER TABLE Users ADD UserStatusMessage NVARCHAR(200) NULL"
                DatabaseManager.execute_query(query)
                app_logger.info("Added UserStatusMessage column to Users table")
        except Exception as e:
            app_logger.error(f"Error adding UserStatusMessage column: {e}")

    @staticmethod
    def update_user_status(user_id, status):
        """Update user status and last seen"""
        try:
            DatabaseManager.ensure_last_seen_column()
            if status == 'Online':
                query = "UPDATE Users SET Status = ?, LastSeenAt = GETDATE() WHERE UserID = ?"
            else:
                query = "UPDATE Users SET Status = ? WHERE UserID = ?"
            return DatabaseManager.execute_query(query, (status, user_id))
        except Exception as e:
            app_logger.error(f"Update user status error: {e}")
            return 0
    
    @staticmethod
    def get_user_profile(user_id):
        """Get user profile"""
        try:
            DatabaseManager.ensure_last_seen_column()
            query = """
                SELECT FullName, Username, Email, Status, LastSeenAt
                FROM Users
                WHERE UserID = ?
            """
            user = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            if user:
                return {
                    'full_name': user[0],
                    'username': user[1],
                    'email': user[2],
                    'status': user[3],
                    'last_seen': user[4].strftime('%Y-%m-%d %H:%M:%S') if user[4] else None
                }
            return {
                'full_name': '',
                'username': '',
                'email': '',
                'status': 'Offline',
                'last_seen': None
            }
        except Exception as e:
            app_logger.error(f"Get user profile error: {e}")
            return {
                'full_name': '',
                'username': '',
                'email': '',
                'status': 'Offline',
                'last_seen': None
            }

    @staticmethod
    def get_user_last_seen(user_id):
        """Get last seen time for a user"""
        try:
            DatabaseManager.ensure_last_seen_column()
            query = "SELECT LastSeenAt FROM Users WHERE UserID = ?"
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            if result and result[0]:
                return result[0].strftime('%Y-%m-%d %H:%M:%S')
            return None
        except Exception as e:
            app_logger.error(f"Get user last seen error: {e}")
            return None

    @staticmethod
    def set_user_status_message(user_id, status_message):
        """Set user status message"""
        try:
            DatabaseManager.ensure_user_status_message_column()
            query = "UPDATE Users SET UserStatusMessage = ? WHERE UserID = ?"
            return DatabaseManager.execute_query(query, (status_message, user_id))
        except Exception as e:
            app_logger.error(f"Set user status message error: {e}")
            return 0

    @staticmethod
    def get_user_status_message(user_id):
        """Get user status message"""
        try:
            DatabaseManager.ensure_user_status_message_column()
            query = "SELECT UserStatusMessage FROM Users WHERE UserID = ?"
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            return result[0] if result and result[0] else ''
        except Exception as e:
            app_logger.error(f"Get user status message error: {e}")
            return ''
    
    @staticmethod
    def get_user_by_email(email):
        """Get user by email"""
        try:
            query = "SELECT UserID, Username, Password, FullName, Email, Status FROM Users WHERE Email = ?"
            return DatabaseManager.execute_query(query, (email,), fetch_one=True)
        except Exception as e:
            app_logger.error(f"Get user by email error: {e}")
            return None
    
    @staticmethod
    def username_exists(username):
        """Check if username exists"""
        try:
            query = "SELECT 1 FROM Users WHERE Username = ?"
            result = DatabaseManager.execute_query(query, (username,), fetch_one=True)
            return result is not None
        except Exception as e:
            app_logger.error(f"Username exists error: {e}")
            return False
    
    @staticmethod
    def get_unread_counts(user_id):
        """Get unread message counts for user"""
        try:
            query = """
                SELECT RoomID, COUNT(*) AS UnreadCount
                FROM Messages
                WHERE RoomID IS NOT NULL AND IsRead = 0 AND SenderID != ?
                GROUP BY RoomID
            """
            rows = DatabaseManager.execute_query(query, (user_id,), fetch_all=True)
            return {row[0]: row[1] for row in rows}
        except Exception as e:
            app_logger.error(f"Get unread counts error: {e}")
            return {}
    
    @staticmethod
    def get_user_by_oauth(provider, oauth_id):
        """Get user by OAuth provider and ID"""
        try:
            query = "SELECT UserID, FullName, Username, Email FROM Users WHERE OAuthProvider = ? AND OAuthId = ?"
            return DatabaseManager.execute_query(query, (provider, oauth_id), fetch_one=True)
        except Exception as e:
            app_logger.error(f"Get user by OAuth error: {e}")
            return None
    
    @staticmethod
    def create_oauth_user(provider, oauth_id, email, full_name):
        """Create OAuth user"""
        try:
            import secrets
            from werkzeug.security import generate_password_hash
            
            username_base = email.split('@')[0] if email else provider
            username = DatabaseManager.generate_unique_username(username_base)
            password_hash = generate_password_hash(secrets.token_urlsafe(16))
            
            query = """
                INSERT INTO Users (Username, FullName, Email, Password, Status, IsVerified, OAuthProvider, OAuthId)
                VALUES (?, ?, ?, ?, 'Offline', 1, ?, ?)
            """
            DatabaseManager.execute_query(query, (username, full_name, email, password_hash, provider, oauth_id))
            
            # Get the created user
            return DatabaseManager.get_user_by_oauth(provider, oauth_id)
        except Exception as e:
            app_logger.error(f"Create OAuth user error: {e}")
            return None
    
    @staticmethod
    def generate_unique_username(base):
        """Generate unique username"""
        if not base:
            base = 'user'
        base = ''.join(ch for ch in base if ch.isalnum()).lower() or 'user'
        candidate = base
        suffix = 1
        while DatabaseManager.username_exists(candidate):
            candidate = f"{base}{suffix}"
            suffix += 1
        return candidate
    
    @staticmethod
    def get_group_rooms(user_id):
        """Get group rooms for user"""
        try:
            query = """
                SELECT r.RoomID,
                       r.RoomName,
                       r.GroupAvatar,
                       COALESCE(last.LastMessage, 'Chưa có tin nhắn') AS LastMessage,
                       last.LastSentAt,
                       COALESCE(unread.UnreadCount, 0) AS UnreadCount
                FROM Rooms r
                OUTER APPLY (
                    SELECT TOP 1 CASE WHEN MessageType = 'Image' THEN '[Ảnh]' ELSE Content END AS LastMessage,
                                   SentAt AS LastSentAt
                    FROM Messages m
                    WHERE m.RoomID = r.RoomID
                    ORDER BY SentAt DESC
                ) last
                LEFT JOIN (
                    SELECT RoomID, COUNT(*) AS UnreadCount
                    FROM Messages
                    WHERE IsRead = 0 AND SenderID != ?
                    GROUP BY RoomID
                ) unread ON unread.RoomID = r.RoomID
                WHERE r.IsGroup = 1
                ORDER BY last.LastSentAt DESC
            """
            rows = DatabaseManager.execute_query(query, (user_id,), fetch_all=True)
            rooms = []
            for row in rows:
                last_sent = row[4].strftime('%H:%M') if row[4] else ''
                rooms.append({
                    'room_id': row[0],
                    'room_name': row[1],
                    'group_avatar': row[2],
                    'last_message': row[3],
                    'last_sent_at': last_sent,
                    'unread_count': row[5]
                })
            return rooms
        except Exception as e:
            app_logger.error(f"Get group rooms error: {e}")
            return []
    
    @staticmethod
    def get_private_rooms(user_id):
        """Get private rooms for user"""
        try:
            query = """
                  SELECT r.RoomID,
                      r.RoomName,
                      u.UserID AS OtherUserID,
                      u.FullName AS OtherUserName,
                       COALESCE(last.LastMessage, 'Chưa có tin nhắn') AS LastMessage,
                       last.LastSentAt,
                       COALESCE(unread.UnreadCount, 0) AS UnreadCount
                FROM Rooms r
                JOIN RoomParticipants rp2 ON rp2.RoomID = r.RoomID AND rp2.UserID = ?
                JOIN RoomParticipants rp ON rp.RoomID = r.RoomID AND rp.UserID != ?
                JOIN Users u ON u.UserID = rp.UserID
                OUTER APPLY (
                    SELECT TOP 1 CASE WHEN MessageType = 'Image' THEN '[Ảnh]' ELSE Content END AS LastMessage,
                                   SentAt AS LastSentAt
                    FROM Messages m
                    WHERE m.RoomID = r.RoomID
                    ORDER BY SentAt DESC
                ) last
                LEFT JOIN (
                    SELECT RoomID, COUNT(*) AS UnreadCount
                    FROM Messages
                    WHERE IsRead = 0 AND SenderID != ?
                    GROUP BY RoomID
                ) unread ON unread.RoomID = r.RoomID
                WHERE r.IsGroup = 0
                ORDER BY last.LastSentAt DESC
            """
            rows = DatabaseManager.execute_query(query, (user_id, user_id, user_id), fetch_all=True)
            rooms = []
            for row in rows:
                last_sent = row[5].strftime('%H:%M') if row[5] else ''
                rooms.append({
                    'room_id': row[0],
                    'room_name': row[1],
                    'other_user_id': row[2],
                    'display_name': row[3],
                    'last_message': row[4],
                    'last_sent_at': last_sent,
                    'unread_count': row[6]
                })
            return rooms
        except Exception as e:
            app_logger.error(f"Get private rooms error: {e}")
            return []
    
    @staticmethod
    def create_group_room(user_id, group_name):
        """Create a new group room"""
        if not group_name or not group_name.strip():
            return None
        try:
            # Insert room
            query = "INSERT INTO Rooms (RoomName, IsGroup) VALUES (?, 1)"
            DatabaseManager.execute_query(query, (group_name.strip(),))
            
            # Get the room ID
            query = "SELECT CAST(SCOPE_IDENTITY() AS INT) AS RoomID"
            row = DatabaseManager.execute_query(query, fetch_one=True)
            room_id = row[0] if row else None
            
            if room_id:
                # Add user to room
                query = "INSERT INTO RoomParticipants (RoomID, UserID) VALUES (?, ?)"
                DatabaseManager.execute_query(query, (room_id, user_id))
            
            return room_id
        except Exception as e:
            app_logger.error(f"Create group room error: {e}")
            return None
    
    @staticmethod
    def get_or_create_private_room(user_id, target_user_id):
        """Get or create private room between two users"""
        try:
            user_id = int(user_id)
            target_user_id = int(target_user_id)
        except Exception:
            return None
        
        if user_id == target_user_id:
            return None
        
        first_id, second_id = sorted([user_id, target_user_id])
        room_name = f"private_{first_id}_{second_id}"
        
        try:
            # Check if room exists
            query = "SELECT RoomID FROM Rooms WHERE IsGroup = 0 AND RoomName = ?"
            existing = DatabaseManager.execute_query(query, (room_name,), fetch_one=True)
            
            if existing:
                room_id = existing[0]
            else:
                # Create new room
                query = "INSERT INTO Rooms (RoomName, IsGroup) VALUES (?, 0)"
                DatabaseManager.execute_query(query, (room_name,))
                
                query = "SELECT CAST(SCOPE_IDENTITY() AS INT)"
                row = DatabaseManager.execute_query(query, fetch_one=True)
                room_id = int(row[0]) if row and row[0] is not None else None
            
            if room_id is None:
                raise ValueError('Could not get RoomID when creating private room')
            
            # Add participants
            for participant_id in (user_id, target_user_id):
                query = "SELECT 1 FROM RoomParticipants WHERE RoomID = ? AND UserID = ?"
                if not DatabaseManager.execute_query(query, (room_id, participant_id), fetch_one=True):
                    query = "INSERT INTO RoomParticipants(RoomID, UserID) VALUES (?, ?)"
                    DatabaseManager.execute_query(query, (room_id, participant_id))
            
            # Get target user name
            query = "SELECT FullName FROM Users WHERE UserID = ?"
            target_user = DatabaseManager.execute_query(query, (target_user_id,), fetch_one=True)
            target_name = target_user[0] if target_user else f"User {target_user_id}"
            
            return room_id, f"Chat with {target_name}"
        except Exception as e:
            app_logger.error(f"Get or create private room error: {e}")
            return None
    
    @staticmethod
    def get_analytics_data(export_type):
        """Get analytics data for export"""
        try:
            if export_type == 'users':
                query = """
                    SELECT UserID, FullName, Username, Email, Status, CreatedAt
                    FROM Users
                    ORDER BY CreatedAt DESC
                """
            elif export_type == 'messages':
                query = """
                    SELECT m.MessageID, m.Content, m.MessageType, m.SentAt,
                           u.Username as SenderName
                    FROM Messages m
                    JOIN Users u ON m.SenderID = u.UserID
                    ORDER BY m.SentAt DESC
                """
            elif export_type == 'rooms':
                query = """
                    SELECT RoomID, RoomName, IsGroup, CreatedAt
                    FROM Rooms
                    ORDER BY CreatedAt DESC
                """
            elif export_type == 'files':
                query = """
                    SELECT f.FileID, f.FileName, f.FileType, f.FileSize, f.UploadedAt,
                           u.Username as Uploader
                    FROM SharedFiles f
                    JOIN Users u ON f.UploaderID = u.UserID
                    ORDER BY f.UploadedAt DESC
                """
            else:
                return None
            
            return DatabaseManager.execute_query(query, fetch_all=True)
        except Exception as e:
            app_logger.error(f"Get analytics data error: {e}")
            return None
    
    @staticmethod
    def get_room_messages(room_id, limit=100):
        """Get messages for a room"""
        try:
            query = """
                SELECT m.MessageID, m.SenderID, u.FullName as SenderName, m.Content, m.MessageType,
                       m.SentAt, m.IsRead, m.EditedAt, m.IsDeleted, m.DeletedAt
                FROM Messages m
                JOIN Users u ON m.SenderID = u.UserID
                WHERE m.RoomID = ? AND (m.IsDeleted IS NULL OR m.IsDeleted = 0)
                ORDER BY m.SentAt ASC
            """
            messages = DatabaseManager.execute_query(query, (room_id,), fetch_all=True)
            
            result = []
            for msg in messages:
                result.append({
                    'message_id': msg[0],
                    'sender_id': msg[1],
                    'sender_name': msg[2],
                    'content': msg[3],
                    'type': msg[4],
                    'sent_at': msg[5].strftime('%Y-%m-%d %H:%M:%S') if msg[5] else '',
                    'is_read': bool(msg[6]),
                    'edited_at': msg[7].strftime('%Y-%m-%d %H:%M:%S') if msg[7] else None,
                    'is_deleted': bool(msg[8]),
                    'deleted_at': msg[9].strftime('%Y-%m-%d %H:%M:%S') if msg[9] else None
                })
            return result
        except Exception as e:
            app_logger.error(f"Get room messages error: {e}")
            return []
    
    @staticmethod
    def mark_messages_as_read(room_id, user_id):
        """Mark messages as read in a room"""
        try:
            query = "UPDATE Messages SET IsRead = 1 WHERE RoomID = ? AND SenderID != ? AND IsRead = 0"
            return DatabaseManager.execute_query(query, (room_id, user_id))
        except Exception as e:
            app_logger.error(f"Mark messages as read error: {e}")
            return 0
    
    @staticmethod
    def edit_message(message_id, user_id, new_content):
        """Edit a message"""
        try:
            # Check permission
            query = "SELECT SenderID FROM Messages WHERE MessageID = ?"
            message = DatabaseManager.execute_query(query, (message_id,), fetch_one=True)
            
            if not message or message[0] != user_id:
                return False
            
            # Update message
            query = "UPDATE Messages SET Content = ?, EditedAt = GETDATE() WHERE MessageID = ?"
            DatabaseManager.execute_query(query, (new_content, message_id))
            return True
        except Exception as e:
            app_logger.error(f"Edit message error: {e}")
            return False
    
    @staticmethod
    def delete_message(message_id, user_id):
        """Delete a message (soft delete)"""
        try:
            # Check permission
            query = "SELECT SenderID FROM Messages WHERE MessageID = ?"
            message = DatabaseManager.execute_query(query, (message_id,), fetch_one=True)
            
            if not message or message[0] != user_id:
                return False
            
            # Soft delete message
            query = "UPDATE Messages SET IsDeleted = 1, DeletedAt = GETDATE() WHERE MessageID = ?"
            DatabaseManager.execute_query(query, (message_id,))
            return True
        except Exception as e:
            app_logger.error(f"Delete message error: {e}")
            return False
    
    @staticmethod
    def search(query, user_id):
        """Search for groups and users"""
        try:
            pattern = f"%{query}%"
            results = []
            
            # Search groups
            query_sql = "SELECT RoomID, RoomName FROM Rooms WHERE IsGroup = 1 AND RoomName LIKE ?"
            groups = DatabaseManager.execute_query(query_sql, (pattern,), fetch_all=True)
            for group in groups:
                results.append({'id': group[0], 'type': 'Group', 'name': group[1]})
            
            # Search users
            query_sql = "SELECT UserID, FullName, Username FROM Users WHERE UserID != ? AND (FullName LIKE ? OR Username LIKE ?)"
            users = DatabaseManager.execute_query(query_sql, (user_id, pattern, pattern), fetch_all=True)
            for user in users:
                results.append({'id': user[0], 'type': 'User', 'name': user[1]})
            
            return results
        except Exception as e:
            app_logger.error(f"Search error: {e}")
            return []
    
    @staticmethod
    def update_user_profile(user_id, fullname, username, avatar_url=None):
        """Update user profile"""
        try:
            # Update basic info
            query = "UPDATE Users SET FullName = ?, Username = ? WHERE UserID = ?"
            DatabaseManager.execute_query(query, (fullname, username, user_id))
            
            # Update avatar if provided
            if avatar_url:
                # Ensure AvatarUrl column exists
                if not DatabaseManager.column_exists('Users', 'AvatarUrl'):
                    query = "ALTER TABLE Users ADD AvatarUrl NVARCHAR(500) NULL"
                    DatabaseManager.execute_query(query)
                
                query = "UPDATE Users SET AvatarUrl = ? WHERE UserID = ?"
                DatabaseManager.execute_query(query, (avatar_url, user_id))
            
            return True
        except Exception as e:
            app_logger.error(f"Update user profile error: {e}")
            return False
    
    @staticmethod
    def check_user_exists(username, email):
        """Check if user already exists by username or email"""
        try:
            query = "SELECT 1 FROM Users WHERE Username = ? OR Email = ?"
            result = DatabaseManager.execute_query(query, (username, email), fetch_one=True)
            return result is not None
        except Exception as e:
            app_logger.error(f"Check user exists error: {e}")
            return False
    
    @staticmethod
    def register_user(username, fullname, email, password, verification_token=None):
        """Register a new user"""
        try:
            from werkzeug.security import generate_password_hash
            hashed_password = generate_password_hash(password)
            
            query = """
                INSERT INTO Users (Username, FullName, Email, Password, Status, IsVerified, VerificationToken)
                VALUES (?, ?, ?, ?, 'Offline', 0, ?)
            """
            DatabaseManager.execute_query(query, (username, fullname, email, hashed_password, verification_token))
            return True
        except Exception as e:
            app_logger.error(f"Register user error: {e}")
            return False
    
    @staticmethod
    def ensure_shared_files_table():
        """Ensure SharedFiles table exists"""
        try:
            if not DatabaseManager.column_exists('SharedFiles', 'FileID'):
                query = """
                    CREATE TABLE SharedFiles (
                        FileID INT IDENTITY(1,1) PRIMARY KEY,
                        FileName NVARCHAR(255) NOT NULL,
                        OriginalFileName NVARCHAR(255) NOT NULL,
                        FilePath NVARCHAR(500) NOT NULL,
                        FileType NVARCHAR(50) NOT NULL,
                        FileSize INT NOT NULL,
                        UploadedBy INT NOT NULL,
                        UploadedAt DATETIME DEFAULT GETDATE(),
                        RoomID INT NULL,
                        FOREIGN KEY (UploadedBy) REFERENCES Users(UserID),
                        FOREIGN KEY (RoomID) REFERENCES Rooms(RoomID)
                    )
                """
                DatabaseManager.execute_query(query)
        except Exception as e:
            app_logger.error(f"Ensure shared files table error: {e}")
    
    @staticmethod
    def upload_file(unique_filename, original_filename, file_url, file_type, file_size, user_id, room_id=None):
        """Upload file information to database"""
        try:
            DatabaseManager.ensure_shared_files_table()
            
            query = """
                INSERT INTO SharedFiles (FileName, OriginalFileName, FilePath, FileType, FileSize, UploadedBy, RoomID)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            DatabaseManager.execute_query(query, (unique_filename, original_filename, file_url, file_type, file_size, user_id, room_id))
            return True
        except Exception as e:
            app_logger.error(f"Upload file error: {e}")
            return False
    
    @staticmethod
    def get_file_info(file_id):
        """Get file information by ID"""
        try:
            query = """
                SELECT FileName, OriginalFileName, FilePath, FileType, FileSize, UploadedBy
                FROM SharedFiles
                WHERE FileID = ?
            """
            return DatabaseManager.execute_query(query, (file_id,), fetch_one=True)
        except Exception as e:
            app_logger.error(f"Get file info error: {e}")
            return None
    
    @staticmethod
    def get_analytics_overview():
        """Get analytics overview statistics"""
        try:
            stats = {}
            
            # User statistics
            stats['total_users'] = DatabaseManager.execute_query("SELECT COUNT(*) as Total FROM Users", fetch_one=True)[0]
            stats['new_users_today'] = DatabaseManager.execute_query("SELECT COUNT(*) as NewUsers FROM Users WHERE CAST(CreatedAt AS DATE) = CAST(GETDATE() AS DATE)", fetch_one=True)[0]
            stats['new_users_week'] = DatabaseManager.execute_query("SELECT COUNT(*) as NewUsers FROM Users WHERE CAST(CreatedAt AS DATE) >= DATEADD(day, -7, GETDATE())", fetch_one=True)[0]
            stats['new_users_month'] = DatabaseManager.execute_query("SELECT COUNT(*) as NewUsers FROM Users WHERE CAST(CreatedAt AS DATE) >= DATEADD(day, -30, GETDATE())", fetch_one=True)[0]
            
            # Message statistics
            stats['total_messages'] = DatabaseManager.execute_query("SELECT COUNT(*) as Total FROM Messages", fetch_one=True)[0]
            stats['messages_today'] = DatabaseManager.execute_query("SELECT COUNT(*) as Today FROM Messages WHERE CAST(SentAt AS DATE) = CAST(GETDATE() AS DATE)", fetch_one=True)[0]
            stats['messages_week'] = DatabaseManager.execute_query("SELECT COUNT(*) as Week FROM Messages WHERE CAST(SentAt AS DATE) >= DATEADD(day, -7, GETDATE())", fetch_one=True)[0]
            stats['messages_month'] = DatabaseManager.execute_query("SELECT COUNT(*) as Month FROM Messages WHERE CAST(SentAt AS DATE) >= DATEADD(day, -30, GETDATE())", fetch_one=True)[0]
            
            # Room statistics
            stats['total_rooms'] = DatabaseManager.execute_query("SELECT COUNT(*) as Total FROM Rooms", fetch_one=True)[0]
            stats['total_groups'] = DatabaseManager.execute_query("SELECT COUNT(*) as Groups FROM Rooms WHERE IsGroup = 1", fetch_one=True)[0]
            stats['new_rooms_today'] = DatabaseManager.execute_query("SELECT COUNT(*) as NewRooms FROM Rooms WHERE CAST(CreatedAt AS DATE) = CAST(GETDATE() AS DATE)", fetch_one=True)[0]
            
            # File statistics
            stats['total_files'] = DatabaseManager.execute_query("SELECT COUNT(*) as Total FROM SharedFiles", fetch_one=True)[0]
            stats['files_today'] = DatabaseManager.execute_query("SELECT COUNT(*) as Today FROM SharedFiles WHERE CAST(UploadedAt AS DATE) = CAST(GETDATE() AS DATE)", fetch_one=True)[0]
            result = DatabaseManager.execute_query("SELECT SUM(FileSize) as TotalSize FROM SharedFiles", fetch_one=True)
            stats['total_file_size'] = result[0] if result[0] else 0
            
            # Online users
            stats['online_users'] = DatabaseManager.execute_query("SELECT COUNT(*) as Online FROM Users WHERE Status = 'Online'", fetch_one=True)[0]
            
            return stats
        except Exception as e:
            app_logger.error(f"Get analytics overview error: {e}")
            return {}
    
    @staticmethod
    def get_analytics_user_activity(days=30):
        """Get user activity analytics"""
        try:
            # User activity by date
            query = """
                SELECT CAST(CreatedAt AS DATE) as Date, COUNT(*) as NewUsers
                FROM Users
                WHERE CAST(CreatedAt AS DATE) >= DATEADD(day, -?, GETDATE())
                GROUP BY CAST(CreatedAt AS DATE)
                ORDER BY Date DESC
            """
            user_activity = DatabaseManager.execute_query(query, (days,), fetch_all=True)
            
            # Message activity by date
            query = """
                SELECT CAST(SentAt AS DATE) as Date, COUNT(*) as MessageCount
                FROM Messages
                WHERE CAST(SentAt AS DATE) >= DATEADD(day, -?, GETDATE())
                GROUP BY CAST(SentAt AS DATE)
                ORDER BY Date DESC
            """
            message_activity = DatabaseManager.execute_query(query, (days,), fetch_all=True)
            
            # Top 10 active users
            query = """
                SELECT TOP 10 u.FullName, COUNT(m.MessageID) as MessageCount
                FROM Users u
                LEFT JOIN Messages m ON u.UserID = m.SenderID
                WHERE m.SentAt >= DATEADD(day, -?, GETDATE())
                GROUP BY u.UserID, u.FullName
                ORDER BY MessageCount DESC
            """
            top_users = DatabaseManager.execute_query(query, (days,), fetch_all=True)
            
            return {
                'user_activity': [{'date': ua[0].strftime('%Y-%m-%d') if ua[0] else '', 'new_users': ua[1]} for ua in user_activity],
                'message_activity': [{'date': ma[0].strftime('%Y-%m-%d') if ma[0] else '', 'message_count': ma[1]} for ma in message_activity],
                'top_users': [{'name': tu[0], 'message_count': tu[1]} for tu in top_users]
            }
        except Exception as e:
            app_logger.error(f"Get analytics user activity error: {e}")
            return {'user_activity': [], 'message_activity': [], 'top_users': []}
    
    @staticmethod
    def get_analytics_room_stats(days=30):
        """Get room statistics analytics"""
        try:
            # Top 10 active rooms
            query = """
                SELECT TOP 10 r.RoomName, COUNT(m.MessageID) as MessageCount,
                       COUNT(DISTINCT m.SenderID) as ActiveUsers
                FROM Rooms r
                LEFT JOIN Messages m ON r.RoomID = m.RoomID
                WHERE m.SentAt >= DATEADD(day, -?, GETDATE())
                GROUP BY r.RoomID, r.RoomName
                ORDER BY MessageCount DESC
            """
            top_rooms = DatabaseManager.execute_query(query, (days,), fetch_all=True)
            
            # Room type statistics
            query = """
                SELECT CASE WHEN IsGroup = 1 THEN 'Group' ELSE 'Private' END as RoomType,
                       COUNT(*) as Count
                FROM Rooms
                GROUP BY IsGroup
            """
            room_types = DatabaseManager.execute_query(query, fetch_all=True)
            
            # Room creation by date
            query = """
                SELECT CAST(CreatedAt AS DATE) as Date, COUNT(*) as NewRooms
                FROM Rooms
                WHERE CAST(CreatedAt AS DATE) >= DATEADD(day, -?, GETDATE())
                GROUP BY CAST(CreatedAt AS DATE)
                ORDER BY Date DESC
            """
            room_creation = DatabaseManager.execute_query(query, (days,), fetch_all=True)
            
            return {
                'top_rooms': [{'name': tr[0], 'message_count': tr[1], 'active_users': tr[2]} for tr in top_rooms],
                'room_types': [{'type': rt[0], 'count': rt[1]} for rt in room_types],
                'room_creation': [{'date': rc[0].strftime('%Y-%m-%d') if rc[0] else '', 'new_rooms': rc[1]} for rc in room_creation]
            }
        except Exception as e:
            app_logger.error(f"Get analytics room stats error: {e}")
            return {'top_rooms': [], 'room_types': [], 'room_creation': []}
    
    @staticmethod
    def get_analytics_file_stats(days=30):
        """Get file statistics analytics"""
        try:
            # File statistics by type
            query = """
                SELECT FileType, COUNT(*) as Count, SUM(FileSize) as TotalSize
                FROM SharedFiles
                WHERE UploadedAt >= DATEADD(day, -?, GETDATE())
                GROUP BY FileType
                ORDER BY Count DESC
            """
            file_types = DatabaseManager.execute_query(query, (days,), fetch_all=True)
            
            # File uploads by date
            query = """
                SELECT CAST(UploadedAt AS DATE) as Date, COUNT(*) as FileCount,
                       SUM(FileSize) as TotalSize
                FROM SharedFiles
                WHERE CAST(UploadedAt AS DATE) >= DATEADD(day, -?, GETDATE())
                GROUP BY CAST(UploadedAt AS DATE)
                ORDER BY Date DESC
            """
            file_uploads = DatabaseManager.execute_query(query, (days,), fetch_all=True)
            
            # Top 10 uploaders
            query = """
                SELECT TOP 10 u.FullName, COUNT(sf.FileID) as FileCount,
                       SUM(sf.FileSize) as TotalSize
                FROM Users u
                LEFT JOIN SharedFiles sf ON u.UserID = sf.UploadedBy
                WHERE sf.UploadedAt >= DATEADD(day, -?, GETDATE())
                GROUP BY u.UserID, u.FullName
                ORDER BY FileCount DESC
            """
            top_uploaders = DatabaseManager.execute_query(query, (days,), fetch_all=True)
            
            return {
                'file_types': [{'type': ft[0], 'count': ft[1], 'total_size': ft[2]} for ft in file_types],
                'file_uploads': [{'date': fu[0].strftime('%Y-%m-%d') if fu[0] else '', 'file_count': fu[1], 'total_size': fu[2]} for fu in file_uploads],
                'top_uploaders': [{'name': tu[0], 'file_count': tu[1], 'total_size': tu[2]} for tu in top_uploaders]
            }
        except Exception as e:
            app_logger.error(f"Get analytics file stats error: {e}")
            return {'file_types': [], 'file_uploads': [], 'top_uploaders': []}
    
    @staticmethod
    def verify_email_token(token):
        """Verify email token"""
        try:
            query = "SELECT UserID FROM Users WHERE VerificationToken = ?"
            user = DatabaseManager.execute_query(query, (token,), fetch_one=True)
            
            if not user:
                return False
            
            user_id = user[0]
            query = "UPDATE Users SET IsVerified = 1, VerificationToken = NULL WHERE UserID = ?"
            DatabaseManager.execute_query(query, (user_id,))
            return True
        except Exception as e:
            app_logger.error(f"Verify email token error: {e}")
            return False
    
    @staticmethod
    def set_password_reset_token(email, token, expires_at):
        """Set password reset token for user"""
        try:
            query = "UPDATE Users SET ResetToken = ?, ResetTokenExpiresAt = ? WHERE Email = ?"
            DatabaseManager.execute_query(query, (token, expires_at, email))
            return True
        except Exception as e:
            app_logger.error(f"Set password reset token error: {e}")
            return False
    
    @staticmethod
    def reset_password_with_token(token, new_password):
        """Reset password using token"""
        try:
            from werkzeug.security import generate_password_hash
            from datetime import datetime
            
            query = "SELECT UserID, ResetTokenExpiresAt FROM Users WHERE ResetToken = ?"
            user = DatabaseManager.execute_query(query, (token,), fetch_one=True)
            
            if not user or not user[1] or user[1] < datetime.now():
                return False
            
            user_id = user[0]
            hashed_password = generate_password_hash(new_password)
            query = "UPDATE Users SET Password = ?, ResetToken = NULL, ResetTokenExpiresAt = NULL, IsVerified = 1 WHERE UserID = ?"
            DatabaseManager.execute_query(query, (hashed_password, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Reset password with token error: {e}")
            return False
    
    @staticmethod
    def update_user_oauth(email, provider, oauth_id):
        """Update user OAuth information"""
        try:
            query = "UPDATE Users SET OAuthProvider = ?, OAuthId = ?, IsVerified = 1 WHERE Email = ?"
            DatabaseManager.execute_query(query, (provider, oauth_id, email))
            return True
        except Exception as e:
            app_logger.error(f"Update user OAuth error: {e}")
            return False
    
    @staticmethod
    def get_online_users():
        """Get list of online users"""
        try:
            query = """
                SELECT UserID, FullName, Status
                FROM Users
                WHERE Status = 'Online'
                ORDER BY FullName
            """
            users = DatabaseManager.execute_query(query, fetch_all=True)
            return [{'user_id': user[0], 'user_name': user[1], 'status': user[2]} for user in users]
        except Exception as e:
            app_logger.error(f"Get online users error: {e}")
            return []
    
    @staticmethod
    def update_notification_enabled(user_id, enabled):
        """Update notification enabled status for user"""
        try:
            # Ensure NotificationEnabled column exists
            if not DatabaseManager.column_exists('Users', 'NotificationEnabled'):
                query = "ALTER TABLE Users ADD NotificationEnabled BIT NOT NULL DEFAULT 1"
                DatabaseManager.execute_query(query)
            
            query = "UPDATE Users SET NotificationEnabled = ? WHERE UserID = ?"
            DatabaseManager.execute_query(query, (enabled, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Update notification enabled error: {e}")
            return False
    
    @staticmethod
    def ensure_notifications_table():
        """Ensure Notifications table exists"""
        try:
            if not DatabaseManager.column_exists('Notifications', 'NotificationID'):
                query = """
                    CREATE TABLE Notifications (
                        NotificationID INT IDENTITY(1,1) PRIMARY KEY,
                        UserID INT NOT NULL,
                        Title NVARCHAR(255) NOT NULL,
                        Message NVARCHAR(1000) NOT NULL,
                        Type NVARCHAR(50) NOT NULL,
                        IsRead BIT NOT NULL DEFAULT 0,
                        CreatedAt DATETIME DEFAULT GETDATE(),
                        FOREIGN KEY (UserID) REFERENCES Users(UserID)
                    )
                """
                DatabaseManager.execute_query(query)
        except Exception as e:
            app_logger.error(f"Ensure notifications table error: {e}")
    
    @staticmethod
    def create_notification(user_id, title, message, notification_type):
        """Create a notification"""
        try:
            DatabaseManager.ensure_notifications_table()
            query = """
                INSERT INTO Notifications (UserID, Title, Message, Type)
                VALUES (?, ?, ?, ?)
            """
            DatabaseManager.execute_query(query, (user_id, title, message, notification_type))
            return True
        except Exception as e:
            app_logger.error(f"Create notification error: {e}")
            return False
    
    @staticmethod
    def get_user_notifications(user_id):
        """Get notifications for a user"""
        try:
            query = """
                SELECT NotificationID, Title, Message, Type, IsRead, CreatedAt
                FROM Notifications
                WHERE UserID = ?
                ORDER BY CreatedAt DESC
            """
            notifications = DatabaseManager.execute_query(query, (user_id,), fetch_all=True)
            return [{
                'notification_id': notif[0],
                'title': notif[1],
                'message': notif[2],
                'type': notif[3],
                'is_read': bool(notif[4]),
                'created_at': notif[5].strftime('%Y-%m-%d %H:%M:%S') if notif[5] else ''
            } for notif in notifications]
        except Exception as e:
            app_logger.error(f"Get user notifications error: {e}")
            return []
    
    @staticmethod
    def mark_notification_read(notification_id, user_id):
        """Mark notification as read"""
        try:
            query = """
                UPDATE Notifications
                SET IsRead = 1
                WHERE NotificationID = ? AND UserID = ?
            """
            DatabaseManager.execute_query(query, (notification_id, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Mark notification read error: {e}")
            return False
    
    @staticmethod
    def is_room_admin(room_id, user_id):
        """Check if user is admin of a room"""
        try:
            # Prefer role stored in RoomRoles (newer table)
            DatabaseManager.ensure_room_roles_table()
            rr_query = "SELECT Role FROM RoomRoles WHERE RoomID = ? AND UserID = ?"
            rr = DatabaseManager.execute_query(rr_query, (room_id, user_id), fetch_one=True)
            if rr and rr[0] == 'Admin':
                return True

            # Fallback: check RoomParticipants.Role column for backward compatibility
            query = """
                SELECT COUNT(*) as IsAdmin
                FROM RoomParticipants
                WHERE RoomID = ? AND UserID = ? AND Role = 'Admin'
            """
            result = DatabaseManager.execute_query(query, (room_id, user_id), fetch_one=True)
            return result[0] > 0 if result else False
        except Exception as e:
            app_logger.error(f"Is room admin error: {e}")
            return False
    
    @staticmethod
    def user_exists(user_id):
        """Check if user exists"""
        try:
            query = "SELECT COUNT(*) FROM Users WHERE UserID = ?"
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            return result[0] > 0 if result else False
        except Exception as e:
            app_logger.error(f"User exists error: {e}")
            return False

@staticmethod
def create_notification(user_id, title, message, notification_type):
    """Create a notification"""
    try:
        DatabaseManager.ensure_notifications_table()
        query = """
            INSERT INTO Notifications (UserID, Title, Message, Type)
            VALUES (?, ?, ?, ?)
        """
        DatabaseManager.execute_query(query, (user_id, title, message, notification_type))
        return True
    except Exception as e:
        app_logger.error(f"Create notification error: {e}")
        return False

@staticmethod
def get_user_notifications(user_id):
    """Get notifications for a user"""
    try:
        query = """
            SELECT NotificationID, Title, Message, Type, IsRead, CreatedAt
            FROM Notifications
            WHERE UserID = ?
            ORDER BY CreatedAt DESC
        """
        notifications = DatabaseManager.execute_query(query, (user_id,), fetch_all=True)
        return [{
            'notification_id': notif[0],
            'title': notif[1],
            'message': notif[2],
            'type': notif[3],
            'is_read': bool(notif[4]),
            'created_at': notif[5].strftime('%Y-%m-%d %H:%M:%S') if notif[5] else ''
        } for notif in notifications]
    except Exception as e:
        app_logger.error(f"Get user notifications error: {e}")
        return []

@staticmethod
def mark_notification_read(notification_id, user_id):
    """Mark notification as read"""
    try:
        query = """
            UPDATE Notifications
            SET IsRead = 1
            WHERE NotificationID = ? AND UserID = ?
        """
        DatabaseManager.execute_query(query, (notification_id, user_id))
        return True
    except Exception as e:
        app_logger.error(f"Mark notification read error: {e}")
        return False

@staticmethod
def is_room_admin(room_id, user_id):
    """Check if user is admin of a room"""
    try:
        # Prefer role stored in RoomRoles (newer table)
        DatabaseManager.ensure_room_roles_table()
        rr_query = "SELECT Role FROM RoomRoles WHERE RoomID = ? AND UserID = ?"
        rr = DatabaseManager.execute_query(rr_query, (room_id, user_id), fetch_one=True)
        if rr and rr[0] == 'Admin':
            return True

        # Fallback: check RoomParticipants.Role column for backward compatibility
        query = """
            SELECT COUNT(*) as IsAdmin
            FROM RoomParticipants
            WHERE RoomID = ? AND UserID = ? AND Role = 'Admin'
        """
        result = DatabaseManager.execute_query(query, (room_id, user_id), fetch_one=True)
        return result[0] > 0 if result else False
    except Exception as e:
        app_logger.error(f"Is room admin error: {e}")
        return False

@staticmethod
def user_exists(user_id):
    """Check if user exists"""
    try:
        query = "SELECT COUNT(*) FROM Users WHERE UserID = ?"
        result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
        return result[0] > 0 if result else False
    except Exception as e:
        app_logger.error(f"User exists error: {e}")
        return False

@staticmethod
def save_message(user_id, content, msg_type='Text', room_id=1, reply_to_message_id=None):
    """Lưu tin nhắn vào database"""
    try:
        query = """
            INSERT INTO Messages (SenderID, Content, MessageType, RoomID, ReplyToMessageID, SentAt, IsRead)
            VALUES (?, ?, ?, ?, ?, GETDATE(), 0)
        """
        DatabaseManager.execute_query(query, (user_id, content, msg_type, room_id, reply_to_message_id))
        return True
    except Exception as e:
        app_logger.error(f"Save message error: {e}")
        return False

@staticmethod
def save_forwarded_message(user_id, original_message_id, target_room_id):
    """Lưu forwarded message vào database"""
    try:
        # Get original message
        original_query = """
            SELECT Content, MessageType, SenderID
            FROM Messages
            WHERE MessageID = ?
        """
        original = DatabaseManager.execute_query(original_query, (original_message_id,), fetch_one=True)
        
        if not original:
            return False
        
        content = original[0]
        msg_type = original[1]
        original_sender_id = original[2]
        
        # Check if ForwardedFromMessageID column exists
        if not DatabaseManager.column_exists('Messages', 'ForwardedFromMessageID'):
            query = "ALTER TABLE Messages ADD ForwardedFromMessageID INT NULL"
            DatabaseManager.execute_query(query)
        
        # Insert forwarded message
        query = """
            INSERT INTO Messages (SenderID, Content, MessageType, RoomID, ForwardedFromMessageID, SentAt, IsRead)
            VALUES (?, ?, ?, ?, ?, GETDATE(), 0)
        """
        DatabaseManager.execute_query(query, (user_id, content, msg_type, target_room_id, original_message_id))
        return True
    except Exception as e:
        app_logger.error(f"Save forwarded message error: {e}")
        return False

    @staticmethod
    def update_email_notification_enabled(user_id, enabled):
        """Cập nhật trạng thái email notification của user"""
        try:
            # Check if EmailNotificationEnabled column exists
            if not DatabaseManager.column_exists('Users', 'EmailNotificationEnabled'):
                query = "ALTER TABLE Users ADD EmailNotificationEnabled BIT DEFAULT 0"
                DatabaseManager.execute_query(query)
            
            query = "UPDATE Users SET EmailNotificationEnabled = ? WHERE UserID = ?"
            DatabaseManager.execute_query(query, (1 if enabled else 0, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Update email notification enabled error: {e}")
            return False

    @staticmethod
    def get_email_notification_enabled(user_id):
        """Lấy trạng thái email notification của user"""
        try:
            # Check if column exists
            if not DatabaseManager.column_exists('Users', 'EmailNotificationEnabled'):
                return False
            
            query = "SELECT EmailNotificationEnabled FROM Users WHERE UserID = ?"
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            return bool(result[0]) if result and result[0] is not None else False
        except Exception as e:
            app_logger.error(f"Get email notification enabled error: {e}")
            return False

    @staticmethod
    def get_users_with_email_notification_enabled(room_id):
        """Lấy danh sách users trong phòng có bật email notification"""
        try:
            query = """
                SELECT u.UserID, u.Email, u.FullName
                FROM Users u
                JOIN RoomParticipants rp ON u.UserID = rp.UserID
                WHERE rp.RoomID = ? 
                AND u.Email IS NOT NULL 
                AND u.Email != ''
                AND u.EmailNotificationEnabled = 1
            """
            users = DatabaseManager.execute_query(query, (room_id,), fetch_all=True)
            return [{
                'user_id': user[0],
                'email': user[1],
                'full_name': user[2]
            } for user in users]
        except Exception as e:
            app_logger.error(f"Get users with email notification enabled error: {e}")
            return []

@staticmethod
def remove_member_from_group(room_id, user_id):
    """Remove member from group"""
    try:
        query = """
            DELETE FROM RoomParticipants
            WHERE RoomID = ? AND UserID = ?
        """
        DatabaseManager.execute_query(query, (room_id, user_id))
        return True
    except Exception as e:
        app_logger.error(f"Remove member from group error: {e}")
        return False

@staticmethod
def update_group_info(room_id, room_name, description=None):
    """Update group information"""
    try:
        # Ensure Rooms table has necessary columns
        if not DatabaseManager.column_exists('Rooms', 'Description'):
            DatabaseManager.execute_query("ALTER TABLE Rooms ADD Description NVARCHAR(500) NULL")
        
        if not DatabaseManager.column_exists('Rooms', 'AvatarUrl'):
            DatabaseManager.execute_query("ALTER TABLE Rooms ADD AvatarUrl NVARCHAR(500) NULL")
        
        query = """
            UPDATE Rooms
            SET RoomName = ?, Description = ?
            WHERE RoomID = ?
        """
        DatabaseManager.execute_query(query, (room_name, description, room_id))
        return True
    except Exception as e:
        app_logger.error(f"Update group info error: {e}")
        return False

    @staticmethod
    def create_group_invite(room_id, inviter_id, invitee_id):
        """Tạo group invite"""
        try:
            # Check if GroupInvites table exists
            if not DatabaseManager.table_exists('GroupInvites'):
                query = """
                    CREATE TABLE GroupInvites (
                        InviteID INT IDENTITY(1,1) PRIMARY KEY,
                        RoomID INT NOT NULL,
                        InviterID INT NOT NULL,
                        InviteeID INT NOT NULL,
                        Status NVARCHAR(50) DEFAULT 'Pending',
                        CreatedAt DATETIME DEFAULT GETDATE(),
                        FOREIGN KEY (RoomID) REFERENCES Rooms(RoomID),
                        FOREIGN KEY (InviterID) REFERENCES Users(UserID),
                        FOREIGN KEY (InviteeID) REFERENCES Users(UserID)
                    )
                """
                DatabaseManager.execute_query(query)
            
            # Check if invite already exists
            check_query = """
                SELECT InviteID FROM GroupInvites 
                WHERE RoomID = ? AND InviteeID = ? AND Status = 'Pending'
            """
            existing = DatabaseManager.execute_query(check_query, (room_id, invitee_id), fetch_one=True)
            if existing:
                return False  # Invite already exists
            
            # Create invite
            query = """
                INSERT INTO GroupInvites (RoomID, InviterID, InviteeID, Status, CreatedAt)
                VALUES (?, ?, ?, 'Pending', GETDATE())
            """
            DatabaseManager.execute_query(query, (room_id, inviter_id, invitee_id))
            return True
        except Exception as e:
            app_logger.error(f"Create group invite error: {e}")
            return False

    @staticmethod
    def get_pending_invites(user_id):
        """Lấy danh sách pending invites của user"""
        try:
            query = """
                SELECT gi.InviteID, gi.RoomID, gi.InviterID, gi.CreatedAt,
                       r.RoomName, r.AvatarUrl, u.FullName as InviterName
                FROM GroupInvites gi
                JOIN Rooms r ON gi.RoomID = r.RoomID
                JOIN Users u ON gi.InviterID = u.UserID
                WHERE gi.InviteeID = ? AND gi.Status = 'Pending'
                ORDER BY gi.CreatedAt DESC
            """
            invites = DatabaseManager.execute_query(query, (user_id,), fetch_all=True)
            return [{
                'invite_id': invite[0],
                'room_id': invite[1],
                'inviter_id': invite[2],
                'created_at': invite[3],
                'room_name': invite[4],
                'room_avatar': invite[5],
                'inviter_name': invite[6]
            } for invite in invites]
        except Exception as e:
            app_logger.error(f"Get pending invites error: {e}")
            return []

    @staticmethod
    def accept_decline_invite(invite_id, user_id, action):
        """Chấp nhận hoặc từ chối group invite"""
        try:
            # Get invite info
            query = """
                SELECT RoomID, InviteeID FROM GroupInvites 
                WHERE InviteID = ? AND InviteeID = ? AND Status = 'Pending'
            """
            invite = DatabaseManager.execute_query(query, (invite_id, user_id), fetch_one=True)
            
            if not invite:
                return False
            
            room_id = invite[0]
            
            if action == 'accept':
                # Add user to group
                DatabaseManager.add_member_to_group(room_id, user_id)
            
            # Update invite status
            update_query = """
                UPDATE GroupInvites 
                SET Status = ? 
                WHERE InviteID = ?
            """
            DatabaseManager.execute_query(update_query, ('Accepted' if action == 'accept' else 'Declined', invite_id))
            return True
        except Exception as e:
            app_logger.error(f"Accept/decline invite error: {e}")
            return False

@staticmethod
def is_room_member(room_id, user_id):
    """Check if user is member of a room"""
    try:
        query = """
            SELECT COUNT(*) as IsMember
            FROM RoomParticipants
            WHERE RoomID = ? AND UserID = ?
        """
        result = DatabaseManager.execute_query(query, (room_id, user_id), fetch_one=True)
        return result[0] > 0 if result else False
    except Exception as e:
        app_logger.error(f"Is room member error: {e}")
        return False

@staticmethod
def get_group_members(room_id):
    """Get group members"""
    try:
        query = """
            SELECT u.UserID, u.FullName, u.Username, rp.Role, rp.JoinedAt, u.Status
            FROM RoomParticipants rp
            JOIN Users u ON rp.UserID = u.UserID
            WHERE rp.RoomID = ?
            ORDER BY rp.Role DESC, u.FullName
        """
        members = DatabaseManager.execute_query(query, (room_id,), fetch_all=True)
        return [{
            'user_id': member[0],
            'full_name': member[1],
            'username': member[2],
            'role': member[3],
            'joined_at': member[4].strftime('%Y-%m-%d %H:%M:%S') if member[4] else '',
            'status': member[5]
        } for member in members]
    except Exception as e:
        app_logger.error(f"Get group members error: {e}")
        return []

@staticmethod
def search_messages_in_room(room_id, query, page=1, limit=20):
    """Search messages in a room"""
    try:
        offset = (page - 1) * limit
        
        # Search messages
        search_query = """
            SELECT m.MessageID, m.SenderID, u.FullName as SenderName, m.Content,
                   m.MessageType, m.SentAt, m.EditedAt, m.IsDeleted
            FROM Messages m
            JOIN Users u ON m.SenderID = u.UserID
            WHERE m.RoomID = ? AND (m.IsDeleted IS NULL OR m.IsDeleted = 0)
              AND (m.Content LIKE ? OR u.FullName LIKE ?)
            ORDER BY m.SentAt DESC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """
        messages = DatabaseManager.execute_query(search_query, (room_id, f"%{query}%", f"%{query}%", offset, limit), fetch_all=True)
        
        # Get total count
        count_query = """
            SELECT COUNT(*) as TotalResults
            FROM Messages m
            JOIN Users u ON m.SenderID = u.UserID
            WHERE m.RoomID = ? AND (m.IsDeleted IS NULL OR m.IsDeleted = 0)
              AND (m.Content LIKE ? OR u.FullName LIKE ?)
        """
        total = DatabaseManager.execute_query(count_query, (room_id, f"%{query}%", f"%{query}%"), fetch_one=True)[0]
        
        return {
            'messages': [{
                'message_id': msg[0],
                'sender_id': msg[1],
                'sender_name': msg[2],
                'content': msg[3],
                'message_type': msg[4],
                'sent_at': msg[5].strftime('%Y-%m-%d %H:%M:%S') if msg[5] else '',
                'edited_at': msg[6].strftime('%Y-%m-%d %H:%M:%S') if msg[6] else None,
                'is_deleted': bool(msg[7])
            } for msg in messages],
            'total': total,
            'page': page,
            'limit': limit
        }
    except Exception as e:
        app_logger.error(f"Search messages in room error: {e}")
        return {'messages': [], 'total': 0, 'page': page, 'limit': limit}

@staticmethod
def global_search_messages(user_id, query, page=1, limit=20):
    """Global search across all user's rooms"""
    try:
        offset = (page - 1) * limit
        
        # Search messages
        search_query = """
            SELECT DISTINCT m.MessageID, m.SenderID, u.FullName as SenderName, m.Content,
                   m.MessageType, m.SentAt, m.RoomID, r.RoomName,
                   CASE WHEN r.IsGroup = 1 THEN r.RoomName ELSE 'Chat riêng' END as RoomDisplayName
            FROM Messages m
            JOIN Users u ON m.SenderID = u.UserID
            JOIN Rooms r ON m.RoomID = r.RoomID
            JOIN RoomParticipants rp ON r.RoomID = rp.RoomID AND rp.UserID = ?
            WHERE (m.IsDeleted IS NULL OR m.IsDeleted = 0)
              AND (m.Content LIKE ? OR u.FullName LIKE ? OR r.RoomName LIKE ?)
            ORDER BY m.SentAt DESC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """
        messages = DatabaseManager.execute_query(search_query, (user_id, f"%{query}%", f"%{query}%", f"%{query}%", offset, limit), fetch_all=True)
        
        # Get total count
        count_query = """
            SELECT COUNT(DISTINCT m.MessageID) as TotalResults
            FROM Messages m
            JOIN Users u ON m.SenderID = u.UserID
            JOIN Rooms r ON m.RoomID = r.RoomID
            JOIN RoomParticipants rp ON r.RoomID = rp.RoomID AND rp.UserID = ?
            WHERE (m.IsDeleted IS NULL OR m.IsDeleted = 0)
              AND (m.Content LIKE ? OR u.FullName LIKE ? OR r.RoomName LIKE ?)
        """
        total = DatabaseManager.execute_query(count_query, (user_id, f"%{query}%", f"%{query}%", f"%{query}%"), fetch_one=True)[0]
        
        return {
            'messages': [{
                'message_id': msg[0],
                'sender_id': msg[1],
                'sender_name': msg[2],
                'content': msg[3],
                'type': msg[4],
                'sent_at': msg[5].strftime('%Y-%m-%d %H:%M:%S') if msg[5] else '',
                'room_id': msg[6],
                'room_name': msg[7],
                'room_display_name': msg[8]
            } for msg in messages],
            'total': total,
            'page': page,
            'limit': limit
        }
    except Exception as e:
        app_logger.error(f"Global search messages error: {e}")
        return {'messages': [], 'total': 0, 'page': page, 'limit': limit}

@staticmethod
def get_search_suggestions(user_id, query):
    """Get search suggestions for users and rooms"""
    try:
        search_query = """
            SELECT DISTINCT 'user' as type, u.FullName as name, u.Username as username
            FROM Users u
            WHERE u.UserID != ? AND (u.FullName LIKE ? OR u.Username LIKE ?)
            UNION ALL
            SELECT DISTINCT 'room' as type, r.RoomName as name, '' as username
            FROM Rooms r
            JOIN RoomParticipants rp ON r.RoomID = rp.RoomID AND rp.UserID = ?
            WHERE r.RoomName LIKE ?
            ORDER BY name
        """
        suggestions = DatabaseManager.execute_query(search_query, (user_id, f"%{query}%", f"%{query}%", user_id, f"%{query}%"), fetch_all=True)
        return [{
            'type': sug[0],
            'name': sug[1],
            'username': sug[2]
        } for sug in suggestions]
    except Exception as e:
        app_logger.error(f"Get search suggestions error: {e}")
        return []
    
    @staticmethod
    def update_group_info(room_id, room_name, description=None):
        """Update group information"""
        try:
            # Ensure Rooms table has necessary columns
            if not DatabaseManager.column_exists('Rooms', 'Description'):
                DatabaseManager.execute_query("ALTER TABLE Rooms ADD Description NVARCHAR(500) NULL")
            
            if not DatabaseManager.column_exists('Rooms', 'AvatarUrl'):
                DatabaseManager.execute_query("ALTER TABLE Rooms ADD AvatarUrl NVARCHAR(500) NULL")
            
            query = """
                UPDATE Rooms
                SET RoomName = ?, Description = ?
                WHERE RoomID = ?
            """
            DatabaseManager.execute_query(query, (room_name, description, room_id))
            return True
        except Exception as e:
            app_logger.error(f"Update group info error: {e}")
            return False
    
    @staticmethod
    def is_room_member(room_id, user_id):
        """Check if user is member of a room"""
        try:
            query = """
                SELECT COUNT(*) as IsMember
                FROM RoomParticipants
                WHERE RoomID = ? AND UserID = ?
            """
            result = DatabaseManager.execute_query(query, (room_id, user_id), fetch_one=True)
            return result[0] > 0 if result else False
        except Exception as e:
            app_logger.error(f"Is room member error: {e}")
            return False
    
    @staticmethod
    def get_group_members(room_id):
        """Get group members"""
        try:
            query = """
                SELECT u.UserID, u.FullName, u.Username, rp.Role, rp.JoinedAt, u.Status
                FROM RoomParticipants rp
                JOIN Users u ON rp.UserID = u.UserID
                WHERE rp.RoomID = ?
                ORDER BY rp.Role DESC, u.FullName
            """
            members = DatabaseManager.execute_query(query, (room_id,), fetch_all=True)
            return [{
                'user_id': member[0],
                'full_name': member[1],
                'username': member[2],
                'role': member[3],
                'joined_at': member[4].strftime('%Y-%m-%d %H:%M:%S') if member[4] else '',
                'status': member[5]
            } for member in members]
        except Exception as e:
            app_logger.error(f"Get group members error: {e}")
            return []
    
    @staticmethod
    def search_messages_in_room(room_id, query, page=1, limit=20):
        """Search messages in a room"""
        try:
            offset = (page - 1) * limit
            
            # Search messages
            search_query = """
                SELECT m.MessageID, m.SenderID, u.FullName as SenderName, m.Content,
                       m.MessageType, m.SentAt, m.EditedAt, m.IsDeleted
                FROM Messages m
                JOIN Users u ON m.SenderID = u.UserID
                WHERE m.RoomID = ? AND (m.IsDeleted IS NULL OR m.IsDeleted = 0)
                  AND (m.Content LIKE ? OR u.FullName LIKE ?)
                ORDER BY m.SentAt DESC
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            """
            messages = DatabaseManager.execute_query(search_query, (room_id, f"%{query}%", f"%{query}%", offset, limit), fetch_all=True)
            
            # Get total count
            count_query = """
                SELECT COUNT(*) as TotalResults
                FROM Messages m
                JOIN Users u ON m.SenderID = u.UserID
                WHERE m.RoomID = ? AND (m.IsDeleted IS NULL OR m.IsDeleted = 0)
                  AND (m.Content LIKE ? OR u.FullName LIKE ?)
            """
            total = DatabaseManager.execute_query(count_query, (room_id, f"%{query}%", f"%{query}%"), fetch_one=True)[0]
            
            return {
                'messages': [{
                    'message_id': msg[0],
                    'sender_id': msg[1],
                    'sender_name': msg[2],
                    'content': msg[3],
                    'message_type': msg[4],
                    'sent_at': msg[5].strftime('%Y-%m-%d %H:%M:%S') if msg[5] else '',
                    'edited_at': msg[6].strftime('%Y-%m-%d %H:%M:%S') if msg[6] else None,
                    'is_deleted': bool(msg[7])
                } for msg in messages],
                'total': total,
                'page': page,
                'limit': limit
            }
        except Exception as e:
            app_logger.error(f"Search messages in room error: {e}")
            return {'messages': [], 'total': 0, 'page': page, 'limit': limit}
    
    @staticmethod
    def global_search_messages(user_id, query, page=1, limit=20):
        """Global search across all user's rooms"""
        try:
            offset = (page - 1) * limit
            
            # Search messages
            search_query = """
                SELECT DISTINCT m.MessageID, m.SenderID, u.FullName as SenderName, m.Content,
                       m.MessageType, m.SentAt, m.RoomID, r.RoomName,
                       CASE WHEN r.IsGroup = 1 THEN r.RoomName ELSE 'Chat riêng' END as RoomDisplayName
                FROM Messages m
                JOIN Users u ON m.SenderID = u.UserID
                JOIN Rooms r ON m.RoomID = r.RoomID
                JOIN RoomParticipants rp ON r.RoomID = rp.RoomID AND rp.UserID = ?
                WHERE (m.IsDeleted IS NULL OR m.IsDeleted = 0)
                  AND (m.Content LIKE ? OR u.FullName LIKE ? OR r.RoomName LIKE ?)
                ORDER BY m.SentAt DESC
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            """
            messages = DatabaseManager.execute_query(search_query, (user_id, f"%{query}%", f"%{query}%", f"%{query}%", offset, limit), fetch_all=True)
            
            # Get total count
            count_query = """
                SELECT COUNT(DISTINCT m.MessageID) as TotalResults
                FROM Messages m
                JOIN Users u ON m.SenderID = u.UserID
                JOIN Rooms r ON m.RoomID = r.RoomID
                JOIN RoomParticipants rp ON r.RoomID = rp.RoomID AND rp.UserID = ?
                WHERE (m.IsDeleted IS NULL OR m.IsDeleted = 0)
                  AND (m.Content LIKE ? OR u.FullName LIKE ? OR r.RoomName LIKE ?)
            """
            total = DatabaseManager.execute_query(count_query, (user_id, f"%{query}%", f"%{query}%", f"%{query}%"), fetch_one=True)[0]
            
            return {
                'messages': [{
                    'message_id': msg[0],
                    'sender_id': msg[1],
                    'sender_name': msg[2],
                    'content': msg[3],
                    'type': msg[4],
                    'sent_at': msg[5].strftime('%Y-%m-%d %H:%M:%S') if msg[5] else '',
                    'room_id': msg[6],
                    'room_name': msg[7],
                    'room_display_name': msg[8]
                } for msg in messages],
                'total': total,
                'page': page,
                'limit': limit
            }
        except Exception as e:
            app_logger.error(f"Global search messages error: {e}")
            return {'messages': [], 'total': 0, 'page': page, 'limit': limit}
    
    @staticmethod
    def get_search_suggestions(user_id, query):
        """Get search suggestions for users and rooms"""
        try:
            search_query = """
                SELECT DISTINCT 'user' as type, u.FullName as name, u.Username as username
                FROM Users u
                WHERE u.UserID != ? AND (u.FullName LIKE ? OR u.Username LIKE ?)
                UNION ALL
                SELECT DISTINCT 'room' as type, r.RoomName as name, '' as username
                FROM Rooms r
                JOIN RoomParticipants rp ON r.RoomID = rp.RoomID AND rp.UserID = ?
                WHERE r.RoomName LIKE ?
                ORDER BY name
                LIMIT 10
            """
            suggestions = DatabaseManager.execute_query(search_query, (user_id, f"%{query}%", f"%{query}%", user_id, f"%{query}%"), fetch_all=True)
            return [{
                'type': sug[0],
                'name': sug[1],
                'username': sug[2]
            } for sug in suggestions]
        except Exception as e:
            app_logger.error(f"Get search suggestions error: {e}")
            return []
    
    @staticmethod
    def set_theme(user_id, theme):
        """Set user theme"""
        try:
            # Ensure Users table has Theme column
            if not DatabaseManager.column_exists('Users', 'Theme'):
                DatabaseManager.execute_query("ALTER TABLE Users ADD Theme NVARCHAR(20) NOT NULL DEFAULT 'light'")
            
            query = """
                UPDATE Users
                SET Theme = ?
                WHERE UserID = ?
            """
            DatabaseManager.execute_query(query, (theme, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Set theme error: {e}")
            return False
    
    @staticmethod
    def get_theme(user_id):
        """Get user theme"""
        try:
            # Ensure Users table has Theme column
            if not DatabaseManager.column_exists('Users', 'Theme'):
                DatabaseManager.execute_query("ALTER TABLE Users ADD Theme NVARCHAR(20) NOT NULL DEFAULT 'light'")
            
            query = """
                SELECT Theme
                FROM Users
                WHERE UserID = ?
            """
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            return result[0] if result else 'light'
        except Exception as e:
            app_logger.error(f"Get theme error: {e}")
            return 'light'
    
    @staticmethod
    def toggle_theme(user_id):
        """Toggle user theme between light and dark"""
        try:
            # Ensure Users table has Theme column
            if not DatabaseManager.column_exists('Users', 'Theme'):
                DatabaseManager.execute_query("ALTER TABLE Users ADD Theme NVARCHAR(20) NOT NULL DEFAULT 'light'")
            
            # Get current theme
            query = """
                SELECT Theme
                FROM Users
                WHERE UserID = ?
            """
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            current_theme = result[0] if result else 'light'
            
            # Toggle theme
            new_theme = 'dark' if current_theme == 'light' else 'light'
            
            # Update theme
            update_query = """
                UPDATE Users
                SET Theme = ?
                WHERE UserID = ?
            """
            DatabaseManager.execute_query(update_query, (new_theme, user_id))
            return new_theme
        except Exception as e:
            app_logger.error(f"Toggle theme error: {e}")
            return 'light'
    
    @staticmethod
    def is_admin(user_id):
        """Check if user is admin"""
        try:
            # Ensure Users table has Role column
            if not DatabaseManager.column_exists('Users', 'Role'):
                DatabaseManager.execute_query("ALTER TABLE Users ADD Role NVARCHAR(20) NOT NULL DEFAULT 'User'")
            
            query = """
                SELECT Role
                FROM Users
                WHERE UserID = ?
            """
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            role = result[0] if result else 'User'
            return role == 'Admin'
        except Exception as e:
            app_logger.error(f"Is admin error: {e}")
            return False
    
    @staticmethod
    def get_admin_dashboard_stats():
        """Get admin dashboard statistics"""
        try:
            # Total counts
            total_users = DatabaseManager.execute_query("SELECT COUNT(*) as TotalUsers FROM Users", fetch_one=True)[0]
            total_rooms = DatabaseManager.execute_query("SELECT COUNT(*) as TotalRooms FROM Rooms", fetch_one=True)[0]
            total_messages = DatabaseManager.execute_query("SELECT COUNT(*) as TotalMessages FROM Messages", fetch_one=True)[0]
            total_files = DatabaseManager.execute_query("SELECT COUNT(*) as TotalFiles FROM SharedFiles", fetch_one=True)[0]
            
            # Online users
            online_users = DatabaseManager.execute_query("SELECT COUNT(*) as OnlineUsers FROM Users WHERE Status = 'Online'", fetch_one=True)[0]
            
            # Daily stats (last 7 days)
            daily_stats_query = """
                SELECT CAST(SentAt AS DATE) as Date, COUNT(*) as MessageCount
                FROM Messages
                WHERE SentAt >= DATEADD(day, -7, GETDATE())
                GROUP BY CAST(SentAt AS DATE)
                ORDER BY Date DESC
            """
            daily_stats = DatabaseManager.execute_query(daily_stats_query, fetch_all=True)
            
            # Top 10 users
            top_users_query = """
                SELECT TOP 10 u.FullName, COUNT(m.MessageID) as MessageCount
                FROM Users u
                LEFT JOIN Messages m ON u.UserID = m.SenderID
                WHERE m.SentAt >= DATEADD(day, -30, GETDATE())
                GROUP BY u.UserID, u.FullName
                ORDER BY MessageCount DESC
            """
            top_users = DatabaseManager.execute_query(top_users_query, fetch_all=True)
            
            # Top 10 rooms
            top_rooms_query = """
                SELECT TOP 10 r.RoomName, COUNT(m.MessageID) as MessageCount
                FROM Rooms r
                LEFT JOIN Messages m ON r.RoomID = m.RoomID
                WHERE m.SentAt >= DATEADD(day, -30, GETDATE())
                GROUP BY r.RoomID, r.RoomName
                ORDER BY MessageCount DESC
            """
            top_rooms = DatabaseManager.execute_query(top_rooms_query, fetch_all=True)
            
            return {
                'total_users': total_users,
                'total_rooms': total_rooms,
                'total_messages': total_messages,
                'total_files': total_files,
                'online_users': online_users,
                'daily_stats': daily_stats,
                'top_users': top_users,
                'top_rooms': top_rooms
            }
        except Exception as e:
            app_logger.error(f"Get admin dashboard stats error: {e}")
            return {
                'total_users': 0,
                'total_rooms': 0,
                'total_messages': 0,
                'total_files': 0,
                'online_users': 0,
                'daily_stats': [],
                'top_users': [],
                'top_rooms': []
            }
    
    @staticmethod
    def get_admin_users(page=1, limit=20):
        """Get admin users with pagination"""
        try:
            offset = (page - 1) * limit
            
            query = """
                SELECT u.UserID, u.FullName, u.Username, u.Email, u.Status, u.Role,
                       u.CreatedAt, u.LastLoginAt,
                       COUNT(m.MessageID) as MessageCount
                FROM Users u
                LEFT JOIN Messages m ON u.UserID = m.SenderID
                GROUP BY u.UserID, u.FullName, u.Username, u.Email, u.Status, u.Role, u.CreatedAt, u.LastLoginAt
                ORDER BY u.CreatedAt DESC
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            """
            users = DatabaseManager.execute_query(query, (offset, limit), fetch_all=True)
            
            count_query = "SELECT COUNT(*) as Total FROM Users"
            total_count = DatabaseManager.execute_query(count_query, fetch_one=True)[0]
            
            return {
                'users': [{
                    'user_id': user[0],
                    'full_name': user[1],
                    'username': user[2],
                    'email': user[3],
                    'status': user[4],
                    'role': user[5],
                    'created_at': user[6].strftime('%Y-%m-%d %H:%M:%S') if user[6] else '',
                    'last_login': user[7].strftime('%Y-%m-%d %H:%M:%S') if user[7] else '',
                    'message_count': user[8]
                } for user in users],
                'total': total_count,
                'page': page,
                'limit': limit
            }
        except Exception as e:
            app_logger.error(f"Get admin users error: {e}")
            return {'users': [], 'total': 0, 'page': page, 'limit': limit}
    
    @staticmethod
    def update_user_role(user_id, new_role):
        """Update user role"""
        try:
            query = """
                UPDATE Users
                SET Role = ?
                WHERE UserID = ?
            """
            DatabaseManager.execute_query(query, (new_role, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Update user role error: {e}")
            return False
    
    @staticmethod
    def get_system_stats():
        """Get system statistics"""
        try:
            stats = {}
            
            # User stats
            stats['total_users'] = DatabaseManager.execute_query("SELECT COUNT(*) as Total FROM Users", fetch_one=True)[0]
            stats['online_users'] = DatabaseManager.execute_query("SELECT COUNT(*) as Online FROM Users WHERE Status = 'Online'", fetch_one=True)[0]
            stats['new_users_today'] = DatabaseManager.execute_query("SELECT COUNT(*) as Today FROM Users WHERE CAST(CreatedAt AS DATE) = CAST(GETDATE() AS DATE)", fetch_one=True)[0]
            
            # Message stats
            stats['total_messages'] = DatabaseManager.execute_query("SELECT COUNT(*) as Total FROM Messages", fetch_one=True)[0]
            stats['messages_today'] = DatabaseManager.execute_query("SELECT COUNT(*) as Today FROM Messages WHERE CAST(SentAt AS DATE) = CAST(GETDATE() AS DATE)", fetch_one=True)[0]
            
            # File stats
            stats['total_files'] = DatabaseManager.execute_query("SELECT COUNT(*) as Total FROM SharedFiles", fetch_one=True)[0]
            result = DatabaseManager.execute_query("SELECT SUM(FileSize) as TotalSize FROM SharedFiles", fetch_one=True)
            stats['total_file_size'] = result[0] if result and result[0] else 0
            
            # Room stats
            stats['total_rooms'] = DatabaseManager.execute_query("SELECT COUNT(*) as Total FROM Rooms", fetch_one=True)[0]
            stats['total_groups'] = DatabaseManager.execute_query("SELECT COUNT(*) as Groups FROM Rooms WHERE IsGroup = 1", fetch_one=True)[0]
            
            return stats
        except Exception as e:
            app_logger.error(f"Get system stats error: {e}")
            return {
                'total_users': 0,
                'online_users': 0,
                'new_users_today': 0,
                'total_messages': 0,
                'messages_today': 0,
                'total_files': 0,
                'total_file_size': 0,
                'total_rooms': 0,
                'total_groups': 0
            }
    
    @staticmethod
    def ensure_voice_messages_table():
        """Ensure VoiceMessages table exists"""
        try:
            if not DatabaseManager.column_exists('VoiceMessages', 'VoiceID'):
                create_table_query = """
                    CREATE TABLE VoiceMessages (
                        VoiceID INT IDENTITY(1,1) PRIMARY KEY,
                        FileName NVARCHAR(255) NOT NULL,
                        FilePath NVARCHAR(500) NOT NULL,
                        Duration INT NULL,
                        FileSize INT NOT NULL,
                        UploadedBy INT NOT NULL,
                        RoomID INT NULL,
                        CreatedAt DATETIME DEFAULT GETDATE(),
                        FOREIGN KEY (UploadedBy) REFERENCES Users(UserID),
                        FOREIGN KEY (RoomID) REFERENCES Rooms(RoomID)
                    )
                """
                DatabaseManager.execute_query(create_table_query)
        except Exception as e:
            app_logger.error(f"Ensure voice messages table error: {e}")
    
    @staticmethod
    def save_voice_message(filename, filepath, filesize, uploaded_by, room_id=None, duration=None):
        """Save voice message to database"""
        try:
            DatabaseManager.ensure_voice_messages_table()
            query = """
                INSERT INTO VoiceMessages (FileName, FilePath, FileSize, UploadedBy, RoomID, Duration)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            DatabaseManager.execute_query(query, (filename, filepath, filesize, uploaded_by, room_id, duration))
            return True
        except Exception as e:
            app_logger.error(f"Save voice message error: {e}")
            return False
    
    @staticmethod
    def get_voice_messages(room_id, user_id):
        """Get voice messages for a room"""
        try:
            # Check if user is member of the room
            if not DatabaseManager.is_room_member(room_id, user_id):
                return []
            
            query = """
                SELECT vm.VoiceID, vm.FileName, vm.FilePath, vm.Duration,
                       vm.FileSize, vm.CreatedAt, u.FullName as SenderName
                FROM VoiceMessages vm
                JOIN Users u ON vm.UploadedBy = u.UserID
                WHERE vm.RoomID = ?
                ORDER BY vm.CreatedAt DESC
            """
            voice_messages = DatabaseManager.execute_query(query, (room_id,), fetch_all=True)
            return [{
                'voice_id': vm[0],
                'filename': vm[1],
                'filepath': vm[2],
                'duration': vm[3],
                'file_size': vm[4],
                'created_at': vm[5].strftime('%Y-%m-%d %H:%M:%S') if vm[5] else '',
                'sender_name': vm[6]
            } for vm in voice_messages]
        except Exception as e:
            app_logger.error(f"Get voice messages error: {e}")
            return []
    
    @staticmethod
    def enable_2fa(user_id, secret):
        """Enable 2FA for user"""
        try:
            # Ensure Users table has 2FA columns
            if not DatabaseManager.column_exists('Users', 'TwoFASecret'):
                DatabaseManager.execute_query("ALTER TABLE Users ADD TwoFASecret NVARCHAR(255) NULL")
            
            if not DatabaseManager.column_exists('Users', 'TwoFAEnabled'):
                DatabaseManager.execute_query("ALTER TABLE Users ADD TwoFAEnabled BIT NOT NULL DEFAULT 0")
            
            # Save secret
            query = """
                UPDATE Users
                SET TwoFASecret = ?, TwoFAEnabled = 0
                WHERE UserID = ?
            """
            DatabaseManager.execute_query(query, (secret, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Enable 2FA error: {e}")
            return False
    
    @staticmethod
    def get_2fa_secret(user_id):
        """Get 2FA secret for user"""
        try:
            query = """
                SELECT TwoFASecret
                FROM Users
                WHERE UserID = ?
            """
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            return result[0] if result and result[0] else None
        except Exception as e:
            app_logger.error(f"Get 2FA secret error: {e}")
            return None
    
    @staticmethod
    def enable_2fa_verified(user_id):
        """Enable 2FA after verification"""
        try:
            query = """
                UPDATE Users
                SET TwoFAEnabled = 1
                WHERE UserID = ?
            """
            DatabaseManager.execute_query(query, (user_id,))
            return True
        except Exception as e:
            app_logger.error(f"Enable 2FA verified error: {e}")
            return False
    
    @staticmethod
    def get_user_password_and_2fa_secret(user_id):
        """Get user password and 2FA secret"""
        try:
            query = """
                SELECT Password, TwoFASecret
                FROM Users
                WHERE UserID = ?
            """
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            return result if result else (None, None)
        except Exception as e:
            app_logger.error(f"Get user password and 2FA secret error: {e}")
            return (None, None)
    
    @staticmethod
    def disable_2fa(user_id):
        """Disable 2FA for user"""
        try:
            query = """
                UPDATE Users
                SET TwoFAEnabled = 0, TwoFASecret = NULL
                WHERE UserID = ?
            """
            DatabaseManager.execute_query(query, (user_id,))
            return True
        except Exception as e:
            app_logger.error(f"Disable 2FA error: {e}")
            return False
    
    @staticmethod
    def get_2fa_secret_and_status(user_id):
        """Get 2FA secret and enabled status for user"""
        try:
            query = """
                SELECT TwoFASecret, TwoFAEnabled
                FROM Users
                WHERE UserID = ?
            """
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            return result if result else (None, False)
        except Exception as e:
            app_logger.error(f"Get 2FA secret and status error: {e}")
            return (None, False)
    
    @staticmethod
    def is_2fa_enabled(user_id):
        """Check if 2FA is enabled for user"""
        try:
            query = """
                SELECT TwoFAEnabled
                FROM Users
                WHERE UserID = ?
            """
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            return bool(result[0]) if result else False
        except Exception as e:
            app_logger.error(f"Is 2FA enabled error: {e}")
            return False

    @staticmethod
    def ensure_message_reactions_table():
        """Ensure MessageReactions table exists"""
        try:
            if not DatabaseManager.column_exists('MessageReactions', 'ReactionID'):
                query = """
                    CREATE TABLE MessageReactions (
                        ReactionID INT IDENTITY(1,1) PRIMARY KEY,
                        MessageID INT NOT NULL,
                        UserID INT NOT NULL,
                        Emoji NVARCHAR(50) NOT NULL,
                        CreatedAt DATETIME DEFAULT GETDATE(),
                        FOREIGN KEY (MessageID) REFERENCES Messages(MessageID),
                        FOREIGN KEY (UserID) REFERENCES Users(UserID),
                        UNIQUE (MessageID, UserID, Emoji)
                    )
                """
                DatabaseManager.execute_query(query)
                app_logger.info("Created MessageReactions table")
        except Exception as e:
            app_logger.error(f"Ensure message reactions table error: {e}")
    
    @staticmethod
    def add_reaction(message_id, user_id, emoji):
        """Add reaction to message"""
        try:
            DatabaseManager.ensure_message_reactions_table()
            query = """
                INSERT INTO MessageReactions (MessageID, UserID, Emoji)
                VALUES (?, ?, ?)
            """
            DatabaseManager.execute_query(query, (message_id, user_id, emoji))
            return True
        except pyodbc.IntegrityError:
            # User already reacted with this emoji
            return False
        except Exception as e:
            app_logger.error(f"Add reaction error: {e}")
            return False
    
    @staticmethod
    def remove_reaction(message_id, user_id, emoji):
        """Remove reaction from message"""
        try:
            query = """
                DELETE FROM MessageReactions
                WHERE MessageID = ? AND UserID = ? AND Emoji = ?
            """
            DatabaseManager.execute_query(query, (message_id, user_id, emoji))
            return True
        except Exception as e:
            app_logger.error(f"Remove reaction error: {e}")
            return False
    
    @staticmethod
    def get_message_reactions(message_id):
        """Get all reactions for a message"""
        try:
            query = """
                SELECT Emoji, COUNT(*) as Count
                FROM MessageReactions
                WHERE MessageID = ?
                GROUP BY Emoji
            """
            reactions = DatabaseManager.execute_query(query, (message_id,), fetch_all=True)
            return {emoji: count for emoji, count in reactions}
        except Exception as e:
            app_logger.error(f"Get message reactions error: {e}")
            return {}

    @staticmethod
    def ensure_reply_column():
        """Ensure ReplyToMessageID column exists in Messages table"""
        try:
            if not DatabaseManager.column_exists('Messages', 'ReplyToMessageID'):
                query = "ALTER TABLE Messages ADD ReplyToMessageID INT NULL"
                DatabaseManager.execute_query(query)
                app_logger.info("Added ReplyToMessageID column to Messages table")
        except Exception as e:
            app_logger.error(f"Ensure reply column error: {e}")
    
    @staticmethod
    def get_message_for_reply(message_id):
        """Get message details for reply"""
        try:
            DatabaseManager.ensure_reply_column()
            query = """
                SELECT M.MessageID, M.Content, M.MessageType, U.FullName as SenderName, M.SentAt
                FROM Messages M
                JOIN Users U ON M.SenderID = U.UserID
                WHERE M.MessageID = ?
            """
            result = DatabaseManager.execute_query(query, (message_id,), fetch_one=True)
            if result:
                return {
                    'message_id': result[0],
                    'content': result[1],
                    'type': result[2],
                    'sender_name': result[3],
                    'sent_at': result[4].strftime('%Y-%m-%d %H:%M:%S') if result[4] else None
                }
            return None
        except Exception as e:
            app_logger.error(f"Get message for reply error: {e}")
            return None

    @staticmethod
    def ensure_pinned_column():
        """Ensure IsPinned column exists in Messages table"""
        try:
            if not DatabaseManager.column_exists('Messages', 'IsPinned'):
                query = "ALTER TABLE Messages ADD IsPinned BIT DEFAULT 0"
                DatabaseManager.execute_query(query)
                app_logger.info("Added IsPinned column to Messages table")
        except Exception as e:
            app_logger.error(f"Ensure pinned column error: {e}")
    
    @staticmethod
    def pin_message(message_id, user_id):
        """Pin a message"""
        try:
            DatabaseManager.ensure_pinned_column()
            # Check if user has permission (admin or message sender)
            query = """
                SELECT SenderID, RoomID FROM Messages WHERE MessageID = ?
            """
            result = DatabaseManager.execute_query(query, (message_id,), fetch_one=True)
            if not result:
                return False
            
            sender_id = result[0]
            # Allow pinning if user is sender or admin
            if sender_id != user_id:
                # Check if user is admin
                user_role = DatabaseManager.get_user_role(user_id)
                if user_role != 'Admin':
                    return False
            
            query = "UPDATE Messages SET IsPinned = 1 WHERE MessageID = ?"
            DatabaseManager.execute_query(query, (message_id,))
            return True
        except Exception as e:
            app_logger.error(f"Pin message error: {e}")
            return False
    
    @staticmethod
    def unpin_message(message_id, user_id):
        """Unpin a message"""
        try:
            DatabaseManager.ensure_pinned_column()
            query = "UPDATE Messages SET IsPinned = 0 WHERE MessageID = ?"
            DatabaseManager.execute_query(query, (message_id,))
            return True
        except Exception as e:
            app_logger.error(f"Unpin message error: {e}")
            return False
    
    @staticmethod
    def get_pinned_messages(room_id):
        """Get all pinned messages for a room"""
        try:
            DatabaseManager.ensure_pinned_column()
            query = """
                SELECT m.MessageID, m.Content, m.MessageType, m.SentAt, m.ReplyToMessageID,
                       u.Username as SenderName, u.UserID as SenderID
                FROM Messages m
                JOIN Users u ON m.SenderID = u.UserID
                WHERE m.RoomID = ? AND m.IsPinned = 1 AND m.IsDeleted = 0
                ORDER BY m.SentAt DESC
            """
            messages = DatabaseManager.execute_query(query, (room_id,), fetch_all=True)
            return messages
        except Exception as e:
            app_logger.error(f"Get pinned messages error: {e}")
            return []

    @staticmethod
    def ensure_mentions_table():
        """Ensure Mentions table exists"""
        try:
            if not DatabaseManager.column_exists('Mentions', 'MentionID'):
                query = """
                    CREATE TABLE Mentions (
                        MentionID INT IDENTITY(1,1) PRIMARY KEY,
                        MessageID INT NOT NULL,
                        MentionedUserID INT NOT NULL,
                        MentioningUserID INT NOT NULL,
                        CreatedAt DATETIME DEFAULT GETDATE(),
                        IsRead BIT DEFAULT 0,
                        FOREIGN KEY (MessageID) REFERENCES Messages(MessageID),
                        FOREIGN KEY (MentionedUserID) REFERENCES Users(UserID),
                        FOREIGN KEY (MentioningUserID) REFERENCES Users(UserID)
                    )
                """
                DatabaseManager.execute_query(query)
                app_logger.info("Created Mentions table")
        except Exception as e:
            app_logger.error(f"Ensure mentions table error: {e}")
    
    @staticmethod
    def save_mentions(message_id, mentioned_user_ids, mentioning_user_id):
        """Save mentions for a message"""
        try:
            DatabaseManager.ensure_mentions_table()
            for mentioned_user_id in mentioned_user_ids:
                query = """
                    INSERT INTO Mentions (MessageID, MentionedUserID, MentioningUserID)
                    VALUES (?, ?, ?)
                """
                DatabaseManager.execute_query(query, (message_id, mentioned_user_id, mentioning_user_id))
            return True
        except Exception as e:
            app_logger.error(f"Save mentions error: {e}")
            return False
    
    @staticmethod
    def parse_mentions(content, room_id):
        """Parse @mentions from message content and return user IDs"""
        try:
            import re
            mentions = re.findall(r'@(\w+)', content)
            if not mentions:
                return []
            
            # Get users in the room
            query = """
                SELECT DISTINCT u.UserID, u.Username
                FROM Users u
                JOIN RoomParticipants rp ON u.UserID = rp.UserID
                WHERE rp.RoomID = ? AND u.Username IN ({})
            """.format(','.join(['?' for _ in mentions]))
            
            params = [room_id] + mentions
            users = DatabaseManager.execute_query(query, params, fetch_all=True)
            
            # Map usernames to user IDs
            username_to_id = {user[1]: user[0] for user in users}
            mentioned_ids = [username_to_id.get(username) for username in mentions if username in username_to_id]
            
            return mentioned_ids
        except Exception as e:
            app_logger.error(f"Parse mentions error: {e}")
            return []
    
    @staticmethod
    def get_user_mentions(user_id):
        """Get all mentions for a user"""
        try:
            DatabaseManager.ensure_mentions_table()
            query = """
                SELECT m.MentionID, m.MessageID, m.MentioningUserID, m.CreatedAt, m.IsRead,
                       msg.Content, msg.RoomID, u.Username as MentioningUsername
                FROM Mentions m
                JOIN Messages msg ON m.MessageID = msg.MessageID
                JOIN Users u ON m.MentioningUserID = u.UserID
                WHERE m.MentionedUserID = ?
                ORDER BY m.CreatedAt DESC
            """
            mentions = DatabaseManager.execute_query(query, (user_id,), fetch_all=True)
            return mentions
        except Exception as e:
            app_logger.error(f"Get user mentions error: {e}")
            return []
    
    @staticmethod
    def mark_mention_as_read(mention_id):
        """Mark a mention as read"""
        try:
            DatabaseManager.ensure_mentions_table()
            query = "UPDATE Mentions SET IsRead = 1 WHERE MentionID = ?"
            DatabaseManager.execute_query(query, (mention_id,))
            return True
        except Exception as e:
            app_logger.error(f"Mark mention as read error: {e}")
            return False

    @staticmethod
    def ensure_group_avatar_column():
        """Ensure GroupAvatar column exists in Rooms table"""
        try:
            if not DatabaseManager.column_exists('Rooms', 'GroupAvatar'):
                query = "ALTER TABLE Rooms ADD GroupAvatar NVARCHAR(500) NULL"
                DatabaseManager.execute_query(query)
                app_logger.info("Added GroupAvatar column to Rooms table")
        except Exception as e:
            app_logger.error(f"Ensure group avatar column error: {e}")

    @staticmethod
    def update_group_avatar(room_id, avatar_url):
        """Update group avatar for a room"""
        try:
            DatabaseManager.ensure_group_avatar_column()
            query = "UPDATE Rooms SET GroupAvatar = ? WHERE RoomID = ?"
            DatabaseManager.execute_query(query, (avatar_url, room_id))
            return True
        except Exception as e:
            app_logger.error(f"Update group avatar error: {e}")
            return False

    @staticmethod
    def get_group_avatar(room_id):
        """Get group avatar for a room"""
        try:
            DatabaseManager.ensure_group_avatar_column()
            query = "SELECT GroupAvatar FROM Rooms WHERE RoomID = ?"
            result = DatabaseManager.execute_query(query, (room_id,), fetch_one=True)
            return result[0] if result and result[0] else None
        except Exception as e:
            app_logger.error(f"Get group avatar error: {e}")
            return None

    @staticmethod
    def ensure_muted_rooms_table():
        """Ensure MutedRooms table exists"""
        try:
            if not DatabaseManager.column_exists('MutedRooms', 'MutedRoomID'):
                query = """
                    CREATE TABLE MutedRooms (
                        MutedRoomID INT IDENTITY(1,1) PRIMARY KEY,
                        UserID INT NOT NULL,
                        RoomID INT NOT NULL,
                        MutedAt DATETIME DEFAULT GETDATE(),
                        FOREIGN KEY (UserID) REFERENCES Users(UserID),
                        FOREIGN KEY (RoomID) REFERENCES Rooms(RoomID),
                        UNIQUE(UserID, RoomID)
                    )
                """
                DatabaseManager.execute_query(query)
                app_logger.info("Created MutedRooms table")
        except Exception as e:
            app_logger.error(f"Ensure muted rooms table error: {e}")

    @staticmethod
    def mute_room(user_id, room_id):
        """Mute notifications for a room"""
        try:
            DatabaseManager.ensure_muted_rooms_table()
            query = """
                IF NOT EXISTS (SELECT 1 FROM MutedRooms WHERE UserID = ? AND RoomID = ?)
                INSERT INTO MutedRooms (UserID, RoomID) VALUES (?, ?)
            """
            DatabaseManager.execute_query(query, (user_id, room_id, user_id, room_id))
            return True
        except Exception as e:
            app_logger.error(f"Mute room error: {e}")
            return False

    @staticmethod
    def unmute_room(user_id, room_id):
        """Unmute notifications for a room"""
        try:
            DatabaseManager.ensure_muted_rooms_table()
            query = "DELETE FROM MutedRooms WHERE UserID = ? AND RoomID = ?"
            DatabaseManager.execute_query(query, (user_id, room_id))
            return True
        except Exception as e:
            app_logger.error(f"Unmute room error: {e}")
            return False

    @staticmethod
    def is_room_muted(user_id, room_id):
        """Check if a room is muted for a user"""
        try:
            DatabaseManager.ensure_muted_rooms_table()
            query = "SELECT 1 FROM MutedRooms WHERE UserID = ? AND RoomID = ?"
            result = DatabaseManager.execute_query(query, (user_id, room_id), fetch_one=True)
            return result is not None
        except Exception as e:
            app_logger.error(f"Check room muted error: {e}")
            return False

    @staticmethod
    def get_muted_rooms(user_id):
        """Get all muted rooms for a user"""
        try:
            DatabaseManager.ensure_muted_rooms_table()
            query = "SELECT RoomID FROM MutedRooms WHERE UserID = ?"
            results = DatabaseManager.execute_query(query, (user_id,), fetch_all=True)
            return [r[0] for r in results]
        except Exception as e:
            app_logger.error(f"Get muted rooms error: {e}")
            return []

    @staticmethod
    def ensure_room_roles_table():
        """Ensure RoomRoles table exists"""
        try:
            if not DatabaseManager.column_exists('RoomRoles', 'RoleID'):
                query = """
                    CREATE TABLE RoomRoles (
                        RoleID INT IDENTITY(1,1) PRIMARY KEY,
                        RoomID INT NOT NULL,
                        UserID INT NOT NULL,
                        Role NVARCHAR(50) DEFAULT 'Member',
                        AssignedAt DATETIME DEFAULT GETDATE(),
                        FOREIGN KEY (RoomID) REFERENCES Rooms(RoomID),
                        FOREIGN KEY (UserID) REFERENCES Users(UserID),
                        UNIQUE(RoomID, UserID)
                    )
                """
                DatabaseManager.execute_query(query)
                app_logger.info("Created RoomRoles table")
        except Exception as e:
            app_logger.error(f"Ensure room roles table error: {e}")

    @staticmethod
    def assign_role(room_id, user_id, role):
        """Assign a role to a user in a room"""
        try:
            DatabaseManager.ensure_room_roles_table()
            # Validate role
            valid_roles = ['Admin', 'Moderator', 'Member']
            if role not in valid_roles:
                role = 'Member'
            query = """
                IF EXISTS (SELECT 1 FROM RoomRoles WHERE RoomID = ? AND UserID = ?)
                    UPDATE RoomRoles SET Role = ? WHERE RoomID = ? AND UserID = ?
                ELSE
                    INSERT INTO RoomRoles (RoomID, UserID, Role) VALUES (?, ?, ?)
            """
            DatabaseManager.execute_query(query, (room_id, user_id, role, room_id, user_id, room_id, user_id, role))

            # Try to keep RoomParticipants.Role column in sync for compatibility
            try:
                if DatabaseManager.column_exists('RoomParticipants', 'Role'):
                    update_q = "UPDATE RoomParticipants SET Role = ? WHERE RoomID = ? AND UserID = ?"
                    DatabaseManager.execute_query(update_q, (role, room_id, user_id))
            except Exception as e:
                app_logger.warning(f"Could not sync RoomParticipants.Role for user {user_id} in room {room_id}: {e}")

            return True
        except Exception as e:
            app_logger.error(f"Assign role error: {e}")
            return False

    @staticmethod
    def get_user_role(room_id, user_id):
        """Get user's role in a room"""
        try:
            DatabaseManager.ensure_room_roles_table()
            query = "SELECT Role FROM RoomRoles WHERE RoomID = ? AND UserID = ?"
            result = DatabaseManager.execute_query(query, (room_id, user_id), fetch_one=True)
            return result[0] if result else 'Member'
        except Exception as e:
            app_logger.error(f"Get user role error: {e}")
            return 'Member'

    @staticmethod
    def get_room_members_with_roles(room_id):
        """Get all members of a room with their roles"""
        try:
            DatabaseManager.ensure_room_roles_table()
            query = """
                SELECT u.UserID, u.FullName, u.Username, u.Status, rr.Role
                FROM Users u
                JOIN RoomParticipants rp ON u.UserID = rp.UserID
                LEFT JOIN RoomRoles rr ON u.UserID = rr.UserID AND rp.RoomID = rr.RoomID
                WHERE rp.RoomID = ?
            """
            results = DatabaseManager.execute_query(query, (room_id,), fetch_all=True)
            return [{
                'user_id': r[0],
                'full_name': r[1],
                'username': r[2],
                'status': r[3],
                'role': r[4] or 'Member'
            } for r in results]
        except Exception as e:
            app_logger.error(f"Get room members with roles error: {e}")
            return []

    @staticmethod
    def remove_role(room_id, user_id):
        """Remove a user's role (reset to Member)"""
        try:
            DatabaseManager.ensure_room_roles_table()
            query = "DELETE FROM RoomRoles WHERE RoomID = ? AND UserID = ?"
            DatabaseManager.execute_query(query, (room_id, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Remove role error: {e}")
            return False

# Initialize database tables
DatabaseManager.ensure_room_participants_table()
DatabaseManager.ensure_user_auth_columns()
