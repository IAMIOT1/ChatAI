# ChatAI API Documentation

## Overview

ChatAI là ứng dụng chat real-time được xây dựng với Flask và Socket.IO. API này cung cấp các endpoint để quản lý users, rooms, messages, files và các tính năng khác.

## Base URL

```
http://localhost:8888
```

## Authentication

Hầu hết các API endpoint yêu cầu authentication thông qua session. User cần đăng nhập trước khi sử dụng các API.

## Error Response Format

```json
{
    "success": false,
    "message": "Error description"
}
```

## Success Response Format

```json
{
    "success": true,
    "data": { ... }
}
```

---

## User Management APIs

### User Registration

**POST** `/register`

Đăng ký user mới.

**Request Body:**
```json
{
    "username": "string",
    "fullname": "string", 
    "email": "string",
    "password": "string",
    "confirm_password": "string"
}
```

**Response:**
```json
{
    "success": true,
    "message": "Đăng ký thành công"
}
```

### User Login

**POST** `/login`

Đăng nhập user.

**Request Body:**
```json
{
    "username": "string", // hoặc email
    "password": "string"
}
```

**Response:**
```json
{
    "success": true,
    "message": "Đăng nhập thành công"
}
```

### User Logout

**GET** `/logout`

Đăng xuất user.

**Response:**
```json
{
    "success": true,
    "message": "Đăng xuất thành công"
}
```

### Update Profile

**POST** `/update_profile`

Cập nhật thông tin user.

**Request Body (multipart/form-data):**
- `fullname`: string
- `username`: string
- `avatar`: file (optional)

**Response:**
```json
{
    "success": true,
    "message": "Cập nhật thông tin thành công"
}
```

### Upload Avatar

**POST** `/upload_avatar`

Upload avatar cho user.

**Request Body (multipart/form-data):**
- `avatar`: file

**Response:**
```json
{
    "success": true,
    "avatar_url": "/static/uploads/avatars/filename.jpg",
    "message": "Upload avatar thành công"
}
```

---

## Room Management APIs

### Get Group Rooms

**GET** `/get_group_rooms`

Lấy danh sách phòng chat nhóm của user.

**Response:**
```json
{
    "success": true,
    "rooms": [
        {
            "room_id": 1,
            "room_name": "Group Name",
            "last_message": "Last message content",
            "last_sent_at": "14:30",
            "unread_count": 5
        }
    ]
}
```

### Get Private Rooms

**GET** `/get_private_rooms`

Lấy danh sách phòng chat riêng của user.

**Response:**
```json
{
    "success": true,
    "rooms": [
        {
            "room_id": 2,
            "room_name": "private_1_2",
            "display_name": "John Doe",
            "last_message": "Last message content",
            "last_sent_at": "14:30",
            "unread_count": 2
        }
    ]
}
```

### Create Group

**POST** `/create_group`

Tạo phòng chat nhóm mới.

**Request Body:**
```json
{
    "name": "string"
}
```

**Response:**
```json
{
    "success": true,
    "room_id": 123,
    "room_name": "Group Name"
}
```

### Get Private Room

**GET** `/private_room/{user_id}`

Lấy hoặc tạo phòng chat riêng với user khác.

**Response:**
```json
{
    "success": true,
    "room_id": 456,
    "room_name": "Chat với John Doe"
}
```

### Add Group Member

**POST** `/add_group_member/{room_id}`

Thêm thành viên vào nhóm (chỉ admin).

**Request Body:**
```json
{
    "user_id": 123
}
```

**Response:**
```json
{
    "success": true,
    "message": "Đã thêm thành viên vào nhóm"
}
```

### Remove Group Member

**POST** `/remove_group_member/{room_id}`

Xóa thành viên khỏi nhóm.

**Request Body:**
```json
{
    "user_id": 123
}
```

**Response:**
```json
{
    "success": true,
    "message": "Đã xóa thành viên khỏi nhóm"
}
```

### Get Group Members

**GET** `/get_group_members/{room_id}`

Lấy danh sách thành viên nhóm.

**Response:**
```json
{
    "success": true,
    "members": [
        {
            "user_id": 1,
            "full_name": "John Doe",
            "username": "johndoe",
            "role": "Admin",
            "joined_at": "2023-01-01 10:00:00",
            "status": "Online"
        }
    ]
}
```

### Leave Group

**POST** `/leave_group/{room_id}`

Rời khỏi nhóm.

