# Database Configuration Guide

## Lỗi Database Connection đã được sửa!

### Nguyên nhân lỗi:
- Thiếu file `.env` trong thư mục dự án
- Connection string được xây dựng sai logic

### Các thay đổi đã thực hiện:
1. ✅ Tạo file `.env` từ `.env.example`
2. ✅ Sửa logic connection string để xử lý đúng Trusted Connection
3. ✅ Thêm error handling chi tiết cho database operations
4. ✅ Cải thiện logging để theo dõi lỗi

### Cấu hình Database trong file `.env`:

```bash
# Database Configuration
DB_DRIVER=ODBC Driver 17 for SQL Server
DB_SERVER=IAMIOT                    # Thay bằng server SQL của bạn
DB_NAME=DNU_ChatApp                  # Thay bằng database name
DB_TRUSTED_CONNECTION=true          # true cho Windows Auth, false cho SQL Auth
DB_USER=                             # Chỉ cần khi DB_TRUSTED_CONNECTION=false
DB_PASSWORD=                         # Chỉ cần khi DB_TRUSTED_CONNECTION=false
```

### Các tùy chọn kết nối:

#### 1. Windows Authentication (Trusted Connection)
```bash
DB_SERVER=YOUR_SERVER_NAME
DB_TRUSTED_CONNECTION=true
DB_USER=
DB_PASSWORD=
```

#### 2. SQL Server Authentication
```bash
DB_SERVER=YOUR_SERVER_NAME
DB_TRUSTED_CONNECTION=false
DB_USER=your_sql_username
DB_PASSWORD=your_sql_password
```

### Kiểm tra kết nối:
1. Khởi động lại ứng dụng: `python app.py`
2. Kiểm tra logs trong thư mục `logs/`
3. Nếu vẫn lỗi, kiểm tra:
   - SQL Server đang chạy
   - ODBC Driver 17 đã được cài đặt
   - Network connection đến server

### Các lỗi thường gặp:
- **"NoneType object has no attribute 'split'"**: Đã sửa bằng cách tạo file `.env`
- **"SQL Server does not exist"**: Kiểm tra `DB_SERVER` trong `.env`
- **"Login failed"**: Kiểm tra authentication method và credentials

### Logging:
- Error logs được lưu trong `logs/chatai_YYYYMMDD.log`
- Kiểm tra log để biết chi tiết lỗi database connection
