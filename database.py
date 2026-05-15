#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database management module for ChatAI application
"""
import psycopg2
import pyodbc
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from logger_config import app_logger

import psycopg2
import os
import time


def init_db():
    # 1. Lấy link kết nối từ biến môi trường Render
    db_url = os.environ.get('DATABASE_URL')
    
    # Xử lý lỗi định dạng link nếu có
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        
    print("Đang kết nối tới Database...")
    
    try:
        # 2. Thiết lập kết nối
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # 3. Đọc nội dung file SQLQuery1.sql
        # File này phải nằm cùng thư mục với database.py
        sql_file_path = 'SQLQuery1.sql'
        
        if os.path.exists(sql_file_path):
            with open(sql_file_path, 'r', encoding='utf-8') as f:
                sql_script = f.read()
                
            print(f"Đang thực thi các lệnh trong {sql_file_path}...")
            # Chạy toàn bộ code SQL
            cur.execute(sql_script)
            
            # Lưu thay đổi
            conn.commit()
            print("Chúc mừng Tới! Đã chuyển code SQL sang Database thành công.")
        else:
            print(f"Lỗi: Không tìm thấy file {sql_file_path} trong thư mục dự án.")

    except Exception as e:
        print(f"Có lỗi xảy ra khi chuyển dữ liệu: {e}")
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    init_db()
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
    def init_db_from_file():

        conn = None

        try:

            conn = DatabaseManager.get_db_connection()

            conn.autocommit = True

            cursor = conn.cursor()

            sql_path = os.path.join(
                os.path.dirname(__file__),
                "SQLQuery1.sql"
            )

            with open(sql_path, "r", encoding="utf-8") as f:
                sql = f.read()

            cursor.execute(sql)

            print("=== ĐÃ KHỞI TẠO DATABASE ===")

        except Exception as e:

            print(f"--- LỖI DB: {e} ---")

        finally:

            if conn:
                conn.close()
    
    @staticmethod
    def get_db_connection():
        try:
            if config.database_url:
                db_url = config.database_url
                
                # Render bắt buộc phải có SSL để kết nối PostgreSQL
                if "sslmode=require" not in db_url:
                    if "?" in db_url:
                        db_url += "&sslmode=require"
                    else:
                        db_url += "?sslmode=require"
                        
                # Kết nối PostgreSQL (Render)
                return psycopg2.connect(db_url)
                
            # Kết nối SQL Server (Máy nhà)
            return pyodbc.connect(config.conn_str)
        except Exception as e:
            app_logger.error(f"Database connection error: {e}")
            raise
    @staticmethod
    def execute_query(query, params=None, fetch_one=False, fetch_all=False):
        conn = None

        try:
            conn = DatabaseManager.get_db_connection()

            if config.database_url:
                # PostgreSQL syntax
                query = query.replace('?', '%s')
                query = query.replace('GETDATE()', 'CURRENT_TIMESTAMP')

            cursor = conn.cursor()

            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            result = None

            if fetch_one:
                result = cursor.fetchone()

            elif fetch_all:
                result = cursor.fetchall()

            else:
                conn.commit()
                result = cursor.rowcount

            return result

        except Exception as e:
            app_logger.error(f"Query execution error: {e}")

            if conn:
                conn.rollback()

            raise

        finally:
            if conn:
                conn.close()

    @staticmethod
    def create_user(username, password, full_name, email=None):
        # Dùng chữ thường cho bảng/cột để Postgres không báo lỗi 'relation does not exist'
        query = """
            INSERT INTO users (username, password, fullname, email, status, createdat)
            VALUES (?, ?, ?, ?, 'Offline', GETDATE())
        """
        params = (username, generate_password_hash(password), full_name, email)
        return DatabaseManager.execute_query(query, params)
    @staticmethod
    def get_user_by_phone(phone):
        """Lấy thông tin người dùng bằng số điện thoại (Chuẩn PostgreSQL)"""
        try:
            # Đảm bảo cột phone đã tồn tại (nếu bạn có hàm khởi tạo tự động)
            # DatabaseManager.ensure_phone_column() 

            # Lưu ý: PostgreSQL phân biệt chữ hoa chữ thường, nên dùng chữ thường cho bảng 'users' và cột 'phone'
            query = "SELECT id, username, password, fullname, phone, status FROM users WHERE phone = ?"
            
            # Hàm execute_query phía trên sẽ tự đổi '?' thành '%s' và 'users' thành lowercase nếu cần
            return DatabaseManager.execute_query(query, (phone,), fetch_one=True)
        except Exception as e:
            app_logger.error(f"Lỗi khi lấy user theo số điện thoại: {e}")
            return None
    @staticmethod
    def get_user_by_username(username):
        query = "SELECT id, username, password, fullname, email, status FROM users WHERE username = ?"
        return DatabaseManager.execute_query(query, (username,), fetch_one=True)

    @staticmethod
    def save_message(user_id, content, msg_type='Text', room_id=1, reply_to_message_id=None):
        try:
            # Luôn kiểm tra/đảm bảo cột tồn tại trước (hàm này cũng phải sửa sang Postgres)
            DatabaseManager.ensure_reply_column() 
            
            if reply_to_message_id:
                query = """
                    INSERT INTO messages (roomid, senderid, content, messagetype, isread, sentat, replytomessageid)
                    VALUES (?, ?, ?, ?, 0, GETDATE(), ?)
                """
                params = (room_id, user_id, content, msg_type, reply_to_message_id)
            else:
                query = """
                    INSERT INTO messages (roomid, senderid, content, messagetype, isread, sentat)
                    VALUES (?, ?, ?, ?, 0, GETDATE())
                """
                params = (room_id, user_id, content, msg_type)
            return DatabaseManager.execute_query(query, params)
        except Exception as e:
            app_logger.error(f"Save message error: {e}")
            raise
    
    @staticmethod
    def get_room_messages(room_id, limit=50):
        """Lấy tin nhắn trong phòng (Tương thích Postgres & SQL Server)"""
        try:
            DatabaseManager.ensure_reply_column()
            # Sử dụng cú pháp SQL tiêu chuẩn, LIMIT sẽ được xử lý nếu cần
            # Lưu ý: Bỏ 'TOP {}' vì Postgres không hiểu, ta sẽ dùng LIMIT ở cuối
            query = """
                SELECT m.messageid, m.content, m.messagetype, m.sentat, m.isread,
                       u.username as sendername, u.id as senderid, m.replytomessageid
                FROM messages m
                JOIN users u ON m.senderid = u.id
                WHERE m.roomid = ? AND m.isdeleted = 0
                ORDER BY m.sentat DESC
                LIMIT {}
            """.format(limit)
            
            # Nếu chạy SQL Server máy nhà, bạn có thể cần đổi LIMIT ngược lại thành TOP 
            # nhưng tốt nhất là dùng LIMIT vì Postgres trên Render là ưu tiên.
            messages = DatabaseManager.execute_query(query, (room_id,), fetch_all=True)
            return messages
        except Exception as e:
            app_logger.error(f"Get room messages error: {e}")
            return []

    @staticmethod
    def get_analytics_data(export_type):
        """Lấy dữ liệu thống kê để xuất file"""
        try:
            # Chuyển hết tên bảng về chữ thường để tránh lỗi trên Postgres
            if export_type == 'users':
                query = "SELECT id, username, fullname, email, status, createdat FROM users ORDER BY createdat DESC"
            elif export_type == 'messages':
                query = """
                    SELECT m.messageid, m.content, m.messagetype, m.sentat, u.username as sendername
                    FROM messages m
                    JOIN users u ON m.senderid = u.id
                    ORDER BY m.sentat DESC
                """
            elif export_type == 'rooms':
                query = "SELECT roomid, roomname, isgroup, createdat FROM rooms ORDER BY createdat DESC"
            elif export_type == 'files':
                query = """
                    SELECT fileid, filename, filetype, filesize, uploadedat, u.username as uploadername
                    FROM files f
                    JOIN users u ON f.uploadedby = u.id
                    ORDER BY f.uploadedat DESC
                """
            else:
                return None
            
            return DatabaseManager.execute_query(query, fetch_all=True)
        except Exception as e:
            app_logger.error(f"Get analytics data error: {e}")
            return None

    @staticmethod
    def ensure_room_participants_table():
        """Đảm bảo bảng RoomParticipants tồn tại (Chuẩn PostgreSQL)"""
        try:
            app_logger.info(f"Checking/creating roomparticipants table")
            # Postgres dùng 'CREATE TABLE IF NOT EXISTS', không dùng BEGIN/END/OBJECT_ID
            query = """
                CREATE TABLE IF NOT EXISTS roomparticipants (
                    roomid INT NOT NULL,
                    id INT NOT NULL,
                    joinedat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (roomid, id),
                    FOREIGN KEY (roomid) REFERENCES rooms(roomid) ON DELETE CASCADE,
                    FOREIGN KEY (id) REFERENCES users(id) ON DELETE CASCADE
                )
            """
            DatabaseManager.execute_query(query)
            app_logger.info(f"RoomParticipants table checked/created successfully")
        except Exception as e:
            app_logger.error(f"RoomParticipants table creation error: {e}")
    
    @staticmethod
    def ensure_user_auth_columns():
        """Đảm bảo các cột xác thực tồn tại (Chuẩn Postgres)"""
        try:
            conn = DatabaseManager.get_db_connection()
            cursor = conn.cursor()
            
            # Định nghĩa các cột theo kiểu dữ liệu Postgres (sẽ tự đổi trong execute_query)
            columns_to_add = [
                ('email', "ALTER TABLE users ADD COLUMN email VARCHAR(255) NULL"),
                ('isverified', "ALTER TABLE users ADD COLUMN isverified BOOLEAN NOT NULL DEFAULT FALSE"),
                ('verificationtoken', "ALTER TABLE users ADD COLUMN verificationtoken VARCHAR(255) NULL"),
                ('oauthprovider', "ALTER TABLE users ADD COLUMN oauthprovider VARCHAR(50) NULL"),
                ('oauthid', "ALTER TABLE users ADD COLUMN oauthid VARCHAR(255) NULL"),
                ('resettoken', "ALTER TABLE users ADD COLUMN resettoken VARCHAR(255) NULL"),
                ('resettokenexpiresat', "ALTER TABLE users ADD COLUMN resettokenexpiresat TIMESTAMP NULL")
            ]
            
            message_columns_to_add = [
                ('editedat', "ALTER TABLE messages ADD COLUMN editedat TIMESTAMP NULL")
            ]
            
            for col, sql in columns_to_add:
                if not DatabaseManager.column_exists('users', col):
                    DatabaseManager.execute_query(sql) # Dùng hàm này để tự động replace kiểu dữ liệu
            
            for col, sql in message_columns_to_add:
                if not DatabaseManager.column_exists('messages', col):
                    DatabaseManager.execute_query(sql)
                    
            conn.commit()
            conn.close()
        except Exception as e:
            app_logger.error(f"Auth columns check error: {e}")

    @staticmethod
    def ensure_last_seen_column():
        try:
            if not DatabaseManager.column_exists('users', 'lastseenat'):
                query = "ALTER TABLE users ADD COLUMN lastseenat TIMESTAMP NULL"
                DatabaseManager.execute_query(query)
        except Exception as e:
            app_logger.error(f"Error adding LastSeenAt column: {e}")

    @staticmethod
    def update_user_status(user_id, status):
        try:
            if status == 'Online':
                # Phải là WHERE id = ? (BỎ userid)
                query = "UPDATE users SET status = ?, lastseenat = CURRENT_TIMESTAMP WHERE id = ?"
                return DatabaseManager.execute_query(query, (status, user_id))
            else:
                # Phải là WHERE id = ? (BỎ userid)
                query = "UPDATE users SET status = ? WHERE id = ?"
                return DatabaseManager.execute_query(query, (status, user_id))
        except Exception as e:
            # ...
            app_logger.error(f"Update user status error: {e}")
            return 0
    @staticmethod
    def column_exists(table, column):
        """Kiểm tra cột tồn tại (Tương thích cả SQL Server & Postgres)"""

        conn = None

        try:
            conn = DatabaseManager.get_db_connection()
            cursor = conn.cursor()

            # PostgreSQL dùng %s
            # SQL Server dùng ?
            placeholder = '%s' if config.database_url else '?'

            query = f"""
                SELECT 1
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = {placeholder}
                AND COLUMN_NAME = {placeholder}
            """

            # PostgreSQL metadata thường lowercase
            table_name = table.lower() if config.database_url else table
            column_name = column.lower() if config.database_url else column

            cursor.execute(query, (table_name, column_name))

            exists = cursor.fetchone() is not None

            return exists

        except Exception as e:

            app_logger.error(f"Column check error: {e}")

            return False

        finally:

            if conn:
                conn.close()
    @staticmethod
    def ensure_user_status_message_column():
        """Đảm bảo cột UserStatusMessage tồn tại (Chuẩn Postgres)"""
        try:
            # Postgres dùng chữ thường 'userstatusmessage' và kiểu VARCHAR
            if not DatabaseManager.column_exists('users', 'userstatusmessage'):
                query = "ALTER TABLE users ADD COLUMN userstatusmessage VARCHAR(200) NULL"
                DatabaseManager.execute_query(query)
                app_logger.info("Đã thêm cột userstatusmessage vào bảng users")
        except Exception as e:
            app_logger.error(f"Lỗi khi thêm cột userstatusmessage: {e}")
    
    @staticmethod
    def get_user_profile(user_id):
        """Lấy thông tin cá nhân (Tương thích Postgres & SQL Server)"""
        try:
            # Luôn kiểm tra các cột cần thiết trước
            DatabaseManager.ensure_phone_column()
            DatabaseManager.ensure_last_seen_column()
            
            # Sử dụng chữ thường cho bảng 'users' và các cột
            query = """
                SELECT fullname, username, phone, status, lastseenat
                FROM users
                WHERE id = ?
            """
            user = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            
            if user:
                return {
                    'full_name': user[0] if user[0] else '',
                    'username': user[1] if user[1] else '',
                    'phone': user[2] if user[2] else '',
                    'status': user[3] if user[3] else 'Offline',
                    'last_seen': user[4].strftime('%Y-%m-%d %H:%M:%S') if user[4] else None
                }
            
            return {
                'full_name': '',
                'username': '',
                'phone': '',
                'status': 'Offline',
                'last_seen': None
            }
        except Exception as e:
            app_logger.error(f"Get user profile error: {e}")
            return {
                'full_name': '', 'username': '', 'phone': '',
                'status': 'Offline', 'last_seen': None
            }

    @staticmethod
    def get_user_last_seen(user_id):
        """Lấy thời gian hoạt động cuối cùng"""
        try:
            DatabaseManager.ensure_last_seen_column()
            query = "SELECT lastseenat FROM users WHERE id = ?"
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            
            if result and result[0]:
                # Xử lý trường hợp result[0] đã là string hoặc object datetime
                if isinstance(result[0], str):
                    return result[0]
                return result[0].strftime('%Y-%m-%d %H:%M:%S')
            return None
        except Exception as e:
            app_logger.error(f"Get user last seen error: {e}")
            return None

    @staticmethod
    def set_user_status_message(user_id, status_message):
        """Cập nhật dòng trạng thái (Status Message)"""
        try:
            DatabaseManager.ensure_user_status_message_column()
            # Đảm bảo dùng đúng tên cột chữ thường đã tạo ở hàm ensure trước đó
            query = "UPDATE users SET userstatusmessage = ? WHERE id = ?"
            return DatabaseManager.execute_query(query, (status_message, user_id))
        except Exception as e:
            app_logger.error(f"Set user status message error: {e}")
            return 0

    @staticmethod
    def get_user_status_message(user_id):
        """Lấy dòng trạng thái của người dùng"""
        try:
            DatabaseManager.ensure_user_status_message_column()
            # Chuyển UserStatusMessage và Users về chữ thường
            query = "SELECT userstatusmessage FROM users WHERE id = ?"
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            return result[0] if result and result[0] else ''
        except Exception as e:
            app_logger.error(f"Get user status message error: {e}")
            return ''
    
    @staticmethod
    def get_user_by_email(email):
        """Tìm người dùng qua email (Tương thích Postgres)"""
        try:
            # Đảm bảo cột email tồn tại trước khi truy vấn
            DatabaseManager.ensure_user_auth_columns()
            query = "SELECT id, username, password, fullname, email, status FROM users WHERE email = ?"
            return DatabaseManager.execute_query(query, (email,), fetch_one=True)
        except Exception as e:
            app_logger.error(f"Get user by email error: {e}")
            return None
    
    @staticmethod
    def username_exists(username):
        """Kiểm tra username đã tồn tại chưa"""
        try:
            query = "SELECT 1 FROM users WHERE username = ?"
            result = DatabaseManager.execute_query(query, (username,), fetch_one=True)
            return result is not None
        except Exception as e:
            app_logger.error(f"Username exists error: {e}")
            return False
    
    @staticmethod
    def get_unread_counts(user_id):
        """Lấy số lượng tin nhắn chưa đọc"""
        try:
            # Chuyển đổi các cột IsRead, RoomID, SenderID về chữ thường
            query = """
                SELECT roomid, COUNT(*) AS unreadcount
                FROM messages
                WHERE roomid IS NOT NULL AND isread = 0 AND senderid != ?
                GROUP BY roomid
            """
            rows = DatabaseManager.execute_query(query, (user_id,), fetch_all=True)
            return {row[0]: row[1] for row in rows} if rows else {}
        except Exception as e:
            app_logger.error(f"Get unread counts error: {e}")
            return {}
    
    @staticmethod
    def get_user_by_oauth(provider, oauth_id):
        """Lấy người dùng qua OAuth (Tương thích Postgres)"""
        try:
            # Chuyển tên cột và bảng về chữ thường
            query = "SELECT id, fullname, username, email FROM users WHERE oauthprovider = ? AND oauthid = ?"
            return DatabaseManager.execute_query(query, (provider, oauth_id), fetch_one=True)
        except Exception as e:
            app_logger.error(f"Get user by OAuth error: {e}")
            return None
    
    @staticmethod
    def create_oauth_user(provider, oauth_id, email, full_name):
        """Tạo người dùng OAuth mới"""
        try:
            import secrets
            from werkzeug.security import generate_password_hash
            
            username_base = email.split('@')[0] if email else provider
            username = DatabaseManager.generate_unique_username(username_base)
            password_hash = generate_password_hash(secrets.token_urlsafe(16))
            
            # Chú ý: IsVerified BIT -> BOOLEAN (1 -> TRUE)
            query = """
                INSERT INTO users (username, fullname, email, password, status, isverified, oauthprovider, oauthid)
                VALUES (?, ?, ?, ?, 'Offline', TRUE, ?, ?)
            """
            DatabaseManager.execute_query(query, (username, full_name, email, password_hash, provider, oauth_id))
            
            return DatabaseManager.get_user_by_oauth(provider, oauth_id)
        except Exception as e:
            app_logger.error(f"Create OAuth user error: {e}")
            return None

    @staticmethod
    def get_group_rooms(user_id):
        """Lấy danh sách nhóm (Sử dụng LATERAL cho PostgreSQL)"""
        try:
            # SỬA LỖI: r.isgroup = TRUE thay vì 1
            query = """
                SELECT r.roomid,
                       r.roomname,
                       r.groupavatar,
                       COALESCE(last_msg.content_display, 'Chưa có tin nhắn') AS lastmessage,
                       last_msg.sentat AS lastsentat,
                       COALESCE(unread.unreadcount, 0) AS unreadcount
                FROM rooms r
                LEFT JOIN LATERAL (
                    SELECT CASE WHEN messagetype = 'Image' THEN '[Ảnh]' ELSE content END AS content_display,
                           sentat
                    FROM messages m
                    WHERE m.roomid = r.roomid
                    ORDER BY sentat DESC
                    LIMIT 1
                ) last_msg ON TRUE
                LEFT JOIN (
                    SELECT roomid, COUNT(*) AS unreadcount
                    FROM messages
                    WHERE isread = 0 AND senderid != ?
                    GROUP BY roomid
                ) unread ON unread.roomid = r.roomid
                WHERE r.isgroup = TRUE
                ORDER BY last_msg.sentat DESC NULLS LAST
            """
            # DatabaseManager.execute_query sẽ tự xử lý dấu '?' sang '%s' cho Postgres
            rows = DatabaseManager.execute_query(query, (user_id,), fetch_all=True)
            
            rooms = []
            for row in rows:
                # row[4] là lastsentat (TIMESTAMP)
                last_sent = row[4].strftime('%H:%M') if row[4] and hasattr(row[4], 'strftime') else ''
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
            return []@staticmethod
    def get_group_rooms(user_id):
        """Lấy danh sách nhóm (Sử dụng LATERAL cho PostgreSQL)"""
        try:
            # SỬA LỖI: r.isgroup = TRUE thay vì 1
            query = """
                SELECT r.roomid,
                       r.roomname,
                       r.groupavatar,
                       COALESCE(last_msg.content_display, 'Chưa có tin nhắn') AS lastmessage,
                       last_msg.sentat AS lastsentat,
                       COALESCE(unread.unreadcount, 0) AS unreadcount
                FROM rooms r
                LEFT JOIN LATERAL (
                    SELECT CASE WHEN messagetype = 'Image' THEN '[Ảnh]' ELSE content END AS content_display,
                           sentat
                    FROM messages m
                    WHERE m.roomid = r.roomid
                    ORDER BY sentat DESC
                    LIMIT 1
                ) last_msg ON TRUE
                LEFT JOIN (
                    SELECT roomid, COUNT(*) AS unreadcount
                    FROM messages
                    WHERE isread = 0 AND senderid != ?
                    GROUP BY roomid
                ) unread ON unread.roomid = r.roomid
                WHERE r.isgroup = TRUE
                ORDER BY last_msg.sentat DESC NULLS LAST
            """
            # DatabaseManager.execute_query sẽ tự xử lý dấu '?' sang '%s' cho Postgres
            rows = DatabaseManager.execute_query(query, (user_id,), fetch_all=True)
            
            rooms = []
            for row in rows:
                # row[4] là lastsentat (TIMESTAMP)
                last_sent = row[4].strftime('%H:%M') if row[4] and hasattr(row[4], 'strftime') else ''
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
    def generate_unique_username(base):
        """
        Tạo username duy nhất (Tương thích Postgres & SQL Server)
        """
        try:
            if not base:
                base = 'user'
            
            # 1. Làm sạch base: Loại bỏ ký tự đặc biệt, chuyển về chữ thường
            # Postgres phân biệt chữ hoa/thường nên dùng lowercase là an toàn nhất
            base = ''.join(ch for ch in base if ch.isalnum()).lower()
            if not base:
                base = 'user'
                
            candidate = base
            suffix = 1
            
            # 2. Vòng lặp kiểm tra sự tồn tại
            # Hàm DatabaseManager.username_exists đã được tối ưu ở trên sẽ xử lý việc query
            while DatabaseManager.username_exists(candidate):
                candidate = f"{base}{suffix}"
                suffix += 1
            
            return candidate
        except Exception as e:
            app_logger.error(f"Lỗi khi tạo username duy nhất: {e}")
            # Nếu lỗi, trả về một username ngẫu nhiên kèm timestamp để tránh crash app
            import time
            return f"user_{int(time.time())}"
    
    @staticmethod
    def get_private_rooms(user_id):
        """Lấy danh sách phòng chat cá nhân (Tương thích Postgres)"""
        try:
            # Sửa lỗi: r.isgroup = FALSE thay vì 0
            query = """
                SELECT r.roomid,
                       r.roomname,
                       u.id AS otherid,
                       u.fullname AS otherusername,
                       COALESCE(last_msg.content_display, 'Chưa có tin nhắn') AS lastmessage,
                       last_msg.sentat AS lastsentat,
                       COALESCE(unread.unreadcount, 0) AS unreadcount
                FROM rooms r
                JOIN roomparticipants rp2 ON rp2.roomid = r.roomid AND rp2.id = ?
                JOIN roomparticipants rp ON rp.roomid = r.roomid AND rp.id != ?
                JOIN users u ON u.id = rp.id
                LEFT JOIN LATERAL (
                    SELECT CASE WHEN messagetype = 'Image' THEN '[Ảnh]' ELSE content END AS content_display,
                           sentat
                    FROM messages m
                    WHERE m.roomid = r.roomid
                    ORDER BY sentat DESC
                    LIMIT 1
                ) last_msg ON TRUE
                LEFT JOIN (
                    SELECT roomid, COUNT(*) AS unreadcount
                    FROM messages
                    WHERE isread = 0 AND senderid != ?
                    GROUP BY roomid
                ) unread ON unread.roomid = r.roomid
                WHERE r.isgroup = FALSE
                ORDER BY last_msg.sentat DESC NULLS LAST
            """
            # DatabaseManager.execute_query sẽ tự đổi '?' thành '%s' cho Postgres
            rows = DatabaseManager.execute_query(query, (user_id, user_id, user_id), fetch_all=True)
            
            rooms = []
            for row in rows:
                # row[5] là lastsentat (kiểu datetime)
                last_sent = row[5].strftime('%H:%M') if row[5] and hasattr(row[5], 'strftime') else ''
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
        """Tạo phòng nhóm mới (Tương thích Postgres)"""
        if not group_name or not group_name.strip():
            return None
        try:
            # 1. Chèn phòng mới và lấy ID ngay lập tức bằng RETURNING
            # IsGroup 1 (BIT) -> TRUE (BOOLEAN)
            query = "INSERT INTO rooms (roomname, isgroup) VALUES (?, TRUE) RETURNING roomid"
            row = DatabaseManager.execute_query(query, (group_name.strip(),), fetch_one=True)
            room_id = row[0] if row else None
            
            if room_id:
                # 2. Thêm người tạo vào phòng
                query = "INSERT INTO roomparticipants (roomid, id) VALUES (?, ?)"
                DatabaseManager.execute_query(query, (room_id, user_id))
            
            return room_id
        except Exception as e:
            app_logger.error(f"Create group room error: {e}")
            return None
    
    @staticmethod
    def get_or_create_private_room(user_id, target_user_id):
        """Lấy hoặc tạo phòng chat riêng (Tương thích Postgres)"""
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
            # 1. Kiểm tra phòng tồn tại (Dùng chữ thường cho bảng/cột)
            query = "SELECT roomid FROM rooms WHERE isgroup = FALSE AND roomname = ?"
            existing = DatabaseManager.execute_query(query, (room_name,), fetch_one=True)
            
            if existing:
                room_id = existing[0]
            else:
                # 2. Tạo phòng mới và lấy ID ngay lập tức bằng RETURNING
                query = "INSERT INTO rooms (roomname, isgroup) VALUES (?, FALSE) RETURNING roomid"
                row = DatabaseManager.execute_query(query, (room_name,), fetch_one=True)
                room_id = int(row[0]) if row and row[0] is not None else None
            
            if room_id is None:
                raise ValueError('Could not get roomid when creating private room')
            
            # 3. Thêm thành viên (Dùng bảng roomparticipants)
            for participant_id in (user_id, target_user_id):
                check_query = "SELECT 1 FROM roomparticipants WHERE roomid = ? AND id = ?"
                if not DatabaseManager.execute_query(check_query, (room_id, participant_id), fetch_one=True):
                    insert_query = "INSERT INTO roomparticipants (roomid, id) VALUES (?, ?)"
                    DatabaseManager.execute_query(insert_query, (room_id, participant_id))
            
            # 4. Lấy tên người nhận
            query = "SELECT fullname FROM users WHERE id = ?"
            target_user = DatabaseManager.execute_query(query, (target_user_id,), fetch_one=True)
            target_name = target_user[0] if target_user else f"User {target_user_id}"
            
            return room_id, f"Chat với {target_name}"
        except Exception as e:
            app_logger.error(f"Get or create private room error: {e}")
            return None

    @staticmethod
    def get_analytics_data(export_type):
        """Lấy dữ liệu thống kê (Tương thích Postgres)"""
        try:
            # PostgreSQL yêu cầu tên bảng/cột chính xác (viết thường là an toàn nhất)
            if export_type == 'users':
                query = """
                    SELECT id, fullname, username, email, status, createdat
                    FROM users
                    ORDER BY createdat DESC
                """
            elif export_type == 'messages':
                query = """
                    SELECT m.messageid, m.content, m.messagetype, m.sentat,
                           u.username as sendername
                    FROM messages m
                    JOIN users u ON m.senderid = u.id
                    ORDER BY m.sentat DESC
                """
            elif export_type == 'rooms':
                query = """
                    SELECT roomid, roomname, isgroup, createdat
                    FROM rooms
                    ORDER BY createdat DESC
                """
            elif export_type == 'files':
                query = """
                    SELECT f.fileid, f.filename, f.filetype, f.filesize, f.uploadedat,
                           u.username as uploader
                    FROM sharedfiles f
                    JOIN users u ON f.uploaderid = u.id
                    ORDER BY f.uploadedat DESC
                """
            else:
                return None
            
            return DatabaseManager.execute_query(query, fetch_all=True)
        except Exception as e:
            app_logger.error(f"Get analytics data error: {e}")
            return None
    
    @staticmethod
    def get_room_messages(room_id, limit=100):
        """Lấy danh sách tin nhắn trong phòng (Tương thích Postgres)"""
        try:
            # Chuyển tên bảng Messages -> messages, Users -> users
            # Chuyển tên cột về chữ thường
            query = """
                SELECT m.messageid, m.senderid, u.fullname as sendername, m.content, m.messagetype,
                       m.sentat, m.isread, m.editedat, m.isdeleted, m.deletedat
                FROM messages m
                JOIN users u ON m.senderid = u.id
                WHERE m.roomid = ? AND (m.isdeleted IS NULL OR m.isdeleted = FALSE)
                ORDER BY m.sentat ASC
                LIMIT ?
            """
            # Thêm biến limit vào truy vấn để tối ưu hiệu năng
            messages = DatabaseManager.execute_query(query, (room_id, limit), fetch_all=True)
            
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
        """Đánh dấu tin nhắn đã đọc"""
        try:
            # isread = 1 -> isread = TRUE (hoặc vẫn dùng 0/1 nếu execute_query hỗ trợ chuyển đổi)
            query = "UPDATE messages SET isread = TRUE WHERE roomid = ? AND senderid != ? AND isread = FALSE"
            return DatabaseManager.execute_query(query, (room_id, user_id))
        except Exception as e:
            app_logger.error(f"Mark messages as read error: {e}")
            return 0
    
    @staticmethod
    def edit_message(message_id, user_id, new_content):
        """Chỉnh sửa tin nhắn (Sử dụng CURRENT_TIMESTAMP cho Postgres)"""
        try:
            # Kiểm tra quyền sở hữu tin nhắn
            query = "SELECT senderid FROM messages WHERE messageid = ?"
            message = DatabaseManager.execute_query(query, (message_id,), fetch_one=True)
            
            if not message or message[0] != user_id:
                return False
            
            # Cập nhật nội dung và thời gian sửa đổi
            # Đổi GETDATE() thành CURRENT_TIMESTAMP
            query = "UPDATE messages SET content = ?, editedat = CURRENT_TIMESTAMP WHERE messageid = ?"
            DatabaseManager.execute_query(query, (new_content, message_id))
            return True
        except Exception as e:
            app_logger.error(f"Edit message error: {e}")
            return False
    
    @staticmethod
    def delete_message(message_id, user_id):
        """Xóa tin nhắn (Xóa tạm - Soft delete)"""
        try:
            # Kiểm tra quyền sở hữu tin nhắn
            query = "SELECT senderid FROM messages WHERE messageid = ?"
            message = DatabaseManager.execute_query(query, (message_id,), fetch_one=True)
            
            if not message or message[0] != user_id:
                return False
            
            # Thực hiện xóa tạm: Đổi IsDeleted = 1 thành TRUE, GETDATE() thành CURRENT_TIMESTAMP
            query = "UPDATE messages SET isdeleted = TRUE, deletedat = CURRENT_TIMESTAMP WHERE messageid = ?"
            DatabaseManager.execute_query(query, (message_id,))
            return True
        except Exception as e:
            app_logger.error(f"Delete message error: {e}")
            return False
    
    @staticmethod
    def search(query_str, user_id):
        """Tìm kiếm nhóm và người dùng"""
        try:
            DatabaseManager.ensure_phone_column()
            pattern = f"%{query_str}%"
            results = []
            
            # Tìm kiếm nhóm: IsGroup = 1 thành TRUE
            query_sql = "SELECT roomid, roomname FROM rooms WHERE isgroup = TRUE AND roomname LIKE ?"
            groups = DatabaseManager.execute_query(query_sql, (pattern,), fetch_all=True)
            for group in groups:
                results.append({'id': group[0], 'type': 'Group', 'name': group[1]})
            
            # Tìm kiếm người dùng qua số điện thoại, tên hoặc username
            query_sql = """
                SELECT id, fullname, username, phone 
                FROM users 
                WHERE id != ? AND (phone LIKE ? OR fullname LIKE ? OR username LIKE ?)
            """
            users = DatabaseManager.execute_query(query_sql, (user_id, pattern, pattern, pattern), fetch_all=True)
            for user in users:
                results.append({'id': user[0], 'type': 'User', 'name': user[1], 'phone': user[3]})
            
            return results
        except Exception as e:
            app_logger.error(f"Search error: {e}")
            return []
    
    @staticmethod
    def update_user_profile(user_id, fullname, username, avatar_url=None, phone=None):
        """Cập nhật thông tin cá nhân"""
        try:
            DatabaseManager.ensure_phone_column()
            # Cập nhật thông tin cơ bản
            query = "UPDATE users SET fullname = ?, username = ? WHERE id = ?"
            DatabaseManager.execute_query(query, (fullname, username, user_id))
            
            # Cập nhật ảnh đại diện nếu có
            if avatar_url:
                query = "UPDATE users SET avatarurl = ? WHERE id = ?"
                DatabaseManager.execute_query(query, (avatar_url, user_id))
            
            # Cập nhật số điện thoại nếu có
            if phone:
                query = "UPDATE users SET phone = ? WHERE id = ?"
                DatabaseManager.execute_query(query, (phone, user_id))
            
            return True
        except Exception as e:
            app_logger.error(f"Update user profile error: {e}")
            return False


    @staticmethod
    def check_user_exists(username, phone):
        """Kiểm tra người dùng đã tồn tại qua username hoặc số điện thoại"""
        try:
            DatabaseManager.ensure_phone_column()
            # Sử dụng chữ thường cho tên bảng và cột
            query = "SELECT 1 FROM users WHERE username = ? OR phone = ?"
            result = DatabaseManager.execute_query(query, (username, phone), fetch_one=True)
            return result is not None
        except Exception as e:
            app_logger.error(f"Check user exists error: {e}")
            return False
    
    @staticmethod
    def register_user(username, fullname, phone, password, verification_token=None, is_verified=False):
        """Đăng ký người dùng mới (Tương thích Postgres)"""
        try:
            from werkzeug.security import generate_password_hash
            hashed_password = generate_password_hash(password)
            
            DatabaseManager.ensure_phone_column()
            
            app_logger.info(f"Registering user: username={username}, phone={phone}")
            
            # Chuyển đổi 1/0 thành TRUE/FALSE cho kiểu BOOLEAN của Postgres
            query = """
                INSERT INTO users (username, fullname, phone, password, status, isverified, verificationtoken)
                VALUES (?, ?, ?, ?, 'Offline', ?, ?)
            """
            DatabaseManager.execute_query(query, (username, fullname, phone, hashed_password, is_verified, verification_token))
            return True
        except Exception as e:
            app_logger.error(f"Register user error: {e}")
            return False
    
    @staticmethod
    def ensure_phone_column():
        """Đảm bảo cột phone tồn tại trong bảng users"""
        try:
            # PostgreSQL dùng VARCHAR thay cho NVARCHAR
            if not DatabaseManager.column_exists('users', 'phone'):
                query = "ALTER TABLE users ADD COLUMN phone VARCHAR(20) NULL"
                DatabaseManager.execute_query(query)
                app_logger.info("Added phone column to users table")
        except Exception as e:
            app_logger.error(f"Ensure phone column error: {e}")

    @staticmethod
    def ensure_shared_files_table():
        """Khởi tạo bảng sharedfiles nếu chưa có (Chuẩn Postgres)"""
        try:
            # Kiểm tra sự tồn tại của bảng sharedfiles
            if not DatabaseManager.table_exists('sharedfiles'):
                query = """
                    CREATE TABLE sharedfiles (
                        fileid SERIAL PRIMARY KEY,
                        filename VARCHAR(255) NOT NULL,
                        originalfilename VARCHAR(255) NOT NULL,
                        filepath VARCHAR(500) NOT NULL,
                        filetype VARCHAR(50) NOT NULL,
                        filesize INT NOT NULL,
                        uploaderid INT NOT NULL,
                        uploadedat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        roomid INT NULL,
                        CONSTRAINT fk_uploader FOREIGN KEY (uploaderid) REFERENCES users(id),
                        CONSTRAINT fk_room FOREIGN KEY (roomid) REFERENCES rooms(roomid)
                    )
                """
                DatabaseManager.execute_query(query)
                app_logger.info("Created sharedfiles table")
        except Exception as e:
            app_logger.error(f"Ensure shared files table error: {e}")
    
    @staticmethod
    def upload_file(unique_filename, original_filename, file_url, file_type, file_size, user_id, room_id=None):
        """Lưu thông tin file vào database (Tương thích Postgres)"""
        try:
            DatabaseManager.ensure_shared_files_table()
            
            # Chuyển tên bảng/cột về chữ thường
            # Đổi UploadedBy thành uploaderid để đồng bộ với hàm ensure_shared_files_table
            query = """
                INSERT INTO sharedfiles (filename, originalfilename, filepath, filetype, filesize, uploaderid, roomid)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            DatabaseManager.execute_query(query, (unique_filename, original_filename, file_url, file_type, file_size, user_id, room_id))
            return True
        except Exception as e:
            app_logger.error(f"Upload file error: {e}")
            return False
    
    @staticmethod
    def get_file_info(file_id):
        """Lấy thông tin file theo ID"""
        try:
            query = """
                SELECT filename, originalfilename, filepath, filetype, filesize, uploaderid
                FROM sharedfiles
                WHERE fileid = ?
            """
            return DatabaseManager.execute_query(query, (file_id,), fetch_one=True)
        except Exception as e:
            app_logger.error(f"Get file info error: {e}")
            return None
    
    @staticmethod
    def get_analytics_overview():
        """Lấy số liệu thống kê tổng quan (Chuẩn PostgreSQL)"""
        try:
            stats = {}
            
            # 1. Thống kê User
            stats['total_users'] = DatabaseManager.execute_query("SELECT COUNT(*) FROM users", fetch_one=True)[0]
            # Postgres dùng CURRENT_DATE thay cho CAST(GETDATE() AS DATE)
            stats['new_users_today'] = DatabaseManager.execute_query("SELECT COUNT(*) FROM users WHERE createdat::date = CURRENT_DATE", fetch_one=True)[0]
            # Postgres dùng toán tử INTERVAL thay cho DATEADD
            stats['new_users_week'] = DatabaseManager.execute_query("SELECT COUNT(*) FROM users WHERE createdat >= CURRENT_DATE - INTERVAL '7 days'", fetch_one=True)[0]
            stats['new_users_month'] = DatabaseManager.execute_query("SELECT COUNT(*) FROM users WHERE createdat >= CURRENT_DATE - INTERVAL '30 days'", fetch_one=True)[0]
            
            # 2. Thống kê Tin nhắn
            stats['total_messages'] = DatabaseManager.execute_query("SELECT COUNT(*) FROM messages", fetch_one=True)[0]
            stats['messages_today'] = DatabaseManager.execute_query("SELECT COUNT(*) FROM messages WHERE sentat::date = CURRENT_DATE", fetch_one=True)[0]
            stats['messages_week'] = DatabaseManager.execute_query("SELECT COUNT(*) FROM messages WHERE sentat >= CURRENT_DATE - INTERVAL '7 days'", fetch_one=True)[0]
            stats['messages_month'] = DatabaseManager.execute_query("SELECT COUNT(*) FROM messages WHERE sentat >= CURRENT_DATE - INTERVAL '30 days'", fetch_one=True)[0]
            
            # 3. Thống kê Phòng
            stats['total_rooms'] = DatabaseManager.execute_query("SELECT COUNT(*) FROM rooms", fetch_one=True)[0]
            stats['total_groups'] = DatabaseManager.execute_query("SELECT COUNT(*) FROM rooms WHERE isgroup = TRUE", fetch_one=True)[0]
            stats['new_rooms_today'] = DatabaseManager.execute_query("SELECT COUNT(*) FROM rooms WHERE createdat::date = CURRENT_DATE", fetch_one=True)[0]
            
            # 4. Thống kê File
            stats['total_files'] = DatabaseManager.execute_query("SELECT COUNT(*) FROM sharedfiles", fetch_one=True)[0]
            stats['files_today'] = DatabaseManager.execute_query("SELECT COUNT(*) FROM sharedfiles WHERE uploadedat::date = CURRENT_DATE", fetch_one=True)[0]
            result = DatabaseManager.execute_query("SELECT SUM(filesize) FROM sharedfiles", fetch_one=True)
            stats['total_file_size'] = result[0] if result and result[0] else 0
            
            # 5. Người dùng trực tuyến
            stats['online_users'] = DatabaseManager.execute_query("SELECT COUNT(*) FROM users WHERE status = 'Online'", fetch_one=True)[0]
            
            return stats
        except Exception as e:
            app_logger.error(f"Get analytics overview error: {e}")
            return {}
    
    @staticmethod
    def get_analytics_user_activity(days=30):
        """Lấy dữ liệu hoạt động của người dùng (Tương thích Postgres)"""
        try:
            # 1. Người dùng mới theo ngày
            # Postgres dùng ::date và CURRENT_DATE - INTERVAL
            query = """
                SELECT createdat::date as date, COUNT(*) as newusers
                FROM users
                WHERE createdat >= CURRENT_DATE - (? || ' days')::interval
                GROUP BY createdat::date
                ORDER BY date DESC
            """
            user_activity = DatabaseManager.execute_query(query, (days,), fetch_all=True)
            
            # 2. Số lượng tin nhắn theo ngày
            query = """
                SELECT sentat::date as date, COUNT(*) as messagecount
                FROM messages
                WHERE sentat >= CURRENT_DATE - (? || ' days')::interval
                GROUP BY sentat::date
                ORDER BY date DESC
            """
            message_activity = DatabaseManager.execute_query(query, (days,), fetch_all=True)
            
            # 3. Top 10 người dùng tích cực nhất
            # Đổi TOP 10 thành LIMIT 10 ở cuối câu lệnh
            query = """
                SELECT u.fullname, COUNT(m.messageid) as messagecount
                FROM users u
                LEFT JOIN messages m ON u.id = m.senderid
                WHERE m.sentat >= CURRENT_DATE - (? || ' days')::interval
                GROUP BY u.id, u.fullname
                ORDER BY messagecount DESC
                LIMIT 10
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
        """Lấy số liệu thống kê phòng chat (Tương thích Postgres)"""
        try:
            # 1. Top 10 phòng chat tích cực
            query = """
                SELECT r.roomname, COUNT(m.messageid) as messagecount,
                       COUNT(DISTINCT m.senderid) as activeusers
                FROM rooms r
                LEFT JOIN messages m ON r.roomid = m.roomid
                WHERE m.sentat >= CURRENT_DATE - (? || ' days')::interval
                GROUP BY r.roomid, r.roomname
                ORDER BY messagecount DESC
                LIMIT 10
            """
            top_rooms = DatabaseManager.execute_query(query, (days,), fetch_all=True)
            
            # 2. Thống kê loại phòng (Nhóm vs Cá nhân)
            # isgroup là kiểu BOOLEAN trên Postgres
            query = """
                SELECT CASE WHEN isgroup = TRUE THEN 'Group' ELSE 'Private' END as roomtype,
                       COUNT(*) as count
                FROM rooms
                GROUP BY isgroup
            """
            room_types = DatabaseManager.execute_query(query, fetch_all=True)
            
            # 3. Số phòng mới tạo theo ngày
            query = """
                SELECT createdat::date as date, COUNT(*) as newrooms
                FROM rooms
                WHERE createdat >= CURRENT_DATE - (? || ' days')::interval
                GROUP BY createdat::date
                ORDER BY date DESC
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
        """Lấy số liệu thống kê về tệp tin (Tương thích Postgres)"""
        try:
            # 1. Thống kê theo loại tệp
            # Postgres dùng INTERVAL thay cho DATEADD
            query = """
                SELECT filetype, COUNT(*) as count, SUM(filesize) as totalsize
                FROM sharedfiles
                WHERE uploadedat >= CURRENT_DATE - (? || ' days')::interval
                GROUP BY filetype
                ORDER BY count DESC
            """
            file_types = DatabaseManager.execute_query(query, (days,), fetch_all=True)
            
            # 2. Lượng upload theo ngày
            # Postgres dùng ::date thay cho CAST(... AS DATE)
            query = """
                SELECT uploadedat::date as date, COUNT(*) as filecount,
                       SUM(filesize) as totalsize
                FROM sharedfiles
                WHERE uploadedat::date >= CURRENT_DATE - (? || ' days')::interval
                GROUP BY uploadedat::date
                ORDER BY date DESC
            """
            file_uploads = DatabaseManager.execute_query(query, (days,), fetch_all=True)
            
            # 3. Top 10 người tải lên nhiều nhất
            # Đổi TOP 10 thành LIMIT 10 ở cuối và dùng uploaderid
            query = """
                SELECT u.fullname, COUNT(sf.fileid) as filecount,
                       SUM(sf.filesize) as totalsize
                FROM users u
                LEFT JOIN sharedfiles sf ON u.id = sf.uploaderid
                WHERE sf.uploadedat >= CURRENT_DATE - (? || ' days')::interval
                GROUP BY u.id, u.fullname
                ORDER BY filecount DESC
                LIMIT 10
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
        """Xác thực token email (Tương thích Postgres)"""
        try:
            # Kiểm tra token trong bảng users
            query = "SELECT id FROM users WHERE verificationtoken = ?"
            user = DatabaseManager.execute_query(query, (token,), fetch_one=True)
            
            if not user:
                return False
            
            user_id = user[0]
            # isverified kiểu BOOLEAN trên Postgres -> dùng TRUE
            query = "UPDATE users SET isverified = TRUE, verificationtoken = NULL WHERE id = ?"
            DatabaseManager.execute_query(query, (user_id,))
            return True
        except Exception as e:
            app_logger.error(f"Verify email token error: {e}")
            return False
    
    @staticmethod
    def set_password_reset_token(email, token, expires_at):
        """Thiết lập token đặt lại mật khẩu cho người dùng"""
        try:
            # PostgreSQL yêu cầu tên bảng/cột viết thường
            query = "UPDATE users SET resettoken = ?, resettokenexpiresat = ? WHERE email = ?"
            DatabaseManager.execute_query(query, (token, expires_at, email))
            return True
        except Exception as e:
            app_logger.error(f"Set password reset token error: {e}")
            return False
    
    @staticmethod
    def reset_password_with_token(token, new_password):
        """Đặt lại mật khẩu bằng token (Tương thích Postgres)"""
        try:
            from werkzeug.security import generate_password_hash
            from datetime import datetime
            
            # Lấy thông tin user và thời gian hết hạn
            query = "SELECT id, resettokenexpiresat FROM users WHERE resettoken = ?"
            user = DatabaseManager.execute_query(query, (token,), fetch_one=True)
            
            # Kiểm tra token tồn tại và còn hạn không
            if not user or not user[1] or user[1] < datetime.now():
                return False
            
            user_id = user[0]
            hashed_password = generate_password_hash(new_password)
            
            # Cập nhật mật khẩu mới, xóa token và đánh dấu đã xác thực (isverified = TRUE)
            query = """
                UPDATE users 
                SET password = ?, resettoken = NULL, resettokenexpiresat = NULL, isverified = TRUE 
                WHERE id = ?
            """
            DatabaseManager.execute_query(query, (hashed_password, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Reset password with token error: {e}")
            return False
    
    @staticmethod
    def update_user_oauth(email, provider, oauth_id):
        """Cập nhật thông tin OAuth (Google/Facebook)"""
        try:
            # Đảm bảo isverified = TRUE cho người dùng đăng nhập qua bên thứ ba
            query = "UPDATE users SET oauthprovider = ?, oauthid = ?, isverified = TRUE WHERE email = ?"
            DatabaseManager.execute_query(query, (provider, oauth_id, email))
            return True
        except Exception as e:
            app_logger.error(f"Update user OAuth error: {e}")
            return False
    
    @staticmethod
    def get_online_users():
        """Lấy danh sách người dùng đang trực tuyến (Tương thích Postgres)"""
        try:
            # Chuyển tên bảng/cột về chữ thường
            query = """
                SELECT id, fullname, status
                FROM users
                WHERE status = 'Online'
                ORDER BY fullname
            """
            users = DatabaseManager.execute_query(query, fetch_all=True)
            return [{'user_id': user[0], 'user_name': user[1], 'status': user[2]} for user in users]
        except Exception as e:
            app_logger.error(f"Get online users error: {e}")
            return []
    
    @staticmethod
    def update_notification_enabled(user_id, enabled):
        """Cập nhật trạng thái bật/tắt thông báo cho người dùng"""
        try:
            # Kiểm tra và thêm cột notificationenabled nếu chưa có
            # BIT của SQL Server chuyển thành BOOLEAN của Postgres
            if not DatabaseManager.column_exists('users', 'notificationenabled'):
                query = "ALTER TABLE users ADD COLUMN notificationenabled BOOLEAN NOT NULL DEFAULT TRUE"
                DatabaseManager.execute_query(query)
            
            query = "UPDATE users SET notificationenabled = ? WHERE id = ?"
            DatabaseManager.execute_query(query, (enabled, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Update notification enabled error: {e}")
            return False
    
    @staticmethod
    def ensure_notifications_table():
        """Đảm bảo bảng notifications tồn tại (Chuẩn Postgres)"""
        try:
            if not DatabaseManager.table_exists('notifications'):
                # IDENTITY(1,1) -> SERIAL
                # BIT -> BOOLEAN
                # GETDATE() -> CURRENT_TIMESTAMP
                query = """
                    CREATE TABLE notifications (
                        notificationid SERIAL PRIMARY KEY,
                        id INT NOT NULL,
                        title VARCHAR(255) NOT NULL,
                        message TEXT NOT NULL,
                        type VARCHAR(50) NOT NULL,
                        isread BOOLEAN NOT NULL DEFAULT FALSE,
                        createdat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT fk_user_notification FOREIGN KEY (id) REFERENCES users(id)
                    )
                """
                DatabaseManager.execute_query(query)
                app_logger.info("Created notifications table")
        except Exception as e:
            app_logger.error(f"Ensure notifications table error: {e}")
    
    @staticmethod
    def create_notification(user_id, title, message, notification_type):
        """Tạo một thông báo mới (Tương thích Postgres)"""
        try:
            DatabaseManager.ensure_notifications_table()
            
            # Sử dụng tên bảng/cột viết thường
            query = """
                INSERT INTO notifications (id, title, message, type)
                VALUES (?, ?, ?, ?)
            """
            DatabaseManager.execute_query(query, (user_id, title, message, notification_type))
            return True
        except Exception as e:
            app_logger.error(f"Create notification error: {e}")
            return False
    
    @staticmethod
    def get_user_notifications(user_id):
        """Lấy danh sách thông báo của người dùng"""
        try:
            # Truy vấn sắp xếp theo thời gian mới nhất
            query = """
                SELECT notificationid, title, message, type, isread, createdat
                FROM notifications
                WHERE id = ?
                ORDER BY createdat DESC
            """
            notifications = DatabaseManager.execute_query(query, (user_id,), fetch_all=True)
            
            return [{
                'notification_id': notif[0],
                'title': notif[1],
                'message': notif[2],
                'type': notif[3],
                'is_read': bool(notif[4]), # PostgreSQL trả về True/False cho kiểu BOOLEAN
                'created_at': notif[5].strftime('%Y-%m-%d %H:%M:%S') if notif[5] else ''
            } for notif in notifications]
        except Exception as e:
            app_logger.error(f"Get user notifications error: {e}")
            return []
    
    @staticmethod
    def mark_notification_read(notification_id, user_id):
        """Đánh dấu thông báo là đã đọc (Sử dụng chuẩn BOOLEAN)"""
        try:
            # Chuyển IsRead = 1 (BIT) thành isread = TRUE (BOOLEAN)
            query = """
                UPDATE notifications
                SET isread = TRUE
                WHERE notificationid = ? AND id = ?
            """
            DatabaseManager.execute_query(query, (notification_id, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Mark notification read error: {e}")
            return False
    
    @staticmethod
    def is_room_admin(room_id, user_id):
        """Kiểm tra xem người dùng có phải là Admin của phòng không"""
        try:
            # Ưu tiên kiểm tra trong bảng roomroles (Bảng phân quyền mới)
            DatabaseManager.ensure_room_roles_table()
            rr_query = "SELECT role FROM roomroles WHERE roomid = ? AND id = ?"
            rr = DatabaseManager.execute_query(rr_query, (room_id, user_id), fetch_one=True)
            if rr and rr[0] == 'Admin':
                return True

            # Phương án dự phòng: kiểm tra cột role trong bảng roomparticipants
            query = """
                SELECT COUNT(*) 
                FROM roomparticipants 
                WHERE roomid = ? AND id = ? AND role = 'Admin'
            """
            result = DatabaseManager.execute_query(query, (room_id, user_id), fetch_one=True)
            return result[0] > 0 if result else False
        except Exception as e:
            app_logger.error(f"Is room admin error: {e}")
            return False
    
    @staticmethod
    def user_exists(user_id):
        """Kiểm tra sự tồn tại của người dùng qua id"""
        try:
            query = "SELECT COUNT(*) FROM users WHERE id = ?"
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            return result[0] > 0 if result else False
        except Exception as e:
            app_logger.error(f"User exists error: {e}")
            return False

    @staticmethod
    def create_notification(user_id, title, message, notification_type):
        """Tạo một thông báo mới cho người dùng"""
        try:
            DatabaseManager.ensure_notifications_table()
            query = """
                INSERT INTO notifications (id, title, message, type)
                VALUES (?, ?, ?, ?)
            """
            DatabaseManager.execute_query(query, (user_id, title, message, notification_type))
            return True
        except Exception as e:
            app_logger.error(f"Create notification error: {e}")
            return False

    @staticmethod
    def get_user_notifications(user_id):
        """Lấy danh sách thông báo của người dùng (Tương thích Postgres)"""
        try:
            # Chuyển tên bảng/cột về chữ thường để khớp với cấu trúc Postgres
            query = """
                SELECT notificationid, title, message, type, isread, createdat
                FROM notifications
                WHERE id = ?
                ORDER BY createdat DESC
            """
            notifications = DatabaseManager.execute_query(query, (user_id,), fetch_all=True)
            
            return [{
                'notification_id': notif[0],
                'title': notif[1],
                'message': notif[2],
                'type': notif[3],
                # PostgreSQL trả về giá trị True/False cho kiểu BOOLEAN
                'is_read': bool(notif[4]),
                'created_at': notif[5].strftime('%Y-%m-%d %H:%M:%S') if notif[5] else ''
            } for notif in notifications]
        except Exception as e:
            app_logger.error(f"Get user notifications error: {e}")
            return []

    @staticmethod
    def mark_notification_read(notification_id, user_id):
        """Đánh dấu thông báo là đã đọc (Chuẩn Postgres BOOLEAN)"""
        try:
            # Đổi IsRead = 1 thành isread = TRUE cho phù hợp với PostgreSQL
            query = """
                UPDATE notifications
                SET isread = TRUE
                WHERE notificationid = ? AND id = ?
            """
            DatabaseManager.execute_query(query, (notification_id, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Mark notification read error: {e}")
            return False

    @staticmethod
    def is_room_admin(room_id, user_id):
        """Kiểm tra quyền Admin của người dùng trong phòng (Tương thích Postgres)"""
        try:
            # Đảm bảo bảng roomroles tồn tại
            DatabaseManager.ensure_room_roles_table()
            
            # Kiểm tra trong bảng roomroles (Cấu trúc mới)
            rr_query = "SELECT role FROM roomroles WHERE roomid = ? AND id = ?"
            rr = DatabaseManager.execute_query(rr_query, (room_id, user_id), fetch_one=True)
            if rr and rr[0] == 'Admin':
                return True

            # Phương án dự phòng (Fallback): kiểm tra trong bảng roomparticipants
            query = """
                SELECT COUNT(*) 
                FROM roomparticipants 
                WHERE roomid = ? AND id = ? AND role = 'Admin'
            """
            result = DatabaseManager.execute_query(query, (room_id, user_id), fetch_one=True)
            return result[0] > 0 if result else False
        except Exception as e:
            app_logger.error(f"Is room admin error: {e}")
            return False

    @staticmethod
    def user_exists(user_id):
        """Kiểm tra sự tồn tại của người dùng (Tương thích Postgres)"""
        try:
            # PostgreSQL ưu tiên tên bảng và cột viết thường
            query = "SELECT COUNT(*) FROM users WHERE id = ?"
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            return result[0] > 0 if result else False
        except Exception as e:
            app_logger.error(f"User exists error: {e}")
            return False

    @staticmethod
    def save_message(user_id, content, msg_type='Text', room_id=1, reply_to_message_id=None):
        """Lưu tin nhắn vào database (Chuẩn Postgres)"""
        try:
            # GETDATE() của SQL Server được thay bằng CURRENT_TIMESTAMP trong Postgres
            # IsRead là kiểu BOOLEAN nên dùng FALSE thay vì 0
            query = """
                INSERT INTO messages (senderid, content, messagetype, roomid, replytomessageid, sentat, isread)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, FALSE)
            """
            DatabaseManager.execute_query(query, (user_id, content, msg_type, room_id, reply_to_message_id))
            return True
        except Exception as e:
            app_logger.error(f"Save message error: {e}")
            return False

    @staticmethod
    def save_forwarded_message(user_id, original_message_id, target_room_id):
        """Lưu tin nhắn được chuyển tiếp (Forwarded message)"""
        try:
            # Lấy thông tin tin nhắn gốc
            original_query = """
                SELECT content, messagetype, senderid
                FROM messages
                WHERE messageid = ?
            """
            original = DatabaseManager.execute_query(original_query, (original_message_id,), fetch_one=True)
            
            if not original:
                return False
            
            content = original[0]
            msg_type = original[1]
            # Lưu ý: original_sender_id có thể dùng để hiển thị "Forwarded from..." trên giao diện
            
            # Kiểm tra và thêm cột forwardedfrommessageid nếu chưa tồn tại
            if not DatabaseManager.column_exists('messages', 'forwardedfrommessageid'):
                query = "ALTER TABLE messages ADD COLUMN forwardedfrommessageid INT NULL"
                DatabaseManager.execute_query(query)
            
            # Chèn tin nhắn mới với tham chiếu đến ID tin nhắn gốc
            query = """
                INSERT INTO messages (senderid, content, messagetype, roomid, forwardedfrommessageid, sentat, isread)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, FALSE)
            """
            DatabaseManager.execute_query(query, (user_id, content, msg_type, target_room_id, original_message_id))
            return True
        except Exception as e:
            app_logger.error(f"Save forwarded message error: {e}")
            return False
    @staticmethod
    def user_exists(user_id):
        """Kiểm tra sự tồn tại của người dùng (Tương thích Postgres)"""
        try:
            # PostgreSQL ưu tiên tên bảng và cột viết thường
            query = "SELECT COUNT(*) FROM users WHERE id = ?"
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            return result[0] > 0 if result else False
        except Exception as e:
            app_logger.error(f"User exists error: {e}")
            return False

    @staticmethod
    def save_message(user_id, content, msg_type='Text', room_id=1, reply_to_message_id=None):
        """Lưu tin nhắn vào database (Chuẩn Postgres)"""
        try:
            # GETDATE() của SQL Server được thay bằng CURRENT_TIMESTAMP trong Postgres
            # IsRead là kiểu BOOLEAN nên dùng FALSE thay vì 0
            query = """
                INSERT INTO messages (senderid, content, messagetype, roomid, replytomessageid, sentat, isread)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, FALSE)
            """
            DatabaseManager.execute_query(query, (user_id, content, msg_type, room_id, reply_to_message_id))
            return True
        except Exception as e:
            app_logger.error(f"Save message error: {e}")
            return False

    @staticmethod
    def save_forwarded_message(user_id, original_message_id, target_room_id):
        """Lưu tin nhắn được chuyển tiếp (Forwarded message)"""
        try:
            # Lấy thông tin tin nhắn gốc
            original_query = """
                SELECT content, messagetype, senderid
                FROM messages
                WHERE messageid = ?
            """
            original = DatabaseManager.execute_query(original_query, (original_message_id,), fetch_one=True)
            
            if not original:
                return False
            
            content = original[0]
            msg_type = original[1]
            # Lưu ý: original_sender_id có thể dùng để hiển thị "Forwarded from..." trên giao diện
            
            # Kiểm tra và thêm cột forwardedfrommessageid nếu chưa tồn tại
            if not DatabaseManager.column_exists('messages', 'forwardedfrommessageid'):
                query = "ALTER TABLE messages ADD COLUMN forwardedfrommessageid INT NULL"
                DatabaseManager.execute_query(query)
            
            # Chèn tin nhắn mới với tham chiếu đến ID tin nhắn gốc
            query = """
                INSERT INTO messages (senderid, content, messagetype, roomid, forwardedfrommessageid, sentat, isread)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, FALSE)
            """
            DatabaseManager.execute_query(query, (user_id, content, msg_type, target_room_id, original_message_id))
            return True
        except Exception as e:
            app_logger.error(f"Save forwarded message error: {e}")
            return False

    @staticmethod
    def update_email_notification_enabled(user_id, enabled):
        """Cập nhật trạng thái email notification của user (Tương thích Postgres)"""
        try:
            # Kiểm tra và thêm cột emailnotificationenabled nếu chưa có
            # PostgreSQL dùng BOOLEAN thay vì BIT
            if not DatabaseManager.column_exists('users', 'emailnotificationenabled'):
                query = "ALTER TABLE users ADD COLUMN emailnotificationenabled BOOLEAN DEFAULT FALSE"
                DatabaseManager.execute_query(query)
            
            # Sử dụng giá trị Boolean trực tiếp (True/False)
            query = "UPDATE users SET emailnotificationenabled = ? WHERE id = ?"
            DatabaseManager.execute_query(query, (enabled, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Update email notification enabled error: {e}")
            return False

    @staticmethod
    def get_email_notification_enabled(user_id):
        """Lấy trạng thái email notification của user"""
        try:
            if not DatabaseManager.column_exists('users', 'emailnotificationenabled'):
                return False
            
            query = "SELECT emailnotificationenabled FROM users WHERE id = ?"
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            # Postgres trả về True/False cho kiểu BOOLEAN
            return bool(result[0]) if result and result[0] is not None else False
        except Exception as e:
            app_logger.error(f"Get email notification enabled error: {e}")
            return False

    @staticmethod
    def get_users_with_email_notification_enabled(room_id):
        """Lấy danh sách users trong phòng có bật email notification (Postgres)"""
        try:
            # Query dùng BOOLEAN condition: emailnotificationenabled = TRUE
            query = """
                SELECT u.id, u.email, u.fullname
                FROM users u
                JOIN roomparticipants rp ON u.id = rp.id
                WHERE rp.roomid = ? 
                AND u.email IS NOT NULL 
                AND u.email != ''
                AND u.emailnotificationenabled = TRUE
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
        """Xóa thành viên khỏi nhóm (Tương thích Postgres)"""
        try:
            # Chuyển tên bảng/cột về chữ thường
            query = """
                DELETE FROM roomparticipants
                WHERE roomid = ? AND id = ?
            """
            DatabaseManager.execute_query(query, (room_id, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Remove member from group error: {e}")
            return False

    @staticmethod
    def update_group_info(room_id, room_name, description=None):
        """Cập nhật thông tin nhóm (Chuẩn Postgres)"""
        try:
            # PostgreSQL dùng TEXT hoặc VARCHAR thay vì NVARCHAR
            if not DatabaseManager.column_exists('rooms', 'description'):
                DatabaseManager.execute_query("ALTER TABLE rooms ADD COLUMN description VARCHAR(500) NULL")
            
            if not DatabaseManager.column_exists('rooms', 'avatarurl'):
                DatabaseManager.execute_query("ALTER TABLE rooms ADD COLUMN avatarurl VARCHAR(500) NULL")
            
            query = """
                UPDATE rooms
                SET roomname = ?, description = ?
                WHERE roomid = ?
            """
            DatabaseManager.execute_query(query, (room_name, description, room_id))
            return True
        except Exception as e:
            app_logger.error(f"Update group info error: {e}")
            return False

    @staticmethod
    def create_group_invite(room_id, inviter_id, invitee_id):
        """Tạo lời mời vào nhóm (Tương thích Postgres)"""
        try:
            # Kiểm tra và tạo bảng groupinvites nếu chưa có
            if not DatabaseManager.table_exists('groupinvites'):
                # IDENTITY(1,1) -> SERIAL
                # GETDATE() -> CURRENT_TIMESTAMP
                query = """
                    CREATE TABLE groupinvites (
                        inviteid SERIAL PRIMARY KEY,
                        roomid INT NOT NULL,
                        inviterid INT NOT NULL,
                        inviteeid INT NOT NULL,
                        status VARCHAR(50) DEFAULT 'Pending',
                        createdat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT fk_room FOREIGN KEY (roomid) REFERENCES rooms(roomid),
                        CONSTRAINT fk_inviter FOREIGN KEY (inviterid) REFERENCES users(id),
                        CONSTRAINT fk_invitee FOREIGN KEY (inviteeid) REFERENCES users(id)
                    )
                """
                DatabaseManager.execute_query(query)
            
            # Kiểm tra xem lời mời đang chờ (Pending) đã tồn tại chưa
            check_query = """
                SELECT inviteid FROM groupinvites 
                WHERE roomid = ? AND inviteeid = ? AND status = 'Pending'
            """
            existing = DatabaseManager.execute_query(check_query, (room_id, invitee_id), fetch_one=True)
            if existing:
                return False 
            
            # Tạo lời mời mới
            query = """
                INSERT INTO groupinvites (roomid, inviterid, inviteeid, status, createdat)
                VALUES (?, ?, ?, 'Pending', CURRENT_TIMESTAMP)
            """
            DatabaseManager.execute_query(query, (room_id, inviter_id, invitee_id))
            return True
        except Exception as e:
            app_logger.error(f"Create group invite error: {e}")
            return False

    @staticmethod
    def get_pending_invites(user_id):
        """Lấy danh sách lời mời đang chờ của người dùng (Tương thích Postgres)"""
        try:
            # Chuyển tên bảng/cột về chữ thường
            query = """
                SELECT gi.inviteid, gi.roomid, gi.inviterid, gi.createdat,
                       r.roomname, r.avatarurl, u.fullname as invitername
                FROM groupinvites gi
                JOIN rooms r ON gi.roomid = r.roomid
                JOIN users u ON gi.inviterid = u.id
                WHERE gi.inviteeid = ? AND gi.status = 'Pending'
                ORDER BY gi.createdat DESC
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
        """Chấp nhận hoặc từ chối lời mời vào nhóm"""
        try:
            # Lấy thông tin lời mời
            query = """
                SELECT roomid, inviteeid FROM groupinvites 
                WHERE inviteid = ? AND inviteeid = ? AND status = 'Pending'
            """
            invite = DatabaseManager.execute_query(query, (invite_id, user_id), fetch_one=True)
            
            if not invite:
                return False
            
            room_id = invite[0]
            
            if action == 'accept':
                # Thêm user vào nhóm (Gọi hàm đã có trong DatabaseManager)
                DatabaseManager.add_member_to_group(room_id, user_id)
            
            # Cập nhật trạng thái lời mời
            update_query = """
                UPDATE groupinvites 
                SET status = ? 
                WHERE inviteid = ?
            """
            status = 'Accepted' if action == 'accept' else 'Declined'
            DatabaseManager.execute_query(update_query, (status, invite_id))
            return True
        except Exception as e:
            app_logger.error(f"Accept/decline invite error: {e}")
            return False

    @staticmethod
    def is_room_member(room_id, user_id):
        """Kiểm tra xem người dùng có phải thành viên phòng không"""
        try:
            query = """
                SELECT COUNT(*) 
                FROM roomparticipants 
                WHERE roomid = ? AND id = ?
            """
            result = DatabaseManager.execute_query(query, (room_id, user_id), fetch_one=True)
            return result[0] > 0 if result else False
        except Exception as e:
            app_logger.error(f"Is room member error: {e}")
            return False

        
    @staticmethod
    def ensure_room_participants_table():
        """Đảm bảo bảng roomparticipants tồn tại (Chuẩn Postgres)"""
        try:
            app_logger.info("Checking/creating roomparticipants table")
            # PostgreSQL dùng cú pháp CREATE TABLE IF NOT EXISTS đơn giản hơn
            query = """
                CREATE TABLE IF NOT EXISTS roomparticipants (
                    roomid INT NOT NULL,
                    id INT NOT NULL,
                    joinedat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    role VARCHAR(50) DEFAULT 'Member',
                    PRIMARY KEY (roomid, id),
                    CONSTRAINT fk_room FOREIGN KEY (roomid) REFERENCES rooms(roomid),
                    CONSTRAINT fk_user FOREIGN KEY (id) REFERENCES users(id)
                )
            """
            DatabaseManager.execute_query(query)
            app_logger.info("roomparticipants table checked/created successfully")
        except Exception as e:
            app_logger.error(f"RoomParticipants table creation error: {e}")

    @staticmethod
    def get_group_members(room_id):
        """Lấy danh sách thành viên trong nhóm (Postgres)"""
        try:
            query = """
                SELECT u.id, u.fullname, u.username, rp.role, rp.joinedat, u.status
                FROM roomparticipants rp
                JOIN users u ON rp.id = u.id
                WHERE rp.roomid = ?
                ORDER BY CASE WHEN rp.role = 'Admin' THEN 1 ELSE 2 END, u.fullname
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
    def search_messages_in_room(room_id, search_text, page=1, limit=20):
        """Tìm kiếm tin nhắn trong phòng (Phân trang chuẩn Postgres)"""
        try:
            offset = (page - 1) * limit
            
            # PostgreSQL dùng LIMIT và OFFSET thay vì OFFSET/FETCH NEXT
            # Sử dụng ILIKE để tìm kiếm không phân biệt hoa thường (đặc trưng của Postgres)
            search_query = """
                SELECT m.messageid, m.senderid, u.fullname as sendername, m.content,
                       m.messagetype, m.sentat, m.editedat, m.isdeleted
                FROM messages m
                JOIN users u ON m.senderid = u.id
                WHERE m.roomid = ? AND (m.isdeleted IS FALSE OR m.isdeleted IS NULL)
                  AND (m.content ILIKE ? OR u.fullname ILIKE ?)
                ORDER BY m.sentat DESC
                LIMIT ? OFFSET ?
            """
            messages = DatabaseManager.execute_query(
                search_query, 
                (room_id, f"%{search_text}%", f"%{search_text}%", limit, offset), 
                fetch_all=True
            )
            
            # Lấy tổng số kết quả
            count_query = """
                SELECT COUNT(*)
                FROM messages m
                JOIN users u ON m.senderid = u.id
                WHERE m.roomid = ? AND (m.isdeleted IS FALSE OR m.isdeleted IS NULL)
                  AND (m.content ILIKE ? OR u.fullname ILIKE ?)
            """
            total_result = DatabaseManager.execute_query(
                count_query, 
                (room_id, f"%{search_text}%", f"%{search_text}%"), 
                fetch_one=True
            )
            total = total_result[0] if total_result else 0
            
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
    def global_search_messages(user_id, query_text, page=1, limit=20):
        """Tìm kiếm tin nhắn toàn cầu trên tất cả các phòng mà user tham gia"""
        try:
            offset = (page - 1) * limit
            search_pattern = f"%{query_text}%"
            
            # PostgreSQL dùng LIMIT/OFFSET thay vì OFFSET/FETCH
            # Sử dụng ILIKE để tìm kiếm tiếng Việt có dấu/không dấu linh hoạt hơn
            search_query = """
                SELECT DISTINCT m.messageid, m.senderid, u.fullname as sendername, m.content,
                       m.messagetype, m.sentat, m.roomid, r.roomname,
                       CASE WHEN r.isgroup IS TRUE THEN r.roomname ELSE 'Chat riêng' END as roomdisplayname
                FROM messages m
                JOIN users u ON m.senderid = u.id
                JOIN rooms r ON m.roomid = r.roomid
                JOIN roomparticipants rp ON r.roomid = rp.roomid AND rp.id = ?
                WHERE (m.isdeleted IS FALSE OR m.isdeleted IS NULL)
                  AND (m.content ILIKE ? OR u.fullname ILIKE ? OR r.roomname ILIKE ?)
                ORDER BY m.sentat DESC
                LIMIT ? OFFSET ?
            """
            messages = DatabaseManager.execute_query(
                search_query, 
                (user_id, search_pattern, search_pattern, search_pattern, limit, offset), 
                fetch_all=True
            )
            
            # Lấy tổng số kết quả (Dùng COUNT DISTINCT để tránh trùng lặp)
            count_query = """
                SELECT COUNT(DISTINCT m.messageid)
                FROM messages m
                JOIN users u ON m.senderid = u.id
                JOIN rooms r ON m.roomid = r.roomid
                JOIN roomparticipants rp ON r.roomid = rp.roomid AND rp.id = ?
                WHERE (m.isdeleted IS FALSE OR m.isdeleted IS NULL)
                  AND (m.content ILIKE ? OR u.fullname ILIKE ? OR r.roomname ILIKE ?)
            """
            total_result = DatabaseManager.execute_query(
                count_query, 
                (user_id, search_pattern, search_pattern, search_pattern), 
                fetch_one=True
            )
            total = total_result[0] if total_result else 0
            
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
    def get_search_suggestions(user_id, query_text):
        """Lấy gợi ý tìm kiếm cho người dùng và phòng chat"""
        try:
            search_pattern = f"%{query_text}%"
            # Postgres yêu cầu các cột trong UNION ALL phải tương đồng hoàn toàn về kiểu dữ liệu
            search_query = """
                SELECT DISTINCT 'user' as type, u.fullname as name, u.username as username
                FROM users u
                WHERE u.id != ? AND (u.fullname ILIKE ? OR u.username ILIKE ?)
                UNION ALL
                SELECT DISTINCT 'room' as type, r.roomname as name, '' as username
                FROM rooms r
                JOIN roomparticipants rp ON r.roomid = rp.roomid AND rp.id = ?
                WHERE r.roomname ILIKE ?
                ORDER BY name
                LIMIT 10
            """
            suggestions = DatabaseManager.execute_query(
                search_query, 
                (user_id, search_pattern, search_pattern, user_id, search_pattern), 
                fetch_all=True
            )
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
        """Cập nhật thông tin nhóm (Tương thích Postgres)"""
        try:
            # PostgreSQL dùng VARCHAR thay cho NVARCHAR
            if not DatabaseManager.column_exists('rooms', 'description'):
                DatabaseManager.execute_query("ALTER TABLE rooms ADD COLUMN description VARCHAR(500) NULL")
            
            if not DatabaseManager.column_exists('rooms', 'avatarurl'):
                DatabaseManager.execute_query("ALTER TABLE rooms ADD COLUMN avatarurl VARCHAR(500) NULL")
            
            query = """
                UPDATE rooms
                SET roomname = ?, description = ?
                WHERE roomid = ?
            """
            DatabaseManager.execute_query(query, (room_name, description, room_id))
            return True
        except Exception as e:
            app_logger.error(f"Update group info error: {e}")
            return False
    
    @staticmethod
    def is_room_member(room_id, user_id):
        """Kiểm tra xem người dùng có phải thành viên của phòng không"""
        try:
            # Viết thường tên bảng và cột để tránh lỗi định danh trong Postgres
            query = """
                SELECT COUNT(*) 
                FROM roomparticipants 
                WHERE roomid = ? AND id = ?
            """
            result = DatabaseManager.execute_query(query, (room_id, user_id), fetch_one=True)
            return result[0] > 0 if result else False
        except Exception as e:
            app_logger.error(f"Is room member error: {e}")
            return False
    
    @staticmethod
    def get_group_members(room_id):
        """Lấy danh sách thành viên trong nhóm kèm thông tin chi tiết"""
        try:
            query = """
                SELECT u.id, u.fullname, u.username, rp.role, rp.joinedat, u.status
                FROM roomparticipants rp
                JOIN users u ON rp.id = u.id
                WHERE rp.roomid = ?
                ORDER BY CASE WHEN rp.role = 'Admin' THEN 1 ELSE 2 END, u.fullname
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
    def update_group_info(room_id, room_name, description=None):
        """Cập nhật thông tin nhóm (Tương thích Postgres)"""
        try:
            # PostgreSQL dùng VARCHAR thay cho NVARCHAR
            if not DatabaseManager.column_exists('rooms', 'description'):
                DatabaseManager.execute_query("ALTER TABLE rooms ADD COLUMN description VARCHAR(500) NULL")
            
            if not DatabaseManager.column_exists('rooms', 'avatarurl'):
                DatabaseManager.execute_query("ALTER TABLE rooms ADD COLUMN avatarurl VARCHAR(500) NULL")
            
            query = """
                UPDATE rooms
                SET roomname = ?, description = ?
                WHERE roomid = ?
            """
            DatabaseManager.execute_query(query, (room_name, description, room_id))
            return True
        except Exception as e:
            app_logger.error(f"Update group info error: {e}")
            return False
    
    @staticmethod
    def is_room_member(room_id, user_id):
        """Kiểm tra xem người dùng có phải thành viên của phòng không"""
        try:
            # Viết thường tên bảng và cột để tránh lỗi định danh trong Postgres
            query = """
                SELECT COUNT(*) 
                FROM roomparticipants 
                WHERE roomid = ? AND id = ?
            """
            result = DatabaseManager.execute_query(query, (room_id, user_id), fetch_one=True)
            return result[0] > 0 if result else False
        except Exception as e:
            app_logger.error(f"Is room member error: {e}")
            return False
    
    @staticmethod
    def get_group_members(room_id):
        """Lấy danh sách thành viên trong nhóm kèm thông tin chi tiết"""
        try:
            query = """
                SELECT u.id, u.fullname, u.username, rp.role, rp.joinedat, u.status
                FROM roomparticipants rp
                JOIN users u ON rp.id = u.id
                WHERE rp.roomid = ?
                ORDER BY CASE WHEN rp.role = 'Admin' THEN 1 ELSE 2 END, u.fullname
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
    def search_messages_in_room(room_id, query_text, page=1, limit=20):
        """Tìm kiếm tin nhắn trong một phòng cụ thể (Chuẩn Postgres)"""
        try:
            offset = (page - 1) * limit
            search_pattern = f"%{query_text}%"
            
            # Sử dụng LIMIT/OFFSET thay cho OFFSET/FETCH NEXT
            # ILIKE giúp tìm kiếm không phân biệt hoa thường và hỗ trợ tốt hơn cho tiếng Việt
            search_query = """
                SELECT m.messageid, m.senderid, u.fullname as sendername, m.content,
                       m.messagetype, m.sentat, m.editedat, m.isdeleted
                FROM messages m
                JOIN users u ON m.senderid = u.id
                WHERE m.roomid = ? AND (m.isdeleted IS FALSE OR m.isdeleted IS NULL)
                  AND (m.content ILIKE ? OR u.fullname ILIKE ?)
                ORDER BY m.sentat DESC
                LIMIT ? OFFSET ?
            """
            messages = DatabaseManager.execute_query(
                search_query, 
                (room_id, search_pattern, search_pattern, limit, offset), 
                fetch_all=True
            )
            
            # Lấy tổng số kết quả để phân trang
            count_query = """
                SELECT COUNT(*)
                FROM messages m
                JOIN users u ON m.senderid = u.id
                WHERE m.roomid = ? AND (m.isdeleted IS FALSE OR m.isdeleted IS NULL)
                  AND (m.content ILIKE ? OR u.fullname ILIKE ?)
            """
            total_result = DatabaseManager.execute_query(
                count_query, 
                (room_id, search_pattern, search_pattern), 
                fetch_one=True
            )
            total = total_result[0] if total_result else 0
            
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
    def global_search_messages(user_id, query_text, page=1, limit=20):
        """Tìm kiếm tin nhắn trên tất cả các phòng mà người dùng tham gia"""
        try:
            offset = (page - 1) * limit
            search_pattern = f"%{query_text}%"
            
            # Logic xử lý: Chỉ tìm trong các phòng mà user_id là thành viên (RoomParticipants)
            search_query = """
                SELECT DISTINCT m.messageid, m.senderid, u.fullname as sendername, m.content,
                       m.messagetype, m.sentat, m.roomid, r.roomname,
                       CASE WHEN r.isgroup IS TRUE THEN r.roomname ELSE 'Chat riêng' END as roomdisplayname
                FROM messages m
                JOIN users u ON m.senderid = u.id
                JOIN rooms r ON m.roomid = r.roomid
                JOIN roomparticipants rp ON r.roomid = rp.roomid AND rp.id = ?
                WHERE (m.isdeleted IS FALSE OR m.isdeleted IS NULL)
                  AND (m.content ILIKE ? OR u.fullname ILIKE ? OR r.roomname ILIKE ?)
                ORDER BY m.sentat DESC
                LIMIT ? OFFSET ?
            """
            messages = DatabaseManager.execute_query(
                search_query, 
                (user_id, search_pattern, search_pattern, search_pattern, limit, offset), 
                fetch_all=True
            )
            
            # Đếm tổng số kết quả duy nhất
            count_query = """
                SELECT COUNT(DISTINCT m.messageid)
                FROM messages m
                JOIN users u ON m.senderid = u.id
                JOIN rooms r ON m.roomid = r.roomid
                JOIN roomparticipants rp ON r.roomid = rp.roomid AND rp.id = ?
                WHERE (m.isdeleted IS FALSE OR m.isdeleted IS NULL)
                  AND (m.content ILIKE ? OR u.fullname ILIKE ? OR r.roomname ILIKE ?)
            """
            total_result = DatabaseManager.execute_query(
                count_query, 
                (user_id, search_pattern, search_pattern, search_pattern), 
                fetch_one=True
            )
            total = total_result[0] if total_result else 0
            
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
    def get_search_suggestions(user_id, query_text):
        """Lấy gợi ý tìm kiếm cho người dùng và phòng chat (Tương thích Postgres)"""
        try:
            search_pattern = f"%{query_text}%"
            # Sử dụng ILIKE để tìm kiếm không phân biệt hoa thường
            search_query = """
                SELECT DISTINCT 'user' as type, u.fullname as name, u.username as username
                FROM users u
                WHERE u.id != ? AND (u.fullname ILIKE ? OR u.username ILIKE ?)
                UNION ALL
                SELECT DISTINCT 'room' as type, r.roomname as name, '' as username
                FROM rooms r
                JOIN roomparticipants rp ON r.roomid = rp.roomid AND rp.id = ?
                WHERE r.roomname ILIKE ?
                ORDER BY name
                LIMIT 10
            """
            suggestions = DatabaseManager.execute_query(
                search_query, 
                (user_id, search_pattern, search_pattern, user_id, search_pattern), 
                fetch_all=True
            )
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
        """Thiết lập giao diện (Light/Dark) cho người dùng"""
        try:
            # Kiểm tra và tạo cột theme nếu chưa có (Postgres dùng VARCHAR)
            if not DatabaseManager.column_exists('users', 'theme'):
                DatabaseManager.execute_query("ALTER TABLE users ADD COLUMN theme VARCHAR(20) NOT NULL DEFAULT 'light'")
            
            query = """
                UPDATE users
                SET theme = ?
                WHERE id = ?
            """
            DatabaseManager.execute_query(query, (theme, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Set theme error: {e}")
            return False
    
    @staticmethod
    def get_theme(user_id):
        """Lấy cấu hình giao diện của người dùng"""
        try:
            if not DatabaseManager.column_exists('users', 'theme'):
                DatabaseManager.execute_query("ALTER TABLE users ADD COLUMN theme VARCHAR(20) NOT NULL DEFAULT 'light'")
            
            query = """
                SELECT theme
                FROM users
                WHERE id = ?
            """
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            return result[0] if result else 'light'
        except Exception as e:
            app_logger.error(f"Get theme error: {e}")
            return 'light'
    
    @staticmethod
    def toggle_theme(user_id):
        """Chuyển đổi giao diện sáng/tối cho người dùng"""
        try:
            if not DatabaseManager.column_exists('users', 'theme'):
                DatabaseManager.execute_query("ALTER TABLE users ADD COLUMN theme VARCHAR(20) NOT NULL DEFAULT 'light'")
            
            # Lấy theme hiện tại
            query = "SELECT theme FROM users WHERE id = ?"
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            current_theme = result[0] if result else 'light'
            
            # Đảo ngược theme
            new_theme = 'dark' if current_theme == 'light' else 'light'
            
            update_query = "UPDATE users SET theme = ? WHERE id = ?"
            DatabaseManager.execute_query(update_query, (new_theme, user_id))
            return new_theme
        except Exception as e:
            app_logger.error(f"Toggle theme error: {e}")
            return 'light'
    
    @staticmethod
    def is_admin(user_id):
        """Kiểm tra quyền quản trị viên (Admin)"""
        try:
            if not DatabaseManager.column_exists('users', 'role'):
                DatabaseManager.execute_query("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'User'")
            
            query = "SELECT role FROM users WHERE id = ?"
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            role = result[0] if result else 'User'
            return role == 'Admin'
        except Exception as e:
            app_logger.error(f"Is admin error: {e}")
            return False
    
    @staticmethod
    def get_admin_dashboard_stats():
        """Lấy thống kê tổng quan cho trang quản trị (Chuẩn Postgres)"""
        try:
            # Các câu lệnh đếm tổng đơn giản
            total_users = DatabaseManager.execute_query("SELECT COUNT(*) FROM users", fetch_one=True)[0]
            total_rooms = DatabaseManager.execute_query("SELECT COUNT(*) FROM rooms", fetch_one=True)[0]
            total_messages = DatabaseManager.execute_query("SELECT COUNT(*) FROM messages", fetch_one=True)[0]
            total_files = DatabaseManager.execute_query("SELECT COUNT(*) FROM sharedfiles", fetch_one=True)[0]
            online_users = DatabaseManager.execute_query("SELECT COUNT(*) FROM users WHERE status = 'Online'", fetch_one=True)[0]
            
            # Thống kê tin nhắn 7 ngày gần nhất (Dùng INTERVAL)
            daily_stats_query = """
                SELECT sentat::DATE as Date, COUNT(*) as MessageCount
                FROM messages
                WHERE sentat >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY sentat::DATE
                ORDER BY Date DESC
            """
            daily_stats = DatabaseManager.execute_query(daily_stats_query, fetch_all=True)
            
            # Top 10 người dùng tích cực nhất (30 ngày qua)
            top_users_query = """
                SELECT u.fullname, COUNT(m.messageid) as MessageCount
                FROM users u
                LEFT JOIN messages m ON u.id = m.senderid
                WHERE m.sentat >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY u.id, u.fullname
                ORDER BY MessageCount DESC
                LIMIT 10
            """
            top_users = DatabaseManager.execute_query(top_users_query, fetch_all=True)
            
            # Top 10 phòng chat sôi nổi nhất (30 ngày qua)
            top_rooms_query = """
                SELECT r.roomname, COUNT(m.messageid) as MessageCount
                FROM rooms r
                LEFT JOIN messages m ON r.roomid = m.roomid
                WHERE m.sentat >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY r.roomid, r.roomname
                ORDER BY MessageCount DESC
                LIMIT 10
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
            return {'total_users': 0, 'total_rooms': 0, 'total_messages': 0, 'online_users': 0}
    
    @staticmethod
    def get_admin_users(page=1, limit=20):
        """Lấy danh sách người dùng cho Admin với phân trang (Chuẩn Postgres)"""
        try:
            offset = (page - 1) * limit
            
            # Sử dụng LIMIT OFFSET thay cho OFFSET FETCH ROWS
            query = """
                SELECT u.id, u.fullname, u.username, u.email, u.status, u.role,
                       u.createdat, u.lastloginat,
                       COUNT(m.messageid) as MessageCount
                FROM users u
                LEFT JOIN messages m ON u.id = m.senderid
                GROUP BY u.id, u.fullname, u.username, u.email, u.status, u.role, u.createdat, u.lastloginat
                ORDER BY u.createdat DESC
                LIMIT ? OFFSET ?
            """
            users = DatabaseManager.execute_query(query, (limit, offset), fetch_all=True)
            
            count_query = "SELECT COUNT(*) FROM users"
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
        """Cập nhật quyền người dùng"""
        try:
            query = "UPDATE users SET role = ? WHERE id = ?"
            DatabaseManager.execute_query(query, (new_role, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Update user role error: {e}")
            return False
    
    @staticmethod
    def get_system_stats():
        """Lấy thống kê hệ thống chi tiết (Postgres)"""
        try:
            stats = {}
            
            # Thống kê User
            stats['total_users'] = DatabaseManager.execute_query("SELECT COUNT(*) FROM users", fetch_one=True)[0]
            stats['online_users'] = DatabaseManager.execute_query("SELECT COUNT(*) FROM users WHERE status = 'Online'", fetch_one=True)[0]
            
            # So sánh ngày trong Postgres: dùng CURRENT_DATE
            stats['new_users_today'] = DatabaseManager.execute_query(
                "SELECT COUNT(*) FROM users WHERE createdat::DATE = CURRENT_DATE", fetch_one=True)[0]
            
            # Thống kê Tin nhắn
            stats['total_messages'] = DatabaseManager.execute_query("SELECT COUNT(*) FROM messages", fetch_one=True)[0]
            stats['messages_today'] = DatabaseManager.execute_query(
                "SELECT COUNT(*) FROM messages WHERE sentat::DATE = CURRENT_DATE", fetch_one=True)[0]
            
            # Thống kê File (Lưu ý: SUM có thể trả về None nếu không có dữ liệu)
            stats['total_files'] = DatabaseManager.execute_query("SELECT COUNT(*) FROM sharedfiles", fetch_one=True)[0]
            result_size = DatabaseManager.execute_query("SELECT SUM(filesize) FROM sharedfiles", fetch_one=True)
            stats['total_file_size'] = result_size[0] if result_size and result_size[0] else 0
            
            # Thống kê Phòng (Postgres dùng kiểu BOOLEAN cho isgroup)
            stats['total_rooms'] = DatabaseManager.execute_query("SELECT COUNT(*) FROM rooms", fetch_one=True)[0]
            stats['total_groups'] = DatabaseManager.execute_query(
                "SELECT COUNT(*) FROM rooms WHERE isgroup IS TRUE", fetch_one=True)[0]
            
            return stats
        except Exception as e:
            app_logger.error(f"Get system stats error: {e}")
            return {'total_users': 0, 'online_users': 0, 'total_messages': 0}
    
    @staticmethod
    def ensure_voice_messages_table():
        """Đảm bảo bảng voicemessages tồn tại (Chuẩn Postgres)"""
        try:
            # PostgreSQL sử dụng chữ thường cho tên bảng/cột để tránh lỗi phân biệt hoa thường
            if not DatabaseManager.column_exists('voicemessages', 'voiceid'):
                create_table_query = """
                    CREATE TABLE voicemessages (
                        voiceid SERIAL PRIMARY KEY,
                        filename VARCHAR(255) NOT NULL,
                        filepath VARCHAR(500) NOT NULL,
                        duration INT NULL,
                        filesize INT NOT NULL,
                        uploadedby INT NOT NULL,
                        roomid INT NULL,
                        createdat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (uploadedby) REFERENCES users(id),
                        FOREIGN KEY (roomid) REFERENCES rooms(roomid)
                    )
                """
                DatabaseManager.execute_query(create_table_query)
        except Exception as e:
            app_logger.error(f"Ensure voice messages table error: {e}")
    
    @staticmethod
    def save_voice_message(filename, filepath, filesize, uploaded_by, room_id=None, duration=None):
        """Lưu thông tin tin nhắn thoại vào cơ sở dữ liệu"""
        try:
            DatabaseManager.ensure_voice_messages_table()
            query = """
                INSERT INTO voicemessages (filename, filepath, filesize, uploadedby, roomid, duration)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            DatabaseManager.execute_query(query, (filename, filepath, filesize, uploaded_by, room_id, duration))
            return True
        except Exception as e:
            app_logger.error(f"Save voice message error: {e}")
            return False
    
    @staticmethod
    def get_voice_messages(room_id, user_id):
        """Lấy danh sách tin nhắn thoại trong phòng chat"""
        try:
            # Kiểm tra xem người dùng có phải thành viên phòng không
            if not DatabaseManager.is_room_member(room_id, user_id):
                return []
            
            query = """
                SELECT vm.voiceid, vm.filename, vm.filepath, vm.duration,
                       vm.filesize, vm.createdat, u.fullname as sendername
                FROM voicemessages vm
                JOIN users u ON vm.uploadedby = u.id
                WHERE vm.roomid = ?
                ORDER BY vm.createdat DESC
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
        """Khởi tạo 2FA cho người dùng (Postgres)"""
        try:
            # Đảm bảo bảng users có cột chứa Secret (Dùng VARCHAR thay cho NVARCHAR)
            if not DatabaseManager.column_exists('users', 'twofasecret'):
                DatabaseManager.execute_query("ALTER TABLE users ADD COLUMN twofasecret VARCHAR(255) NULL")
            
            # Sử dụng kiểu BOOLEAN thay cho BIT
            if not DatabaseManager.column_exists('users', 'twofaenabled'):
                DatabaseManager.execute_query("ALTER TABLE users ADD COLUMN twofaenabled BOOLEAN NOT NULL DEFAULT FALSE")
            
            # Lưu secret và tạm thời để trạng thái chưa kích hoạt (FALSE)
            query = """
                UPDATE users
                SET twofasecret = ?, twofaenabled = FALSE
                WHERE id = ?
            """
            DatabaseManager.execute_query(query, (secret, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Enable 2FA error: {e}")
            return False
    
    @staticmethod
    def get_2fa_secret(user_id):
        """Lấy mã secret 2FA của người dùng"""
        try:
            query = "SELECT twofasecret FROM users WHERE id = ?"
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            return result[0] if result and result[0] else None
        except Exception as e:
            app_logger.error(f"Get 2FA secret error: {e}")
            return None
    
    @staticmethod
    def enable_2fa_verified(user_id):
        """Chính thức kích hoạt 2FA sau khi người dùng nhập đúng mã xác nhận lần đầu"""
        try:
            # Trong Postgres, dùng TRUE cho kiểu BOOLEAN
            query = "UPDATE users SET twofaenabled = TRUE WHERE id = ?"
            DatabaseManager.execute_query(query, (user_id,))
            return True
        except Exception as e:
            app_logger.error(f"Enable 2FA verified error: {e}")
            return False
    
    @staticmethod
    def get_user_password_and_2fa_secret(user_id):
        """Lấy mật khẩu và mã secret 2FA của người dùng (Postgres)"""
        try:
            # PostgreSQL ưu tiên tên cột viết thường
            query = """
                SELECT password, twofasecret
                FROM users
                WHERE id = ?
            """
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            return result if result else (None, None)
        except Exception as e:
            app_logger.error(f"Get user password and 2FA secret error: {e}")
            return (None, None)
    
    @staticmethod
    def disable_2fa(user_id):
        """Tắt tính năng 2FA cho người dùng"""
        try:
            # Trong Postgres, dùng FALSE thay cho 0 và NULL cho secret
            query = """
                UPDATE users
                SET twofaenabled = FALSE, twofasecret = NULL
                WHERE id = ?
            """
            DatabaseManager.execute_query(query, (user_id,))
            return True
        except Exception as e:
            app_logger.error(f"Disable 2FA error: {e}")
            return False
    
    @staticmethod
    def get_2fa_secret_and_status(user_id):
        """Lấy mã secret và trạng thái kích hoạt 2FA"""
        try:
            query = """
                SELECT twofasecret, twofaenabled
                FROM users
                WHERE id = ?
            """
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            # result[1] lúc này sẽ là True hoặc False (kiểu boolean của Postgres)
            return result if result else (None, False)
        except Exception as e:
            app_logger.error(f"Get 2FA secret and status error: {e}")
            return (None, False)
    
    @staticmethod
    def is_2fa_enabled(user_id):
        """Kiểm tra xem 2FA có đang bật hay không"""
        try:
            query = "SELECT twofaenabled FROM users WHERE id = ?"
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            # Postgres trả về giá trị boolean nên không cần ép kiểu phức tạp
            return result[0] if result else False
        except Exception as e:
            app_logger.error(f"Is 2FA enabled error: {e}")
            return False

    @staticmethod
    def ensure_message_reactions_table():
        """Đảm bảo bảng messagereactions tồn tại (Chuẩn Postgres)"""
        try:
            # PostgreSQL ưu tiên tên bảng viết thường
            if not DatabaseManager.column_exists('messagereactions', 'reactionid'):
                query = """
                    CREATE TABLE messagereactions (
                        reactionid SERIAL PRIMARY KEY,
                        messageid INT NOT NULL,
                        id INT NOT NULL,
                        emoji VARCHAR(50) NOT NULL,
                        createdat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (messageid) REFERENCES messages(messageid),
                        FOREIGN KEY (id) REFERENCES users(id),
                        UNIQUE (messageid, id, emoji)
                    )
                """
                DatabaseManager.execute_query(query)
                app_logger.info("Created messagereactions table")
        except Exception as e:
            app_logger.error(f"Ensure message reactions table error: {e}")
    
    @staticmethod
    def add_reaction(message_id, user_id, emoji):
        """Thêm cảm xúc vào tin nhắn"""
        try:
            DatabaseManager.ensure_message_reactions_table()
            query = """
                INSERT INTO messagereactions (messageid, id, emoji)
                VALUES (?, ?, ?)
            """
            DatabaseManager.execute_query(query, (message_id, user_id, emoji))
            return True
        except Exception as e:
            # Trong Postgres, khi vi phạm UNIQUE constraint, ta kiểm tra thông điệp lỗi
            if "unique constraint" in str(e).lower():
                return False  # Người dùng đã thả biểu cảm này rồi
            app_logger.error(f"Add reaction error: {e}")
            return False
    
    @staticmethod
    def remove_reaction(message_id, user_id, emoji):
        """Xóa cảm xúc khỏi tin nhắn"""
        try:
            query = """
                DELETE FROM messagereactions
                WHERE messageid = ? AND id = ? AND emoji = ?
            """
            DatabaseManager.execute_query(query, (message_id, user_id, emoji))
            return True
        except Exception as e:
            app_logger.error(f"Remove reaction error: {e}")
            return False
    
    @staticmethod
    def get_message_reactions(message_id):
        """Lấy tất cả cảm xúc của một tin nhắn (Postgres)"""
        try:
            # PostgreSQL ưu tiên tên viết thường
            query = """
                SELECT emoji, COUNT(*) as count
                FROM messagereactions
                WHERE messageid = ?
                GROUP BY emoji
            """
            reactions = DatabaseManager.execute_query(query, (message_id,), fetch_all=True)
            return {emoji: count for emoji, count in reactions}
        except Exception as e:
            app_logger.error(f"Get message reactions error: {e}")
            return {}

    @staticmethod
    def ensure_reply_column():
        """Đảm bảo cột replytomessageid tồn tại trong bảng messages"""
        try:
            # Sử dụng tên bảng/cột viết thường để tránh lỗi Case-sensitive trên Render
            if not DatabaseManager.column_exists('messages', 'replytomessageid'):
                query = "ALTER TABLE messages ADD COLUMN replytomessageid INT NULL"
                DatabaseManager.execute_query(query)
                app_logger.info("Added replytomessageid column to messages table")
        except Exception as e:
            app_logger.error(f"Ensure reply column error: {e}")
    
    @staticmethod
    def get_message_for_reply(message_id):
        """Lấy thông tin tin nhắn gốc để hiển thị trong phần trả lời"""
        try:
            DatabaseManager.ensure_reply_column()
            # Join bảng users để lấy tên người gửi tin nhắn gốc
            query = """
                SELECT m.messageid, m.content, m.messagetype, u.fullname as sendername, m.sentat
                FROM messages m
                JOIN users u ON m.senderid = u.id
                WHERE m.messageid = ?
            """
            result = DatabaseManager.execute_query(query, (message_id,), fetch_one=True)
            if result:
                return {
                    'message_id': result[0],
                    'content': result[1],
                    'type': result[2],
                    'sender_name': result[3],
                    # Xử lý định dạng thời gian từ TIMESTAMP của Postgres
                    'sent_at': result[4].strftime('%Y-%m-%d %H:%M:%S') if result[4] else None
                }
            return None
        except Exception as e:
            app_logger.error(f"Get message for reply error: {e}")
            return None

    @staticmethod
    def ensure_pinned_column():
        """Đảm bảo cột ispinnned tồn tại trong bảng messages (Postgres)"""
        try:
            # PostgreSQL ưu tiên tên viết thường và sử dụng BOOLEAN thay cho BIT
            if not DatabaseManager.column_exists('messages', 'ispinned'):
                query = "ALTER TABLE messages ADD COLUMN ispinned BOOLEAN DEFAULT FALSE"
                DatabaseManager.execute_query(query)
                app_logger.info("Added ispinned column to messages table")
        except Exception as e:
            app_logger.error(f"Ensure pinned column error: {e}")
    
    @staticmethod
    def pin_message(message_id, user_id):
        """Ghim một tin nhắn"""
        try:
            DatabaseManager.ensure_pinned_column()
            
            # Kiểm tra quyền hạn: Chỉ người gửi hoặc Admin mới được ghim
            query = "SELECT senderid, roomid FROM messages WHERE messageid = ?"
            result = DatabaseManager.execute_query(query, (message_id,), fetch_one=True)
            if not result:
                return False
            
            sender_id = result[0]
            if sender_id != user_id:
                # Kiểm tra vai trò người dùng (Tới đã có hàm get_user_role)
                user_role = DatabaseManager.get_user_role(user_id)
                if user_role != 'Admin':
                    return False
            
            # Trong Postgres, sử dụng giá trị TRUE thay cho 1
            query = "UPDATE messages SET ispinned = TRUE WHERE messageid = ?"
            DatabaseManager.execute_query(query, (message_id,))
            return True
        except Exception as e:
            app_logger.error(f"Pin message error: {e}")
            return False
    
    @staticmethod
    def unpin_message(message_id, user_id):
        """Bỏ ghim một tin nhắn"""
        try:
            DatabaseManager.ensure_pinned_column()
            # Trong Postgres, sử dụng giá trị FALSE thay cho 0
            query = "UPDATE messages SET ispinned = FALSE WHERE messageid = ?"
            DatabaseManager.execute_query(query, (message_id,))
            return True
        except Exception as e:
            app_logger.error(f"Unpin message error: {e}")
            return False
    
    @staticmethod
    def get_pinned_messages(room_id):
        """Lấy tất cả tin nhắn đã ghim trong một phòng (Postgres)"""
        try:
            DatabaseManager.ensure_pinned_column()
            # PostgreSQL ưu tiên tên viết thường. Lưu ý dùng TRUE thay cho 1.
            query = """
                SELECT m.messageid, m.content, m.messagetype, m.sentat, m.replytomessageid,
                       u.username as sendername, u.id as senderid
                FROM messages m
                JOIN users u ON m.senderid = u.id
                WHERE m.roomid = ? AND m.ispinned = TRUE AND m.isdeleted = FALSE
                ORDER BY m.sentat DESC
            """
            messages = DatabaseManager.execute_query(query, (room_id,), fetch_all=True)
            return messages
        except Exception as e:
            app_logger.error(f"Get pinned messages error: {e}")
            return []

    @staticmethod
    def ensure_mentions_table():
        """Đảm bảo bảng mentions tồn tại trong database Postgres"""
        try:
            if not DatabaseManager.column_exists('mentions', 'mentionid'):
                # SERIAL thay IDENTITY, BOOLEAN thay BIT, TIMESTAMP thay DATETIME
                query = """
                    CREATE TABLE mentions (
                        mentionid SERIAL PRIMARY KEY,
                        messageid INT NOT NULL,
                        mentionedid INT NOT NULL,
                        mentioningid INT NOT NULL,
                        createdat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        isread BOOLEAN DEFAULT FALSE,
                        FOREIGN KEY (messageid) REFERENCES messages(messageid),
                        FOREIGN KEY (mentionedid) REFERENCES users(id),
                        FOREIGN KEY (mentioningid) REFERENCES users(id)
                    )
                """
                DatabaseManager.execute_query(query)
                app_logger.info("Created mentions table")
        except Exception as e:
            app_logger.error(f"Ensure mentions table error: {e}")
    
    @staticmethod
    def save_mentions(message_id, mentioned_user_ids, mentioning_user_id):
        """Lưu danh sách những người bị nhắc tên trong tin nhắn"""
        try:
            DatabaseManager.ensure_mentions_table()
            for mentioned_user_id in mentioned_user_ids:
                query = """
                    INSERT INTO mentions (messageid, mentionedid, mentioningid)
                    VALUES (?, ?, ?)
                """
                DatabaseManager.execute_query(query, (message_id, mentioned_user_id, mentioning_user_id))
            return True
        except Exception as e:
            app_logger.error(f"Save mentions error: {e}")
            return False
    
    @staticmethod
    def parse_mentions(content, room_id):
        """Trích xuất @mentions từ nội dung tin nhắn và trả về danh sách ID người dùng"""
        try:
            import re
            # Tìm các chuỗi bắt đầu bằng @ theo sau là chữ cái hoặc số
            mentions = re.findall(r'@(\w+)', content)
            if not mentions:
                return []
            
            # Lấy thông tin người dùng trong phòng chat có username trùng với danh sách mentions
            # Sử dụng tham số hóa để bảo mật SQL Injection
            placeholders = ','.join(['?' for _ in mentions])
            query = f"""
                SELECT DISTINCT u.id, u.username
                FROM users u
                JOIN roomparticipants rp ON u.id = rp.id
                WHERE rp.roomid = ? AND u.username IN ({placeholders})
            """
            
            params = [room_id] + mentions
            users = DatabaseManager.execute_query(query, params, fetch_all=True)
            
            # Tạo dictionary mapping để tra cứu nhanh ID từ username
            username_to_id = {user[1]: user[0] for user in users}
            mentioned_ids = [username_to_id.get(username) for username in mentions if username in username_to_id]
            
            # Loại bỏ các giá trị trùng lặp nếu một người bị tag nhiều lần trong 1 tin nhắn
            return list(set(mentioned_ids))
        except Exception as e:
            app_logger.error(f"Parse mentions error: {e}")
            return []
    
    @staticmethod
    def get_user_mentions(user_id):
        """Lấy tất cả các thông báo nhắc tên của một người dùng (Postgres)"""
        try:
            DatabaseManager.ensure_mentions_table()
            # Sử dụng JOIN để lấy nội dung tin nhắn và tên người đã nhắc mình
            query = """
                SELECT m.mentionid, m.messageid, m.mentioningid, m.createdat, m.isread,
                       msg.content, msg.roomid, u.username as mentioningusername
                FROM mentions m
                JOIN messages msg ON m.messageid = msg.messageid
                JOIN users u ON m.mentioningid = u.id
                WHERE m.mentionedid = ?
                ORDER BY m.createdat DESC
            """
            mentions = DatabaseManager.execute_query(query, (user_id,), fetch_all=True)
            return mentions
        except Exception as e:
            app_logger.error(f"Get user mentions error: {e}")
            return []
    
    @staticmethod
    def mark_mention_as_read(mention_id):
        """Đánh dấu một thông báo nhắc tên là đã đọc"""
        try:
            DatabaseManager.ensure_mentions_table()
            # Trong Postgres, cập nhật IsRead thành TRUE thay vì 1
            query = "UPDATE mentions SET isread = TRUE WHERE mentionid = ?"
            DatabaseManager.execute_query(query, (mention_id,))
            return True
        except Exception as e:
            app_logger.error(f"Mark mention as read error: {e}")
            return False

    @staticmethod
    def ensure_group_avatar_column():
        """Đảm bảo cột groupavatar tồn tại trong bảng rooms (Postgres)"""
        try:
            # PostgreSQL dùng TEXT hoặc VARCHAR thay cho NVARCHAR
            if not DatabaseManager.column_exists('rooms', 'groupavatar'):
                query = "ALTER TABLE rooms ADD COLUMN groupavatar TEXT NULL"
                DatabaseManager.execute_query(query)
                app_logger.info("Added groupavatar column to rooms table")
        except Exception as e:
            app_logger.error(f"Ensure group avatar column error: {e}")

    @staticmethod
    def update_group_avatar(room_id, avatar_url):
        """Cập nhật ảnh đại diện cho phòng chat"""
        try:
            DatabaseManager.ensure_group_avatar_column()
            query = "UPDATE rooms SET groupavatar = ? WHERE roomid = ?"
            DatabaseManager.execute_query(query, (avatar_url, room_id))
            return True
        except Exception as e:
            app_logger.error(f"Update group avatar error: {e}")
            return False

    @staticmethod
    def get_group_avatar(room_id):
        """Lấy link ảnh đại diện của phòng chat"""
        try:
            DatabaseManager.ensure_group_avatar_column()
            query = "SELECT groupavatar FROM rooms WHERE roomid = ?"
            result = DatabaseManager.execute_query(query, (room_id,), fetch_one=True)
            return result[0] if result and result[0] else None
        except Exception as e:
            app_logger.error(f"Get group avatar error: {e}")
            return None

    @staticmethod
    def ensure_muted_rooms_table():
        """Đảm bảo bảng mutedrooms tồn tại trong Postgres"""
        try:
            if not DatabaseManager.column_exists('mutedrooms', 'mutedroomid'):
                # SERIAL thay IDENTITY, TIMESTAMP thay DATETIME
                query = """
                    CREATE TABLE mutedrooms (
                        mutedroomid SERIAL PRIMARY KEY,
                        id INT NOT NULL,
                        roomid INT NOT NULL,
                        mutedat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (id) REFERENCES users(id),
                        FOREIGN KEY (roomid) REFERENCES rooms(roomid),
                        UNIQUE(id, roomid)
                    )
                """
                DatabaseManager.execute_query(query)
                app_logger.info("Created mutedrooms table")
        except Exception as e:
            app_logger.error(f"Ensure muted rooms table error: {e}")

    @staticmethod
    def mute_room(user_id, room_id):
        """Tắt thông báo cho một phòng chat"""
        try:
            DatabaseManager.ensure_muted_rooms_table()
            # Kiểm tra xem đã tắt thông báo chưa
            # Postgres sử dụng tên bảng/cột viết thường để tránh lỗi phân biệt hoa thường
            check_query = "SELECT 1 FROM mutedrooms WHERE id = ? AND roomid = ?"
            exists = DatabaseManager.execute_query(check_query, (user_id, room_id), fetch_one=True)
            
            if not exists:
                insert_query = "INSERT INTO mutedrooms (id, roomid) VALUES (?, ?)"
                DatabaseManager.execute_query(insert_query, (user_id, room_id))
            return True
        except Exception as e:
            app_logger.error(f"Mute room error: {e}")
            return False

    @staticmethod
    def unmute_room(user_id, room_id):
        """Bật lại thông báo cho một phòng chat"""
        try:
            DatabaseManager.ensure_muted_rooms_table()
            query = "DELETE FROM mutedrooms WHERE id = ? AND roomid = ?"
            DatabaseManager.execute_query(query, (user_id, room_id))
            return True
        except Exception as e:
            app_logger.error(f"Unmute room error: {e}")
            return False

    @staticmethod
    def is_room_muted(user_id, room_id):
        """Kiểm tra trạng thái tắt thông báo của một phòng"""
        try:
            DatabaseManager.ensure_muted_rooms_table()
            query = "SELECT 1 FROM mutedrooms WHERE id = ? AND roomid = ?"
            result = DatabaseManager.execute_query(query, (user_id, room_id), fetch_one=True)
            return result is not None
        except Exception as e:
            app_logger.error(f"Check room muted error: {e}")
            return False

    @staticmethod
    def get_muted_rooms(user_id):
        """Lấy danh sách ID của tất cả các phòng đã tắt thông báo"""
        try:
            DatabaseManager.ensure_muted_rooms_table()
            query = "SELECT roomid FROM mutedrooms WHERE id = ?"
            results = DatabaseManager.execute_query(query, (user_id,), fetch_all=True)
            # Trả về list ID đơn giản để dễ dàng xử lý ở Front-end
            return [r[0] for r in results]
        except Exception as e:
            app_logger.error(f"Get muted rooms error: {e}")
            return []

    @staticmethod
    def ensure_room_roles_table():
        """Đảm bảo bảng roomroles tồn tại trong Postgres"""
        try:
            if not DatabaseManager.column_exists('roomroles', 'roleid'):
                # SERIAL thay IDENTITY, VARCHAR thay NVARCHAR, TIMESTAMP thay DATETIME
                query = """
                    CREATE TABLE roomroles (
                        roleid SERIAL PRIMARY KEY,
                        roomid INT NOT NULL,
                        id INT NOT NULL,
                        role VARCHAR(50) DEFAULT 'Member',
                        assignedat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (roomid) REFERENCES rooms(roomid),
                        FOREIGN KEY (id) REFERENCES users(id),
                        UNIQUE(roomid, id)
                    )
                """
                DatabaseManager.execute_query(query)
                app_logger.info("Created roomroles table")
        except Exception as e:
            app_logger.error(f"Ensure room roles table error: {e}")

    @staticmethod
    def assign_role(room_id, user_id, role):
        """Gán quyền cho người dùng trong phòng chat"""
        try:
            DatabaseManager.ensure_room_roles_table()
            
            # Kiểm tra tính hợp lệ của quyền
            valid_roles = ['Admin', 'Moderator', 'Member']
            if role not in valid_roles:
                role = 'Member'
                
            # Kiểm tra xem người dùng đã có quyền trong phòng này chưa
            check_query = "SELECT 1 FROM roomroles WHERE roomid = ? AND id = ?"
            exists = DatabaseManager.execute_query(check_query, (room_id, user_id), fetch_one=True)
            
            if exists:
                update_query = "UPDATE roomroles SET role = ? WHERE roomid = ? AND id = ?"
                DatabaseManager.execute_query(update_query, (role, room_id, user_id))
            else:
                insert_query = "INSERT INTO roomroles (roomid, id, role) VALUES (?, ?, ?)"
                DatabaseManager.execute_query(insert_query, (room_id, user_id, role))

            # Đồng bộ với bảng roomparticipants để đảm bảo tính tương thích
            try:
                if DatabaseManager.column_exists('roomparticipants', 'role'):
                    sync_query = "UPDATE roomparticipants SET role = ? WHERE roomid = ? AND id = ?"
                    DatabaseManager.execute_query(sync_query, (role, room_id, user_id))
            except Exception as e:
                app_logger.warning(f"Sync RoomParticipants.role failed: {e}")

            return True
        except Exception as e:
            app_logger.error(f"Assign role error: {e}")
            return False

    @staticmethod
    def get_user_role(room_id, user_id):
        """Lấy quyền hiện tại của người dùng trong phòng"""
        try:
            DatabaseManager.ensure_room_roles_table()
            query = "SELECT role FROM roomroles WHERE roomid = ? AND id = ?"
            result = DatabaseManager.execute_query(query, (room_id, user_id), fetch_one=True)
            # Mặc định là Member nếu không tìm thấy dữ liệu
            return result[0] if result else 'Member'
        except Exception as e:
            app_logger.error(f"Get user role error: {e}")
            return 'Member'

    @staticmethod
    def get_room_members_with_roles(room_id):
        """Lấy danh sách thành viên trong phòng kèm theo quyền hạn (Postgres)"""
        try:
            DatabaseManager.ensure_room_roles_table()
            # Sử dụng LEFT JOIN để đảm bảo ngay cả khi chưa có bản ghi trong roomroles, 
            # thành viên vẫn hiện ra với quyền mặc định.
            query = """
                SELECT u.id, u.fullname, u.username, u.status, rr.role
                FROM users u
                JOIN roomparticipants rp ON u.id = rp.id
                LEFT JOIN roomroles rr ON u.id = rr.id AND rp.roomid = rr.roomid
                WHERE rp.roomid = ?
            """
            results = DatabaseManager.execute_query(query, (room_id,), fetch_all=True)
            
            # Trả về danh sách dictionary để Tới dễ dàng đổ dữ liệu lên UI (HTML/React/Flutter)
            return [{
                'user_id': r[0],
                'full_name': r[1],
                'username': r[2],
                'status': r[3],
                'role': r[4] if r[4] else 'Member'
            } for r in results]
        except Exception as e:
            app_logger.error(f"Get room members with roles error: {e}")
            return []

    @staticmethod
    def remove_role(room_id, user_id):
        """Xóa quyền hạn đặc biệt của người dùng (Reset về Member)"""
        try:
            DatabaseManager.ensure_room_roles_table()
            # Trong Postgres, chỉ cần xóa dòng tương ứng trong roomroles, 
            # logic get_room_members_with_roles sẽ tự hiểu là 'Member'.
            query = "DELETE FROM roomroles WHERE roomid = ? AND id = ?"
            DatabaseManager.execute_query(query, (room_id, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Remove role error: {e}")
            return False

# Khởi tạo các bảng cần thiết khi chạy ứng dụng
DatabaseManager.ensure_room_participants_table()
DatabaseManager.ensure_user_auth_columns()