**Response:**
```json
{
    "success": true,
    "message": "Đã rời nhóm"
}
```

---

## Message Management APIs

### Send Message

**Socket.IO Event** `message`

Gửi tin nhắn real-time.

**Data:**
```json
{
    "message": "string",
    "room": 123,
    "type": "text" // text, image, file, voice
}
```

### Get Message History

**GET** `/history/{room_id}`

Lấy lịch sử tin nhắn của phòng.

**Response:**
```json
{
    "success": true,
    "messages": [
        {
            "message_id": 1,
            "senderid": 123,
            "sender_name": "John Doe",
            "content": "Hello world",
            "type": "text",
            "sent_at": "2023-01-01 10:00:00",
            "is_read": true,
            "edited_at": null,
            "is_deleted": false,
            "deleted_at": null
        }
    ]
}
```

### Edit Message

**POST** `/edit_message/{message_id}`

Chỉnh sửa tin nhắn.

**Request Body:**
```json
{
    "content": "Updated message content"
}
```

**Response:**
```json
{
    "success": true,
    "message": "Chỉnh sửa tin nhắn thành công"
}
```

### Delete Message

**POST** `/delete_message/{message_id}`

Xóa tin nhắn (soft delete).

**Response:**
```json
{
    "success": true,
    "message": "Xóa tin nhắn thành công"
}
```

### Search Messages

**GET** `/search_messages/{room_id}`

Tìm kiếm tin nhắn trong phòng.

**Query Parameters:**
- `q`: string - từ khóa tìm kiếm
- `page`: int - trang hiện tại (default: 1)
- `limit`: int - số lượng kết quả (default: 20)

**Response:**
```json
{
    "success": true,
    "messages": [...],
    "pagination": {
        "page": 1,
        "limit": 20,
        "total": 100,
        "total_pages": 5,
        "has_next": true,
        "has_prev": false
    }
}
```

### Global Search

**GET** `/global_search`

Tìm kiếm trong tất cả các phòng.

**Query Parameters:**
- `q`: string - từ khóa tìm kiếm
- `page`: int - trang hiện tại
- `limit`: int - số lượng kết quả

**Response:**
```json
{
    "success": true,
    "messages": [
        {
            "message_id": 1,
            "sender_name": "John Doe",
            "content": "Hello world",
            "sent_at": "2023-01-01 10:00:00",
            "room_id": 123,
            "room_name": "Group Chat"
        }
    ],
    "pagination": {...}
}
```

---

## File Sharing APIs

### Upload File

**POST** `/upload_file`

Upload file chia sẻ.

**Request Body (multipart/form-data):**
- `file`: file
- `room_id`: int

**Response:**
```json
{
    "success": true,
    "file_url": "/static/uploads/files/document/file.pdf",
    "filename": "document.pdf",
    "file_type": "document",
    "file_size": 1024000,
    "message": "Upload file thành công"
}
```

### Download File

**GET** `/download_file/{file_id}`

Download file đã chia sẻ.

**Response:** File download

### Send File (Socket.IO)

**Socket.IO Event** `send_file`

Gửi file real-time.

**Data:**
```json
{
    "file_data": "base64_encoded_data",
    "filename": "document.pdf",
    "file_type": "document",
    "room": 123
}
```

---

## Voice Message APIs

### Upload Voice

**POST** `/upload_voice`

Upload voice message.

**Request Body (multipart/form-data):**
- `voice`: file
- `room_id`: int

**Response:**
```json
{
    "success": true,
    "voice_url": "/static/uploads/files/voice/voice.webm",
    "filename": "voice.webm",
    "file_size": 512000,
    "message": "Upload voice message thành công"
}
```

### Get Voice Messages

**GET** `/get_voice_messages/{room_id}`

Lấy danh sách voice messages trong phòng.

**Response:**
```json
{
    "success": true,
    "voice_messages": [
        {
            "voice_id": 1,
            "filename": "voice.webm",
            "voice_url": "/static/uploads/files/voice/voice.webm",
            "duration": 30,
            "file_size": 512000,
            "created_at": "2023-01-01 10:00:00",
            "sender_name": "John Doe"
        }
    ]
}
```

### Send Voice (Socket.IO)

**Socket.IO Event** `send_voice`

Gửi voice message real-time.

**Data:**
```json
{
    "voice_data": "base64_encoded_data",
    "filename": "voice.webm",
    "duration": 30,
    "room": 123
}
```

