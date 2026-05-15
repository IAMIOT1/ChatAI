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
            INSERT INTO users (username, password_hash, fullname, email, status, createdat)
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
        query = "SELECT id, username, password_hash, fullname, email, status FROM users WHERE id = ?"
        return DatabaseManager.execute_query(query, (username,), fetch_one=True)

    @staticmethod
    def save_message(user_id, content, msg_type='Text', room_id=1, reply_to_message_id=None):
        try:
            # Tạm thời comment dòng này nếu bạn đã build DB cứng trên Render
            # DatabaseManager.ensure_reply_column() 
            
            if reply_to_message_id:
                query = """
                    INSERT INTO messages (room_id, sender_id, content, messagetype, isread, sentat, reply_to_message_id)
                    VALUES (?, ?, ?, ?, 0, GETDATE(), ?)
                """
                params = (room_id, user_id, content, msg_type, reply_to_message_id)
            else:
                query = """
                    INSERT INTO messages (room_id, sender_id, content, messagetype, isread, sentat)
                    VALUES (?, ?, ?, ?, 0, GETDATE())
                """
                params = (room_id, user_id, content, msg_type)
            return DatabaseManager.execute_query(query, params)
        except Exception as e:
            app_logger.error(f"Save message error: {e}")
            raise
    
    @staticmethod
    def get_room_messages(room_id, limit=50):
        try:
            # Cột khóa chính của messages giờ là 'id'
            # Cột khóa ngoại là 'room_id' và 'sender_id'
            query = """
                SELECT m.id, m.content, m.messagetype, m.sentat, m.isread,
                    u.username as sendername, u.id as senderid, m.reply_to_message_id
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                WHERE m.room_id = ? AND m.isdeleted = FALSE
                ORDER BY m.sentat DESC
                LIMIT {}
            """.format(limit)
            
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
                query = "SELECT id, room_name, createdat FROM rooms ORDER BY createdat DESC"
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
        try:
            query = """
                CREATE TABLE IF NOT EXISTS room_participants (
                    room_id INTEGER REFERENCES rooms(id) ON DELETE CASCADE,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    joinedat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (room_id, user_id)
                )
            """
            DatabaseManager.execute_query(query)
        except Exception as e:
            app_logger.error(f"room_participants table creation error: {e}")
    
    @staticmethod
    def ensure_user_auth_columns():
        """Đảm bảo các cột xác thực tồn tại (Chuẩn Postgres)"""
        try:
            # Danh sách cột cần kiểm tra trong bảng users
            columns_to_add = [
                ('email', "ALTER TABLE users ADD COLUMN email VARCHAR(255) NULL"),
                ('isverified', "ALTER TABLE users ADD COLUMN isverified BOOLEAN NOT NULL DEFAULT FALSE"),
                ('verificationtoken', "ALTER TABLE users ADD COLUMN verificationtoken VARCHAR(255) NULL"),
                ('oauthprovider', "ALTER TABLE users ADD COLUMN oauthprovider VARCHAR(50) NULL"),
                ('oauthid', "ALTER TABLE users ADD COLUMN oauthid VARCHAR(255) NULL"),
                ('resettoken', "ALTER TABLE users ADD COLUMN resettoken VARCHAR(255) NULL"),
                ('resettokenexpiresat', "ALTER TABLE users ADD COLUMN resettokenexpiresat TIMESTAMP NULL")
            ]
            
            for col, sql in columns_to_add:
                # Luôn kiểm tra tên cột bằng chữ thường
                if not DatabaseManager.column_exists('users', col.lower()):
                    DatabaseManager.execute_query(sql)
            
            # Kiểm tra cột trong bảng messages
            if not DatabaseManager.column_exists('messages', 'editedat'):
                DatabaseManager.execute_query("ALTER TABLE messages ADD COLUMN editedat TIMESTAMP NULL")
                
            app_logger.info("Checked/Added auth columns successfully")
        except Exception as e:
            app_logger.error(f"Auth columns check error: {e}")

    @staticmethod
    def ensure_last_seen_column():
        """Đảm bảo cột trạng thái hoạt động tồn tại"""
        try:
            if not DatabaseManager.column_exists('users', 'lastseenat'):
                # Dùng TIMESTAMP DEFAULT CURRENT_TIMESTAMP để tự động lưu giờ hoạt động
                query = "ALTER TABLE users ADD COLUMN lastseenat TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                DatabaseManager.execute_query(query)
        except Exception as e:
            app_logger.error(f"Error adding lastseenat column: {e}")

    @staticmethod
    def update_user_status(user_id, status):
        try:
            # Gộp logic: Nếu Online thì cập nhật cả thời gian, nếu Offline thì chỉ cập nhật status
            if status == 'Online':
                query = "UPDATE users SET status = ?, lastseenat = CURRENT_TIMESTAMP WHERE id = ?"
            else:
                query = "UPDATE users SET status = ? WHERE id = ?"
                
            return DatabaseManager.execute_query(query, (status, user_id))
        except Exception as e:
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
        """Lấy thông tin cá nhân (Khớp chuẩn Postgres trên Render)"""
        try:
            # Tới đảm bảo cột status message đã tồn tại nhé
            DatabaseManager.ensure_user_status_message_column()
            DatabaseManager.ensure_phone_column()
            
            # Thêm 'userstatusmessage' vào câu lệnh SELECT
            query = """
                SELECT fullname, username, phone, status, lastseenat, userstatusmessage
                FROM users
                WHERE id = ?
            """
            user = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            
            if user:
                return {
                    'full_name': user[0] or '',
                    'username': user[1] or '',
                    'phone': user[2] or '',
                    'status': user[3] or 'Offline',
                    # Xử lý format thời gian an toàn
                    'last_seen': user[4].strftime('%d/%m/%Y %H:%M') if user[4] and hasattr(user[4], 'strftime') else None,
                    # Lấy cột tiểu sử mới thêm vào
                    'bio': user[5] or '' 
                }
            
            return None # Trả về None để bên app.py dễ xử lý redirect nếu không thấy user
        except Exception as e:
            app_logger.error(f"Lỗi lấy Profile của user {user_id}: {e}")
            return None

    @staticmethod
    def get_user_last_seen(user_id):
        """Lấy thời gian hoạt động cuối cùng (Tối ưu format)"""
        try:
            # Thay vì ensure liên tục, hãy đảm bảo cột đã có từ lúc khởi tạo app
            query = "SELECT lastseenat FROM users WHERE id = ?"
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            
            if result and result[0]:
                dt = result[0]
                # Nếu là string (thường gặp khi dùng SQLite hoặc một số cấu hình Postgres cũ)
                if isinstance(dt, str):
                    return dt
                
                # Format kiểu Việt Nam cho thân thiện
                return dt.strftime('%H:%M - %d/%m/%Y')
            
            return "Chưa từng hoạt động"
        except Exception as e:
            app_logger.error(f"Lỗi lấy last_seen của user {user_id}: {e}")
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
    def set_user_status_message(user_id, status_message):
        """Cập nhật dòng trạng thái (Cắt bớt nếu quá dài)"""
        try:
            if not status_message:
                status_message = ""
                
            # Giới hạn 200 ký tự để tránh làm hỏng giao diện hoặc lỗi DB
            clean_message = status_message.strip()[:200]
            
            query = "UPDATE users SET userstatusmessage = ? WHERE id = ?"
            result = DatabaseManager.execute_query(query, (clean_message, user_id))
            
            if result:
                app_logger.info(f"User {user_id} đã cập nhật trạng thái mới.")
            return result
        except Exception as e:
            app_logger.error(f"Lỗi cập nhật status message cho user {user_id}: {e}")
            return 0
    
    @staticmethod
    def get_user_by_email(email):
        """Tìm người dùng qua email (Khớp chuẩn Postgres)"""
        try:
            # Tên cột trong DB mới: id, username, password_hash, fullname, email, status
            query = "SELECT id, username, password_hash, fullname, email, status FROM users WHERE email = ?"
            return DatabaseManager.execute_query(query, (email,), fetch_one=True)
        except Exception as e:
            app_logger.error(f"Lỗi tìm user theo email {email}: {e}")
            return None

    @staticmethod
    def username_exists(username):
        """Kiểm tra username đã tồn tại chưa"""
        try:
            query = "SELECT 1 FROM users WHERE username = ?"
            result = DatabaseManager.execute_query(query, (username,), fetch_one=True)
            return result is not None
        except Exception as e:
            app_logger.error(f"Lỗi kiểm tra username {username}: {e}")
            return False
    
    @staticmethod
    def get_unread_counts(user_id):
        """Lấy số lượng tin nhắn chưa đọc theo từng phòng"""
        try:
            # room_id: để biết phòng nào có tin nhắn mới
            # isread = 0 (hoặc FALSE nếu dùng kiểu Boolean)
            # sender_id != user_id: không đếm tin nhắn của chính mình
            query = """
                SELECT room_id, COUNT(*) AS unread_count
                FROM messages
                WHERE isread = 0 AND sender_id != ?
                GROUP BY room_id
            """
            rows = DatabaseManager.execute_query(query, (user_id,), fetch_all=True)
            
            # Trả về dictionary: {room_id: count}
            # Ví dụ: {1: 5, 2: 10} nghĩa là phòng 1 có 5 tin chưa đọc
            return {row[0]: row[1] for row in rows} if rows else {}
        except Exception as e:
            app_logger.error(f"Lỗi lấy số tin nhắn chưa đọc của user {user_id}: {e}")
            return {}
    
    @staticmethod
    def get_user_by_oauth(provider, oauth_id):
        """Lấy người dùng qua OAuth (Khớp chuẩn Postgres)"""
        try:
            # Postgres ưu tiên chữ thường. Đảm bảo tên cột khớp với lúc ADD COLUMN
            query = "SELECT id, fullname, username, email FROM users WHERE oauthprovider = ? AND oauthid = ?"
            return DatabaseManager.execute_query(query, (provider, oauth_id), fetch_one=True)
        except Exception as e:
            app_logger.error(f"Lỗi lấy user OAuth ({provider}): {e}")
            return None
    
    @staticmethod
    def create_oauth_user(provider, oauth_id, email, full_name):
        """Tạo người dùng OAuth mới (Tối ưu cho Postgres)"""
        try:
            import secrets
            from werkzeug.security import generate_password_hash
            
            # Tạo username duy nhất từ email
            username_base = email.split('@')[0] if email else f"{provider}_{secrets.token_hex(4)}"
            username = DatabaseManager.generate_unique_username(username_base)
            
            # Tạo mật khẩu ngẫu nhiên (vì login OAuth không cần dùng pass này)
            password_hash = generate_password_hash(secrets.token_urlsafe(16))
            
            # LƯU Ý: Đổi tên cột 'password' thành 'password_hash' nếu Tới dùng tên đó trong file SQL
            # 'TRUE' trong Postgres dành cho kiểu BOOLEAN
            query = """
                INSERT INTO users (username, fullname, email, password_hash, status, isverified, oauthprovider, oauthid, createdat)
                VALUES (?, ?, ?, ?, 'Offline', TRUE, ?, ?, CURRENT_TIMESTAMP)
            """
            params = (username, full_name, email, password_hash, provider, oauth_id)
            
            DatabaseManager.execute_query(query, params)
            
            # Sau khi tạo xong, lấy lại thông tin user để trả về
            return DatabaseManager.get_user_by_oauth(provider, oauth_id)
        except Exception as e:
            app_logger.error(f"Lỗi tạo user OAuth mới: {e}")
            return None

    @staticmethod
    def get_group_rooms(user_id):
        """Lấy danh sách nhóm (Chuẩn hóa cho PostgreSQL trên Render)"""
        try:
            query = """
                SELECT r.id,
                    r.room_name,
                    r.group_avatar,
                    COALESCE(last_msg.content_display, 'Chưa có tin nhắn') AS lastmessage,
                    last_msg.sentat AS lastsentat,
                    COALESCE(unread.unreadcount, 0) AS unreadcount
                FROM rooms r
                LEFT JOIN LATERAL (
                    SELECT CASE 
                            WHEN messagetype = 'Image' THEN '[Ảnh]' 
                            WHEN messagetype = 'File' THEN '[Tệp tin]'
                            ELSE content 
                        END AS content_display,
                        sentat
                    FROM messages m
                    WHERE m.room_id = r.id  -- SỬA: dùng room_id thay vì id
                    ORDER BY sentat DESC
                    LIMIT 1
                ) last_msg ON TRUE
                LEFT JOIN (
                    SELECT room_id, COUNT(*) AS unreadcount -- SỬA: dùng room_id
                    FROM messages
                    WHERE isread = 0 AND sender_id != ?    -- SỬA: dùng sender_id
                    GROUP BY room_id                        -- SỬA: dùng room_id
                ) unread ON unread.room_id = r.id
                WHERE r.isgroup = TRUE
                ORDER BY last_msg.sentat DESC NULLS LAST
            """
            
            rows = DatabaseManager.execute_query(query, (user_id,), fetch_all=True)
            
            rooms = []
            if rows:
                for row in rows:
                    # Xử lý thời gian hiển thị: Nếu là hôm nay thì hiện giờ, cũ hơn thì hiện ngày
                    last_sent_dt = row[4]
                    last_sent_str = ''
                    if last_sent_dt and hasattr(last_sent_dt, 'strftime'):
                        if last_sent_dt.date() == datetime.now().date():
                            last_sent_str = last_sent_dt.strftime('%H:%M')
                        else:
                            last_sent_str = last_sent_dt.strftime('%d/%m')
                    
                    rooms.append({
                        'room_id': row[0],
                        'room_name': row[1] or 'Nhóm không tên',
                        'group_avatar': row[2] or '/static/images/default-group.png',
                        'last_message': row[3],
                        'last_sent_at': last_sent_str,
                        'unread_count': row[5]
                    })
            return rooms
        except Exception as e:
            app_logger.error(f"Lỗi lấy danh sách nhóm của user {user_id}: {e}")
            return []
    @staticmethod
    def get_group_rooms(user_id):
        """Lấy danh sách nhóm (Sử dụng LATERAL cho PostgreSQL)"""
        try:
            # SỬA LỖI: Sử dụng room_id thay vì id trong các lệnh JOIN và WHERE của bảng messages
            query = """
                SELECT r.id,
                    r.room_name,
                    r.group_avatar,
                    COALESCE(last_msg.content_display, 'Chưa có tin nhắn') AS lastmessage,
                    last_msg.sentat AS lastsentat,
                    COALESCE(unread.unreadcount, 0) AS unreadcount
                FROM rooms r
                LEFT JOIN LATERAL (
                    SELECT CASE 
                            WHEN messagetype = 'Image' THEN '[Ảnh]' 
                            WHEN messagetype = 'File' THEN '[Tệp tin]'
                            ELSE content 
                        END AS content_display,
                        sentat
                    FROM messages m
                    WHERE m.room_id = r.id  -- SỬA: m.room_id thay vì m.id
                    ORDER BY sentat DESC
                    LIMIT 1
                ) last_msg ON TRUE
                LEFT JOIN (
                    SELECT room_id, COUNT(*) AS unreadcount -- SỬA: room_id
                    FROM messages
                    WHERE isread = 0 AND sender_id != ?    -- SỬA: sender_id
                    GROUP BY room_id                        -- SỬA: room_id
                ) unread ON unread.room_id = r.id
                WHERE r.isgroup = TRUE
                ORDER BY last_msg.sentat DESC NULLS LAST
            """
            rows = DatabaseManager.execute_query(query, (user_id,), fetch_all=True)
            
            rooms = []
            if rows:
                for row in rows:
                    # Xử lý format thời gian
                    dt = row[4]
                    last_sent = dt.strftime('%H:%M') if dt and hasattr(dt, 'strftime') else ''
                    
                    rooms.append({
                        'room_id': row[0],
                        'room_name': row[1] or 'Nhóm không tên',
                        'group_avatar': row[2] or '/static/images/default-group.png',
                        'last_message': row[3],
                        'last_sent_at': last_sent,
                        'unread_count': row[5]
                    })
            return rooms
        except Exception as e:
            app_logger.error(f"Lỗi lấy danh sách nhóm: {e}")
            return []
    @staticmethod
    def generate_unique_username(base):
        """Tạo username duy nhất (Tối ưu cho Postgres)"""
        try:
            if not base:
                base = 'user'
            
            # Làm sạch chuỗi: Giữ lại chữ cái và số, tối đa 15 ký tự base để tránh quá dài khi thêm suffix
            import re
            base = re.sub(r'[^a-zA-Z0-0]', '', base).lower()[:15]
            
            if not base:
                base = 'user'
                
            candidate = base
            suffix = 1
            
            # Giới hạn 100 lần thử để bảo vệ tài nguyên hệ thống
            while DatabaseManager.username_exists(candidate) and suffix < 100:
                candidate = f"{base}{suffix}"
                suffix += 1
                
            # Nếu sau 100 lần vẫn trùng (hiếm), thêm timestamp ngắn
            if suffix >= 100:
                import time
                candidate = f"{base}_{str(int(time.time()))[-4:]}"
                
            return candidate
        except Exception as e:
            app_logger.error(f"Lỗi tạo username: {e}")
            return f"user_{uuid.uuid4().hex[:8]}"
    
    @staticmethod
    def get_private_rooms(user_id):
        """Lấy danh sách phòng chat cá nhân (Đã sửa lỗi tham chiếu cột cho Postgres)"""
        try:
            # Sử dụng đúng tên cột: room_id, user_id, sender_id
            query = """
                SELECT r.id,
                    r.room_name,
                    u.id AS otherid,
                    u.fullname AS otherusername,
                    COALESCE(last_msg.content_display, 'Chưa có tin nhắn') AS lastmessage,
                    last_msg.sentat AS lastsentat,
                    COALESCE(unread.unreadcount, 0) AS unreadcount
                FROM rooms r
                -- Tham gia của chính mình
                JOIN room_participants rp2 ON rp2.room_id = r.id AND rp2.user_id = ?
                -- Tham gia của đối phương (người còn lại trong phòng 1-1)
                JOIN room_participants rp ON rp.room_id = r.id AND rp.user_id != ?
                JOIN users u ON u.id = rp.user_id
                -- Lấy tin nhắn cuối cùng
                LEFT JOIN LATERAL (
                    SELECT CASE 
                            WHEN messagetype = 'Image' THEN '[Ảnh]' 
                            WHEN messagetype = 'File' THEN '[Tệp tin]'
                            ELSE content 
                        END AS content_display,
                        sentat
                    FROM messages m
                    WHERE m.room_id = r.id  -- SỬA: room_id thay vì id
                    ORDER BY sentat DESC
                    LIMIT 1
                ) last_msg ON TRUE
                -- Đếm số tin chưa đọc
                LEFT JOIN (
                    SELECT room_id, COUNT(*) AS unreadcount
                    FROM messages
                    WHERE isread = 0 AND sender_id != ?  -- SỬA: sender_id thay vì senderid
                    GROUP BY room_id
                ) unread ON unread.room_id = r.id
                WHERE r.isgroup = FALSE
                ORDER BY last_msg.sentat DESC NULLS LAST
            """
            
            # Truyền user_id 3 lần cho 3 dấu '?'
            rows = DatabaseManager.execute_query(query, (user_id, user_id, user_id), fetch_all=True)
            
            rooms = []
            if rows:
                for row in rows:
                    # Format thời gian linh hoạt
                    dt = row[5]
                    last_sent = ''
                    if dt and hasattr(dt, 'strftime'):
                        # Nếu là hôm nay thì hiện giờ, không thì hiện ngày
                        from datetime import datetime
                        if dt.date() == datetime.now().date():
                            last_sent = dt.strftime('%H:%M')
                        else:
                            last_sent = dt.strftime('%d/%m')
                    
                    rooms.append({
                        'room_id': row[0],
                        'room_name': row[1],
                        'other_user_id': row[2],
                        'display_name': row[3] or row[1], # Ưu tiên tên người dùng, nếu null thì lấy tên phòng
                        'last_message': row[4],
                        'last_sent_at': last_sent,
                        'unread_count': row[6]
                    })
            return rooms
        except Exception as e:
            app_logger.error(f"Lỗi lấy danh sách phòng cá nhân của user {user_id}: {e}")
            return []

    @staticmethod
    def create_group_room(user_id, group_name):
        """Tạo phòng nhóm mới (Chuẩn hóa Postgres)"""
        if not group_name or not group_name.strip():
            return None
        try:
            # 1. Chèn phòng mới. Trong Postgres, dùng RETURNING id để lấy ID ngay lập tức
            # Chú ý: room_name thay vì roomname nếu bạn dùng gạch dưới
            query = "INSERT INTO rooms (room_name, isgroup, created_at) VALUES (?, TRUE, CURRENT_TIMESTAMP) RETURNING id"
            row = DatabaseManager.execute_query(query, (group_name.strip(),), fetch_one=True)
            room_id = row[0] if row else None
            
            if room_id:
                # 2. Thêm người tạo vào phòng với quyền Admin/Chủ phòng
                # SỬA LỖI: Cột phải là room_id và user_id
                query = "INSERT INTO room_participants (room_id, user_id) VALUES (?, ?)"
                DatabaseManager.execute_query(query, (room_id, user_id))
                
                app_logger.info(f"User {user_id} đã tạo nhóm mới: {group_name} (ID: {room_id})")
            
            return room_id
        except Exception as e:
            app_logger.error(f"Lỗi tạo nhóm: {e}")
            return None
    
    @staticmethod
    def get_or_create_private_room(user_id, target_user_id):
        """Lấy hoặc tạo phòng chat riêng 1-1"""
        try:
            user_id, target_user_id = int(user_id), int(target_user_id)
            if user_id == target_user_id: return None
            
            # Sắp xếp ID để room_name luôn duy nhất giữa 2 người (ví dụ: private_1_5)
            first_id, second_id = sorted([user_id, target_user_id])
            room_name = f"private_{first_id}_{second_id}"
            
            # 1. Kiểm tra phòng đã tồn tại chưa
            query = "SELECT id FROM rooms WHERE isgroup = FALSE AND room_name = ?"
            existing = DatabaseManager.execute_query(query, (room_name,), fetch_one=True)
            
            if existing:
                room_id = existing[0]
            else:
                # 2. Tạo phòng mới nếu chưa có
                query = "INSERT INTO rooms (room_name, isgroup, created_at) VALUES (?, FALSE, CURRENT_TIMESTAMP) RETURNING id"
                row = DatabaseManager.execute_query(query, (room_name,), fetch_one=True)
                room_id = row[0] if row else None

            if not room_id: return None
            
            # 3. Đảm bảo cả 2 đều có tên trong danh sách tham gia (room_participants)
            for p_id in [user_id, target_user_id]:
                # Kiểm tra xem đã tham gia chưa để tránh lỗi trùng khóa (Duplicate)
                check = "SELECT 1 FROM room_participants WHERE room_id = ? AND user_id = ?"
                if not DatabaseManager.query_exists(check, (room_id, p_id)):
                    insert_p = "INSERT INTO room_participants (room_id, user_id) VALUES (?, ?)"
                    DatabaseManager.execute_query(insert_p, (room_id, p_id))
            
            # 4. Lấy tên người nhận để hiển thị tiêu đề chat
            query_name = "SELECT fullname FROM users WHERE id = ?"
            target_user = DatabaseManager.execute_query(query_name, (target_user_id,), fetch_one=True)
            display_name = target_user[0] if target_user else f"Người dùng {target_user_id}"
            
            return room_id, display_name
            
        except Exception as e:
            app_logger.error(f"Lỗi xử lý phòng chat riêng: {e}")
            return None

    @staticmethod
    def get_analytics_data(export_type):
        """Lấy dữ liệu thống kê (Khớp chuẩn Postgres & tiêu đề CSV)"""
        try:
            if export_type == 'users':
                query = """
                    SELECT id, fullname, username, email, status, created_at
                    FROM users
                    ORDER BY created_at DESC
                """
            elif export_type == 'messages':
                # Sử dụng các tên cột có gạch dưới: message_id, sender_id, sent_at
                query = """
                    SELECT m.id, m.content, m.messagetype, m.sent_at,
                        u.username as sendername
                    FROM messages m
                    JOIN users u ON m.sender_id = u.id
                    ORDER BY m.sent_at DESC
                """
            elif export_type == 'rooms':
                query = """
                    SELECT id, room_name, isgroup, created_at
                    FROM rooms
                    ORDER BY created_at DESC
                """
            elif export_type == 'files':
                query = """
                    SELECT f.id, f.filename, f.filetype, f.filesize, f.uploaded_at,
                        u.username as uploader
                    FROM sharedfiles f
                    JOIN users u ON f.uploader_id = u.id
                    ORDER BY f.uploaded_at DESC
                """
            else:
                return None
            
            return DatabaseManager.execute_query(query, fetch_all=True)
        except Exception as e:
            app_logger.error(f"Lỗi lấy dữ liệu Analytics ({export_type}): {e}")
            return None
    
    @staticmethod
    def get_room_messages(room_id, limit=100):
        """Lấy danh sách tin nhắn trong phòng (Tối ưu cho Postgres)"""
        try:
            # SỬA: m.room_id = ? thay vì m.id = ?
            # SỬA: m.is_deleted thay vì m.isdeleted
            query = """
                SELECT m.id, m.sender_id, u.fullname as sendername, m.content, m.messagetype,
                    m.sent_at, m.isread, m.edited_at, m.is_deleted, m.deleted_at
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                WHERE m.room_id = ? AND (m.is_deleted IS FALSE OR m.is_deleted IS NULL)
                ORDER BY m.sent_at ASC
                LIMIT ?
            """
            messages = DatabaseManager.execute_query(query, (room_id, limit), fetch_all=True)
            
            result = []
            if messages:
                for msg in messages:
                    result.append({
                        'message_id': msg[0],
                        'sender_id': msg[1],
                        'sender_name': msg[2],
                        'content': msg[3],
                        'type': msg[4],
                        # Format ISO để Javascript ở Client dễ xử lý
                        'sent_at': msg[5].strftime('%Y-%m-%d %H:%M:%S') if msg[5] and hasattr(msg[5], 'strftime') else '',
                        'is_read': bool(msg[6]),
                        'edited_at': msg[7].strftime('%Y-%m-%d %H:%M:%S') if msg[7] and hasattr(msg[7], 'strftime') else None,
                        'is_deleted': bool(msg[8]),
                        'deleted_at': msg[9].strftime('%Y-%m-%d %H:%M:%S') if msg[9] and hasattr(msg[9], 'strftime') else None
                    })
            return result
        except Exception as e:
            app_logger.error(f"Lỗi lấy tin nhắn phòng {room_id}: {e}")
            return []
    
    @staticmethod
    def mark_messages_as_read(room_id, user_id):
        """Đánh dấu tin nhắn đã đọc trong một phòng (Tối ưu Postgres)"""
        try:
            # SỬA: Dùng room_id để lọc tin nhắn trong phòng đó
            # SỬA: Dùng sender_id và is_read theo chuẩn gạch dưới
            query = """
                UPDATE messages 
                SET isread = TRUE 
                WHERE room_id = ? AND sender_id != ? AND isread = FALSE
            """
            return DatabaseManager.execute_query(query, (room_id, user_id))
        except Exception as e:
            app_logger.error(f"Lỗi đánh dấu đã đọc tại phòng {room_id}: {e}")
            return 0
    
    @staticmethod
    def edit_message(message_id, user_id, new_content):
        """Chỉnh sửa tin nhắn (Khớp chuẩn Postgres)"""
        try:
            # 1. Kiểm tra quyền sở hữu (Chỉ người gửi mới được sửa)
            # SỬA: Dùng id thay vì messageid, sender_id thay vì senderid
            query = "SELECT sender_id FROM messages WHERE id = ?"
            message = DatabaseManager.execute_query(query, (message_id,), fetch_one=True)
            
            if not message or message[0] != user_id:
                return False
            
            # 2. Cập nhật nội dung
            # SỬA: edited_at thay vì editedat
            query = "UPDATE messages SET content = ?, edited_at = CURRENT_TIMESTAMP WHERE id = ?"
            DatabaseManager.execute_query(query, (new_content, message_id))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi sửa tin nhắn {message_id}: {e}")
            return False
    
    @staticmethod
    def delete_message(message_id, user_id):
        """Xóa tin nhắn (Soft delete - Vẫn giữ trong DB nhưng ẩn trên UI)"""
        try:
            # 1. Kiểm tra quyền sở hữu
            query = "SELECT sender_id FROM messages WHERE id = ?"
            message = DatabaseManager.execute_query(query, (message_id,), fetch_one=True)
            
            if not message or message[0] != user_id:
                return False
            
            # 2. Thực hiện xóa tạm
            # SỬA: is_deleted và deleted_at (có dấu gạch dưới)
            query = "UPDATE messages SET is_deleted = TRUE, deleted_at = CURRENT_TIMESTAMP WHERE id = ?"
            DatabaseManager.execute_query(query, (message_id,))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi xóa tin nhắn {message_id}: {e}")
            return False
    
    @staticmethod
    def search(query_str, user_id):
        """Tìm kiếm nhóm và người dùng (Hỗ trợ tiếng Việt không phân biệt hoa thường)"""
        try:
            # 1. Đảm bảo cột phone tồn tại (Nên gọi lúc khởi động app sẽ tốt hơn)
            # DatabaseManager.ensure_phone_column()
            
            pattern = f"%{query_str}%"
            results = []
            
            # 2. Tìm kiếm nhóm: Sử dụng room_name và ILIKE
            query_groups = "SELECT id, room_name FROM rooms WHERE isgroup = TRUE AND room_name ILIKE ?"
            groups = DatabaseManager.execute_query(query_groups, (pattern,), fetch_all=True)
            if groups:
                for group in groups:
                    results.append({'id': group[0], 'type': 'Group', 'name': group[1]})
            
            # 3. Tìm kiếm người dùng: Loại bỏ chính mình (user_id) khỏi kết quả
            query_users = """
                SELECT id, fullname, username, phone 
                FROM users 
                WHERE id != ? AND (phone ILIKE ? OR fullname ILIKE ? OR username ILIKE ?)
            """
            users = DatabaseManager.execute_query(query_users, (user_id, pattern, pattern, pattern), fetch_all=True)
            if users:
                for user in users:
                    results.append({
                        'id': user[0], 
                        'type': 'User', 
                        'name': user[1], 
                        'phone': user[3] or ''
                    })
            
            return results
        except Exception as e:
            app_logger.error(f"Lỗi tìm kiếm với từ khóa '{query_str}': {e}")
            return []
    
    @staticmethod
    def update_user_profile(user_id, fullname, username, avatar_url=None, phone=None):
        """Cập nhật thông tin cá nhân (Tối ưu hiệu năng truy vấn)"""
        try:
            # Xây dựng câu lệnh update động
            updates = ["fullname = ?", "username = ?"]
            params = [fullname, username]
            
            if avatar_url:
                updates.append("avatarurl = ?") # Hoặc avatar_url tùy tên cột bạn đặt
                params.append(avatar_url)
                
            if phone:
                updates.append("phone = ?")
                params.append(phone)
                
            params.append(user_id)
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
            
            DatabaseManager.execute_query(query, tuple(params))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi cập nhật hồ sơ user {user_id}: {e}")
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
        """Đăng ký người dùng mới (Chuẩn hóa cho Postgres Render)"""
        try:
            from werkzeug.security import generate_password_hash
            hashed_password = generate_password_hash(password)
            
            # Đảm bảo cột phone và các cột cần thiết tồn tại
            DatabaseManager.ensure_phone_column()
            
            app_logger.info(f"Đang đăng ký user: {username} - SĐT: {phone}")
            
            # SỬA LỖI: Đồng bộ tên cột (dùng gạch dưới)
            # SỬA LỖI: Postgres dùng TRUE/FALSE trực tiếp cho kiểu BOOLEAN
            query = """
                INSERT INTO users (username, fullname, phone, password, status, is_verified, verification_token, created_at)
                VALUES (?, ?, ?, ?, 'Offline', ?, ?, CURRENT_TIMESTAMP)
            """
            
            # Lưu ý: is_verified truyền vào nên là kiểu bool (True/False)
            params = (username, fullname, phone, hashed_password, is_verified, verification_token)
            DatabaseManager.execute_query(query, params)
            
            return True
        except Exception as e:
            app_logger.error(f"Lỗi đăng ký user {username}: {e}")
            return False
    
    @staticmethod
    def ensure_phone_column():
        """Tự động thêm cột phone nếu chưa có (Tương thích Postgres)"""
        try:
            # Kiểm tra cột 'phone' trong bảng 'users'
            # Lưu ý: Postgres lưu tên bảng/cột mặc định là chữ thường
            if not DatabaseManager.column_exists('users', 'phone'):
                # VARCHAR(20) là đủ cho số điện thoại, dùng NULL để không lỗi dữ liệu cũ
                query = "ALTER TABLE users ADD COLUMN phone VARCHAR(20) NULL"
                DatabaseManager.execute_query(query)
                app_logger.info("Đã bổ sung cột 'phone' vào bảng users thành công.")
        except Exception as e:
            app_logger.error(f"Lỗi kiểm tra/thêm cột phone: {e}")
    @staticmethod
    def ensure_shared_files_table():
        """Khởi tạo bảng shared_files nếu chưa có (Chuẩn PostgreSQL)"""
        try:
            # Kiểm tra bảng (tên bảng nên viết thường)
            if not DatabaseManager.table_exists('shared_files'):
                query = """
                    CREATE TABLE shared_files (
                        id SERIAL PRIMARY KEY,
                        filename VARCHAR(255) NOT NULL,
                        original_filename VARCHAR(255) NOT NULL,
                        file_path VARCHAR(500) NOT NULL,
                        file_type VARCHAR(50) NOT NULL,
                        file_size BIGINT NOT NULL, -- Dùng BIGINT để chứa file dung lượng lớn
                        uploader_id INT NOT NULL,
                        room_id INT NULL,          -- Cột ID phòng
                        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT fk_uploader FOREIGN KEY (uploader_id) REFERENCES users(id) ON DELETE CASCADE,
                        CONSTRAINT fk_room FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
                    )
                """
                DatabaseManager.execute_query(query)
                app_logger.info("Đã khởi tạo bảng shared_files thành công.")
        except Exception as e:
            app_logger.error(f"Lỗi khởi tạo bảng shared_files: {e}")
    
    @staticmethod
    def upload_file(unique_filename, original_filename, file_url, file_type, file_size, user_id, room_id=None):
        """Lưu thông tin file vào database"""
        try:
            # Luôn đảm bảo bảng tồn tại trước khi chèn
            DatabaseManager.ensure_shared_files_table()
            
            # SỬA: Đồng bộ tên cột (dùng gạch dưới)
            query = """
                INSERT INTO shared_files (filename, original_filename, file_path, file_type, file_size, uploader_id, room_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            params = (unique_filename, original_filename, file_url, file_type, file_size, user_id, room_id)
            
            DatabaseManager.execute_query(query, params)
            return True
        except Exception as e:
            app_logger.error(f"Lỗi lưu thông tin file {original_filename}: {e}")
            return False
    
    @staticmethod
    def get_file_info(file_id):
        """Lấy thông tin file theo ID (Chuẩn Postgres)"""
        try:
            # SỬA: Tên bảng shared_files và các cột có dấu gạch dưới
            query = """
                SELECT filename, original_filename, file_path, file_type, file_size, uploader_id
                FROM shared_files
                WHERE id = ?
            """
            return DatabaseManager.execute_query(query, (file_id,), fetch_one=True)
        except Exception as e:
            app_logger.error(f"Lỗi lấy thông tin file {file_id}: {e}")
            return None
    
    @staticmethod
    def get_analytics_overview():
        """Lấy số liệu thống kê tổng quan (Tối ưu cho PostgreSQL Render)"""
        try:
            stats = {}
            
            # 1. Thống kê User (Gộp các điều kiện vào 1 câu query để giảm độ trễ)
            user_query = """
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE created_at::date = CURRENT_DATE) as today,
                    COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE - INTERVAL '7 days') as week,
                    COUNT(*) FILTER (WHERE status = 'Online') as online
                FROM users
            """
            res_u = DatabaseManager.execute_query(user_query, fetch_one=True)
            stats['total_users'] = res_u[0]
            stats['new_users_today'] = res_u[1]
            stats['new_users_week'] = res_u[2]
            stats['online_users'] = res_u[3]

            # 2. Thống kê Tin nhắn
            msg_query = """
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE sent_at::date = CURRENT_DATE) as today,
                    COUNT(*) FILTER (WHERE sent_at >= CURRENT_DATE - INTERVAL '7 days') as week
                FROM messages
            """
            res_m = DatabaseManager.execute_query(msg_query, fetch_one=True)
            stats['total_messages'] = res_m[0]
            stats['messages_today'] = res_m[1]
            stats['messages_week'] = res_m[2]

            # 3. Thống kê Phòng
            room_query = """
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE isgroup = TRUE) as groups,
                    COUNT(*) FILTER (WHERE created_at::date = CURRENT_DATE) as today
                FROM rooms
            """
            res_r = DatabaseManager.execute_query(room_query, fetch_one=True)
            stats['total_rooms'] = res_r[0]
            stats['total_groups'] = res_r[1]
            stats['new_rooms_today'] = res_r[2]

            # 4. Thống kê File
            file_query = """
                SELECT 
                    COUNT(*) as total,
                    COALESCE(SUM(file_size), 0) as total_size
                FROM shared_files
            """
            res_f = DatabaseManager.execute_query(file_query, fetch_one=True)
            stats['total_files'] = res_f[0]
            stats['total_file_size'] = res_f[1]

            # Giữ lại các field cũ để tránh lỗi giao diện
            stats['new_users_month'] = 0 # Có thể bổ sung FILTER nếu cần
            stats['messages_month'] = 0
            stats['files_today'] = 0

            return stats
        except Exception as e:
            app_logger.error(f"Lỗi lấy thống kê tổng quan: {e}")
            return {}
    
    @staticmethod
    def get_analytics_user_activity(days=30):
        """Lấy dữ liệu hoạt động để vẽ biểu đồ (Chuẩn PostgreSQL Render)"""
        try:
            # 1. Thống kê người dùng mới theo ngày
            # SỬA: INTERVAL '1 day' * ? để truyền tham số days an toàn
            query_users = """
                SELECT created_at::date as date, COUNT(*) as new_users
                FROM users
                WHERE created_at >= CURRENT_DATE - (INTERVAL '1 day' * ?)
                GROUP BY date
                ORDER BY date DESC
            """
            user_activity = DatabaseManager.execute_query(query_users, (days,), fetch_all=True)
            
            # 2. Số lượng tin nhắn theo ngày
            query_messages = """
                SELECT sent_at::date as date, COUNT(*) as message_count
                FROM messages
                WHERE sent_at >= CURRENT_DATE - (INTERVAL '1 day' * ?)
                GROUP BY date
                ORDER BY date DESC
            """
            message_activity = DatabaseManager.execute_query(query_messages, (days,), fetch_all=True)
            
            # 3. Top 10 người dùng tích cực nhất (Dựa trên số tin nhắn gửi đi)
            query_top = """
                SELECT u.fullname, COUNT(m.id) as message_count
                FROM users u
                INNER JOIN messages m ON u.id = m.sender_id
                WHERE m.sent_at >= CURRENT_DATE - (INTERVAL '1 day' * ?)
                GROUP BY u.id, u.fullname
                ORDER BY message_count DESC
                LIMIT 10
            """
            top_users = DatabaseManager.execute_query(query_top, (days,), fetch_all=True)
            
            # 4. Trả về format JSON cho Frontend (Chart.js / Google Charts)
            return {
                'user_activity': [
                    {'date': ua[0].strftime('%Y-%m-%d') if ua[0] else '', 'new_users': ua[1]} 
                    for ua in user_activity
                ],
                'message_activity': [
                    {'date': ma[0].strftime('%Y-%m-%d') if ma[0] else '', 'message_count': ma[1]} 
                    for ma in message_activity
                ],
                'top_users': [
                    {'name': tu[0], 'message_count': tu[1]} 
                    for tu in top_users
                ]
            }
        except Exception as e:
            app_logger.error(f"Lỗi lấy dữ liệu biểu đồ hoạt động ({days} ngày): {e}")
            return {'user_activity': [], 'message_activity': [], 'top_users': []}
    
    @staticmethod
    def get_analytics_room_stats(days=30):
        """Thống kê hoạt động của các phòng chat (Chuẩn Postgres)"""
        try:
            # 1. Top 10 phòng chat tích cực nhất
            # SỬA: m.room_id thay vì m.id để khớp với cấu trúc bảng messages
            query_top = """
                SELECT r.room_name, COUNT(m.id) as message_count,
                    COUNT(DISTINCT m.sender_id) as active_users
                FROM rooms r
                INNER JOIN messages m ON r.id = m.room_id
                WHERE m.sent_at >= CURRENT_DATE - (INTERVAL '1 day' * ?)
                GROUP BY r.id, r.room_name
                ORDER BY message_count DESC
                LIMIT 10
            """
            top_rooms = DatabaseManager.execute_query(query_top, (days,), fetch_all=True)
            
            # 2. Thống kê loại phòng (Group vs Private)
            query_types = """
                SELECT CASE WHEN isgroup = TRUE THEN 'Group' ELSE 'Private' END as room_type,
                    COUNT(*) as count
                FROM rooms
                GROUP BY isgroup
            """
            room_types = DatabaseManager.execute_query(query_types, fetch_all=True)
            
            # 3. Số phòng mới tạo theo ngày
            query_creation = """
                SELECT created_at::date as date, COUNT(*) as new_rooms
                FROM rooms
                WHERE created_at >= CURRENT_DATE - (INTERVAL '1 day' * ?)
                GROUP BY date
                ORDER BY date DESC
            """
            room_creation = DatabaseManager.execute_query(query_creation, (days,), fetch_all=True)
            
            return {
                'top_rooms': [{'name': tr[0], 'message_count': tr[1], 'active_users': tr[2]} for tr in top_rooms],
                'room_types': [{'type': rt[0], 'count': rt[1]} for rt in room_types],
                'room_creation': [{'date': rc[0].strftime('%Y-%m-%d') if rc[0] else '', 'new_rooms': rc[1]} for rc in room_creation]
            }
        except Exception as e:
            app_logger.error(f"Lỗi thống kê phòng chat ({days} ngày): {e}")
            return {'top_rooms': [], 'room_types': [], 'room_creation': []}
    
    @staticmethod
    def get_analytics_file_stats(days=30):
        """Thống kê tệp tin đã chia sẻ (Chuẩn Postgres)"""
        try:
            # 1. Thống kê theo loại tệp (Image, PDF, Document...)
            query_types = """
                SELECT file_type, COUNT(*) as count, SUM(file_size) as total_size
                FROM shared_files
                WHERE uploaded_at >= CURRENT_DATE - (INTERVAL '1 day' * ?)
                GROUP BY file_type
                ORDER BY count DESC
            """
            file_types = DatabaseManager.execute_query(query_types, (days,), fetch_all=True)
            
            # 2. Lượng upload theo ngày
            query_uploads = """
                SELECT uploaded_at::date as date, COUNT(*) as file_count,
                    SUM(file_size) as total_size
                FROM shared_files
                WHERE uploaded_at >= CURRENT_DATE - (INTERVAL '1 day' * ?)
                GROUP BY date
                ORDER BY date DESC
            """
            file_uploads = DatabaseManager.execute_query(query_uploads, (days,), fetch_all=True)
            
            # 3. Top 10 người tải lên nhiều nhất
            query_top = """
                SELECT u.fullname, COUNT(sf.id) as file_count,
                    SUM(sf.file_size) as total_size
                FROM users u
                INNER JOIN shared_files sf ON u.id = sf.uploader_id
                WHERE sf.uploaded_at >= CURRENT_DATE - (INTERVAL '1 day' * ?)
                GROUP BY u.id, u.fullname
                ORDER BY file_count DESC
                LIMIT 10
            """
            top_uploaders = DatabaseManager.execute_query(query_top, (days,), fetch_all=True)
            
            return {
                'file_types': [{'type': ft[0], 'count': ft[1], 'total_size': ft[2]} for ft in file_types],
                'file_uploads': [
                    {'date': fu[0].strftime('%Y-%m-%d') if fu[0] else '', 'file_count': fu[1], 'total_size': fu[2]} 
                    for fu in file_uploads
                ],
                'top_uploaders': [{'name': tu[0], 'file_count': tu[1], 'total_size': tu[2]} for tu in top_uploaders]
            }
        except Exception as e:
            app_logger.error(f"Lỗi thống kê tệp tin ({days} ngày): {e}")
            return {'file_types': [], 'file_uploads': [], 'top_uploaders': []}
    
    @staticmethod
    def verify_email_token(token):
        """Xác thực token email (Tương thích PostgreSQL Render)"""
        try:
            # SỬA: verification_token (có gạch dưới)
            query = "SELECT id FROM users WHERE verification_token = ?"
            user = DatabaseManager.execute_query(query, (token,), fetch_one=True)
            
            if not user:
                return False
            
            user_id = user[0]
            # SỬA: is_verified và verification_token (có gạch dưới)
            # Postgres hiểu TRUE là kiểu BOOLEAN chuẩn
            query = """
                UPDATE users 
                SET is_verified = TRUE, verification_token = NULL 
                WHERE id = ?
            """
            DatabaseManager.execute_query(query, (user_id,))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi xác thực email token: {e}")
            return False
    
    @staticmethod
    def set_password_reset_token(email, token, expires_at):
        """Thiết lập token đặt lại mật khẩu cho người dùng"""
        try:
            # SỬA: reset_token và reset_token_expires_at (có gạch dưới)
            # Đảm bảo cột email trong bảng users được viết thường
            query = """
                UPDATE users 
                SET reset_token = ?, reset_token_expires_at = ? 
                WHERE email = ?
            """
            DatabaseManager.execute_query(query, (token, expires_at, email))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi thiết lập reset token cho email {email}: {e}")
            return False
    
    @staticmethod
    def reset_password_with_token(token, new_password):
        """Đặt lại mật khẩu bằng token (Chuẩn PostgreSQL Render)"""
        try:
            from werkzeug.security import generate_password_hash
            from datetime import datetime
            
            # 1. Lấy thông tin user và thời gian hết hạn (Dùng tên cột có gạch dưới)
            query = "SELECT id, reset_token_expires_at FROM users WHERE reset_token = ?"
            user = DatabaseManager.execute_query(query, (token,), fetch_one=True)
            
            # 2. Kiểm tra token có hợp lệ và còn hạn hay không
            if not user or not user[1] or user[1] < datetime.now():
                return False
            
            user_id = user[0]
            hashed_password = generate_password_hash(new_password)
            
            # 3. Cập nhật mật khẩu mới và xóa sạch các token reset
            # Tự động gán is_verified = TRUE vì họ đã xác thực qua email thành công
            query = """
                UPDATE users 
                SET password = ?, 
                    reset_token = NULL, 
                    reset_token_expires_at = NULL, 
                    is_verified = TRUE 
                WHERE id = ?
            """
            DatabaseManager.execute_query(query, (hashed_password, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi đặt lại mật khẩu với token: {e}")
            return False
    
    @staticmethod
    def update_user_oauth(email, provider, oauth_id):
        """Cập nhật thông tin OAuth (Google/Facebook)"""
        try:
            # Chuyển email về chữ thường để tránh lỗi so sánh
            email = email.lower()
            
            # SỬA: oauth_provider, oauth_id, is_verified (theo chuẩn gạch dưới)
            query = """
                UPDATE users 
                SET oauth_provider = ?, 
                    oauth_id = ?, 
                    is_verified = TRUE 
                WHERE email = ?
            """
            DatabaseManager.execute_query(query, (provider, oauth_id, email))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi cập nhật OAuth cho {email}: {e}")
            return False
    
    @staticmethod
    def get_online_users():
        """Lấy danh sách người dùng đang trực tuyến (Chuẩn Postgres)"""
        try:
            # SỬA: Đảm bảo tên cột khớp với các hàm trước đó
            query = """
                SELECT id, fullname, status
                FROM users
                WHERE status = 'Online'
                ORDER BY fullname ASC
            """
            users = DatabaseManager.execute_query(query, fetch_all=True)
            
            # Trả về list dictionary để dễ xử lý ở Frontend
            return [
                {'user_id': user[0], 'user_name': user[1], 'status': user[2]} 
                for user in users
            ]
        except Exception as e:
            app_logger.error(f"Lỗi lấy danh sách user online: {e}")
            return []
    
    @staticmethod
    def update_notification_enabled(user_id, enabled):
        """Cập nhật trạng thái bật/tắt thông báo cho người dùng"""
        try:
            # SỬA: notification_enabled (có dấu gạch dưới)
            column_name = 'notification_enabled'
            
            # 1. Kiểm tra và thêm cột nếu chưa có (dùng BOOLEAN cho Postgres)
            if not DatabaseManager.column_exists('users', column_name):
                query_alter = f"ALTER TABLE users ADD COLUMN {column_name} BOOLEAN NOT NULL DEFAULT TRUE"
                DatabaseManager.execute_query(query_alter)
                app_logger.info(f"Đã bổ sung cột {column_name} vào bảng users.")
            
            # 2. Cập nhật trạng thái
            query_update = f"UPDATE users SET {column_name} = ? WHERE id = ?"
            DatabaseManager.execute_query(query_update, (enabled, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi cập nhật cài đặt thông báo cho user {user_id}: {e}")
            return False
    
    @staticmethod
    def ensure_notifications_table():
        """Đảm bảo bảng notifications tồn tại (Chuẩn PostgreSQL)"""
        try:
            # Tên bảng viết thường theo chuẩn Postgres
            if not DatabaseManager.table_exists('notifications'):
                query = """
                    CREATE TABLE notifications (
                        id SERIAL PRIMARY KEY,
                        user_id INT NOT NULL,
                        title VARCHAR(255) NOT NULL,
                        message TEXT NOT NULL,
                        notification_type VARCHAR(50) NOT NULL,
                        is_read BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT fk_user_notification FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """
                DatabaseManager.execute_query(query)
                app_logger.info("Đã tạo bảng notifications thành công.")
        except Exception as e:
            app_logger.error(f"Lỗi khởi tạo bảng notifications: {e}")
    
    @staticmethod
    def create_notification(user_id, title, message, notification_type):
        """Tạo một thông báo mới cho người dùng"""
        try:
            # Đảm bảo bảng đã tồn tại
            DatabaseManager.ensure_notifications_table()
            
            # SỬA: Đồng bộ tên cột user_id, notification_type (gạch dưới)
            query = """
                INSERT INTO notifications (user_id, title, message, notification_type)
                VALUES (?, ?, ?, ?)
            """
            params = (user_id, title, message, notification_type)
            DatabaseManager.execute_query(query, params)
            return True
        except Exception as e:
            app_logger.error(f"Lỗi tạo thông báo cho user {user_id}: {e}")
            return False
    
    @staticmethod
    def get_user_notifications(user_id):
        """Lấy danh sách thông báo của người dùng (Sắp xếp mới nhất)"""
        try:
            # SỬA: Đồng bộ tên cột (id -> user_id, type -> notification_type, ...)
            query = """
                SELECT id, title, message, notification_type, is_read, created_at
                FROM notifications
                WHERE user_id = ?
                ORDER BY created_at DESC
            """
            notifications = DatabaseManager.execute_query(query, (user_id,), fetch_all=True)
            
            return [{
                'notification_id': notif[0],
                'title': notif[1],
                'message': notif[2],
                'type': notif[3],
                'is_read': notif[4], # Postgres BOOLEAN trả về chuẩn True/False
                'created_at': notif[5].strftime('%H:%M %d/%m/%Y') if notif[5] else ''
            } for notif in notifications]
        except Exception as e:
            app_logger.error(f"Lỗi lấy thông báo cho user {user_id}: {e}")
            return []
    
    @staticmethod
    def mark_notification_read(notification_id, user_id):
        """Đánh dấu thông báo là đã đọc (Chuẩn BOOLEAN)"""
        try:
            # SỬA: Đồng bộ tên cột is_read và user_id
            query = """
                UPDATE notifications
                SET is_read = TRUE
                WHERE id = ? AND user_id = ?
            """
            DatabaseManager.execute_query(query, (notification_id, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi đánh dấu đã đọc cho thông báo {notification_id}: {e}")
            return False
    
    @staticmethod
    def is_room_admin(room_id, user_id):
        """Kiểm tra quyền Admin của người dùng trong phòng chat"""
        try:
            # 1. Đảm bảo bảng phân quyền tồn tại
            DatabaseManager.ensure_room_roles_table()
            
            # SỬA LỖI: Phân biệt cột room_id và user_id
            # Nếu bảng room_roles của Tới dùng tên cột khác, hãy điều chỉnh cho khớp nhé
            rr_query = "SELECT role FROM room_roles WHERE room_id = ? AND user_id = ?"
            rr = DatabaseManager.execute_query(rr_query, (room_id, user_id), fetch_one=True)
            
            if rr and rr[0] == 'Admin':
                return True

            # 2. Phương án dự phòng: Kiểm tra ở bảng tham gia phòng (room_participants)
            query = """
                SELECT COUNT(*) 
                FROM room_participants 
                WHERE room_id = ? AND user_id = ? AND role = 'Admin'
            """
            result = DatabaseManager.execute_query(query, (room_id, user_id), fetch_one=True)
            return result[0] > 0 if result else False
        except Exception as e:
            app_logger.error(f"Lỗi kiểm tra quyền Admin (Room: {room_id}, User: {user_id}): {e}")
            return False
    
    @staticmethod
    def user_exists(user_id):
        """Kiểm tra người dùng có tồn tại trong hệ thống không"""
        try:
            # Trong Postgres, dùng COUNT(*) hoặc SELECT 1 đều được
            query = "SELECT 1 FROM users WHERE id = ?"
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            return result is not None
        except Exception as e:
            app_logger.error(f"Lỗi kiểm tra tồn tại user {user_id}: {e}")
            return False

    @staticmethod
    def create_notification(user_id, title, message, notification_type):
        """Tạo một thông báo mới cho người dùng (Chuẩn Postgres)"""
        try:
            # Luôn đảm bảo bảng tồn tại
            DatabaseManager.ensure_notifications_table()
            
            # SỬA: Đồng bộ tên cột với bảng notifications (user_id, notification_type)
            query = """
                INSERT INTO notifications (user_id, title, message, notification_type)
                VALUES (?, ?, ?, ?)
            """
            DatabaseManager.execute_query(query, (user_id, title, message, notification_type))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi tạo thông báo cho user {user_id}: {e}")
            return False

    @staticmethod
    def get_user_notifications(user_id):
        """Lấy danh sách thông báo của người dùng (Sắp xếp mới nhất)"""
        try:
            # SỬA: Lấy đúng tên cột id (khóa chính), user_id, notification_type
            query = """
                SELECT id, title, message, notification_type, is_read, created_at
                FROM notifications
                WHERE user_id = ?
                ORDER BY created_at DESC
            """
            notifications = DatabaseManager.execute_query(query, (user_id,), fetch_all=True)
            
            return [{
                'notification_id': notif[0],
                'title': notif[1],
                'message': notif[2],
                'type': notif[3],
                'is_read': notif[4], # Postgres BOOLEAN trả về True/False trực tiếp
                'created_at': notif[5].strftime('%H:%M %d/%m/%Y') if notif[5] else ''
            } for notif in notifications]
        except Exception as e:
            app_logger.error(f"Lỗi lấy thông báo cho user {user_id}: {e}")
            return []

    @staticmethod
    def mark_notification_read(notification_id, user_id):
        """Đánh dấu thông báo là đã đọc (Chuẩn Postgres BOOLEAN)"""
        try:
            # SỬA: Đồng bộ tên cột (id -> khóa chính của thông báo, user_id -> chủ sở hữu)
            query = """
                UPDATE notifications
                SET is_read = TRUE
                WHERE id = ? AND user_id = ?
            """
            DatabaseManager.execute_query(query, (notification_id, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi đánh dấu đã đọc thông báo {notification_id}: {e}")
            return False

    @staticmethod
    def is_room_admin(room_id, user_id):
        """Kiểm tra quyền Admin của người dùng trong phòng (Tương thích Postgres)"""
        try:
            # 1. Đảm bảo bảng phân quyền tồn tại
            DatabaseManager.ensure_room_roles_table()
            
            # SỬA LỖI: Phải tách rõ room_id và user_id
            rr_query = "SELECT role FROM room_roles WHERE room_id = ? AND user_id = ?"
            rr = DatabaseManager.execute_query(rr_query, (room_id, user_id), fetch_one=True)
            
            if rr and rr[0] == 'Admin':
                return True

            # 2. Phương án dự phòng: Kiểm tra trong bảng room_participants
            query = """
                SELECT COUNT(*) 
                FROM room_participants 
                WHERE room_id = ? AND user_id = ? AND role = 'Admin'
            """
            result = DatabaseManager.execute_query(query, (room_id, user_id), fetch_one=True)
            return result[0] > 0 if result else False
        except Exception as e:
            app_logger.error(f"Lỗi kiểm tra quyền Admin phòng {room_id} cho user {user_id}: {e}")
            return False

    @staticmethod
    def user_exists(user_id):
        """Kiểm tra sự tồn tại của người dùng (Tương thích Postgres)"""
        try:
            # Trong Postgres, dùng COUNT(*) hoặc SELECT 1 đều được
            query = "SELECT 1 FROM users WHERE id = ?"
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            return result is not None
        except Exception as e:
            app_logger.error(f"Lỗi kiểm tra user_exists ({user_id}): {e}")
            return False

    @staticmethod
    def save_message(user_id, content, msg_type='Text', room_id=1, reply_to_id=None):
        """Lưu tin nhắn vào database (Chuẩn PostgreSQL Render)"""
        try:
            # SỬA: Đồng bộ tên cột (sender_id, message_type, room_id, reply_to_id, is_read)
            # Bỏ qua cột id (khóa chính) để Postgres SERIAL tự sinh số
            query = """
                INSERT INTO messages (
                    sender_id, content, message_type, room_id, 
                    reply_to_id, sent_at, is_read
                )
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, FALSE)
            """
            params = (user_id, content, msg_type, room_id, reply_to_id)
            DatabaseManager.execute_query(query, params)
            return True
        except Exception as e:
            app_logger.error(f"Lỗi lưu tin nhắn (User: {user_id}, Room: {room_id}): {e}")
            return False

    @staticmethod
    def save_forwarded_message(user_id, original_message_id, target_room_id):
        """Lưu tin nhắn được chuyển tiếp (Chuẩn Postgres Render)"""
        try:
            # 1. Lấy thông tin tin nhắn gốc (Sử dụng chuẩn gạch dưới)
            original_query = """
                SELECT content, message_type 
                FROM messages 
                WHERE id = ?
            """
            original = DatabaseManager.execute_query(original_query, (original_message_id,), fetch_one=True)
            
            if not original:
                app_logger.warning(f"Không tìm thấy tin nhắn gốc ID: {original_message_id}")
                return False
            
            content = original[0]
            msg_type = original[1]
            
            # 2. Tự động thêm cột lưu vết chuyển tiếp nếu chưa có
            column_name = 'forwarded_from_id'
            if not DatabaseManager.column_exists('messages', column_name):
                alter_query = f"ALTER TABLE messages ADD COLUMN {column_name} INT NULL"
                DatabaseManager.execute_query(alter_query)
                app_logger.info(f"Đã bổ sung cột {column_name} vào bảng messages.")
            
            # 3. Chèn tin nhắn mới (Copy nội dung từ tin nhắn gốc)
            # Bỏ qua cột id (SERIAL) để Postgres tự sinh số
            query = """
                INSERT INTO messages (
                    sender_id, content, message_type, room_id, 
                    forwarded_from_id, sent_at, is_read
                )
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, FALSE)
            """
            params = (user_id, content, msg_type, target_room_id, original_message_id)
            DatabaseManager.execute_query(query, params)
            return True
        except Exception as e:
            app_logger.error(f"Lỗi chuyển tiếp tin nhắn: {e}")
            return False
    @staticmethod
    def user_exists(user_id):
        """Kiểm tra sự tồn tại của người dùng (Tương thích Postgres)"""
        try:
            query = "SELECT 1 FROM users WHERE id = ?"
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            return result is not None
        except Exception as e:
            app_logger.error(f"Lỗi kiểm tra user_exists ({user_id}): {e}")
            return False

    @staticmethod
    def save_message(user_id, content, msg_type='Text', room_id=1, reply_to_id=None):
        """Lưu tin nhắn vào database (Chuẩn Postgres Render)"""
        try:
            # SỬA: Đồng bộ tên cột (sender_id, content, message_type, room_id, reply_to_id)
            # Bỏ qua cột ID tự tăng (SERIAL)
            query = """
                INSERT INTO messages (
                    sender_id, content, message_type, room_id, 
                    reply_to_id, sent_at, is_read
                )
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, FALSE)
            """
            # Đảm bảo thứ tự các tham số khớp với câu query
            params = (user_id, content, msg_type, room_id, reply_to_id)
            DatabaseManager.execute_query(query, params)
            return True
        except Exception as e:
            app_logger.error(f"Lỗi lưu tin nhắn (User: {user_id}, Room: {room_id}): {e}")
            return False

    @staticmethod
    def save_forwarded_message(user_id, original_message_id, target_room_id):
        """Lưu tin nhắn được chuyển tiếp (Forwarded message)"""
        try:
            # 1. Lấy nội dung tin nhắn gốc (Dùng chuẩn gạch dưới)
            original_query = """
                SELECT content, message_type 
                FROM messages 
                WHERE id = ?
            """
            original = DatabaseManager.execute_query(original_query, (original_message_id,), fetch_one=True)
            
            if not original:
                app_logger.warning(f"Không tìm thấy tin nhắn gốc ID: {original_message_id}")
                return False
            
            content, msg_type = original[0], original[1]
            
            # 2. Kiểm tra và thêm cột forwarded_from_id nếu chưa có
            column_name = 'forwarded_from_id'
            if not DatabaseManager.column_exists('messages', column_name):
                alter_query = f"ALTER TABLE messages ADD COLUMN {column_name} INT NULL"
                DatabaseManager.execute_query(alter_query)
                app_logger.info(f"Đã bổ sung cột {column_name} cho tính năng Forward.")
            
            # 3. Chèn tin nhắn mới (Copy nội dung từ gốc nhưng người gửi là người Forward)
            query = """
                INSERT INTO messages (
                    sender_id, content, message_type, room_id, 
                    forwarded_from_id, sent_at, is_read
                )
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, FALSE)
            """
            params = (user_id, content, msg_type, target_room_id, original_message_id)
            DatabaseManager.execute_query(query, params)
            return True
        except Exception as e:
            app_logger.error(f"Lỗi chuyển tiếp tin nhắn từ ID {original_message_id}: {e}")
            return False

    @staticmethod
    def update_email_notification_enabled(user_id, enabled):
        """Cập nhật trạng thái email notification (Chuẩn Postgres)"""
        try:
            # SỬA: email_notification_enabled (có gạch dưới)
            column_name = 'email_notification_enabled'
            
            # 1. Kiểm tra và tự động thêm cột BOOLEAN nếu chưa có
            if not DatabaseManager.column_exists('users', column_name):
                query_alter = f"ALTER TABLE users ADD COLUMN {column_name} BOOLEAN DEFAULT FALSE"
                DatabaseManager.execute_query(query_alter)
                app_logger.info(f"Đã bổ sung cột {column_name} vào bảng users.")
            
            # 2. Cập nhật giá trị
            # Lưu ý: Postgres nhận diện True/False của Python cực tốt cho kiểu BOOLEAN
            query_update = f"UPDATE users SET {column_name} = ? WHERE id = ?"
            DatabaseManager.execute_query(query_update, (enabled, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi cập nhật email notification cho user {user_id}: {e}")
            return False

    @staticmethod
    def get_email_notification_enabled(user_id):
        """Lấy trạng thái email notification của user"""
        try:
            column_name = 'email_notification_enabled'
            
            if not DatabaseManager.column_exists('users', column_name):
                return False
            
            query = f"SELECT {column_name} FROM users WHERE id = ?"
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            
            # Postgres trả về True/False trực tiếp, kiểm tra thêm None để tránh lỗi
            if result and result[0] is not None:
                return bool(result[0])
            return False
        except Exception as e:
            app_logger.error(f"Lỗi lấy trạng thái email notification cho user {user_id}: {e}")
            return False

    @staticmethod
    def get_users_with_email_notification_enabled(room_id):
        """Lấy danh sách users trong phòng có bật email notification (Postgres)"""
        try:
            # SỬA: Phân biệt rõ u.id (User) và rp.user_id / rp.room_id
            # Dùng tên cột có gạch dưới (email_notification_enabled)
            query = """
                SELECT u.id, u.email, u.fullname
                FROM users u
                JOIN room_participants rp ON u.id = rp.user_id
                WHERE rp.room_id = ? 
                AND u.email IS NOT NULL 
                AND u.email != ''
                AND u.email_notification_enabled = TRUE
            """
            users = DatabaseManager.execute_query(query, (room_id,), fetch_all=True)
            return [{
                'user_id': user[0],
                'email': user[1],
                'full_name': user[2]
            } for user in users]
        except Exception as e:
            app_logger.error(f"Lỗi lấy danh sách nhận mail cho phòng {room_id}: {e}")
            return []

    @staticmethod
    def remove_member_from_group(room_id, user_id):
        """Xóa thành viên khỏi nhóm (Chuẩn Postgres)"""
        try:
            # SỬA LỖI: Chỉ định rõ room_id và user_id
            # Đảm bảo tên bảng là room_participants (có gạch dưới)
            query = """
                DELETE FROM room_participants
                WHERE room_id = ? AND user_id = ?
            """
            DatabaseManager.execute_query(query, (room_id, user_id))
            
            # Gợi ý: Tới có thể xóa luôn cả quyền trong bảng room_roles nếu có
            role_query = "DELETE FROM room_roles WHERE room_id = ? AND user_id = ?"
            DatabaseManager.execute_query(role_query, (room_id, user_id))
            
            return True
        except Exception as e:
            app_logger.error(f"Lỗi xóa thành viên {user_id} khỏi phòng {room_id}: {e}")
            return False

    @staticmethod
    def update_group_info(room_id, room_name, description=None):
        """Cập nhật thông tin nhóm (Chuẩn Postgres)"""
        try:
            # 1. Đảm bảo các cột tồn tại (Dùng chuẩn gạch dưới)
            if not DatabaseManager.column_exists('rooms', 'description'):
                DatabaseManager.execute_query("ALTER TABLE rooms ADD COLUMN description VARCHAR(500) NULL")
            
            if not DatabaseManager.column_exists('rooms', 'avatar_url'):
                DatabaseManager.execute_query("ALTER TABLE rooms ADD COLUMN avatar_url VARCHAR(500) NULL")
            
            # 2. Cập nhật thông tin
            # SỬA: room_name, room_id (Phân biệt rõ ràng)
            query = """
                UPDATE rooms
                SET room_name = ?, description = ?
                WHERE id = ?
            """
            DatabaseManager.execute_query(query, (room_name, description, room_id))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi cập nhật thông tin phòng {room_id}: {e}")
            return False

    @staticmethod
    def create_group_invite(room_id, inviter_id, invitee_id):
        """Tạo lời mời vào nhóm (Chuẩn Postgres Render)"""
        try:
            # 1. Tạo bảng nếu chưa có (Dùng tên cột rõ ràng)
            if not DatabaseManager.table_exists('group_invites'):
                query_create = """
                    CREATE TABLE group_invites (
                        id SERIAL PRIMARY KEY,
                        room_id INT NOT NULL,
                        inviter_id INT NOT NULL,
                        invitee_id INT NOT NULL,
                        status VARCHAR(50) DEFAULT 'Pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT fk_room FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
                        CONSTRAINT fk_inviter FOREIGN KEY (inviter_id) REFERENCES users(id),
                        CONSTRAINT fk_invitee FOREIGN KEY (invitee_id) REFERENCES users(id)
                    )
                """
                DatabaseManager.execute_query(query_create)
            
            # 2. Kiểm tra xem lời mời 'Pending' đã tồn tại chưa
            check_query = """
                SELECT id FROM group_invites 
                WHERE room_id = ? AND invitee_id = ? AND status = 'Pending'
            """
            existing = DatabaseManager.execute_query(check_query, (room_id, invitee_id), fetch_one=True)
            if existing:
                return False # Đã có lời mời đang chờ, không tạo thêm
            
            # 3. Tạo lời mời mới
            query_insert = """
                INSERT INTO group_invites (room_id, inviter_id, invitee_id, status)
                VALUES (?, ?, ?, 'Pending')
            """
            DatabaseManager.execute_query(query_insert, (room_id, inviter_id, invitee_id))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi tạo lời mời nhóm (Room: {room_id}, To: {invitee_id}): {e}")
            return False

    @staticmethod
    def get_pending_invites(user_id):
        """Lấy danh sách lời mời đang chờ của người dùng (Chuẩn Postgres)"""
        try:
            # SỬA: Đồng bộ tên bảng group_invites và các cột room_id, user_id
            query = """
                SELECT gi.id, gi.room_id, gi.inviter_id, gi.created_at,
                    r.room_name, r.avatar_url, u.fullname as inviter_name
                FROM group_invites gi
                JOIN rooms r ON gi.room_id = r.id
                JOIN users u ON gi.inviter_id = u.id
                WHERE gi.invitee_id = ? AND gi.status = 'Pending'
                ORDER BY gi.created_at DESC
            """
            invites = DatabaseManager.execute_query(query, (user_id,), fetch_all=True)
            
            return [{
                'invite_id': invite[0],
                'room_id': invite[1],
                'inviter_id': invite[2],
                'created_at': invite[3].strftime('%H:%M %d/%m/%Y') if invite[3] else '',
                'room_name': invite[4],
                'room_avatar': invite[5],
                'inviter_name': invite[6]
            } for invite in invites]
        except Exception as e:
            app_logger.error(f"Lỗi lấy danh sách lời mời cho user {user_id}: {e}")
            return []

    @staticmethod
    def accept_decline_invite(invite_id, user_id, action):
        """Chấp nhận hoặc từ chối lời mời vào nhóm"""
        try:
            # 1. Kiểm tra lời mời có tồn tại và thuộc về user này không
            query = """
                SELECT room_id FROM group_invites 
                WHERE id = ? AND invitee_id = ? AND status = 'Pending'
            """
            invite = DatabaseManager.execute_query(query, (invite_id, user_id), fetch_one=True)
            
            if not invite:
                return False
            
            room_id = invite[0]
            
            # 2. Xử lý hành động
            if action == 'accept':
                # Thêm user vào nhóm (Hàm add_member_to_group cần dùng chuẩn room_participants)
                DatabaseManager.add_member_to_group(room_id, user_id)
                new_status = 'Accepted'
            else:
                new_status = 'Declined'
            
            # 3. Cập nhật trạng thái lời mời vào bảng
            update_query = """
                UPDATE group_invites 
                SET status = ? 
                WHERE id = ?
            """
            DatabaseManager.execute_query(update_query, (new_status, invite_id))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi xử lý lời mời {invite_id} (Action: {action}): {e}")
            return False


    @staticmethod
    def ensure_room_participants_table():
        """Đảm bảo bảng room_participants tồn tại (Chuẩn Postgres)"""
        try:
            app_logger.info("Đang kiểm tra/tạo bảng room_participants...")
            # SỬA: Đặt tên cột rõ ràng room_id và user_id
            query = """
                CREATE TABLE IF NOT EXISTS room_participants (
                    room_id INT NOT NULL,
                    user_id INT NOT NULL,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    role VARCHAR(50) DEFAULT 'Member',
                    PRIMARY KEY (room_id, user_id),
                    CONSTRAINT fk_room FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
                    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """
            DatabaseManager.execute_query(query)
            app_logger.info("Bảng room_participants đã sẵn sàng.")
        except Exception as e:
            app_logger.error(f"Lỗi tạo bảng room_participants: {e}")

    @staticmethod
    def is_room_member(room_id, user_id):
        """Kiểm tra xem người dùng có phải thành viên phòng không"""
        try:
            # SỬA: room_id = ? AND user_id = ?
            query = """
                SELECT 1 
                FROM room_participants 
                WHERE room_id = ? AND user_id = ?
            """
            result = DatabaseManager.execute_query(query, (room_id, user_id), fetch_one=True)
            return result is not None
        except Exception as e:
            app_logger.error(f"Lỗi kiểm tra thành viên (Room: {room_id}, User: {user_id}): {e}")
            return False

        
    

    @staticmethod
    def get_group_members(room_id):
        """Lấy danh sách thành viên trong nhóm (Ưu tiên Admin lên đầu)"""
        try:
            # SỬA: Đồng bộ tên cột room_id, user_id, joined_at
            query = """
                SELECT u.id, u.fullname, u.username, rp.role, rp.joined_at, u.status
                FROM room_participants rp
                JOIN users u ON rp.user_id = u.id
                WHERE rp.room_id = ?
                ORDER BY CASE WHEN rp.role = 'Admin' THEN 1 ELSE 2 END, u.fullname
            """
            members = DatabaseManager.execute_query(query, (room_id,), fetch_all=True)
            return [{
                'user_id': member[0],
                'full_name': member[1],
                'username': member[2],
                'role': member[3],
                'joined_at': member[4].strftime('%H:%M %d/%m/%Y') if member[4] else '',
                'status': member[5]
            } for member in members]
        except Exception as e:
            app_logger.error(f"Lỗi lấy danh sách thành viên phòng {room_id}: {e}")
            return []

    @staticmethod
    def search_messages_in_room(room_id, search_text, page=1, limit=20):
        """Tìm kiếm tin nhắn (Chuẩn PostgreSQL ILIKE & Pagination)"""
        try:
            offset = (page - 1) * limit
            search_pattern = f"%{search_text}%"
            
            # SỬA: Đồng bộ tên cột message_id, sender_id, message_type, sent_at...
            search_query = """
                SELECT m.id, m.sender_id, u.fullname as sender_name, m.content,
                    m.message_type, m.sent_at, m.edited_at, m.is_deleted
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                WHERE m.room_id = ? 
                AND (m.is_deleted IS FALSE OR m.is_deleted IS NULL)
                AND (m.content ILIKE ? OR u.fullname ILIKE ?)
                ORDER BY m.sent_at DESC
                LIMIT ? OFFSET ?
            """
            messages = DatabaseManager.execute_query(
                search_query, 
                (room_id, search_pattern, search_pattern, limit, offset), 
                fetch_all=True
            )
            
            # Lấy tổng số kết quả để phân trang ở Frontend
            count_query = """
                SELECT COUNT(*)
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                WHERE m.room_id = ? 
                AND (m.is_deleted IS FALSE OR m.is_deleted IS NULL)
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
                    'sent_at': msg[5].strftime('%H:%M %d/%m/%Y') if msg[5] else '',
                    'edited_at': msg[6].strftime('%H:%M %d/%m/%Y') if msg[6] else None,
                    'is_deleted': bool(msg[7])
                } for msg in messages],
                'total': total,
                'page': page,
                'limit': limit
            }
        except Exception as e:
            app_logger.error(f"Lỗi tìm kiếm tin nhắn trong phòng {room_id}: {e}")
            return {'messages': [], 'total': 0, 'page': page, 'limit': limit}

    @staticmethod
    def global_search_messages(user_id, query_text, page=1, limit=20):
        """Tìm kiếm tin nhắn trên tất cả các phòng mà user tham gia (Postgres)"""
        try:
            offset = (page - 1) * limit
            search_pattern = f"%{query_text}%"
            
            # SỬA: Phân biệt rõ m.id (room_id), rp.room_id và rp.user_id
            # SỬA: Đồng bộ tên cột message_type, sent_at, is_deleted, room_name...
            search_query = """
                SELECT DISTINCT m.id as message_id, m.sender_id, u.fullname as sender_name, m.content,
                    m.message_type, m.sent_at, m.room_id, r.room_name,
                    CASE WHEN r.is_group IS TRUE THEN r.room_name ELSE 'Chat riêng' END as room_display_name
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                JOIN rooms r ON m.room_id = r.id
                JOIN room_participants rp ON r.id = rp.room_id
                WHERE rp.user_id = ? 
                AND (m.is_deleted IS FALSE OR m.is_deleted IS NULL)
                AND (m.content ILIKE ? OR u.fullname ILIKE ? OR r.room_name ILIKE ?)
                ORDER BY m.sent_at DESC
                LIMIT ? OFFSET ?
            """
            messages = DatabaseManager.execute_query(
                search_query, 
                (user_id, search_pattern, search_pattern, search_pattern, limit, offset), 
                fetch_all=True
            )
            
            # Lấy tổng số kết quả
            count_query = """
                SELECT COUNT(DISTINCT m.id)
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                JOIN rooms r ON m.room_id = r.id
                JOIN room_participants rp ON r.id = rp.room_id
                WHERE rp.user_id = ? 
                AND (m.is_deleted IS FALSE OR m.is_deleted IS NULL)
                AND (m.content ILIKE ? OR u.fullname ILIKE ? OR r.room_name ILIKE ?)
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
                    'sent_at': msg[5].strftime('%H:%M %d/%m/%Y') if msg[5] else '',
                    'room_id': msg[6],
                    'room_name': msg[7],
                    'room_display_name': msg[8]
                } for msg in messages],
                'total': total,
                'page': page,
                'limit': limit
            }
        except Exception as e:
            app_logger.error(f"Lỗi tìm kiếm toàn cầu cho user {user_id}: {e}")
            return {'messages': [], 'total': 0, 'page': page, 'limit': limit}

    @staticmethod
    def get_search_suggestions(user_id, query_text):
        """Lấy gợi ý tìm kiếm người dùng và phòng chat (Chuẩn Postgres)"""
        try:
            search_pattern = f"%{query_text}%"
            # SỬA: Phân biệt rõ rp.room_id và rp.user_id
            # SỬA: Đồng bộ tên cột room_name, avatar_url...
            search_query = """
                SELECT DISTINCT 'user' as type, u.fullname as name, u.username as username
                FROM users u
                WHERE u.id != ? AND (u.fullname ILIKE ? OR u.username ILIKE ?)
                
                UNION ALL
                
                SELECT DISTINCT 'room' as type, r.room_name as name, '' as username
                FROM rooms r
                JOIN room_participants rp ON r.id = rp.room_id
                WHERE rp.user_id = ? AND r.room_name ILIKE ?
                
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
            app_logger.error(f"Lỗi gợi ý tìm kiếm cho user {user_id}: {e}")
            return []
    
    @staticmethod
    def update_group_info(room_id, room_name, description=None):
        """Cập nhật thông tin nhóm (Tương thích Postgres Render)"""
        try:
            # 1. Đảm bảo các cột mở rộng tồn tại (Dùng chuẩn gạch dưới)
            if not DatabaseManager.column_exists('rooms', 'description'):
                DatabaseManager.execute_query("ALTER TABLE rooms ADD COLUMN description VARCHAR(500) NULL")
            
            if not DatabaseManager.column_exists('rooms', 'avatar_url'):
                DatabaseManager.execute_query("ALTER TABLE rooms ADD COLUMN avatar_url VARCHAR(500) NULL")
            
            # 2. Thực hiện cập nhật
            # SỬA: room_name thay vì roomname để đồng bộ
            query = """
                UPDATE rooms
                SET room_name = ?, description = ?
                WHERE id = ?
            """
            DatabaseManager.execute_query(query, (room_name, description, room_id))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi cập nhật thông tin phòng {room_id}: {e}")
            return False
    
    @staticmethod
    def is_room_member(room_id, user_id):
        """Kiểm tra xem người dùng có phải thành viên của phòng không"""
        try:
            # SỬA: Chỉ định rõ tên cột room_id và user_id
            # PostgreSQL cần phân biệt rõ các trường trong bảng room_participants
            query = """
                SELECT COUNT(*) 
                FROM room_participants 
                WHERE room_id = ? AND user_id = ?
            """
            result = DatabaseManager.execute_query(query, (room_id, user_id), fetch_one=True)
            return result[0] > 0 if result else False
        except Exception as e:
            app_logger.error(f"Lỗi kiểm tra thành viên (Room: {room_id}, User: {user_id}): {e}")
            return False
    
    @staticmethod
    def get_group_members(room_id):
        """Lấy danh sách thành viên trong nhóm kèm thông tin chi tiết"""
        try:
            # SỬA: rp.user_id = u.id và rp.room_id = ?
            # SỬA: joined_at (dùng gạch dưới cho chuẩn Postgres)
            query = """
                SELECT u.id, u.fullname, u.username, rp.role, rp.joined_at, u.status
                FROM room_participants rp
                JOIN users u ON rp.user_id = u.id
                WHERE rp.room_id = ?
                ORDER BY CASE WHEN rp.role = 'Admin' THEN 1 ELSE 2 END, u.fullname
            """
            members = DatabaseManager.execute_query(query, (room_id,), fetch_all=True)
            return [{
                'user_id': member[0],
                'full_name': member[1],
                'username': member[2],
                'role': member[3],
                'joined_at': member[4].strftime('%H:%M %d/%m/%Y') if member[4] else '',
                'status': member[5]
            } for member in members]
        except Exception as e:
            app_logger.error(f"Lỗi lấy danh sách thành viên phòng {room_id}: {e}")
            return []
    @staticmethod
    def update_group_info(room_id, room_name, description=None):
        """Cập nhật thông tin nhóm (Tương thích Postgres Render)"""
        try:
            # 1. Tự động kiểm tra và nâng cấp cấu trúc bảng nếu thiếu cột
            # Đã đồng bộ sang chuẩn snake_case (avatar_url)
            if not DatabaseManager.column_exists('rooms', 'description'):
                DatabaseManager.execute_query("ALTER TABLE rooms ADD COLUMN description VARCHAR(500) NULL")
            
            if not DatabaseManager.column_exists('rooms', 'avatar_url'):
                DatabaseManager.execute_query("ALTER TABLE rooms ADD COLUMN avatar_url VARCHAR(500) NULL")
            
            # 2. Cập nhật thông tin phòng chat
            query = """
                UPDATE rooms
                SET room_name = ?, description = ?
                WHERE id = ?
            """
            DatabaseManager.execute_query(query, (room_name, description, room_id))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi cập nhật thông tin phòng {room_id}: {e}")
            return False
    
    @staticmethod
    def is_room_member(room_id, user_id):
        """Kiểm tra xem người dùng có phải thành viên của phòng không"""
        try:
            # SỬA LỖI: Chỉ định đích danh room_id và user_id của bảng room_participants
            query = """
                SELECT COUNT(*) 
                FROM room_participants 
                WHERE room_id = ? AND user_id = ?
            """
            result = DatabaseManager.execute_query(query, (room_id, user_id), fetch_one=True)
            return result[0] > 0 if result else False
        except Exception as e:
            app_logger.error(f"Lỗi kiểm tra thành viên phòng (Room: {room_id}, User: {user_id}): {e}")
            return False
    
    @staticmethod
    def get_group_members(room_id):
        """Lấy danh sách thành viên trong nhóm kèm thông tin chi tiết"""
        try:
            # SỬA: rp.user_id nối với u.id; lọc chính xác theo rp.room_id
            # SỬA:joined_at (Chuẩn snake_case)
            query = """
                SELECT u.id, u.fullname, u.username, rp.role, rp.joined_at, u.status
                FROM room_participants rp
                JOIN users u ON rp.user_id = u.id
                WHERE rp.room_id = ?
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
            app_logger.error(f"Lỗi lấy danh sách thành viên phòng {room_id}: {e}")
            return []
    
    @staticmethod
    def search_messages_in_room(room_id, query_text, page=1, limit=20):
        """Tìm kiếm tin nhắn trong một phòng cụ thể (Chuẩn Postgres)"""
        try:
            offset = (page - 1) * limit
            search_pattern = f"%{query_text}%"
            
            # SỬA: m.id thành m.room_id để lọc đúng phòng chat
            # SỬA: Đồng bộ các cột message_id -> id, senderid -> sender_id, messagetype -> message_type...
            search_query = """
                SELECT m.id, m.sender_id, u.fullname as sender_name, m.content,
                    m.message_type, m.sent_at, m.edited_at, m.is_deleted
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                WHERE m.room_id = ? AND (m.is_deleted IS FALSE OR m.is_deleted IS NULL)
                AND (m.content ILIKE ? OR u.fullname ILIKE ?)
                ORDER BY m.sent_at DESC
                LIMIT ? OFFSET ?
            """
            messages = DatabaseManager.execute_query(
                search_query, 
                (room_id, search_pattern, search_pattern, limit, offset), 
                fetch_all=True
            )
            
            # Lấy tổng số kết quả để trả về cho Frontend tính toán số trang
            count_query = """
                SELECT COUNT(*)
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                WHERE m.room_id = ? AND (m.is_deleted IS FALSE OR m.is_deleted IS NULL)
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
            app_logger.error(f"Lỗi tìm kiếm tin nhắn trong phòng {room_id}: {e}")
            return {'messages': [], 'total': 0, 'page': page, 'limit': limit}

    @staticmethod
    def global_search_messages(user_id, query_text, page=1, limit=20):
        """Tìm kiếm tin nhắn trên tất cả các phòng mà người dùng tham gia"""
        try:
            offset = (page - 1) * limit
            search_pattern = f"%{query_text}%"
            
            # SỬA LỖI: Chỉ định rõ m.room_id, r.id, rp.room_id và rp.user_id
            # PostgreSQL cần sự tường minh để không bị lẫn lộn giữa ID tin nhắn và ID phòng
            search_query = """
                SELECT DISTINCT m.id, m.sender_id, u.fullname as sender_name, m.content,
                    m.message_type, m.sent_at, m.room_id, r.room_name,
                    CASE WHEN r.is_group IS TRUE THEN r.room_name ELSE 'Chat riêng' END as room_display_name
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                JOIN rooms r ON m.room_id = r.id
                JOIN room_participants rp ON r.id = rp.room_id
                WHERE rp.user_id = ? 
                AND (m.is_deleted IS FALSE OR m.is_deleted IS NULL)
                AND (m.content ILIKE ? OR u.fullname ILIKE ? OR r.room_name ILIKE ?)
                ORDER BY m.sent_at DESC
                LIMIT ? OFFSET ?
            """
            messages = DatabaseManager.execute_query(
                search_query, 
                (user_id, search_pattern, search_pattern, search_pattern, limit, offset), 
                fetch_all=True
            )
            
            # Đếm tổng số kết quả (Dùng DISTINCT m.id để chính xác)
            count_query = """
                SELECT COUNT(DISTINCT m.id)
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                JOIN rooms r ON m.room_id = r.id
                JOIN room_participants rp ON r.id = rp.room_id
                WHERE rp.user_id = ? 
                AND (m.is_deleted IS FALSE OR m.is_deleted IS NULL)
                AND (m.content ILIKE ? OR u.fullname ILIKE ? OR r.room_name ILIKE ?)
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
                    'sent_at': msg[5].strftime('%H:%M %d/%m/%Y') if msg[5] else '',
                    'room_id': msg[6],
                    'room_name': msg[7],
                    'room_display_name': msg[8]
                } for msg in messages],
                'total': total,
                'page': page,
                'limit': limit
            }
        except Exception as e:
            app_logger.error(f"Lỗi tìm kiếm toàn cầu cho user {user_id}: {e}")
            return {'messages': [], 'total': 0, 'page': page, 'limit': limit}
    
    @staticmethod
    def get_search_suggestions(user_id, query_text):
        """Lấy gợi ý tìm kiếm cho người dùng và phòng chat (Chuẩn Postgres)"""
        try:
            search_pattern = f"%{query_text}%"
            # SỬA: Phân biệt rõ rp.room_id và rp.user_id để lọc đúng phòng user đã tham gia
            search_query = """
                SELECT DISTINCT 'user' as type, u.fullname as name, u.username as username
                FROM users u
                WHERE u.id != ? AND (u.fullname ILIKE ? OR u.username ILIKE ?)
                
                UNION ALL
                
                SELECT DISTINCT 'room' as type, r.room_name as name, '' as username
                FROM rooms r
                JOIN room_participants rp ON r.id = rp.room_id
                WHERE rp.user_id = ? AND r.room_name ILIKE ?
                
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
            app_logger.error(f"Lỗi gợi ý tìm kiếm cho user {user_id}: {e}")
            return []
    
    @staticmethod
    def set_theme(user_id, theme):
        """Thiết lập giao diện (light/dark) cho người dùng"""
        try:
            # Kiểm tra và tạo cột theme nếu chưa có
            if not DatabaseManager.column_exists('users', 'theme'):
                app_logger.info("Thêm cột 'theme' vào bảng users...")
                DatabaseManager.execute_query("ALTER TABLE users ADD COLUMN theme VARCHAR(20) NOT NULL DEFAULT 'light'")
            
            query = "UPDATE users SET theme = ? WHERE id = ?"
            DatabaseManager.execute_query(query, (theme, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi thiết lập theme cho user {user_id}: {e}")
            return False
    
    @staticmethod
    def get_theme(user_id):
        """Lấy cấu hình giao diện của người dùng (Light/Dark)"""
        try:
            # Tự động nâng cấp bảng nếu thiếu cột (Migration lười)
            if not DatabaseManager.column_exists('users', 'theme'):
                DatabaseManager.execute_query("ALTER TABLE users ADD COLUMN theme VARCHAR(20) NOT NULL DEFAULT 'light'")
            
            query = "SELECT theme FROM users WHERE id = ?"
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            
            # Nếu user tồn tại, trả về theme của họ, ngược lại mặc định là 'light'
            return result[0] if result and result[0] else 'light'
        except Exception as e:
            app_logger.error(f"Lỗi lấy theme cho user {user_id}: {e}")
            return 'light'
    
    @staticmethod
    def toggle_theme(user_id):
        """Chuyển đổi giao diện sáng/tối chỉ với một câu lệnh SQL duy nhất"""
        try:
            if not DatabaseManager.column_exists('users', 'theme'):
                DatabaseManager.execute_query("ALTER TABLE users ADD COLUMN theme VARCHAR(20) NOT NULL DEFAULT 'light'")
            
            # Sử dụng CASE WHEN trong SQL để đảo theme ngay lập tức
            # RETURNING theme: Giúp lấy lại giá trị mới sau khi update mà không cần SELECT lại
            query = """
                UPDATE users 
                SET theme = CASE WHEN theme = 'light' THEN 'dark' ELSE 'light' END
                WHERE id = ?
                RETURNING theme
            """
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            
            return result[0] if result else 'light'
        except Exception as e:
            app_logger.error(f"Lỗi chuyển đổi theme cho user {user_id}: {e}")
            return 'light'
    
    @staticmethod
    def is_admin(user_id):
        """Kiểm tra quyền quản trị viên (Admin)"""
        try:
            if not DatabaseManager.column_exists('users', 'role'):
                DatabaseManager.execute_query("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'User'")
            
            query = "SELECT role FROM users WHERE id = ?"
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            role = result[0] if result and result[0] else 'User'
            return role == 'Admin'
        except Exception as e:
            app_logger.error(f"Lỗi kiểm tra quyền Admin cho user {user_id}: {e}")
            return False
    
    @staticmethod
    def get_admin_dashboard_stats():
        """Lấy thống kê tổng quan cho trang quản trị (Chuẩn Postgres)"""
        try:
            # Các câu lệnh đếm tổng cơ bản
            total_users = DatabaseManager.execute_query("SELECT COUNT(*) FROM users", fetch_one=True)[0]
            total_rooms = DatabaseManager.execute_query("SELECT COUNT(*) FROM rooms", fetch_one=True)[0]
            total_messages = DatabaseManager.execute_query("SELECT COUNT(*) FROM messages", fetch_one=True)[0]
            
            # SỬA: Đổi tên bảng thành shared_files cho đồng bộ snake_case nếu cần
            total_files = DatabaseManager.execute_query("SELECT COUNT(*) FROM shared_files", fetch_one=True)[0]
            online_users = DatabaseManager.execute_query("SELECT COUNT(*) FROM users WHERE status = 'Online'", fetch_one=True)[0]
            
            # 1. Thống kê lượng tin nhắn 7 ngày gần nhất (Dùng định dạng cột sent_at)
            daily_stats_query = """
                SELECT sent_at::DATE as msg_date, COUNT(*) as msg_count
                FROM messages
                WHERE sent_at >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY sent_at::DATE
                ORDER BY msg_date DESC
            """
            daily_stats_raw = DatabaseManager.execute_query(daily_stats_query, fetch_all=True)
            daily_stats = [{'date': str(row[0]), 'count': row[1]} for row in daily_stats_raw]
            
            # 2. Top 10 người dùng tích cực nhất (30 ngày qua)
            # SỬA: m.senderid -> m.sender_id, m.messageid -> m.id
            top_users_query = """
                SELECT u.fullname, COUNT(m.id) as msg_count
                FROM users u
                LEFT JOIN messages m ON u.id = m.sender_id
                                    AND m.sent_at >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY u.id, u.fullname
                ORDER BY msg_count DESC
                LIMIT 10
            """
            top_users_raw = DatabaseManager.execute_query(top_users_query, fetch_all=True)
            top_users = [{'fullname': row[0], 'count': row[1]} for row in top_users_raw]
            
            # 3. Top 10 phòng chat sôi nổi nhất (30 ngày qua)
            # SỬA: m.id -> m.room_id (Lỗi logic nghiêm trọng của câu query cũ)
            top_rooms_query = """
                SELECT r.room_name, COUNT(m.id) as msg_count
                FROM rooms r
                LEFT JOIN messages m ON r.id = m.room_id
                                    AND m.sent_at >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY r.id, r.room_name
                ORDER BY msg_count DESC
                LIMIT 10
            """
            top_rooms_raw = DatabaseManager.execute_query(top_rooms_query, fetch_all=True)
            top_rooms = [{'room_name': row[0], 'count': row[1]} for row in top_rooms_raw]
            
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
            app_logger.error(f"Lỗi lấy thống kê Dashboard Admin: {e}")
            return {
                'total_users': 0, 'total_rooms': 0, 'total_messages': 0, 
                'total_files': 0, 'online_users': 0, 'daily_stats': [], 
                'top_users': [], 'top_rooms': []
            }
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
        """Cập nhật quyền người dùng (Admin/User)"""
        try:
            query = "UPDATE users SET role = ? WHERE id = ?"
            DatabaseManager.execute_query(query, (new_role, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi cập nhật quyền cho user {user_id}: {e}")
            return False
    
    @staticmethod
    def get_system_stats():
        """Lấy thống kê hệ thống chi tiết (Postgres Render)"""
        try:
            stats = {}
            
            # 1. Thống kê Người dùng
            stats['total_users'] = DatabaseManager.execute_query("SELECT COUNT(*) FROM users", fetch_one=True)[0]
            stats['online_users'] = DatabaseManager.execute_query("SELECT COUNT(*) FROM users WHERE status = 'Online'", fetch_one=True)[0]
            
            # SỬA: created_at (snake_case)
            stats['new_users_today'] = DatabaseManager.execute_query(
                "SELECT COUNT(*) FROM users WHERE created_at::DATE = CURRENT_DATE", fetch_one=True)[0]
            
            # 2. Thống kê Tin nhắn
            stats['total_messages'] = DatabaseManager.execute_query("SELECT COUNT(*) FROM messages", fetch_one=True)[0]
            
            # SỬA: sent_at (snake_case)
            stats['messages_today'] = DatabaseManager.execute_query(
                "SELECT COUNT(*) FROM messages WHERE sent_at::DATE = CURRENT_DATE", fetch_one=True)[0]
            
            # 3. Thống kê Tài nguyên (File)
            # SỬA: shared_files và file_size (snake_case)
            stats['total_files'] = DatabaseManager.execute_query("SELECT COUNT(*) FROM shared_files", fetch_one=True)[0]
            
            size_query = "SELECT SUM(file_size) FROM shared_files"
            result_size = DatabaseManager.execute_query(size_query, fetch_one=True)
            # Xử lý trường hợp chưa có file nào (tránh lỗi None + int)
            stats['total_file_size'] = result_size[0] if result_size and result_size[0] else 0
            
            # 4. Thống kê Phòng chat
            # SỬA: is_group (snake_case)
            stats['total_rooms'] = DatabaseManager.execute_query("SELECT COUNT(*) FROM rooms", fetch_one=True)[0]
            stats['total_groups'] = DatabaseManager.execute_query(
                "SELECT COUNT(*) FROM rooms WHERE is_group IS TRUE", fetch_one=True)[0]
            
            return stats
        except Exception as e:
            app_logger.error(f"Lỗi lấy thống kê hệ thống: {e}")
            # Trả về các giá trị mặc định để Frontend không bị crash
            return {
                'total_users': 0, 'online_users': 0, 'new_users_today': 0,
                'total_messages': 0, 'messages_today': 0, 
                'total_files': 0, 'total_file_size': 0,
                'total_rooms': 0, 'total_groups': 0
            }
    
    @staticmethod
    def ensure_voice_messages_table():
        """Đảm bảo bảng voice_messages tồn tại (Chuẩn Postgres Render)"""
        try:
            # SỬA LỖI LOGIC: Dùng trực tiếp IF NOT EXISTS của Postgres thay vì check column_exists trên bảng chưa tạo
            # SỬA TÊN CỘT: Đồng bộ sang chuẩn snake_case (id -> voice_id, uploadedby -> sender_id, id phòng -> room_id...)
            create_table_query = """
                CREATE TABLE IF NOT EXISTS voice_messages (
                    id SERIAL PRIMARY KEY,
                    filename VARCHAR(255) NOT NULL,
                    filepath VARCHAR(500) NOT NULL,
                    duration INT NULL,
                    file_size INT NOT NULL,
                    sender_id INT NOT NULL,
                    room_id INT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
                )
            """
            DatabaseManager.execute_query(create_table_query)
        except Exception as e:
            app_logger.error(f"Lỗi kiểm tra/tạo bảng voice_messages: {e}")
    
    @staticmethod
    def save_voice_message(filename, filepath, filesize, uploaded_by, room_id=None, duration=None):
        """Lưu thông tin tin nhắn thoại vào cơ sở dữ liệu"""
        try:
            # 1. Đảm bảo bảng đã sẵn sàng
            DatabaseManager.ensure_voice_messages_table()
            
            # 2. Thực hiện chèn dữ liệu
            # SỬA: Khớp 100% với tên cột mới (file_size, sender_id, room_id)
            query = """
                INSERT INTO voice_messages (filename, filepath, file_size, sender_id, room_id, duration)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            DatabaseManager.execute_query(query, (filename, filepath, filesize, uploaded_by, room_id, duration))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi lưu tin nhắn thoại (File: {filename}): {e}")
            return False
    
    @staticmethod
    def get_voice_messages(room_id, user_id):
        """Lấy danh sách tin nhắn thoại trong phòng chat"""
        try:
            # 1. Bảo mật: Kiểm tra xem người dùng có phải thành viên phòng không
            if not DatabaseManager.is_room_member(room_id, user_id):
                return []
            
            # 2. Truy vấn dữ liệu (Sử dụng chuẩn snake_case)
            # SỬA: voiceid -> id, uploadedby -> sender_id, id -> room_id
            query = """
                SELECT vm.id, vm.filename, vm.filepath, vm.duration,
                    vm.file_size, vm.sent_at, u.fullname as sender_name
                FROM voice_messages vm
                JOIN users u ON vm.sender_id = u.id
                WHERE vm.room_id = ?
                ORDER BY vm.sent_at DESC
            """
            voice_messages = DatabaseManager.execute_query(query, (room_id,), fetch_all=True)
            
            return [{
                'voice_id': vm[0],
                'filename': vm[1],
                'filepath': vm[2],
                'duration': vm[3],
                'file_size': vm[4],
                'sent_at': vm[5].strftime('%H:%M %d/%m/%Y') if vm[5] else '',
                'sender_name': vm[6]
            } for vm in voice_messages]
        except Exception as e:
            app_logger.error(f"Lỗi lấy tin nhắn thoại phòng {room_id}: {e}")
            return []
    
    @staticmethod
    def enable_2fa(user_id, secret):
        """Khởi tạo 2FA cho người dùng (Postgres)"""
        try:
            # Tự động nâng cấp bảng users nếu thiếu cột bảo mật
            # SỬA: twofasecret -> two_fa_secret, twofaenabled -> two_fa_enabled
            if not DatabaseManager.column_exists('users', 'two_fa_secret'):
                DatabaseManager.execute_query("ALTER TABLE users ADD COLUMN two_fa_secret VARCHAR(255) NULL")
            
            if not DatabaseManager.column_exists('users', 'two_fa_enabled'):
                DatabaseManager.execute_query("ALTER TABLE users ADD COLUMN two_fa_enabled BOOLEAN NOT NULL DEFAULT FALSE")
            
            # Lưu secret và để trạng thái chưa kích hoạt (Chờ người dùng quét mã xong mới TRUE)
            query = """
                UPDATE users
                SET two_fa_secret = ?, two_fa_enabled = FALSE
                WHERE id = ?
            """
            DatabaseManager.execute_query(query, (secret, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi khởi tạo 2FA cho user {user_id}: {e}")
            return False
    
    @staticmethod
    def get_2fa_secret(user_id):
        """Lấy mã secret 2FA của người dùng"""
        try:
            # SỬA: twofasecret -> two_fa_secret (Chuẩn snake_case)
            query = "SELECT two_fa_secret FROM users WHERE id = ?"
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            return result[0] if result and result[0] else None
        except Exception as e:
            app_logger.error(f"Lỗi lấy mã 2FA secret cho user {user_id}: {e}")
            return None
    
    @staticmethod
    def enable_2fa_verified(user_id):
        """Chính thức kích hoạt 2FA sau khi người dùng nhập đúng mã xác nhận lần đầu"""
        try:
            # SỬA: twofaenabled -> two_fa_enabled (Chuẩn snake_case)
            # Giữ nguyên giá trị TRUE cho kiểu dữ liệu BOOLEAN trong PostgreSQL
            query = "UPDATE users SET two_fa_enabled = TRUE WHERE id = ?"
            DatabaseManager.execute_query(query, (user_id,))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi kích hoạt chính thức 2FA cho user {user_id}: {e}")
            return False
    
    @staticmethod
    def get_user_password_and_2fa_secret(user_id):
        """Lấy mật khẩu và mã secret 2FA của người dùng (Postgres)"""
        try:
            # SỬA: twofasecret -> two_fa_secret (Chuẩn snake_case)
            query = """
                SELECT password, two_fa_secret
                FROM users
                WHERE id = ?
            """
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            return result if result else (None, None)
        except Exception as e:
            app_logger.error(f"Lỗi lấy thông tin mật khẩu và 2FA cho user {user_id}: {e}")
            return (None, None)
    
    @staticmethod
    def disable_2fa(user_id):
        """Tắt tính năng 2FA cho người dùng"""
        try:
            # SỬA: twofaenabled -> two_fa_enabled, twofasecret -> two_fa_secret
            query = """
                UPDATE users
                SET two_fa_enabled = FALSE, two_fa_secret = NULL
                WHERE id = ?
            """
            DatabaseManager.execute_query(query, (user_id,))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi tắt 2FA cho user {user_id}: {e}")
            return False
    
    @staticmethod
    def get_2fa_secret_and_status(user_id):
        """Lấy mã secret và trạng thái kích hoạt 2FA"""
        try:
            # SỬA: twofasecret -> two_fa_secret, twofaenabled -> two_fa_enabled
            query = """
                SELECT two_fa_secret, two_fa_enabled
                FROM users
                WHERE id = ?
            """
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            # result[1] lúc này sẽ là True hoặc False (kiểu boolean của Postgres)
            return result if result else (None, False)
        except Exception as e:
            app_logger.error(f"Lỗi lấy thông tin secret và trạng thái 2FA cho user {user_id}: {e}")
            return (None, False)
    
    @staticmethod
    def is_2fa_enabled(user_id):
        """Kiểm tra xem 2FA có đang bật hay không"""
        try:
            # SỬA: twofaenabled -> two_fa_enabled
            query = "SELECT two_fa_enabled FROM users WHERE id = ?"
            result = DatabaseManager.execute_query(query, (user_id,), fetch_one=True)
            
            return result[0] if result else False
        except Exception as e:
            app_logger.error(f"Lỗi kiểm tra trạng thái kích hoạt 2FA cho user {user_id}: {e}")
            return False

    @staticmethod
    def ensure_message_reactions_table():
        """Đảm bảo bảng message_reactions tồn tại (Chuẩn Postgres Render)"""
        try:
            # SỬA LOGIC: Dùng trực tiếp IF NOT EXISTS để tránh crash khi bảng chưa có
            # SỬA TÊN CỘT: Chuyển sang snake_case (reaction_id, message_id, user_id, sent_at)
            query = """
                CREATE TABLE IF NOT EXISTS message_reactions (
                    id SERIAL PRIMARY KEY,
                    message_id INT NOT NULL,
                    user_id INT NOT NULL,
                    emoji VARCHAR(50) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE (message_id, user_id, emoji)
                )
            """
            DatabaseManager.execute_query(query)
        except Exception as e:
            app_logger.error(f"Lỗi kiểm tra/tạo bảng message_reactions: {e}")
    
    @staticmethod
    def add_reaction(message_id, user_id, emoji):
        """Thêm cảm xúc vào tin nhắn"""
        try:
            # 1. Đảm bảo bảng đã sẵn sàng
            DatabaseManager.ensure_message_reactions_table()
            
            # 2. Thực hiện chèn biểu cảm mới
            # SỬA: Khớp 100% với tên cột gạch dưới (message_id, user_id)
            query = """
                INSERT INTO message_reactions (message_id, user_id, emoji)
                VALUES (?, ?, ?)
            """
            DatabaseManager.execute_query(query, (message_id, user_id, emoji))
            return True
        except Exception as e:
            # Giữ lại logic bắt lỗi vi phạm UNIQUE constraint rất tốt của Tới
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                app_logger.warning(f"User {user_id} đã thả emoji '{emoji}' cho tin nhắn {message_id} trước đó.")
                return False
            app_logger.error(f"Lỗi thêm biểu cảm cho tin nhắn {message_id}: {e}")
            return False
    
    @staticmethod
    def remove_reaction(message_id, user_id, emoji):
        """Xóa cảm xúc khỏi tin nhắn"""
        try:
            # SỬA: Đổi sang bảng message_reactions, cột message_id và user_id
            query = """
                DELETE FROM message_reactions
                WHERE message_id = ? AND user_id = ? AND emoji = ?
            """
            DatabaseManager.execute_query(query, (message_id, user_id, emoji))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi xóa biểu cảm của user {user_id} tại tin nhắn {message_id}: {e}")
            return False
    
    @staticmethod
    def get_message_reactions(message_id):
        """Lấy tất cả cảm xúc của một tin nhắn (Gom nhóm theo Emoji)"""
        try:
            # SỬA: Đổi tên bảng và cột theo chuẩn snake_case
            query = """
                SELECT emoji, COUNT(*) as emoji_count
                FROM message_reactions
                WHERE message_id = ?
                GROUP BY emoji
            """
            reactions = DatabaseManager.execute_query(query, (message_id,), fetch_all=True)
            
            # Trả về một dictionary dạng: {'❤️': 5, '😂': 2}
            return {row[0]: row[1] for row in reactions}
        except Exception as e:
            app_logger.error(f"Lỗi lấy danh sách gom nhóm biểu cảm cho tin nhắn {message_id}: {e}")
            return {}

    @staticmethod
    def ensure_reply_column():
        """Đảm bảo cột reply_to_message_id tồn tại trong bảng messages"""
        try:
            # SỬA: Chuyển sang chuẩn gạch dưới snake_case
            if not DatabaseManager.column_exists('messages', 'reply_to_message_id'):
                # Thêm khóa ngoại trỏ ngược về chính khóa chính (id) của bảng messages
                query = """
                    ALTER TABLE messages 
                    ADD COLUMN reply_to_message_id INT NULL 
                    REFERENCES messages(id) ON DELETE SET NULL
                """
                DatabaseManager.execute_query(query)
                app_logger.info("Đã thêm cột reply_to_message_id làm khóa ngoại vào bảng messages")
        except Exception as e:
            app_logger.error(f"Lỗi kiểm tra/thêm cột reply cho bảng messages: {e}")
    
    @staticmethod
    def get_message_for_reply(message_id):
        """Lấy thông tin tin nhắn gốc để hiển thị trong phần trả lời"""
        try:
            DatabaseManager.ensure_reply_column()
            
            # SỬA: messageid -> id, senderid -> sender_id, messagetype -> message_type, sentat -> sent_at
            query = """
                SELECT m.id, m.content, m.message_type, u.fullname as sender_name, m.sent_at
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                WHERE m.id = ?
            """
            result = DatabaseManager.execute_query(query, (message_id,), fetch_one=True)
            
            if result:
                return {
                    'message_id': result[0],
                    'content': result[1],
                    'type': result[2],
                    'sender_name': result[3],
                    # Định dạng thời gian hiển thị gọn gàng giống module tin nhắn thoại
                    'sent_at': result[4].strftime('%H:%M %d/%m/%Y') if result[4] else None
                }
                
            return None
        except Exception as e:
            app_logger.error(f"Lỗi lấy tin nhắn gốc cho phản hồi (ID: {message_id}): {e}")
            return None

    @staticmethod
    def ensure_pinned_column():
        """Đảm bảo cột is_pinned tồn tại trong bảng messages (Postgres)"""
        try:
            # SỬA: Chuyển sang chuẩn gạch dưới is_pinned
            if not DatabaseManager.column_exists('messages', 'is_pinned'):
                query = "ALTER TABLE messages ADD COLUMN is_pinned BOOLEAN DEFAULT FALSE"
                DatabaseManager.execute_query(query)
                app_logger.info("Đã thêm cột is_pinned vào bảng messages")
        except Exception as e:
            app_logger.error(f"Lỗi kiểm tra/thêm cột is_pinned cho bảng messages: {e}")
    
    @staticmethod
    def pin_message(message_id, user_id):
        """Ghim một tin nhắn trong phòng chat"""
        try:
            DatabaseManager.ensure_pinned_column()
            
            # 1. Kiểm tra sự tồn tại của tin nhắn và lấy ra người gửi (SỬA: sender_id, id)
            query = "SELECT sender_id FROM messages WHERE id = ?"
            result = DatabaseManager.execute_query(query, (message_id,), fetch_one=True)
            if not result:
                return False
            
            sender_id = result[0]
            # 2. Kiểm tra quyền hạn: Nếu không phải người gửi THÌ phải là Admin
            if sender_id != user_id:
                # Tận dụng hàm is_admin đã viết trước đó của Tới để kiểm tra nhanh
                if not DatabaseManager.is_admin(user_id):
                    app_logger.warning(f"User {user_id} không có quyền ghim tin nhắn {message_id}")
                    return False
            
            # 3. Tiến hành cập nhật trạng thái ghim (SỬA: is_pinned = TRUE)
            query = "UPDATE messages SET is_pinned = TRUE WHERE id = ?"
            DatabaseManager.execute_query(query, (message_id,))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi ghim tin nhắn {message_id}: {e}")
            return False
    
    @staticmethod
    def unpin_message(message_id, user_id):
        """Bỏ ghim một tin nhắn trong phòng chat"""
        try:
            DatabaseManager.ensure_pinned_column()
            
            # SỬA BẢO MẬT (Tùy chọn): Tới nên check quyền tương tự như hàm pin_message 
            # để đảm bảo người nhấn nút bỏ ghim phải là Admin hoặc chính chủ.
            
            # SỬA TÊN CỘT: ispinned -> is_pinned, messageid -> id
            query = "UPDATE messages SET is_pinned = FALSE WHERE id = ?"
            DatabaseManager.execute_query(query, (message_id,))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi bỏ ghim tin nhắn {message_id}: {e}")
            return False
    
    @staticmethod
    def get_pinned_messages(room_id):
        """Lấy tất cả tin nhắn đã ghim trong một phòng (Postgres Render)"""
        try:
            DatabaseManager.ensure_pinned_column()
            
            # SỬA: Thay thế toàn bộ sang chuẩn snake_case
            # QUAN TRỌNG: Sửa m.id thành m.room_id ở mệnh đề WHERE
            query = """
                SELECT m.id, m.content, m.message_type, m.sent_at, m.reply_to_message_id,
                    u.fullname as sender_name, u.id as sender_id
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                WHERE m.room_id = ? AND m.is_pinned IS TRUE AND m.is_deleted IS FALSE
                ORDER BY m.sent_at DESC
            """
            messages_raw = DatabaseManager.execute_query(query, (room_id,), fetch_all=True)
            
            # Định dạng lại dữ liệu trả về cho đồng bộ với các hàm lấy tin nhắn khác
            return [{
                'message_id': row[0],
                'content': row[1],
                'type': row[2],
                'sent_at': row[3].strftime('%H:%M %d/%m/%Y') if row[3] else '',
                'reply_to_message_id': row[4],
                'sender_name': row[5],
                'sender_id': row[6]
            } for row in messages_raw]
        except Exception as e:
            app_logger.error(f"Lỗi lấy danh sách tin nhắn ghim của phòng {room_id}: {e}")
            return []

    @staticmethod
    def ensure_mentions_table():
        """Đảm bảo bảng mentions tồn tại trong database Postgres"""
        try:
            # SỬA LOGIC: Dùng trực tiếp IF NOT EXISTS để hệ thống tự khởi tạo mượt mà lần đầu
            # SỬA TÊN CỘT: Chuyển toàn bộ sang chuẩn snake_case gạch dưới
            query = """
                CREATE TABLE IF NOT EXISTS mentions (
                    id SERIAL PRIMARY KEY,
                    message_id INT NOT NULL,
                    mentioned_id INT NOT NULL,
                    mentioning_id INT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_read BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
                    FOREIGN KEY (mentioned_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (mentioning_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """
            DatabaseManager.execute_query(query)
        except Exception as e:
            app_logger.error(f"Lỗi kiểm tra/tạo bảng mentions: {e}")
    
    @staticmethod
    def save_mentions(message_id, mentioned_user_ids, mentioning_user_id):
        """Lưu danh sách những người bị nhắc tên trong tin nhắn"""
        try:
            DatabaseManager.ensure_mentions_table()
            
            # SỬA: Đồng bộ tên cột mới (message_id, mentioned_id, mentioning_id)
            query = """
                INSERT INTO mentions (message_id, mentioned_id, mentioning_id)
                VALUES (?, ?, ?)
            """
            for mentioned_user_id in mentioned_user_ids:
                DatabaseManager.execute_query(query, (message_id, mentioned_user_id, mentioning_user_id))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi lưu danh sách mention cho tin nhắn {message_id}: {e}")
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
            
            # Tạo placeholder động (?, ?, ?) an toàn chống SQL Injection
            placeholders = ','.join(['?' for _ in mentions])
            
            # SỬA LOGIC QUAN TRỌNG: JOIN u.id = rp.user_id VÀ lọc WHERE rp.room_id = ?
            query = f"""
                SELECT DISTINCT u.id, u.username
                FROM users u
                JOIN room_participants rp ON u.id = rp.user_id
                WHERE rp.room_id = ? AND u.username IN ({placeholders})
            """
            
            params = [room_id] + mentions
            users = DatabaseManager.execute_query(query, params, fetch_all=True)
            
            # Tạo dictionary mapping để tra cứu nhanh ID từ username
            username_to_id = {user[1]: user[0] for user in users}
            mentioned_ids = [username_to_id.get(username) for username in mentions if username in username_to_id]
            
            # Loại bỏ các giá trị trùng lặp nếu một người bị tag nhiều lần trong 1 tin nhắn
            return list(set(mentioned_ids))
        except Exception as e:
            app_logger.error(f"Lỗi phân tách mention trong phòng {room_id}: {e}")
            return []
    
    @staticmethod
    def get_user_mentions(user_id):
        """Lấy tất cả các thông báo nhắc tên của một người dùng (Postgres Render)"""
        try:
            DatabaseManager.ensure_mentions_table()
            
            # SỬA: Chuyển toàn bộ tên cột/bảng sang chuẩn gạch dưới (snake_case)
            # Bổ sung alias rõ ràng cho msg.room_id để biết thông báo thuộc phòng nào
            query = """
                SELECT m.id, m.message_id, m.mentioning_id, m.created_at, m.is_read,
                    msg.content, msg.room_id, u.fullname as mentioning_fullname
                FROM mentions m
                JOIN messages msg ON m.message_id = msg.id
                JOIN users u ON m.mentioning_id = u.id
                WHERE m.mentioned_id = ?
                ORDER BY m.created_at DESC
            """
            mentions_raw = DatabaseManager.execute_query(query, (user_id,), fetch_all=True)
            
            # Trả về danh sách dạng Dict để API Controller dễ xử lý json trả về cho Frontend
            return [{
                'mention_id': row[0],
                'message_id': row[1],
                'sender_id': row[2],
                'created_at': row[3].strftime('%H:%M %d/%m/%Y') if row[3] else '',
                'is_read': row[4],
                'message_content': row[5],
                'room_id': row[6],
                'sender_name': row[7]
            } for row in mentions_raw]
        except Exception as e:
            app_logger.error(f"Lỗi lấy thông báo nhắc tên của user {user_id}: {e}")
            return []
    
    @staticmethod
    def mark_mention_as_read(mention_id):
        """Đánh dấu một thông báo nhắc tên là đã đọc"""
        try:
            DatabaseManager.ensure_mentions_table()
            
            # SỬA: isread -> is_read, mentionid -> id (Chuẩn gạch dưới snake_case)
            # Giữ nguyên giá trị TRUE chuẩn cho kiểu BOOLEAN trong PostgreSQL
            query = "UPDATE mentions SET is_read = TRUE WHERE id = ?"
            DatabaseManager.execute_query(query, (mention_id,))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi cập nhật trạng thái đã đọc cho mention {mention_id}: {e}")
            return False

    @staticmethod
    def ensure_group_avatar_column():
        """Đảm bảo cột group_avatar tồn tại trong bảng rooms (Postgres)"""
        try:
            # SỬA: Chuyển groupavatar sang chuẩn gạch dưới group_avatar
            if not DatabaseManager.column_exists('rooms', 'group_avatar'):
                query = "ALTER TABLE rooms ADD COLUMN group_avatar TEXT NULL"
                DatabaseManager.execute_query(query)
                app_logger.info("Đã thêm cột group_avatar thành công vào bảng rooms")
        except Exception as e:
            app_logger.error(f"Lỗi kiểm tra hoặc thêm cột group_avatar cho bảng rooms: {e}")

    @staticmethod
    def update_group_avatar(room_id, avatar_url):
        """Cập nhật ảnh đại diện cho phòng chat (Chuẩn Postgres Render)"""
        try:
            # Đảm bảo cột lưu trữ đã tồn tại
            DatabaseManager.ensure_group_avatar_column()
            
            # SỬA: groupavatar -> group_avatar (Chuẩn snake_case)
            query = "UPDATE rooms SET group_avatar = ? WHERE id = ?"
            DatabaseManager.execute_query(query, (avatar_url, room_id))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi cập nhật ảnh đại diện cho phòng {room_id}: {e}")
            return False

    @staticmethod
    def get_group_avatar(room_id):
        """Lấy link ảnh đại diện của phòng chat"""
        try:
            DatabaseManager.ensure_group_avatar_column()
            
            # SỬA: groupavatar -> group_avatar (Chuẩn snake_case)
            query = "SELECT group_avatar FROM rooms WHERE id = ?"
            result = DatabaseManager.execute_query(query, (room_id,), fetch_one=True)
            
            return result[0] if result and result[0] else None
        except Exception as e:
            app_logger.error(f"Lỗi lấy ảnh đại diện của phòng {room_id}: {e}")
            return None

    @staticmethod
    def ensure_muted_rooms_table():
        """Đảm bảo bảng muted_rooms tồn tại trong Postgres (Chuẩn Render)"""
        try:
            # SỬA LOGIC: Dùng IF NOT EXISTS và chuyển đổi toàn bộ sang snake_case
            # SỬA TÊN CỘT TRÙNG: id -> user_id, id -> room_id
            query = """
                CREATE TABLE IF NOT EXISTS muted_rooms (
                    id SERIAL PRIMARY KEY,
                    user_id INT NOT NULL,
                    room_id INT NOT NULL,
                    muted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
                    UNIQUE (user_id, room_id)
                )
            """
            DatabaseManager.execute_query(query)
        except Exception as e:
            app_logger.error(f"Lỗi kiểm tra/tạo bảng muted_rooms: {e}")

    @staticmethod
    def mute_room(user_id, room_id):
        """Tắt thông báo cho một phòng chat"""
        try:
            DatabaseManager.ensure_muted_rooms_table()
            
            # SỬA LOGIC: Kiểm tra sự tồn tại dựa trên cặp user_id và room_id rõ ràng
            check_query = "SELECT 1 FROM muted_rooms WHERE user_id = ? AND room_id = ?"
            exists = DatabaseManager.execute_query(check_query, (user_id, room_id), fetch_one=True)
            
            if not exists:
                insert_query = "INSERT INTO muted_rooms (user_id, room_id) VALUES (?, ?)"
                DatabaseManager.execute_query(insert_query, (user_id, room_id))
                
            return True
        except Exception as e:
            app_logger.error(f"Lỗi tắt thông báo phòng {room_id} cho user {user_id}: {e}")
            return False

    @staticmethod
    def unmute_room(user_id, room_id):
        """Bật lại thông báo cho một phòng chat (Chuẩn Postgres Render)"""
        try:
            DatabaseManager.ensure_muted_rooms_table()
            
            # SỬA: Đổi tên bảng thành muted_rooms, tên cột thành user_id và room_id rõ ràng
            query = "DELETE FROM muted_rooms WHERE user_id = ? AND room_id = ?"
            DatabaseManager.execute_query(query, (user_id, room_id))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi bật lại thông báo phòng {room_id} cho user {user_id}: {e}")
            return False

    @staticmethod
    def is_room_muted(user_id, room_id):
        """Kiểm tra trạng thái tắt thông báo của một phòng"""
        try:
            DatabaseManager.ensure_muted_rooms_table()
            
            # SỬA: Đồng bộ tên bảng và phân tách hai cột gạch dưới rõ ràng
            query = "SELECT 1 FROM muted_rooms WHERE user_id = ? AND room_id = ?"
            result = DatabaseManager.execute_query(query, (user_id, room_id), fetch_one=True)
            
            return result is not None
        except Exception as e:
            app_logger.error(f"Lỗi kiểm tra trạng thái ẩn thông báo phòng {room_id} của user {user_id}: {e}")
            return False

    @staticmethod
    def get_muted_rooms(user_id):
        """Lấy danh sách ID của tất cả các phòng đã tắt thông báo"""
        try:
            DatabaseManager.ensure_muted_rooms_table()
            
            # SỬA: Lấy rõ ràng room_id và lọc theo user_id gạch dưới
            query = "SELECT room_id FROM muted_rooms WHERE user_id = ?"
            results = DatabaseManager.execute_query(query, (user_id,), fetch_all=True)
            
            # Trả về list ID đơn giản dạng: [1, 5, 12] để dễ dàng xử lý ở Front-end
            return [r[0] for r in results]
        except Exception as e:
            app_logger.error(f"Lỗi lấy danh sách phòng tắt thông báo của user {user_id}: {e}")
            return []

    @staticmethod
    def ensure_room_roles_table():
        """Đảm bảo bảng room_roles tồn tại trong Postgres (Chuẩn Render)"""
        try:
            # SỬA LOGIC: Dùng trực tiếp IF NOT EXISTS
            # SỬA TÊN CỘT: Tránh trùng tên id, chuyển sang room_id, user_id, role_name
            query = """
                CREATE TABLE IF NOT EXISTS room_roles (
                    id SERIAL PRIMARY KEY,
                    room_id INT NOT NULL,
                    user_id INT NOT NULL,
                    role_name VARCHAR(50) DEFAULT 'Member',
                    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE (room_id, user_id)
                )
            """
            DatabaseManager.execute_query(query)
        except Exception as e:
            app_logger.error(f"Lỗi kiểm tra/tạo bảng room_roles: {e}")

    @staticmethod
    def assign_role(room_id, user_id, role):
        """Gán quyền cho người dùng trong phòng chat (Chuẩn Postgres Render)"""
        try:
            DatabaseManager.ensure_room_roles_table()
            
            # 1. Kiểm tra tính hợp lệ của quyền
            valid_roles = ['Admin', 'Moderator', 'Member']
            if role not in valid_roles:
                role = 'Member'
                
            # 2. Kiểm tra xem người dùng đã có quyền trong phòng này chưa (SỬA: room_id, user_id)
            check_query = "SELECT 1 FROM room_roles WHERE room_id = ? AND user_id = ?"
            exists = DatabaseManager.execute_query(check_query, (room_id, user_id), fetch_one=True)
            
            if exists:
                # SỬA: Cập nhật cột role_name, truyền đúng thứ tự: role, room_id, user_id
                update_query = "UPDATE room_roles SET role_name = ? WHERE room_id = ? AND user_id = ?"
                DatabaseManager.execute_query(update_query, (role, room_id, user_id))
            else:
                # SỬA: Chèn mới vào bảng với các cột rõ ràng: room_id, user_id, role_name
                insert_query = "INSERT INTO room_roles (room_id, user_id, role_name) VALUES (?, ?, ?)"
                DatabaseManager.execute_query(insert_query, (room_id, user_id, role))

            # 3. Đồng bộ tương thích ngược với bảng room_participants (nếu có cột role cũ)
            try:
                if DatabaseManager.column_exists('room_participants', 'role'):
                    sync_query = "UPDATE room_participants SET role = ? WHERE room_id = ? AND user_id = ?"
                    DatabaseManager.execute_query(sync_query, (role, room_id, user_id))
            except Exception as e:
                app_logger.warning(f"Đồng bộ quyền sang bảng room_participants thất bại (Không sao): {e}")

            return True
        except Exception as e:
            app_logger.error(f"Lỗi gán quyền {role} cho user {user_id} tại phòng {room_id}: {e}")
            return False

    @staticmethod
    def get_user_role(room_id, user_id):
        """Lấy quyền hiện tại của người dùng trong phòng chat"""
        try:
            DatabaseManager.ensure_room_roles_table()
            
            # SỬA: Tránh trùng tên cột, dùng room_id và user_id rõ ràng
            query = "SELECT role_name FROM room_roles WHERE room_id = ? AND user_id = ?"
            result = DatabaseManager.execute_query(query, (room_id, user_id), fetch_one=True)
            
            # Mặc định trả về Member nếu tài khoản chưa được ghim quyền đặc biệt
            return result[0] if result else 'Member'
        except Exception as e:
            app_logger.error(f"Lỗi lấy quyền trong phòng {room_id} của user {user_id}: {e}")
            return 'Member'

    @staticmethod
    def get_room_members_with_roles(room_id):
        """Lấy danh sách thành viên trong phòng kèm theo quyền hạn (Postgres Render)"""
        try:
            DatabaseManager.ensure_room_roles_table()
            
            # SỬA LOGIC JOIN: Kết nối u.id với rp.user_id 
            # LEFT JOIN dựa trên cặp khóa song song (room_id VÀ user_id) để tránh lệch nhóm
            query = """
                SELECT u.id, u.fullname, u.username, u.status, rr.role_name
                FROM users u
                JOIN room_participants rp ON u.id = rp.user_id
                LEFT JOIN room_roles rr ON rp.room_id = rr.room_id AND rp.user_id = rr.user_id
                WHERE rp.room_id = ?
            """
            results = DatabaseManager.execute_query(query, (room_id,), fetch_all=True)
            
            # Trả về danh sách dictionary giúp Frontend map dữ liệu lên UI cực nhanh
            return [{
                'user_id': r[0],
                'full_name': r[1],
                'username': r[2],
                'status': r[3],
                'role': r[4] if r[4] else 'Member'  # Fallback về Member rất chuẩn
            } for r in results]
        except Exception as e:
            app_logger.error(f"Lỗi lấy danh sách thành viên kèm quyền của phòng {room_id}: {e}")
            return []
    @staticmethod
    def remove_role(room_id, user_id):
        """Xóa quyền hạn đặc biệt của người dùng (Reset về Member)"""
        try:
            DatabaseManager.ensure_room_roles_table()
            
            # SỬA: Phân tách rõ ràng cột room_id và user_id gạch dưới
            query = "DELETE FROM room_roles WHERE room_id = ? AND user_id = ?"
            DatabaseManager.execute_query(query, (room_id, user_id))
            return True
        except Exception as e:
            app_logger.error(f"Lỗi hủy quyền trong phòng {room_id} của user {user_id}: {e}")
            return False

# Khởi tạo các bảng cần thiết khi chạy ứng dụng
DatabaseManager.ensure_room_participants_table()
DatabaseManager.ensure_user_auth_columns()