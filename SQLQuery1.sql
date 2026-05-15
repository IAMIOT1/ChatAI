-- 1. BẢNG NGƯỜI DÙNG (Giữ nguyên của Tới)
CREATE TABLE IF NOT EXISTS users (
    userid SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL, -- Đây là nơi lưu SĐT
    fullname VARCHAR(100),
    password VARCHAR(255),
    passwordhash TEXT,
    status VARCHAR(20) DEFAULT 'Offline',
    is_public BOOLEAN DEFAULT TRUE, -- Thêm cột công khai để cho phép nhắn tin từ người lạ
    createdat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. BẢNG PHÒNG CHAT (Sửa lại tên cột room_name cho thống nhất)
CREATE TABLE IF NOT EXISTS rooms (
    roomid SERIAL PRIMARY KEY,
    room_name VARCHAR(100) UNIQUE, 
    isgroup BOOLEAN DEFAULT TRUE,
    groupavatar TEXT,
    createdat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. BẢNG KẾT BẠN (QUAN TRỌNG NHẤT CHO LOGIC MỚI)
CREATE TABLE IF NOT EXISTS friendships (
    request_id SERIAL PRIMARY KEY,
    sender_id INTEGER REFERENCES users(userid) ON DELETE CASCADE,
    receiver_id INTEGER REFERENCES users(userid) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'pending', -- 'pending' (chờ), 'accepted' (đã là bạn)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sender_id, receiver_id)
);

-- 4. BẢNG THÀNH VIÊN PHÒNG (Giữ nguyên)
CREATE TABLE IF NOT EXISTS roomparticipants (
    roomid INT NOT NULL,
    userid INT NOT NULL,
    joinedat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (roomid, userid),
    CONSTRAINT fk_room FOREIGN KEY (roomid) REFERENCES rooms(roomid) ON DELETE CASCADE,
    CONSTRAINT fk_user FOREIGN KEY (userid) REFERENCES users(userid) ON DELETE CASCADE
);

-- 5. BẢNG TIN NHẮN (Giữ nguyên)
CREATE TABLE IF NOT EXISTS messages (
    messageid SERIAL PRIMARY KEY,
    roomid INT REFERENCES rooms(roomid) ON DELETE CASCADE,
    senderid INT REFERENCES users(userid) ON DELETE CASCADE,
    content TEXT,
    sentat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    messagetype VARCHAR(20) DEFAULT 'Text',
    isread INT DEFAULT 0,
    isdeleted BOOLEAN DEFAULT FALSE
);

-- 6. DỮ LIỆU KHỞI TẠO (Sửa lỗi tên cột room_name)
INSERT INTO rooms (room_name, isgroup)
VALUES ('Phòng Chat DNU', TRUE)
ON CONFLICT (room_name) DO NOTHING;

INSERT INTO users (username, fullname, password, status)
VALUES ('aibot', 'AI Bot', 'no-password', 'Online')
ON CONFLICT (username) DO NOTHING;