---

## Notification APIs

### Enable Notifications

**POST** `/enable_notifications`

Bật/tắt thông báo.

**Request Body:**
```json
{
    "enabled": true
}
```

**Response:**
```json
{
    "success": true,
    "message": "Cài đặt thông báo đã được cập nhật"
}
```

### Get Notifications

**GET** `/get_notifications`

Lấy danh sách thông báo.

**Response:**
```json
{
    "success": true,
    "notifications": [
        {
            "notification_id": 1,
            "title": "Thông báo mới",
            "message": "Bạn có tin nhắn mới",
            "type": "message",
            "is_read": false,
            "created_at": "2023-01-01 10:00:00"
        }
    ]
}
```

### Mark Notification Read

**POST** `/mark_notification_read/{notification_id}`

Đánh dấu thông báo đã đọc.

**Response:**
```json
{
    "success": true
}
```

---

## Theme APIs

### Set Theme

**POST** `/set_theme`

Cài đặt theme cho user.

**Request Body:**
```json
{
    "theme": "dark" // light, dark, auto
}
```

**Response:**
```json
{
    "success": true,
    "theme": "dark",
    "message": "Đã cập nhật theme"
}
```

### Get Theme

**GET** `/get_theme`

Lấy theme hiện tại.

**Response:**
```json
{
    "theme": "dark"
}
```

### Toggle Theme

**POST** `/toggle_theme`

Chuyển đổi theme.

**Response:**
```json
{
    "success": true,
    "theme": "light",
    "message": "Đã chuyển sang light theme"
}
```

---

## 2FA Authentication APIs

### Enable 2FA

**GET/POST** `/enable_2fa`

Kích hoạt 2FA.

**Response (GET):** HTML page
**Response (POST):** QR code image

### Verify 2FA

**POST** `/verify_2fa`

Xác thực 2FA code.

**Request Body:**
```json
{
    "code": "123456"
}
```

**Response:**
```json
{
    "success": true,
    "message": "2FA đã được kích hoạt thành công"
}
```

### Disable 2FA

**POST** `/disable_2fa`

Tắt 2FA.

**Request Body:**
```json
{
    "password": "user_password",
    "code": "123456"
}
```

**Response:**
```json
{
    "success": true,
    "message": "2FA đã được tắt thành công"
}
```

### Check 2FA Status

**GET** `/check_2fa_status`

Kiểm tra trạng thái 2FA.

**Response:**
```json
{
    "enabled": true
}
```

---

## Admin APIs

### Admin Dashboard

**GET** `/admin`

Trang admin dashboard.

### Get Users

**GET** `/admin/users`

Lấy danh sách users (chỉ admin).

**Query Parameters:**
- `page`: int - trang hiện tại
- `limit`: int - số lượng kết quả

**Response:**
```json
{
    "success": true,
    "users": [
        {
            "user_id": 1,
            "full_name": "John Doe",
            "username": "johndoe",
            "email": "john@example.com",
            "status": "Online",
            "role": "User",
            "created_at": "2023-01-01 10:00:00",
            "last_login": "2023-01-01 15:30:00",
            "message_count": 150
        }
    ],
    "pagination": {...}
}
```

### Update User Role

**POST** `/admin/update_user_role/{user_id}`

Cập nhật role user (chỉ admin).

**Request Body:**
```json
{
    "role": "Admin" // User, Admin, Moderator
}
```

**Response:**
```json
{
    "success": true,
    "message": "Đã cập nhật role"
}
```

### System Stats

**GET** `/admin/system_stats`

Thống kê hệ thống (chỉ admin).

**Response:**
```json
{
    "success": true,
    "stats": {
        "total_users": 1000,
        "online_users": 50,
        "new_users_today": 10,
        "total_messages": 50000,
        "messages_today": 500,
        "total_files": 1000,
        "total_file_size": 1048576000,
        "total_rooms": 100,
        "total_groups": 50
    }
}
```

---

## Analytics APIs

### Analytics Dashboard

**GET** `/analytics`

Trang analytics dashboard.

### Analytics Overview

**GET** `/analytics/overview`

Tổng quan analytics (chỉ admin).

**Response:**
```json
{
    "success": true,
    "stats": {
        "total_users": 1000,
        "new_users_today": 10,
        "new_users_week": 50,
        "new_users_month": 200,
        "total_messages": 50000,
        "messages_today": 500,
        "messages_week": 3000,
        "messages_month": 10000,
        "total_rooms": 100,
        "total_groups": 50,
        "new_rooms_today": 5,
        "total_files": 1000,
        "files_today": 20,
        "total_file_size": 1048576000,
        "online_users": 50
    }
}
```

