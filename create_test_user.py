#!/usr/bin/env python3
"""
Script tạo tài khoản test cho ChatAI
Chạy script này để tạo tài khoản test nhanh chóng
"""

import os
import pyodbc
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
db_driver = os.environ.get('DB_DRIVER', 'ODBC Driver 17 for SQL Server')
db_server = os.environ.get('DB_SERVER', 'IAMIOT')
db_name = os.environ.get('DB_NAME', 'DNU_ChatApp')
db_trusted = os.environ.get('DB_TRUSTED_CONNECTION', 'true').lower() in ['true', '1', 'yes']
db_user = os.environ.get('DB_USER', '')
db_password = os.environ.get('DB_PASSWORD', '')

# Build connection string
conn_str = f"Driver={db_driver};Server={db_server};Database={db_name};"
if db_trusted:
    conn_str += "Trusted_Connection=yes;"
else:
    conn_str += f"UID={db_user};PWD={db_password};"
conn_str += "Encrypt=yes;TrustServerCertificate=yes;"

def create_test_user():
    """Tạo tài khoản test"""
    test_users = [
        {
            'username': 'testuser',
            'fullname': 'Test User',
            'password': '12345678',
            'email': 'test@chatai.local'
        },
        {
            'username': 'admin',
            'fullname': 'Administrator',
            'password': 'admin123',
            'email': 'admin@chatai.local'
        }
    ]
    
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        for user in test_users:
            # Kiểm tra user đã tồn tại chưa
            cursor.execute("SELECT COUNT(*) FROM Users WHERE Username = ? OR Email = ?", 
                         (user['username'], user['email']))
            if cursor.fetchone()[0] > 0:
                print(f"✅ User '{user['username']}' đã tồn tại")
                continue
            
            # Tạo user mới
            password_hash = generate_password_hash(user['password'])
            cursor.execute("""
                INSERT INTO Users (Username, FullName, Email, Password, Status, IsVerified) 
                VALUES (?, ?, ?, ?, 'Offline', 1)
            """, (user['username'], user['fullname'], user['email'], password_hash))
            
            print(f"✅ Đã tạo user '{user['username']}' với password '{user['password']}'")
        
        conn.commit()
        conn.close()
        
        print("\n🎉 Tạo tài khoản test thành công!")
        print("\n📋 Thông tin đăng nhập:")
        print("┌─────────────┬──────────────┬─────────────┬──────────────┐")
        print("│   Username  │   Password   │   Fullname  │    Email     │")
        print("├─────────────┼──────────────┼─────────────┼──────────────┤")
        for user in test_users:
            print(f"│ {user['username']:<11} │ {user['password']:<12} │ {user['fullname']:<11} │ {user['email']:<12} │")
        print("└─────────────┴──────────────┴─────────────┴──────────────┘")
        print("\n🔗 URL đăng nhập: http://localhost:8888/login")
        
    except Exception as e:
        print(f"❌ Lỗi tạo tài khoản test: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🚀 Đang tạo tài khoản test cho ChatAI...")
    print("=" * 50)
    create_test_user()
