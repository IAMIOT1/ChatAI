-- 1. Tạo bảng gốc USERS (Phải có bảng này đầu tiên)
CREATE TABLE IF NOT EXISTS users (
    userid SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    fullname VARCHAR(100),
    password VARCHAR(255),
    passwordhash TEXT,
    status VARCHAR(20) DEFAULT 'Offline',
    createdat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Tạo bảng gốc ROOMS
CREATE TABLE IF NOT EXISTS rooms (
    roomid SERIAL PRIMARY KEY,
    roomname VARCHAR(100),
    isgroup BOOLEAN DEFAULT TRUE,
    createdat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Tạo bảng trung gian ROOMPARTICIPANTS (Liên kết users và rooms)
CREATE TABLE IF NOT EXISTS roomparticipants (
    roomid INT NOT NULL,
    userid INT NOT NULL,
    joinedat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (roomid, userid),
    CONSTRAINT fk_room FOREIGN KEY (roomid) REFERENCES rooms(roomid) ON DELETE CASCADE,
    CONSTRAINT fk_user FOREIGN KEY (userid) REFERENCES users(userid) ON DELETE CASCADE
);

-- 4. Tạo bảng MESSAGES
CREATE TABLE IF NOT EXISTS messages (
    messageid SERIAL PRIMARY KEY,
    roomid INT REFERENCES rooms(roomid) ON DELETE CASCADE,
    senderid INT REFERENCES users(userid) ON DELETE CASCADE,
    content TEXT,
    sentat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    messagetype VARCHAR(20) DEFAULT 'Text'
);

-- 5. Tạo hàm lấy lịch sử Chat
CREATE OR REPLACE FUNCTION getchathistory(p_roomid INT, p_limit INT DEFAULT 100)
RETURNS TABLE (
    messageid INT,
    sendername VARCHAR,
    content TEXT,
    sentat TIMESTAMP,
    messagetype VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        m.messageid,
        u.fullname::VARCHAR,
        m.content,
        m.sentat,
        m.messagetype
    FROM messages m
    JOIN users u ON m.senderid = u.userid
    WHERE m.roomid = p_roomid
    ORDER BY m.sentat ASC
    LIMIT p_limit;
END; $$ LANGUAGE plpgsql;

-- 6. DỮ LIỆU MẪU
INSERT INTO rooms (roomname, isgroup) VALUES ('Phòng Chat DNU', TRUE) ON CONFLICT DO NOTHING;
INSERT INTO users (username, fullname, password, status) VALUES ('aibot', 'AI Bot', 'no-password', 'Online') ON CONFLICT DO NOTHING;

-- Cho AI Bot vào phòng 1 (Giả định roomid 1 vừa tạo)
INSERT INTO roomparticipants (roomid, userid)
SELECT (SELECT roomid FROM rooms LIMIT 1), (SELECT userid FROM users WHERE username = 'aibot')
ON CONFLICT DO NOTHING;