### User Activity Analytics

**GET** `/analytics/user_activity`

Thống kê hoạt động user (chỉ admin).

**Query Parameters:**
- `days`: int - số ngày thống kê (default: 30)

**Response:**
```json
{
    "success": true,
    "user_activity": [
        {
            "date": "2023-01-01",
            "new_users": 10
        }
    ],
    "message_activity": [
        {
            "date": "2023-01-01",
            "message_count": 500
        }
    ],
    "top_users": [
        {
            "name": "John Doe",
            "message_count": 1000
        }
    ]
}
```

### Room Stats Analytics

**GET** `/analytics/room_stats`

Thống kê phòng chat (chỉ admin).

**Query Parameters:**
- `days`: int - số ngày thống kê

**Response:**
```json
{
    "success": true,
    "top_rooms": [
        {
            "name": "General Chat",
            "message_count": 5000,
            "active_users": 50
        }
    ],
    "room_types": [
        {
            "type": "Group",
            "count": 50
        }
    ],
    "room_creation": [
        {
            "date": "2023-01-01",
            "new_rooms": 5
        }
    ]
}
```

### File Stats Analytics

**GET** `/analytics/file_stats`

Thống kê file (chỉ admin).

**Query Parameters:**
- `days`: int - số ngày thống kê

**Response:**
```json
{
    "success": true,
    "file_types": [
        {
            "type": "image",
            "count": 500,
            "total_size": 104857600
        }
    ],
    "file_uploads": [
        {
            "date": "2023-01-01",
            "file_count": 20,
            "total_size": 10485760
        }
    ],
    "top_uploaders": [
        {
            "name": "John Doe",
            "file_count": 50,
            "total_size": 104857600
        }
    ]
}
```

### Export Analytics

**GET** `/analytics/export`

Xuất dữ liệu analytics (chỉ admin).

**Query Parameters:**
- `type`: string - users, messages, rooms

**Response:** CSV file download

---

## Socket.IO Events

### Connection Events

- `connect`: Khi user kết nối
- `disconnect`: Khi user ngắt kết nối
- `join`: User tham gia phòng
- `leave`: User rời phòng

### Message Events

- `message`: Gửi tin nhắn
- `edit_message`: Chỉnh sửa tin nhắn
- `delete_message`: Xóa tin nhắn
- `typing`: User đang gõ tin nhắn

### File Events

- `send_file`: Gửi file
- `file_shared`: File đã được chia sẻ
- `file_error`: Lỗi gửi file

### Voice Events

- `send_voice`: Gửi voice message
- `voice_shared`: Voice đã được chia sẻ
- `voice_error`: Lỗi gửi voice

### Notification Events

- `new_notification`: Thông báo mới
- `join_user_room`: User tham gia room riêng

### Status Events

- `get_online_users`: Lấy danh sách user online
- `online_users_update`: Cập nhật danh sách user online

---

## Error Codes

- `400`: Bad Request - Yêu cầu không hợp lệ
- `401`: Unauthorized - Chưa đăng nhập
- `403`: Forbidden - Không có quyền truy cập
- `404`: Not Found - Không tìm thấy resource
- `500`: Internal Server Error - Lỗi server

## Rate Limiting

API có rate limiting để prevent abuse:
- Message API: 100 requests/phút
- File Upload API: 10 requests/phút
- Search API: 30 requests/phút

## File Upload Limits

- Images: 10MB
- Documents: 20MB
- Videos: 100MB
- Audio: 20MB
- Archives: 50MB

## Supported File Types

### Images
- jpg, jpeg, png, gif, webp

### Documents
- pdf, doc, docx, txt, rtf

### Videos
- mp4, avi, mov, wmv, flv

### Audio
- mp3, wav, ogg, m4a

### Archives
- zip, rar, 7z, tar, gz

---

## Version History

### v1.0.0
- Initial release
- Basic chat functionality
- User authentication
- Room management
- File sharing
- Voice messages
- 2FA authentication
- Analytics system
- Admin dashboard

---

## Support

For support and questions, please contact:
- Email: support@chatai.com
- Documentation: https://docs.chatai.com
- GitHub: https://github.com/chatai/app
