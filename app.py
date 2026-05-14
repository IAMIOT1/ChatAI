import os
import webbrowser
import secrets
import uuid
import pyodbc
import csv
import pyotp
import qrcode
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from flask_socketio import SocketIO, emit, join_room
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.contrib.facebook import make_facebook_blueprint, facebook
from datetime import datetime, timedelta
from dotenv import load_dotenv
from logger_config import app_logger
from io import BytesIO, StringIO
import database
import psycopg2
from flask import send_from_directory

# Hàm này sẽ chạy NGAY LẬP TỨC khi app khởi động
# Trong file app.py
def force_init_db():
    db_url = os.environ.get('DATABASE_URL')
    
    if not db_url:
        print("--- LỖI: Không tìm thấy DATABASE_URL ---")
        return

    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        
    # BẮT BUỘC: Thêm tham số sslmode=require cho database trên Render
    if "sslmode" not in db_url:
        if "?" in db_url:
            db_url += "&sslmode=require"
        else:
            db_url += "?sslmode=require"
    
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # SỬA LỖI ĐƯỜNG DẪN: Dùng đường dẫn tuyệt đối để Linux trên Render đọc được file
        base_dir = os.path.abspath(os.path.dirname(__file__))
        sql_file_path = os.path.join(base_dir, "SQLQuery1.sql")
        
        with open(sql_file_path, 'r', encoding='utf-8-sig') as f:
            # Đọc toàn bộ file và tách theo dấu chấm phẩy
            content = f.read()
            # Lưu ý: Không tách ở các dấu ; bên trong hàm (Function)
            # Ở đây mình tạm dùng cách chạy cả khối nếu có FUNCTION
            if "FUNCTION" in content:
                cur.execute(content)
            else:
                commands = content.split(';')
                for cmd in commands:
                    if cmd.strip():
                        cur.execute(cmd)
            
        conn.commit()
        print("--- ĐÃ KHỞI TẠO XONG TOÀN BỘ DATABASE VÀ FUNCTION ---")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"--- LỖI DB: {e} ---")

# Gọi ngay trước khi chạy app

app = Flask(__name__)
force_init_db()
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', '1871020578')
app.config.update(
    MAIL_SERVER=os.environ.get('MAIL_SERVER', 'smtp.gmail.com'),
    MAIL_PORT=int(os.environ.get('MAIL_PORT', 587)),
    MAIL_USE_TLS=os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', '1', 'yes'],
    MAIL_USE_SSL=os.environ.get('MAIL_USE_SSL', 'false').lower() in ['true', '1', 'yes'],
    MAIL_USERNAME=os.environ.get('MAIL_USERNAME'),
    MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD'),
    MAIL_DEFAULT_SENDER=os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@chatapp.local')
)
mail = Mail(app)

GOOGLE_OAUTH_CLIENT_ID = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')
FACEBOOK_OAUTH_CLIENT_ID = os.environ.get('FACEBOOK_OAUTH_CLIENT_ID')
FACEBOOK_OAUTH_CLIENT_SECRET = os.environ.get('FACEBOOK_OAUTH_CLIENT_SECRET')

google_bp = make_google_blueprint(
    client_id=GOOGLE_OAUTH_CLIENT_ID,
    client_secret=GOOGLE_OAUTH_CLIENT_SECRET,
    scope=["profile", "email"]
)
facebook_bp = make_facebook_blueprint(
    client_id=FACEBOOK_OAUTH_CLIENT_ID,
    client_secret=FACEBOOK_OAUTH_CLIENT_SECRET,
    scope=["email"]
)
app.register_blueprint(google_bp, url_prefix="/login")
app.register_blueprint(facebook_bp, url_prefix="/login")
# Cấu hình SocketIO hỗ trợ gửi dữ liệu lớn (như ảnh Base64)
socketio = SocketIO(app, cors_allowed_origins="*", max_http_buffer_size=10000000)

# Cấu hình kết nối SQL Server - Đã tối ưu cho Driver 17 và Trust Certificate
db_driver = os.environ.get('DB_DRIVER', 'ODBC Driver 17 for SQL Server')
db_server = os.environ.get('DB_SERVER', 'IAMIOT')
db_name = os.environ.get('DB_NAME', 'DNU_ChatApp')
db_trusted = os.environ.get('DB_TRUSTED_CONNECTION', 'true').lower() in ['true', '1', 'yes']
db_user = os.environ.get('DB_USER', '')
db_password = os.environ.get('DB_PASSWORD', '')

conn_str = f"Driver={db_driver};Server={db_server};Database={db_name};"

if db_trusted:
    conn_str += "Trusted_Connection=yes;"
else:
    conn_str += f"UID={db_user};PWD={db_password};"

conn_str += "Encrypt=yes;TrustServerCertificate=yes;"

ensure_room_participants_table = database.DatabaseManager.ensure_room_participants_table
ensure_user_auth_columns = database.DatabaseManager.ensure_user_auth_columns
column_exists = database.DatabaseManager.column_exists

ensure_room_participants_table()


def send_email(subject, recipients, body):
    try:
        msg = Message(subject, recipients=[recipients] if isinstance(recipients, str) else recipients)
        msg.body = body
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Lỗi gửi email: {e}")
        return False


def generate_token(length=48):
    """Generate a secure random token for email verification or password reset."""
    return secrets.token_urlsafe(length)


def validate_phone(phone):
    """Validate phone format - 10 digits"""
    import re
    pattern = r'^[0-9]{10}$'
    return re.match(pattern, phone) is not None


def validate_email(email):
    """Validate email format"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_username(username):
    """Validate username - alphanumeric and underscore, 3-30 chars"""
    import re
    pattern = r'^[a-zA-Z0-9_]{3,30}$'
    return re.match(pattern, username) is not None


def validate_password(password):
    """Validate password - min 8 chars, at least 1 letter and 1 number"""
    import re
    if len(password) < 8:
        return False
    pattern = r'^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d@$!%*#?&]{8,}$'
    return re.match(pattern, password) is not None


def get_user_attr(user, attr_name, fallback_index=None):
    """Extract a named column from a pyodbc row or tuple result."""
    if user is None:
        return None
    if hasattr(user, attr_name):
        return getattr(user, attr_name)
    if fallback_index is not None and isinstance(user, (tuple, list)) and len(user) > fallback_index:
        return user[fallback_index]
    return None


def username_exists(username):
    return database.DatabaseManager.username_exists(username)


def generate_unique_username(base):
    return database.DatabaseManager.generate_unique_username(base)


def get_user_by_email(email):
    return database.DatabaseManager.get_user_by_email(email)


def get_user_by_oauth(provider, oauth_id):
    return database.DatabaseManager.get_user_by_oauth(provider, oauth_id)


def create_oauth_user(provider, oauth_id, email, full_name):
    return database.DatabaseManager.create_oauth_user(provider, oauth_id, email, full_name)

# --- HÀM HỖ TRỢ HỆ THỐNG ---

def update_status(user_id, status):
    """Cập nhật trạng thái Online/Offline vào SQL"""
    database.DatabaseManager.update_user_status(user_id, status)




def get_user_profile(user_id):
    return database.DatabaseManager.get_user_profile(user_id)


def save_to_sql(user_id, content, msg_type='Text', room_id=1, reply_to_message_id=None):
    database.DatabaseManager.save_message(user_id, content, msg_type, room_id, reply_to_message_id)


def get_unread_counts(user_id):
    return database.DatabaseManager.get_unread_counts(user_id)


def get_group_rooms(user_id):
    return database.DatabaseManager.get_group_rooms(user_id)


def get_private_rooms(user_id):
    return database.DatabaseManager.get_private_rooms(user_id)


def create_group_room(user_id, group_name):
    return database.DatabaseManager.create_group_room(user_id, group_name)


def get_or_create_private_room(user_id, target_user_id):
    return database.DatabaseManager.get_or_create_private_room(user_id, target_user_id)

# --- ROUTES GIAO DIỆN ---

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    rooms, friends, history = [], [], []
    profile = {'full_name': '', 'username': '', 'avatar_url': ''}
    unread_counts = {}
    default_room_id = 1
    try:
        group_rooms = get_group_rooms(session['user_id'])
        private_rooms = get_private_rooms(session['user_id'])
        # Deduplicate private_rooms by other_user_id to avoid duplicate recipients
        try:
            unique_private = []
            seen_other = set()
            for pr in private_rooms:
                other_id = None
                if isinstance(pr, dict):
                    other_id = pr.get('other_user_id')
                # fallback to display_name if other_user_id missing
                if other_id is None and isinstance(pr, dict):
                    other_id = pr.get('display_name')
                if other_id not in seen_other:
                    seen_other.add(other_id)
                    unique_private.append(pr)
            private_rooms = unique_private
        except Exception:
            # if anything goes wrong, keep original list
            pass
        unread_counts = get_unread_counts(session['user_id'])
        
        # Lấy danh sách bạn bè (loại trừ bản thân)
        database.DatabaseManager.ensure_phone_column()
        query = "SELECT UserID, FullName, Status, Phone FROM Users WHERE UserID != ?"
        friends = database.DatabaseManager.execute_query(query, (session['user_id'],), fetch_all=True)
        
        default_room_id = group_rooms[0]['room_id'] if group_rooms else (private_rooms[0]['room_id'] if private_rooms else 1)
        
        # Lấy lịch sử chat cho phòng đang được chọn
        history = database.DatabaseManager.get_room_messages(default_room_id)
        
        profile = get_user_profile(session['user_id'])
        profile['is_admin'] = is_admin(session['user_id'])
    except Exception as e:
        print(f"Lỗi tải trang chủ: {e}")
        group_rooms, private_rooms, friends = [], [], []
    user_rooms = [r['room_id'] for r in group_rooms] + [r['room_id'] for r in private_rooms]
    return render_template('index.html', rooms=group_rooms, friends=friends, history=history, profile=profile, selected_room_id=default_room_id, unread_counts=unread_counts, private_rooms=private_rooms, user_rooms=user_rooms)


@app.route('/create_group', methods=['POST'])
def create_group():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})
    data = request.get_json() or {}
    group_name = data.get('name', '').strip()
    if not group_name:
        return jsonify({'success': False, 'message': 'Tên nhóm không được để trống'})
    room_id = create_group_room(session['user_id'], group_name)
    if not room_id:
        return jsonify({'success': False, 'message': 'Không tạo được nhóm'})
    return jsonify({'success': True, 'room_id': room_id, 'room_name': group_name})


@app.route('/private_room/<int:target_user_id>')
def private_room(target_user_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})
    room_data = get_or_create_private_room(session['user_id'], target_user_id)
    if not room_data:
        return jsonify({'success': False, 'message': 'Không tạo được phòng chat riêng'})
    room_id, room_name = room_data
    return jsonify({'success': True, 'room_id': room_id, 'room_name': room_name})


@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    try:
        results = database.DatabaseManager.search(q, session['user_id'])
        return jsonify(results)
    except Exception as e:
        print(f"Lỗi tìm kiếm: {e}")
        return jsonify([])


@app.route('/history/<int:room_id>')
def history(room_id):
    try:
        messages = database.DatabaseManager.get_room_messages(room_id)
        return jsonify(messages)
    except Exception as e:
        app_logger.error(f"Lỗi tải lịch sử: {e}")
        return jsonify([])


@app.route('/mark_read/<int:room_id>', methods=['POST'])
def mark_read(room_id):
    if 'user_id' not in session:
        return jsonify({'success': False})
    try:
        database.DatabaseManager.mark_messages_as_read(room_id, session['user_id'])
        return jsonify({'success': True})
    except Exception as e:
        print(f"Lỗi mark_read: {e}")
        return jsonify({'success': False})



# Cấu hình upload
UPLOAD_FOLDER = 'static/uploads/avatars'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_uploaded_file_size(file):
    try:
        # Try content_length first
        if hasattr(file, 'content_length') and file.content_length:
            return int(file.content_length)
        # Fallback to stream tell/seek
        stream = getattr(file, 'stream', None)
        if stream:
            cur = stream.tell()
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(cur)
            return int(size)
    except Exception:
        pass
    return None


def validate_image_upload(file, max_size=2 * 1024 * 1024):
    """Validate uploaded image file.
    Returns (valid: bool, message_or_size)
    """
    if not file:
        return False, 'Không có file được chọn'

    filename = getattr(file, 'filename', '') or ''
    if filename == '':
        return False, 'Không có file được chọn'

    # Check extension
    if not allowed_file(filename):
        return False, 'Chỉ chấp nhận file ảnh (PNG, JPG, JPEG, GIF, WEBP)'

    # Check mime type
    content_type = getattr(file, 'content_type', '') or ''
    if not content_type.startswith('image/'):
        return False, 'Chỉ chấp nhận file ảnh'

    # Check size
    size = get_uploaded_file_size(file)
    if size is not None and size > max_size:
        return False, f'File quá lớn. Kích thước tối đa: {max_size // (1024*1024)}MB'

    return True, size

@app.route('/upload_avatar', methods=['POST'])
def upload_avatar():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    if 'avatar' not in request.files:
        return jsonify({'success': False, 'message': 'Không có file được chọn'})

    file = request.files['avatar']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Không có file được chọn'})

    # Server-side validation
    valid, info = validate_image_upload(file, max_size=2 * 1024 * 1024)
    if not valid:
        return jsonify({'success': False, 'message': info})

    try:
        # Tạo tên file unique
        filename = secure_filename(file.filename)
        file_extension = filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}"

        # Lưu file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(file_path)

        # Cập nhật database
        avatar_url = f"/static/uploads/avatars/{unique_filename}"
        database.DatabaseManager.update_user_profile(session['user_id'], session.get('user_name', ''), session.get('username', ''), avatar_url)

        app_logger.info(f"User {session['user_id']} uploaded avatar: {avatar_url}")

        return jsonify({
            'success': True,
            'avatar_url': avatar_url,
            'message': 'Cập nhật avatar thành công'
        })

    except Exception as e:
        app_logger.error(f"Lỗi upload avatar: {e}")
        return jsonify({'success': False, 'message': f'Lỗi upload: {str(e)}'})

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    fullname = request.form.get('fullname', '').strip()
    username = request.form.get('username', '').strip()
    phone = request.form.get('phone', '').strip()
    avatar_url = None

    try:
        if 'avatar' in request.files:
            file = request.files['avatar']
            # Validate uploaded avatar
            valid, info = validate_image_upload(file, max_size=2 * 1024 * 1024)
            if valid:
                # Create a unique filename
                filename = secure_filename(file.filename)
                file_extension = filename.rsplit('.', 1)[1].lower()
                unique_filename = f"{uuid.uuid4().hex}.{file_extension}"

                # Save the file
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(file_path)

                avatar_url = f"/static/uploads/avatars/{unique_filename}"
                app_logger.info(f"User {session['user_id']} uploaded avatar: {avatar_url}")
            else:
                flash(info)
        else:
            # No avatar file uploaded
            pass

        # Update user profile information
        user = User.query.get(session['user_id'])
        if user:
            user.fullname = fullname
            user.username = username
            if phone:
                user.phone = phone
            if avatar_url:
                user.avatar_url = avatar_url
            db.session.commit()

        return redirect(url_for('profile'))
    except Exception as e:
        app_logger.error(f"Error updating profile: {str(e)}")
        flash("An error occurred while updating profile. Please try again.")
        return redirect(url_for('profile'))

        # Cập nhật thông tin cơ bản
        database.DatabaseManager.update_user_profile(session['user_id'], fullname, username, avatar_url, phone)

        # Cập nhật session
        session['user_name'] = fullname
        flash("Cập nhật thông tin cá nhân thành công.")

    except Exception as e:
        app_logger.error(f"Lỗi cập nhật profile: {e}")
        flash(f"Lỗi cập nhật thông tin: {str(e)}")
    return redirect(url_for('index'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form['username'].strip()
        password = request.form['password']

        try:
            # Try to get user by username first
            user = database.DatabaseManager.get_user_by_username(identifier)
            
            # If not found, try by phone
            if not user:
                user = database.DatabaseManager.get_user_by_phone(identifier)

            if user:
                # Handle both tuple and Row object
                if hasattr(user, 'UserID'):  # Row object
                    user_id = user.UserID
                    full_name = user.FullName
                    password_hash = user.Password
                else:  # Tuple
                    user_id = user[0]
                    password_hash = user[2]
                    full_name = user[3]
                
                # Debug log
                app_logger.info(f"Login attempt: user_id={user_id}, password_hash={password_hash[:20] if password_hash else None}..., input_password={password[:10]}...")
                
                # Kiểm tra password hash - thử cả 2 cách
                password_valid = False
                if password_hash:
                    # Luôn thử check_password_hash trước
                    try:
                        password_valid = check_password_hash(password_hash, password)
                        app_logger.info(f"Password check (hashed): {password_valid}")
                    except Exception as e:
                        app_logger.warning(f"Hashed check failed: {e}, trying plain text")
                        # Nếu hash check fail, thử plain text
                        password_valid = (password_hash == password)
                        app_logger.info(f"Password check (plain): {password_valid}")
                else:
                    app_logger.warning("Password hash is None or empty")

                if password_valid:
                    # Bỏ qua kiểm tra xác thực email - cho phép đăng nhập ngay
                    session['user_id'] = user_id
                    session['user_name'] = full_name
                    update_status(user_id, 'Online')
                    return redirect(url_for('index'))

            flash("Sai tài khoản hoặc mật khẩu!")
        except pyodbc.Error as e:
            app_logger.error(f"Lỗi kết nối database khi đăng nhập: {e}")
            flash("Lỗi kết nối database. Vui lòng thử lại sau.")
        except Exception as e:
            app_logger.error(f"Lỗi đăng nhập: {e}")
            flash(f"Lỗi đăng nhập: {str(e)}")
    return render_template('login.html', show_register=False)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        fullname = request.form['fullname'].strip()
        phone = request.form['phone'].strip()
        password = request.form['password']
        confirm_password = request.form.get('confirm_password', '')

        # Input validation
        if not validate_username(username):
            flash('Tên đăng nhập phải từ 3-30 ký tự, chỉ chứa chữ cái, số và dấu gạch dưới.')
            return render_template('login.html', show_register=True)

        if not fullname or len(fullname) < 2:
            flash('Họ và tên không được để trống và phải có ít nhất 2 ký tự.')
            return render_template('login.html', show_register=True)

        if not validate_phone(phone):
            flash('Số điện thoại không hợp lệ (phải 10 số).')
            return render_template('login.html', show_register=True)

        if not validate_password(password):
            flash('Mật khẩu phải có ít nhất 8 ký tự, bao gồm chữ và số.')
            return render_template('login.html', show_register=True)

        if password != confirm_password:
            flash('Mật khẩu xác nhận không khớp.')
            return render_template('login.html', show_register=True)

        try:
            if database.DatabaseManager.check_user_exists(username, phone):
                flash('Tên đăng nhập hoặc số điện thoại đã được sử dụng. Vui lòng chọn khác.')
                return render_template('login.html', show_register=True)
            
            # Đăng ký với IsVerified = 1 (bỏ qua xác thực)
            database.DatabaseManager.register_user(username, fullname, phone, password, verification_token=None, is_verified=True)
            
            flash('Đăng ký thành công! Bạn có thể đăng nhập ngay.')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"Lỗi đăng ký: {e}")
    return render_template('login.html', show_register=True)

@app.route('/verify/<token>')
def verify_email(token):
    try:
        success = database.DatabaseManager.verify_email_token(token)
        if not success:
            flash('Liên kết xác thực không hợp lệ hoặc đã hết hạn.')
        else:
            flash('Xác thực email thành công. Bạn có thể đăng nhập ngay bây giờ.')
    except Exception as e:
        flash(f"Lỗi xác thực email: {e}")
    return redirect(url_for('login'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        user = get_user_by_email(email)
        if user:
            token = generate_token()
            expires_at = datetime.now() + timedelta(hours=2)
            try:
                database.DatabaseManager.set_password_reset_token(email, token, expires_at)
                reset_url = url_for('reset_password', token=token, _external=True)
                send_email(
                    'Yêu cầu đặt lại mật khẩu ChatAI',
                    email,
                    f'Xin chào {get_user_attr(user, "FullName", 3)},\n\nNhấp vào liên kết sau để đặt lại mật khẩu của bạn:\n{reset_url}\n\nLiên kết có hiệu lực trong 2 giờ.'
                )
            except Exception as e:
                print(f"Lỗi lưu token reset: {e}")
        flash('Nếu email tồn tại trong hệ thống, hướng dẫn thay đổi mật khẩu đã được gửi.')
    return render_template('forgot_password.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if request.method == 'POST':
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if password != confirm_password:
            flash('Mật khẩu xác nhận không khớp.')
            return render_template('reset_password.html', token=token)
        try:
            success = database.DatabaseManager.reset_password_with_token(token, password)
            if not success:
                flash('Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.')
                return redirect(url_for('login'))
            flash('Đặt lại mật khẩu thành công. Bạn có thể đăng nhập.')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"Lỗi đặt lại mật khẩu: {e}")
    return render_template('reset_password.html', token=token)





@app.route('/login/facebook/authorized')
def facebook_authorized():
    if not facebook.authorized:
        flash('Không thể xác thực Facebook.')
        return redirect(url_for('login'))

    try:
        resp = facebook.get('/me?fields=id,name,email')
        if not resp.ok:
            flash('Không thể xác thực Facebook.')
            return redirect(url_for('login'))

        info = resp.json()
        oauth_id = str(info.get('id'))
        email = info.get('email')
        fullname = info.get('name') or (email.split('@')[0] if email else 'Facebook User')

        app_logger.info(f"Facebook OAuth success: {fullname} ({email})")

        user = get_user_by_oauth('facebook', oauth_id)
        if not user:
            user = get_user_by_email(email) if email else None
            if user:
                try:
                    database.DatabaseManager.update_user_oauth(email, 'facebook', oauth_id)
                    user = get_user_by_email(email)
                    app_logger.info(f"Updated existing user with Facebook OAuth: {email}")
                except Exception as e:
                    app_logger.error(f"Lỗi cập nhật OAuth Facebook: {e}")
            else:
                user = create_oauth_user('facebook', oauth_id, email, fullname)
                if user:
                    app_logger.info(f"Created new user with Facebook OAuth: {email}")

        if user:
            session['user_id'] = int(get_user_attr(user, 'UserID', 0))
            session['user_name'] = get_user_attr(user, 'FullName', 1)
            update_status(session['user_id'], 'Online')
            flash(f'Chào mừng {get_user_attr(user, "FullName", 1)} đã đăng nhập bằng Facebook!')
            return redirect(url_for('index'))

        flash('Không thể đăng nhập bằng Facebook.')
    except Exception as e:
        app_logger.error(f"Lỗi OAuth Facebook: {e}")
        flash(f'Lỗi đăng nhập Facebook: {str(e)}')

    return redirect(url_for('login'))


@app.route('/login/google/authorized')
def google_authorized():
    if not google.authorized:
        flash('Không thể xác thực Google.')
        return redirect(url_for('login'))

    try:
        resp = google.get('/oauth2/v2/userinfo')
        if not resp.ok:
            flash('Không thể xác thực Google.')
            return redirect(url_for('login'))

        info = resp.json()
        oauth_id = str(info.get('id'))
        email = info.get('email')
        fullname = info.get('name') or email.split('@')[0]

        app_logger.info(f"Google OAuth success: {fullname} ({email})")

        user = get_user_by_oauth('google', oauth_id)
        if not user:
            user = get_user_by_email(email)
            if user:
                try:
                    database.DatabaseManager.update_user_oauth(email, 'google', oauth_id)
                    user = get_user_by_email(email)
                    app_logger.info(f"Updated existing user with Google OAuth: {email}")
                except Exception as e:
                    app_logger.error(f"Lỗi cập nhật OAuth Google: {e}")
            else:
                user = create_oauth_user('google', oauth_id, email, fullname)
                if user:
                    app_logger.info(f"Created new user with Google OAuth: {email}")

        if user:
            session['user_id'] = int(get_user_attr(user, 'UserID', 0))
            session['user_name'] = get_user_attr(user, 'FullName', 1)
            update_status(session['user_id'], 'Online')
            flash(f'Chào mừng {get_user_attr(user, "FullName", 1)} đã đăng nhập bằng Google!')
            return redirect(url_for('index'))

        flash('Không thể đăng nhập bằng Google.')
    except Exception as e:
        app_logger.error(f"Lỗi OAuth Google: {e}")
        flash(f'Lỗi đăng nhập Google: {str(e)}')

    return redirect(url_for('login'))


@app.route('/logout')
def logout():
    if 'user_id' in session:
        update_status(session['user_id'], 'Offline')
    session.clear()
    return redirect(url_for('login'))

# --- XỬ LÝ CHAT REALTIME (SOCKET.IO) ---

@socketio.on('message')
def handle_message(data):
    room = data.get('room', 1)
    current_user_id = session.get('user_id')
    message_text = data.get('msg', '')
    message_type = data.get('type', 'Text')
    reply_to_message_id = data.get('reply_to_message_id')
    
    save_to_sql(current_user_id, message_text, msg_type=message_type, room_id=room, reply_to_message_id=reply_to_message_id)
    sent_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    payload = {**data, 'sent_at': sent_at}
    
    # Add reply information to payload if this is a reply
    if reply_to_message_id:
        reply_info = database.DatabaseManager.get_message_for_reply(reply_to_message_id)
        if reply_info:
            payload['reply_to_message_id'] = reply_to_message_id
            payload['reply_to_sender_name'] = reply_info['sender_name']
            payload['reply_to_content'] = reply_info['content'][:50] + '...' if len(reply_info['content']) > 50 else reply_info['content']
    
    # Parse and save mentions
    if message_type == 'Text':
        mentioned_user_ids = database.DatabaseManager.parse_mentions(message_text, room)
        if mentioned_user_ids:
            # Get the message ID that was just saved
            query = "SELECT TOP 1 MessageID FROM Messages WHERE RoomID = ? AND SenderID = ? ORDER BY SentAt DESC"
            message_result = database.DatabaseManager.execute_query(query, (room, current_user_id), fetch_one=True)
            if message_result:
                message_id = message_result[0]
                database.DatabaseManager.save_mentions(message_id, mentioned_user_ids, current_user_id)
                
                # Notify mentioned users
                for mentioned_user_id in mentioned_user_ids:
                    emit('user_mentioned', {
                        'message_id': message_id,
                        'mentioning_user': session.get('user_name'),
                        'content': message_text,
                        'room_id': room,
                        'mentioned_user_id': mentioned_user_id
                    }, room=room)
    
    emit('response', payload, room=room)

    # Send email notifications to users who have enabled email notifications
    try:
        users_to_notify = database.DatabaseManager.get_users_with_email_notification_enabled(room)
        sender_name = session.get('user_name', 'Unknown')
        
        for user in users_to_notify:
            if user['user_id'] != current_user_id:  # Don't send to sender
                email_subject = f"Tin nhắn mới từ {sender_name}"
                email_body = f"""
Xin chào {user['full_name']},

Bạn có tin nhắn mới từ {sender_name}:

{message_text[:200]}{'...' if len(message_text) > 200 else ''}

Đăng nhập vào ChatAI để xem tin nhắn đầy đủ.

---
Đây là email tự động, vui lòng không trả lời.
"""
                send_email(email_subject, user['email'], email_body)
                app_logger.info(f"Email notification sent to {user['email']}")
    except Exception as e:
        app_logger.error(f"Lỗi gửi email notification: {e}")

    if message_type == 'Text' and "@ai" in message_text.lower():
        bot_msg = f"Chào {data.get('user', 'bạn')}, tôi là AI của DNU. Tin nhắn của bạn đã được lưu!"
        save_to_sql(current_user_id, bot_msg, msg_type='Text', room_id=room)
        emit('response', {'user': 'AI Bot', 'msg': bot_msg, 'room': room, 'type': 'Text', 'sent_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, room=room)


@socketio.on('join')
def handle_join(data):
    """Handle user joining a room"""
    room = data.get('room')
    user = data.get('user')
    join_room(room)
    emit('response', {'user': 'System', 'msg': f'{user} đã tham gia phòng', 'room': room}, room=room)


# WebRTC Signaling Events
@socketio.on('video_call_offer')
def handle_video_call_offer(data):
    """Handle WebRTC video call offer"""
    room = data.get('room')
    caller = data.get('caller')
    callee = data.get('callee')
    offer = data.get('offer')
    
    emit('video_call_offer', {
        'caller': caller,
        'callee': callee,
        'offer': offer,
        'room': room
    }, room=room)


@socketio.on('video_call_answer')
def handle_video_call_answer(data):
    """Handle WebRTC video call answer"""
    room = data.get('room')
    caller = data.get('caller')
    callee = data.get('callee')
    answer = data.get('answer')
    
    emit('video_call_answer', {
        'caller': caller,
        'callee': callee,
        'answer': answer
    }, room=room)


@socketio.on('ice_candidate')
def handle_ice_candidate(data):
    """Handle WebRTC ICE candidate"""
    room = data.get('room')
    target_user = data.get('target_user')
    candidate = data.get('candidate')
    
    emit('ice_candidate', {
        'candidate': candidate,
        'target_user': target_user
    }, room=room)


@socketio.on('video_call_end')
def handle_video_call_end(data):
    """Handle video call end"""
    room = data.get('room')
    caller = data.get('caller')
    callee = data.get('callee')
    
    emit('video_call_end', {
        'caller': caller,
        'callee': callee
    }, room=room)


@socketio.on('typing')
def handle_typing(data):
    """Thông báo người dùng đang gõ phím"""
    room = data.get('room', None)
    if room is not None:
        emit('display_typing', data, room=room, include_self=False)
    else:
        emit('display_typing', data, broadcast=True, include_self=False)


@socketio.on('send_image')
def handle_image(data):
    current_user_id = session.get('user_id')
    room = data.get('room', 1)
    save_to_sql(current_user_id, data['image_data'], msg_type='Image', room_id=room)
    emit('response', {'user': data.get('user'), 'room': room, 'type': 'Image', 'image_data': data['image_data'], 'sent_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, room=room)


@socketio.on('connect')
def handle_connect():
    """Khi user kết nối"""
    if 'user_id' in session:
        user_id = session['user_id']
        user_name = session.get('user_name', 'Unknown')

        # Cập nhật trạng thái online trong database
        update_status(user_id, 'Online')

        # Thông báo cho các user khác rằng user này online
        emit('user_status_changed', {
            'user_id': user_id,
            'user_name': user_name,
            'status': 'Online'
        }, broadcast=True, include_self=False)

        app_logger.info(f"User {user_name} ({user_id}) connected")


@socketio.on('disconnect')
def handle_disconnect():
    """Khi user ngắt kết nối"""
    if 'user_id' in session:
        user_id = session['user_id']
        user_name = session.get('user_name', 'Unknown')

        # Cập nhật trạng thái offline trong database
        update_status(user_id, 'Offline')

        # Thông báo cho các user khác rằng user này offline
        emit('user_status_changed', {
            'user_id': user_id,
            'user_name': user_name,
            'status': 'Offline'
        }, broadcast=True, include_self=False)

        app_logger.info(f"User {user_name} ({user_id}) disconnected")


@socketio.on('get_online_users')
def handle_get_online_users():
    """Lấy danh sách user online"""
    try:
        online_users = database.DatabaseManager.get_online_users()
        emit('online_users_list', online_users)
    except Exception as e:
        app_logger.error(f"Lỗi lấy danh sách online users: {e}")
        emit('online_users_list', [])


@socketio.on('edit_message')
def handle_edit_message(data):
    """Xử lý edit tin nhắn"""
    try:
        message_id = data.get('message_id')
        new_content = data.get('new_content', '').strip()
        user_id = session.get('user_id')

        if not message_id or not new_content or not user_id:
            emit('edit_error', {'message': 'Dữ liệu không hợp lệ'})
            return

        success = database.DatabaseManager.edit_message(message_id, user_id, new_content)
        
        if not success:
            emit('edit_error', {'message': 'Bạn không có quyền sửa tin nhắn này'})
            return

        # Get room_id for notification
        query = "SELECT RoomID FROM Messages WHERE MessageID = ?"
        message = database.DatabaseManager.execute_query(query, (message_id,), fetch_one=True)
        room_id = message[0] if message else None

        # Thông báo cho room về message đã được edit
        if room_id:
            emit('message_edited', {
                'message_id': message_id,
                'content': new_content,
                'edited_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'room_id': room_id
            }, room=room_id)

        app_logger.info(f"User {user_id} edited message {message_id}")

    except Exception as e:
        app_logger.error(f"Lỗi edit message: {e}")
        emit('edit_error', {'message': f'Lỗi sửa tin nhắn: {str(e)}'})


@socketio.on('delete_message')
def handle_delete_message(data):
    """Xử lý xóa tin nhắn"""
    try:
        message_id = data.get('message_id')
        user_id = session.get('user_id')

        if not message_id or not user_id:
            emit('delete_error', {'message': 'Dữ liệu không hợp lệ'})
            return

        success = database.DatabaseManager.delete_message(message_id, user_id)
        
        if not success:
            emit('delete_error', {'message': 'Bạn không có quyền xóa tin nhắn này'})
            return

        # Get room_id for notification
        query = "SELECT RoomID FROM Messages WHERE MessageID = ?"
        message = database.DatabaseManager.execute_query(query, (message_id,), fetch_one=True)
        room_id = message[0] if message else None

        # Thông báo cho room về message đã được xóa
        if room_id:
            emit('message_deleted', {
                'message_id': message_id,
                'room_id': room_id
            }, room=room_id)

        app_logger.info(f"User {user_id} deleted message {message_id}")

    except Exception as e:
        app_logger.error(f"Lỗi delete message: {e}")
        emit('delete_error', {'message': f'Lỗi xóa tin nhắn: {str(e)}'})


@socketio.on('add_reaction')
def handle_add_reaction(data):
    """Xử lý thêm reaction"""
    try:
        message_id = data.get('message_id')
        emoji = data.get('emoji', '')
        user_id = session.get('user_id')

        if not message_id or not emoji or not user_id:
            emit('reaction_error', {'message': 'Dữ liệu không hợp lệ'})
            return

        success = database.DatabaseManager.add_reaction(message_id, user_id, emoji)
        
        if success:
            # Get room_id for notification
            query = "SELECT RoomID FROM Messages WHERE MessageID = ?"
            message = database.DatabaseManager.execute_query(query, (message_id,), fetch_one=True)
            room_id = message[0] if message else None

            # Get reactions count
            reactions = database.DatabaseManager.get_message_reactions(message_id)

            if room_id:
                emit('reaction_added', {
                    'message_id': message_id,
                    'emoji': emoji,
                    'reactions': reactions,
                    'room_id': room_id
                }, room=room_id)

            app_logger.info(f"User {user_id} added reaction {emoji} to message {message_id}")
        else:
            emit('reaction_error', {'message': 'Bạn đã reaction với emoji này rồi'})

    except Exception as e:
        app_logger.error(f"Lỗi add reaction: {e}")
        emit('reaction_error', {'message': f'Lỗi: {str(e)}'})


@socketio.on('remove_reaction')
def handle_remove_reaction(data):
    """Xử lý xóa reaction"""
    try:
        message_id = data.get('message_id')
        emoji = data.get('emoji', '')
        user_id = session.get('user_id')

        if not message_id or not emoji or not user_id:
            emit('reaction_error', {'message': 'Dữ liệu không hợp lệ'})
            return

        success = database.DatabaseManager.remove_reaction(message_id, user_id, emoji)
        
        if success:
            # Get room_id for notification
            query = "SELECT RoomID FROM Messages WHERE MessageID = ?"
            message = database.DatabaseManager.execute_query(query, (message_id,), fetch_one=True)
            room_id = message[0] if message else None

            # Get reactions count
            reactions = database.DatabaseManager.get_message_reactions(message_id)

            if room_id:
                emit('reaction_removed', {
                    'message_id': message_id,
                    'emoji': emoji,
                    'reactions': reactions,
                    'room_id': room_id
                }, room=room_id)

            app_logger.info(f"User {user_id} removed reaction {emoji} from message {message_id}")

    except Exception as e:
        app_logger.error(f"Lỗi remove reaction: {e}")
        emit('reaction_error', {'message': f'Lỗi: {str(e)}'})


@socketio.on('pin_message')
def handle_pin_message(data):
    """Xử lý pin tin nhắn"""
    try:
        message_id = data.get('message_id')
        user_id = session.get('user_id')

        if not message_id or not user_id:
            emit('pin_error', {'message': 'Dữ liệu không hợp lệ'})
            return

        success = database.DatabaseManager.pin_message(message_id, user_id)
        
        if success:
            # Get room_id for notification
            query = "SELECT RoomID FROM Messages WHERE MessageID = ?"
            message = database.DatabaseManager.execute_query(query, (message_id,), fetch_one=True)
            room_id = message[0] if message else None

            # Get pinned messages for the room
            if room_id:
                pinned_messages = database.DatabaseManager.get_pinned_messages(room_id)
                emit('message_pinned', {
                    'message_id': message_id,
                    'room_id': room_id,
                    'pinned_messages': pinned_messages
                }, room=room_id)

            app_logger.info(f"User {user_id} pinned message {message_id}")
        else:
            emit('pin_error', {'message': 'Lỗi pin tin nhắn'})

    except Exception as e:
        app_logger.error(f"Lỗi pin message: {e}")
        emit('pin_error', {'message': f'Lỗi: {str(e)}'})


@socketio.on('forward_message')
def handle_forward_message(data):
    """Xử lý forward tin nhắn"""
    try:
        message_id = data.get('message_id')
        target_room_id = data.get('target_room_id')
        user_id = session.get('user_id')
        user_name = session.get('user_name', 'Unknown')

        if not message_id or not target_room_id or not user_id:
            emit('forward_error', {'message': 'Dữ liệu không hợp lệ'})
            return

        # Check if user is member of target room
        if not database.DatabaseManager.is_room_member(target_room_id, user_id):
            emit('forward_error', {'message': 'Bạn không phải thành viên của phòng này'})
            return

        # Forward message
        success = database.DatabaseManager.save_forwarded_message(user_id, message_id, target_room_id)

        if success:
            # Get original message info
            query = """
                SELECT Content, MessageType, u.FullName as OriginalSender
                FROM Messages m
                JOIN Users u ON m.SenderID = u.UserID
                WHERE m.MessageID = ?
            """
            original = database.DatabaseManager.execute_query(query, (message_id,), fetch_one=True)

            if original:
                emit('message_forwarded', {
                    'message_id': message_id,
                    'target_room_id': target_room_id,
                    'content': original[0],
                    'message_type': original[1],
                    'original_sender': original[2],
                    'forwarded_by': user_name,
                    'sent_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }, room=target_room_id)

            app_logger.info(f"User {user_name} forwarded message {message_id} to room {target_room_id}")
        else:
            emit('forward_error', {'message': 'Lỗi forward tin nhắn'})

    except Exception as e:
        app_logger.error(f"Lỗi forward message: {e}")
        emit('forward_error', {'message': f'Lỗi: {str(e)}'})


@socketio.on('unpin_message')
def handle_unpin_message(data):
    """Xử lý unpin tin nhắn"""
    try:
        message_id = data.get('message_id')
        user_id = session.get('user_id')

        if not message_id or not user_id:
            emit('pin_error', {'message': 'Dữ liệu không hợp lệ'})
            return

        success = database.DatabaseManager.unpin_message(message_id, user_id)
        
        if success:
            # Get room_id for notification
            query = "SELECT RoomID FROM Messages WHERE MessageID = ?"
            message = database.DatabaseManager.execute_query(query, (message_id,), fetch_one=True)
            room_id = message[0] if message else None

            # Get pinned messages for the room
            if room_id:
                pinned_messages = database.DatabaseManager.get_pinned_messages(room_id)
                emit('message_unpinned', {
                    'message_id': message_id,
                    'room_id': room_id,
                    'pinned_messages': pinned_messages
                }, room=room_id)

            app_logger.info(f"User {user_id} unpinned message {message_id}")

    except Exception as e:
        app_logger.error(f"Lỗi unpin message: {e}")
        emit('pin_error', {'message': f'Lỗi: {str(e)}'})


@app.route('/edit_message/<int:message_id>', methods=['POST'])
def edit_message_route(message_id):
    """Route cho edit message (backup method)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        data = request.get_json()
        new_content = data.get('content', '').strip()

        if not new_content:
            return jsonify({'success': False, 'message': 'Nội dung không được để trống'})

        success = database.DatabaseManager.edit_message(message_id, session['user_id'], new_content)
        
        if success:
            return jsonify({'success': True, 'message': 'Sửa tin nhắn thành công'})
        else:
            return jsonify({'success': False, 'message': 'Bạn không có quyền sửa tin nhắn này'})

    except Exception as e:
        app_logger.error(f"Lỗi edit message route: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@app.route('/delete_message/<int:message_id>', methods=['POST'])
def delete_message_route(message_id):
    """Route cho delete message (backup method)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        success = database.DatabaseManager.delete_message(message_id, session['user_id'])
        
        if success:
            return jsonify({'success': True, 'message': 'Xóa tin nhắn thành công'})
        else:
            return jsonify({'success': False, 'message': 'Bạn không có quyền xóa tin nhắn này'})

    except Exception as e:
        app_logger.error(f"Lỗi delete message route: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@app.route('/get_pinned_messages/<int:room_id>')
def get_pinned_messages(room_id):
    """Get pinned messages for a room"""
    try:
        pinned_messages = database.DatabaseManager.get_pinned_messages(room_id)
        return jsonify({'success': True, 'pinned_messages': pinned_messages})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e), 'pinned_messages': []})


@app.route('/get_room_users/<int:room_id>')
def get_room_users(room_id):
    """Get users in a room for mention suggestions"""
    try:
        query = """
            SELECT DISTINCT u.UserID, u.Username, u.FullName
            FROM Users u
            JOIN RoomParticipants rp ON u.UserID = rp.UserID
            WHERE rp.RoomID = ? AND u.Status = 'Online'
        """
        users = database.DatabaseManager.execute_query(query, (room_id,), fetch_all=True)
        user_list = [{'user_id': u[0], 'username': u[1], 'full_name': u[2]} for u in users]
        return jsonify({'success': True, 'users': user_list})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e), 'users': []})


@app.route('/upload_group_avatar/<int:room_id>', methods=['POST'])
def upload_group_avatar(room_id):
    """Upload group avatar for a room"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    if 'avatar' not in request.files:
        return jsonify({'success': False, 'message': 'Không có file được chọn'})

    file = request.files['avatar']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Không có file được chọn'})

    try:
        # Check membership: only room members can upload group avatar
        if not database.DatabaseManager.is_room_member(room_id, session['user_id']):
            return jsonify({'success': False, 'message': 'Bạn không có quyền thay đổi avatar nhóm này'})

        # Validate uploaded image (allow slightly larger for groups)
        valid, info = validate_image_upload(file, max_size=3 * 1024 * 1024)
        if not valid:
            return jsonify({'success': False, 'message': info})

        # Create unique filename
        filename = secure_filename(file.filename)
        unique_filename = f"group_{room_id}_{uuid.uuid4().hex}_{filename}"

        # Save file to avatars directory
        avatar_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'group_avatars')
        os.makedirs(avatar_dir, exist_ok=True)

        file_path = os.path.join(avatar_dir, unique_filename)
        file.save(file_path)

        # Compress image (resize to 200x200 for avatar)
        compress_image(file_path, quality=85, max_size=(200, 200))

        # Save to database
        avatar_url = f"/static/uploads/avatars/group_avatars/{unique_filename}"
        database.DatabaseManager.update_group_avatar(room_id, avatar_url)

        app_logger.info(f"User {session['user_id']} uploaded group avatar for room {room_id}")

        return jsonify({
            'success': True,
            'avatar_url': avatar_url,
            'message': 'Upload avatar thành công'
        })

    except Exception as e:
        app_logger.error(f"Lỗi upload group avatar: {e}")
        return jsonify({'success': False, 'message': f'Lỗi upload: {str(e)}'})


@app.route('/get_last_seen/<int:user_id>')
def get_last_seen(user_id):
    """Get last seen time for a user"""
    try:
        last_seen = database.DatabaseManager.get_user_last_seen(user_id)
        return jsonify({'success': True, 'last_seen': last_seen})
    except Exception as e:
        app_logger.error(f"Lỗi get last seen: {e}")
        return jsonify({'success': False, 'last_seen': None})


@app.route('/set_user_status_message', methods=['POST'])
def set_user_status_message():
    """Set user status message"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        status_message = request.json.get('status_message', '').strip()
        if len(status_message) > 200:
            return jsonify({'success': False, 'message': 'Status message quá dài (tối đa 200 ký tự)'})
        
        success = database.DatabaseManager.set_user_status_message(session['user_id'], status_message)
        if success:
            return jsonify({'success': True, 'message': 'Đã cập nhật status message'})
        else:
            return jsonify({'success': False, 'message': 'Lỗi cập nhật status message'})
    except Exception as e:
        app_logger.error(f"Lỗi set user status message: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@app.route('/get_user_status_message/<int:user_id>')
def get_user_status_message(user_id):
    """Get user status message"""
    try:
        status_message = database.DatabaseManager.get_user_status_message(user_id)
        return jsonify({'success': True, 'status_message': status_message})
    except Exception as e:
        app_logger.error(f"Lỗi get user status message: {e}")
        return jsonify({'success': False, 'status_message': ''})


@app.route('/forward_message', methods=['POST'])
def forward_message():
    """Forward message to another room"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        message_id = request.json.get('message_id')
        target_room_id = request.json.get('target_room_id')

        if not message_id or not target_room_id:
            return jsonify({'success': False, 'message': 'Thiếu thông tin'})

        # Check if user is member of target room
        if not database.DatabaseManager.is_room_member(target_room_id, session['user_id']):
            return jsonify({'success': False, 'message': 'Bạn không phải thành viên của phòng này'})

        # Forward message
        success = database.DatabaseManager.save_forwarded_message(session['user_id'], message_id, target_room_id)

        if success:
            return jsonify({'success': True, 'message': 'Đã forward tin nhắn'})
        else:
            return jsonify({'success': False, 'message': 'Lỗi forward tin nhắn'})
    except Exception as e:
        app_logger.error(f"Lỗi forward message: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@app.route('/enable_email_notifications', methods=['POST'])
def enable_email_notifications():
    """Bật/tắt email notifications cho user"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        data = request.get_json()
        enabled = data.get('enabled', True)
        database.DatabaseManager.update_email_notification_enabled(session['user_id'], enabled)
        return jsonify({
            'success': True,
            'message': 'Cài đặt email thông báo đã được cập nhật'
        })

    except Exception as e:
        app_logger.error(f"Lỗi enable email notifications: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@app.route('/get_email_notification_status')
def get_email_notification_status():
    """Lấy trạng thái email notification của user"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'enabled': False})

    try:
        enabled = database.DatabaseManager.get_email_notification_enabled(session['user_id'])
        return jsonify({'success': True, 'enabled': enabled})
    except Exception as e:
        app_logger.error(f"Lỗi get email notification status: {e}")
        return jsonify({'success': False, 'enabled': False})


@app.route('/mute_room/<int:room_id>', methods=['POST'])
def mute_room(room_id):
    """Mute notifications for a room"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        success = database.DatabaseManager.mute_room(session['user_id'], room_id)
        if success:
            return jsonify({'success': True, 'message': 'Đã tắt thông báo'})
        else:
            return jsonify({'success': False, 'message': 'Lỗi tắt thông báo'})
    except Exception as e:
        app_logger.error(f"Lỗi mute room: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@app.route('/unmute_room/<int:room_id>', methods=['POST'])
def unmute_room(room_id):
    """Unmute notifications for a room"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        success = database.DatabaseManager.unmute_room(session['user_id'], room_id)
        if success:
            return jsonify({'success': True, 'message': 'Đã bật thông báo'})
        else:
            return jsonify({'success': False, 'message': 'Lỗi bật thông báo'})
    except Exception as e:
        app_logger.error(f"Lỗi unmute room: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@app.route('/get_muted_rooms')
def get_muted_rooms():
    """Get all muted rooms for current user"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'muted_rooms': []})

    try:
        muted_rooms = database.DatabaseManager.get_muted_rooms(session['user_id'])
        return jsonify({'success': True, 'muted_rooms': muted_rooms})
    except Exception as e:
        app_logger.error(f"Lỗi get muted rooms: {e}")
        return jsonify({'success': False, 'muted_rooms': []})


@app.route('/assign_role/<int:room_id>/<int:user_id>', methods=['POST'])
def assign_role(room_id, user_id):
    """Assign a role to a user in a room"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    role = request.json.get('role', 'Member')
    
    # Check if current user is admin or moderator
    current_user_role = database.DatabaseManager.get_user_role(room_id, session['user_id'])
    if current_user_role not in ['Admin', 'Moderator']:
        return jsonify({'success': False, 'message': 'Bạn không có quyền thay đổi role'})
    
    try:
        success = database.DatabaseManager.assign_role(room_id, user_id, role)
        if success:
            return jsonify({'success': True, 'message': 'Đã thay đổi role'})
        else:
            return jsonify({'success': False, 'message': 'Lỗi thay đổi role'})
    except Exception as e:
        app_logger.error(f"Lỗi assign role: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@app.route('/get_room_members/<int:room_id>')
def get_room_members(room_id):
    """Get all members of a room with their roles"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'members': []})

    try:
        members = database.DatabaseManager.get_room_members_with_roles(room_id)
        return jsonify({'success': True, 'members': members})
    except Exception as e:
        app_logger.error(f"Lỗi get room members: {e}")
        return jsonify({'success': False, 'members': []})


# File Sharing System
ALLOWED_FILE_TYPES = {
    'image': ['jpg', 'jpeg', 'png', 'gif', 'webp'],
    'document': ['pdf', 'doc', 'docx', 'txt', 'rtf'],
    'video': ['mp4', 'avi', 'mov', 'wmv', 'flv'],
    'audio': ['mp3', 'wav', 'ogg', 'm4a'],
    'archive': ['zip', 'rar', '7z', 'tar', 'gz']
}

MAX_FILE_SIZES = {
    'image': 10 * 1024 * 1024,  # 10MB
    'document': 20 * 1024 * 1024,  # 20MB
    'video': 100 * 1024 * 1024,  # 100MB
    'audio': 20 * 1024 * 1024,  # 20MB
    'archive': 50 * 1024 * 1024   # 50MB
}

def get_file_type(filename):
    """Xác định loại file dựa trên extension"""
    if not filename:
        return 'unknown'

    extension = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    for file_type, extensions in ALLOWED_FILE_TYPES.items():
        if extension in extensions:
            return file_type

    return 'unknown'

def is_allowed_file(filename):
    """Kiểm tra xem file có được phép upload không"""
    file_type = get_file_type(filename)
    return file_type != 'unknown'


def compress_image(file_path, quality=85, max_size=(1920, 1080)):
    """Nén ảnh tự động để tiết kiệm dung lượng"""
    try:
        from PIL import Image
        img = Image.open(file_path)
        
        # Resize nếu kích thước quá lớn
        img.thumbnail(max_size, Image.LANCZOS)
        
        # Convert to RGB nếu là RGBA (để lưu thành JPEG)
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        
        # Nén và lưu lại
        img.save(file_path, 'JPEG', quality=quality, optimize=True)
        
        app_logger.info(f"Đã nén ảnh: {file_path}")
        return True
    except Exception as e:
        app_logger.error(f"Lỗi nén ảnh {file_path}: {e}")
        return False


def compress_file(file_path, file_type):
    """Nén file dựa trên loại file"""
    if file_type == 'image':
        return compress_image(file_path)
    # Có thể thêm nén cho các loại file khác ở đây
    return True

def get_max_file_size(filename):
    """Lấy kích thước tối đa cho loại file"""
    file_type = get_file_type(filename)
    return MAX_FILE_SIZES.get(file_type, 10 * 1024 * 1024)  # Default 10MB

@app.route('/upload_file', methods=['POST'])
def upload_file():
    """Upload file chia sẻ"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'Không có file được chọn'})

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Không có file được chọn'})

    try:
        # Kiểm tra loại file
        if not is_allowed_file(file.filename):
            return jsonify({'success': False, 'message': 'Loại file không được hỗ trợ'})

        # Kiểm tra kích thước file
        max_size = get_max_file_size(file.filename)
        if file.content_length > max_size:
            max_mb = max_size // (1024 * 1024)
            return jsonify({'success': False, 'message': f'File quá lớn. Kích thước tối đa: {max_mb}MB'})

        # Tạo tên file unique
        filename = secure_filename(file.filename)
        file_type = get_file_type(filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"

        # Lưu file vào thư mục tương ứng
        upload_dir = os.path.join(app.config['UPLOAD_FOLDER'].replace('avatars', 'files'), file_type)
        os.makedirs(upload_dir, exist_ok=True)

        file_path = os.path.join(upload_dir, unique_filename)
        file.save(file_path)

        # Nén file tự động
        compress_file(file_path, file_type)

        # Lưu thông tin file vào database
        file_url = f"/static/uploads/files/{file_type}/{unique_filename}"

        database.DatabaseManager.upload_file(
            unique_filename, filename, file_url, file_type, 
            file.content_length, session['user_id'], 
            request.form.get('room_id')
        )

        app_logger.info(f"User {session['user_id']} uploaded file: {filename}")

        return jsonify({
            'success': True,
            'file_url': file_url,
            'filename': filename,
            'file_type': file_type,
            'file_size': file.content_length,
            'message': 'Upload file thành công'
        })

    except Exception as e:
        app_logger.error(f"Lỗi upload file: {e}")
        return jsonify({'success': False, 'message': f'Lỗi upload: {str(e)}'})


@app.route('/download_file/<int:file_id>')
def download_file(file_id):
    """Download file đã chia sẻ"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        file_info = database.DatabaseManager.get_file_info(file_id)

        if not file_info:
            return jsonify({'success': False, 'message': 'File không tồn tại'})

        # Kiểm tra quyền (cho phép download tất cả các file trong phòng)
        file_path = os.path.join('static/uploads/files', file_info[3], file_info[0])

        if os.path.exists(file_path):
            return send_file(
                file_path,
                as_attachment=True,
                download_name=file_info[1]
            )
        else:
            return jsonify({'success': False, 'message': 'File không tồn tại trên server'})

    except Exception as e:
        app_logger.error(f"Lỗi download file: {e}")
        return jsonify({'success': False, 'message': f'Lỗi download: {str(e)}'})


@socketio.on('send_file')
def handle_send_file(data):
    """Gửi file qua Socket.IO"""
    try:
        file_data = data.get('file_data')
        filename = data.get('filename')
        file_type = data.get('file_type', 'unknown')
        room = data.get('room', 1)
        user_id = session.get('user_id')
        user_name = session.get('user_name', 'Unknown')

        if not file_data or not filename or not user_id:
            emit('file_error', {'message': 'Dữ liệu file không hợp lệ'})
            return

        # Giải mã base64 và lưu file
        import base64
        try:
            file_content = base64.b64decode(file_data)
        except:
            emit('file_error', {'message': 'File data không hợp lệ'})
            return

        # Lưu file
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        upload_dir = os.path.join(app.config['UPLOAD_FOLDER'].replace('avatars', 'files'), file_type)
        os.makedirs(upload_dir, exist_ok=True)

        file_path = os.path.join(upload_dir, unique_filename)
        with open(file_path, 'wb') as f:
            f.write(file_content)

        # Lưu vào database
        file_url = f"/static/uploads/files/{file_type}/{unique_filename}"
        database.DatabaseManager.upload_file(unique_filename, filename, file_url, file_type, len(file_content), user_id, room)

        # Gửi thông báo file đến room
        emit('file_shared', {
            'user': user_name,
            'room': room,
            'file_url': file_url,
            'filename': filename,
            'file_type': file_type,
            'file_size': len(file_content),
            'sent_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }, room=room)

        app_logger.info(f"User {user_name} shared file: {filename} in room {room}")

    except Exception as e:
        app_logger.error(f"Lỗi send file: {e}")
        emit('file_error', {'message': f'Lỗi gửi file: {str(e)}'})


# Push Notifications System
@app.route('/enable_notifications', methods=['POST'])
def enable_notifications():
    """Bật push notifications cho user"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        data = request.get_json()
        enabled = data.get('enabled', True)
        database.DatabaseManager.update_notification_enabled(session['user_id'], enabled)
        return jsonify({
            'success': True,
            'message': 'Cài đặt thông báo đã được cập nhật'
        })

    except Exception as e:
        app_logger.error(f"Lỗi enable notifications: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@app.route('/send_notification', methods=['POST'])
def send_notification():
    """Gửi notification đến user"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        data = request.get_json()
        target_user_id = data.get('target_user_id')
        notification_title = data.get('title', 'Thông báo mới')
        notification_message = data.get('message', '')
        notification_type = data.get('type', 'message')

        if not target_user_id or not notification_message:
            return jsonify({'success': False, 'message': 'Thiếu thông tin'})

        database.DatabaseManager.create_notification(target_user_id, notification_title, notification_message, notification_type)

        # Gửi real-time notification qua Socket.IO
        emit('new_notification', {
            'notification_id': 0,  # Since we're not using cursor.lastrowid anymore
            'title': notification_title,
            'message': notification_message,
            'type': notification_type,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }, room=f"user_{target_user_id}")

        return jsonify({
            'success': True,
            'message': 'Đã gửi thông báo thành công'
        })

    except Exception as e:
        app_logger.error(f"Lỗi send notification: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@app.route('/get_notifications')
def get_notifications():
    """Lấy danh sách notifications của user"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        notifications = database.DatabaseManager.get_user_notifications(session['user_id'])
        return jsonify({
            'success': True,
            'notifications': notifications
        })

    except Exception as e:
        app_logger.error(f"Lỗi get notifications: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@app.route('/mark_notification_read/<int:notification_id>', methods=['POST'])
def mark_notification_read(notification_id):
    """Đánh dấu notification đã đọc"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        database.DatabaseManager.mark_notification_read(notification_id, session['user_id'])
        return jsonify({'success': True})

    except Exception as e:
        app_logger.error(f"Lỗi mark notification read: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@socketio.on('join_user_room')
def handle_join_user_room():
    """User join vào room riêng để nhận notifications"""
    if 'user_id' in session:
        user_id = session['user_id']
        join_room(f"user_{user_id}")
        emit('joined_user_room', {'user_id': user_id})


# Enhanced Group Management
@app.route('/add_group_member/<int:room_id>', methods=['POST'])
def add_group_member(room_id):
    """Thêm thành viên vào nhóm"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        data = request.get_json()
        target_user_id = data.get('user_id')

        if not target_user_id:
            return jsonify({'success': False, 'message': 'Thiếu user ID'})

        # Kiểm tra quyền (Admin hoặc Moderator)
        current_role = database.DatabaseManager.get_user_role(room_id, session['user_id'])
        if current_role not in ['Admin', 'Moderator']:
            return jsonify({'success': False, 'message': 'Bạn không có quyền thêm thành viên'})

        # Kiểm tra user tồn tại
        if not database.DatabaseManager.user_exists(target_user_id):
            return jsonify({'success': False, 'message': 'User không tồn tại'})

        # Thêm thành viên vào nhóm
        database.DatabaseManager.add_member_to_group(room_id, target_user_id)

        # Thông báo realtime
        emit('group_member_added', {
            'room_id': room_id,
            'user_id': target_user_id,
            'added_by': session['user_id']
        }, room=f"room_{room_id}")

        return jsonify({'success': True, 'message': 'Đã thêm thành viên vào nhóm'})

    except Exception as e:
        app_logger.error(f"Lỗi add group member: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@app.route('/remove_group_member/<int:room_id>', methods=['POST'])
def remove_group_member(room_id):
    """Xóa thành viên khỏi nhóm"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        data = request.get_json()
        target_user_id = data.get('user_id')

        if not target_user_id:
            return jsonify({'success': False, 'message': 'Thiếu user ID'})

        # Kiểm tra quyền: Admin hoặc Moderator có thể xóa thành viên (Moderator không thể xóa Admin)
        current_role = database.DatabaseManager.get_user_role(room_id, session['user_id'])
        is_self = target_user_id == session['user_id']

        if is_self:
            # allow leaving
            database.DatabaseManager.remove_member_from_group(room_id, target_user_id)
        else:
            if current_role not in ['Admin', 'Moderator']:
                return jsonify({'success': False, 'message': 'Bạn không có quyền xóa thành viên'})

            target_role = database.DatabaseManager.get_user_role(room_id, target_user_id)
            if target_role == 'Admin' and current_role != 'Admin':
                return jsonify({'success': False, 'message': 'Bạn không thể xóa Admin'} )

            database.DatabaseManager.remove_member_from_group(room_id, target_user_id)

        # Thông báo realtime
        emit('group_member_removed', {
            'room_id': room_id,
            'user_id': target_user_id,
            'removed_by': session['user_id']
        }, room=f"room_{room_id}")

        return jsonify({'success': True, 'message': 'Đã xóa thành viên khỏi nhóm'})

    except Exception as e:
        app_logger.error(f"Lỗi remove group member: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@app.route('/update_group_settings/<int:room_id>', methods=['POST'])
def update_group_settings(room_id):
    """Cập nhật cài đặt nhóm"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        data = request.get_json()
        group_name = data.get('group_name', '').strip()
        group_description = data.get('description', '').strip()

        if not group_name:
            return jsonify({'success': False, 'message': 'Tên nhóm không được để trống'})

        # Kiểm tra quyền admin của nhóm
        if not database.DatabaseManager.is_room_admin(room_id, session['user_id']):
            return jsonify({'success': False, 'message': 'Bạn không có quyền cập nhật nhóm'})

        # Cập nhật thông tin nhóm
        database.DatabaseManager.update_group_info(room_id, group_name, group_description)

        return jsonify({'success': True, 'message': 'Cập nhật nhóm thành công'})

    except Exception as e:
        app_logger.error(f"Lỗi update group settings: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@app.route('/get_group_members/<int:room_id>')
def get_group_members(room_id):
    """Lấy danh sách thành viên nhóm"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        # Kiểm tra user có trong nhóm không
        if not database.DatabaseManager.is_room_member(room_id, session['user_id']):
            return jsonify({'success': False, 'message': 'Bạn không phải thành viên của nhóm này'})

        # Lấy danh sách thành viên
        members = database.DatabaseManager.get_group_members(room_id)

        return jsonify({
            'success': True,
            'members': members
        })

    except Exception as e:
        app_logger.error(f"Lỗi get group members: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@app.route('/leave_group/<int:room_id>', methods=['POST'])
def leave_group(room_id):
    """Rời nhóm"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        # Xóa user khỏi nhóm
        database.DatabaseManager.remove_member_from_group(room_id, session['user_id'])

        # Thông báo realtime
        emit('group_member_left', {
            'room_id': room_id,
            'user_id': session['user_id'],
            'user_name': session.get('user_name', 'Unknown')
        }, room=room_id)

        return jsonify({'success': True, 'message': 'Đã rời nhóm'})
    except Exception as e:
        app_logger.error(f"Lỗi rời nhóm: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@app.route('/send_group_invite', methods=['POST'])
def send_group_invite():
    """Gửi group invite"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        room_id = request.json.get('room_id')
        invitee_id = request.json.get('invitee_id')

        if not room_id or not invitee_id:
            return jsonify({'success': False, 'message': 'Thiếu thông tin'})

        # Check if user is admin or moderator
        current_role = database.DatabaseManager.get_user_role(room_id, session['user_id'])
        if current_role not in ['Admin', 'Moderator']:
            return jsonify({'success': False, 'message': 'Bạn không có quyền mời thành viên'})

        # Check if invitee is already a member
        if database.DatabaseManager.is_room_member(room_id, invitee_id):
            return jsonify({'success': False, 'message': 'User đã là thành viên của nhóm'})

        # Create invite
        success = database.DatabaseManager.create_group_invite(room_id, session['user_id'], invitee_id)

        if success:
            # Notify invitee via socket
            emit('group_invite_received', {
                'room_id': room_id,
                'inviter_name': session.get('user_name', 'Unknown')
            }, room=f"user_{invitee_id}")

            return jsonify({'success': True, 'message': 'Đã gửi lời mời'})
        else:
            return jsonify({'success': False, 'message': 'Lỗi gửi lời mời hoặc lời mời đã tồn tại'})
    except Exception as e:
        app_logger.error(f"Lỗi gửi group invite: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@app.route('/get_pending_invites')
def get_pending_invites():
    """Lấy danh sách pending invites của user"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'invites': []})

    try:
        invites = database.DatabaseManager.get_pending_invites(session['user_id'])
        return jsonify({'success': True, 'invites': invites})
    except Exception as e:
        app_logger.error(f"Lỗi get pending invites: {e}")
        return jsonify({'success': False, 'invites': []})


@app.route('/accept_decline_invite/<int:invite_id>', methods=['POST'])
def accept_decline_invite(invite_id):
    """Chấp nhận hoặc từ chối group invite"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        action = request.json.get('action', 'accept')

        if action not in ['accept', 'decline']:
            return jsonify({'success': False, 'message': 'Hành động không hợp lệ'})

        success = database.DatabaseManager.accept_decline_invite(invite_id, session['user_id'], action)

        if success:
            message = 'Đã chấp nhận lời mời' if action == 'accept' else 'Đã từ chối lời mời'
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'message': 'Lỗi xử lý lời mời'})
    except Exception as e:
        app_logger.error(f"Lỗi accept/decline invite: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


# Message Search System
@app.route('/search_messages/<int:room_id>')
def search_messages(room_id):
    """Tìm kiếm tin nhắn trong phòng"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        query = request.args.get('q', '').strip()
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))

        if not query or len(query) < 2:
            return jsonify({'success': False, 'message': 'Từ khóa tìm kiếm quá ngắn'})

        # Kiểm tra user có trong phòng không
        if not database.DatabaseManager.is_room_member(room_id, session['user_id']):
            return jsonify({'success': False, 'message': 'Bạn không phải thành viên của phòng này'})

        # Tìm kiếm tin nhắn
        result = database.DatabaseManager.search_messages_in_room(room_id, query, page, limit)

        return jsonify({
            'success': True,
            **result
        })

    except Exception as e:
        app_logger.error(f"Lỗi search messages: {e}")
        return jsonify({'success': False, 'message': f'Lỗi tìm kiếm: {str(e)}'})


@app.route('/global_search')
def global_search():
    """Tìm kiếm toàn bộ tin nhắn của user"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        query = request.args.get('q', '').strip()
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))

        if not query or len(query) < 2:
            return jsonify({'success': False, 'message': 'Từ khóa tìm kiếm quá ngắn'})

        result = database.DatabaseManager.global_search_messages(session['user_id'], query, page, limit)

        return jsonify({
            'success': True,
            **result
        })

    except Exception as e:
        app_logger.error(f"Lỗi global search: {e}")
        return jsonify({'success': False, 'message': f'Lỗi tìm kiếm: {str(e)}'})


@app.route('/search_suggestions')
def search_suggestions():
    """Gợi ý tìm kiếm"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        query = request.args.get('q', '').strip()

        if not query or len(query) < 2:
            return jsonify({'suggestions': []})

        suggestions = database.DatabaseManager.get_search_suggestions(session['user_id'], query)

        return jsonify({
            'suggestions': suggestions
        })

    except Exception as e:
        app_logger.error(f"Lỗi search suggestions: {e}")
        return jsonify({'suggestions': []})


# Dark Theme System
@app.route('/set_theme', methods=['POST'])
def set_theme():
    """Cài đặt theme cho user"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        data = request.get_json()
        theme = data.get('theme', 'light')

        if theme not in ['light', 'dark', 'auto']:
            return jsonify({'success': False, 'message': 'Theme không hợp lệ'})

        database.DatabaseManager.set_theme(session['user_id'], theme)

        return jsonify({
            'success': True,
            'theme': theme,
            'message': 'Đã cập nhật theme'
        })

    except Exception as e:
        app_logger.error(f"Lỗi set theme: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@app.route('/get_theme')
def get_theme():
    """Lấy theme hiện tại của user"""
    if 'user_id' not in session:
        return jsonify({'theme': 'light'})

    try:
        theme = database.DatabaseManager.get_theme(session['user_id'])
        return jsonify({'theme': theme})

    except Exception as e:
        app_logger.error(f"Lỗi get theme: {e}")
        return jsonify({'theme': 'light'})


@app.route('/toggle_theme', methods=['POST'])
def toggle_theme():
    """Chuyển đổi theme (light/dark)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        new_theme = database.DatabaseManager.toggle_theme(session['user_id'])

        return jsonify({
            'success': True,
            'theme': new_theme,
            'message': 'Đã chuyển đổi theme'
        })

    except Exception as e:
        app_logger.error(f"Lỗi toggle theme: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


# Admin Dashboard System
def is_admin(user_id):
    """Kiểm tra user có phải admin không"""
    try:
        return database.DatabaseManager.is_admin(user_id)
    except Exception as e:
        app_logger.error(f"Lỗi check admin: {e}")
        return False


@app.route('/admin')
def admin_dashboard():
    """Admin dashboard"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if not is_admin(session['user_id']):
        flash('Bạn không có quyền truy cập trang này')
        return redirect(url_for('index'))

    try:
        stats = database.DatabaseManager.get_admin_dashboard_stats()

        return render_template('admin_dashboard.html',
                         total_users=stats['total_users'],
                         total_rooms=stats['total_rooms'],
                         total_messages=stats['total_messages'],
                         total_files=stats['total_files'],
                         online_users=stats['online_users'],
                         daily_stats=stats['daily_stats'],
                         top_users=stats['top_users'],
                         top_rooms=stats['top_rooms'])

    except Exception as e:
        app_logger.error(f"Lỗi admin dashboard: {e}")
        flash(f'Lỗi tải dashboard: {str(e)}')
        return redirect(url_for('index'))


@app.route('/admin/users')
def admin_users():
    """Quản lý users"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return redirect(url_for('login'))

    try:
        page = int(request.args.get('page', 1))
        limit = 20
        offset = (page - 1) * limit

        result = database.DatabaseManager.get_admin_users(page, limit)

        return jsonify({
            'success': True,
            'users': result['users'],
            'pagination': {
                'page': page,
                'limit': limit,
                'total': result['total'],
                'total_pages': (result['total'] + limit - 1) // limit
            }
        })

    except Exception as e:
        app_logger.error(f"Lỗi admin users: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@app.route('/admin/update_user_role/<int:user_id>', methods=['POST'])
def admin_update_user_role(user_id):
    """Cập nhật role user"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return jsonify({'success': False, 'message': 'Không có quyền truy cập'})

    try:
        data = request.get_json()
        new_role = data.get('role', 'User')

        if new_role not in ['User', 'Admin', 'Moderator']:
            return jsonify({'success': False, 'message': 'Role không hợp lệ'})

        database.DatabaseManager.update_user_role(user_id, new_role)

        return jsonify({'success': True, 'message': 'Đã cập nhật role'})

    except Exception as e:
        app_logger.error(f"Lỗi update user role: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@app.route('/admin/system_stats')
def admin_system_stats():
    """Thống kê hệ thống"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return jsonify({'success': False, 'message': 'Không có quyền truy cập'})

    try:
        stats = database.DatabaseManager.get_system_stats()

        return jsonify({
            'success': True,
            'stats': stats
        })

    except Exception as e:
        app_logger.error(f"Lỗi system stats: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


# Voice Messages System
@app.route('/upload_voice', methods=['POST'])
def upload_voice():
    """Upload voice message"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        if 'voice' not in request.files:
            return jsonify({'success': False, 'message': 'Không có file âm thanh'})

        voice_file = request.files['voice']
        if voice_file.filename == '':
            return jsonify({'success': False, 'message': 'Không có file âm thanh'})

        # Kiểm tra file type (chỉ chấp nhận audio)
        allowed_audio_types = ['mp3', 'wav', 'ogg', 'm4a', 'webm']
        if not voice_file.filename or '.' not in voice_file.filename:
            return jsonify({'success': False, 'message': 'File không hợp lệ'})

        file_extension = voice_file.filename.rsplit('.', 1)[1].lower()
        if file_extension not in allowed_audio_types:
            return jsonify({'success': False, 'message': 'Chỉ chấp nhận file âm thanh'})

        # Kiểm tra kích thước (tối đa 20MB)
        if voice_file.content_length > 20 * 1024 * 1024:
            return jsonify({'success': False, 'message': 'File âm thanh quá lớn (tối đa 20MB)'})

        # Tạo tên file unique
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}"

        # Lưu file
        upload_dir = os.path.join(app.config['UPLOAD_FOLDER'].replace('avatars', 'files'), 'voice')
        os.makedirs(upload_dir, exist_ok=True)

        file_path = os.path.join(upload_dir, unique_filename)
        voice_file.save(file_path)

        # Lưu thông tin vào database
        voice_url = f"/static/uploads/files/voice/{unique_filename}"

        database.DatabaseManager.save_voice_message(unique_filename, voice_url, voice_file.content_length, session['user_id'], request.form.get('room_id'))

        app_logger.info(f"User {session['user_id']} uploaded voice: {voice_file.filename}")

        return jsonify({
            'success': True,
            'voice_url': voice_url,
            'filename': voice_file.filename,
            'file_size': voice_file.content_length,
            'message': 'Upload voice message thành công'
        })

    except Exception as e:
        app_logger.error(f"Lỗi upload voice: {e}")
        return jsonify({'success': False, 'message': f'Lỗi upload: {str(e)}'})


@socketio.on('send_voice')
def handle_send_voice(data):
    """Gửi voice message qua Socket.IO"""
    try:
        voice_data = data.get('voice_data')
        filename = data.get('filename')
        duration = data.get('duration', 0)
        room = data.get('room', 1)
        user_id = session.get('user_id')
        user_name = session.get('user_name', 'Unknown')

        if not voice_data or not filename or not user_id:
            emit('voice_error', {'message': 'Dữ liệu voice không hợp lệ'})
            return

        # Giải mã base64 và lưu file
        import base64
        try:
            voice_content = base64.b64decode(voice_data)
        except:
            emit('voice_error', {'message': 'Voice data không hợp lệ'})
            return

        # Lưu file
        file_extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'webm'
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}"

        upload_dir = os.path.join(app.config['UPLOAD_FOLDER'].replace('avatars', 'files'), 'voice')
        os.makedirs(upload_dir, exist_ok=True)

        file_path = os.path.join(upload_dir, unique_filename)
        with open(file_path, 'wb') as f:
            f.write(voice_content)

        # Lưu vào database
        voice_url = f"/static/uploads/files/voice/{unique_filename}"

        database.DatabaseManager.save_voice_message(unique_filename, voice_url, len(voice_content), user_id, room, duration)

        # Gửi thông báo voice đến room
        emit('voice_shared', {
            'user': user_name,
            'room': room,
            'voice_url': voice_url,
            'filename': filename,
            'duration': duration,
            'file_size': len(voice_content),
            'sent_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }, room=room)

        app_logger.info(f"User {user_name} shared voice: {filename} in room {room}")

    except Exception as e:
        app_logger.error(f"Lỗi send voice: {e}")
        emit('voice_error', {'message': f'Lỗi gửi voice: {str(e)}'})


@app.route('/get_voice_messages/<int:room_id>')
def get_voice_messages(room_id):
    """Lấy danh sách voice messages trong phòng"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        voice_messages = database.DatabaseManager.get_voice_messages(room_id, session['user_id'])

        return jsonify({
            'success': True,
            'voice_messages': voice_messages
        })

    except Exception as e:
        app_logger.error(f"Lỗi get voice messages: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


# 2FA Authentication System

def generate_2fa_secret():
    """Tạo 2FA secret cho user"""
    return pyotp.random_base32()

def generate_qr_code(secret, username):
    """Tạo QR code cho 2FA"""
    totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=username,
        issuer_name="ChatAI App"
    )

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(totp_uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)

    return buffer

@app.route('/enable_2fa', methods=['GET', 'POST'])
def enable_2fa():
    """Bật 2FA cho user"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'GET':
        return render_template('enable_2fa.html')

    try:
        # Tạo secret mới
        secret = generate_2fa_secret()

        database.DatabaseManager.enable_2fa(session['user_id'], secret)

        # Tạo QR code
        qr_buffer = generate_qr_code(secret, session.get('user_name', 'User'))

        return send_file(
            BytesIO(qr_buffer.read()),
            mimetype='image/png',
            as_attachment=False,
            download_name='2fa_qr.png'
        )

    except Exception as e:
        app_logger.error(f"Lỗi enable 2FA: {e}")
        flash(f'Lỗi kích hoạt 2FA: {str(e)}')
        return redirect(url_for('index'))

@app.route('/verify_2fa', methods=['POST'])
def verify_2fa():
    """Xác thực 2FA code"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        data = request.get_json()
        code = data.get('code', '').strip()

        if not code or len(code) != 6:
            return jsonify({'success': False, 'message': 'Mã 2FA không hợp lệ'})

        # Lấy secret của user
        secret = database.DatabaseManager.get_2fa_secret(session['user_id'])
        
        if not secret:
            return jsonify({'success': False, 'message': '2FA chưa được thiết lập'})

        # Xác thực code
        totp = pyotp.TOTP(secret)
        is_valid = totp.verify(code)

        if is_valid:
            # Bật 2FA
            database.DatabaseManager.enable_2fa_verified(session['user_id'])

            return jsonify({
                'success': True,
                'message': '2FA đã được kích hoạt thành công'
            })
        else:
            return jsonify({'success': False, 'message': 'Mã 2FA không chính xác'})

    except Exception as e:
        app_logger.error(f"Lỗi verify 2FA: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})

@app.route('/disable_2fa', methods=['POST'])
def disable_2fa():
    """Tắt 2FA"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập'})

    try:
        data = request.get_json()
        password = data.get('password', '')
        code = data.get('code', '').strip()

        if not password or not code:
            return jsonify({'success': False, 'message': 'Vui lòng nhập mật khẩu và mã 2FA'})

        # Kiểm tra mật khẩu
        result = database.DatabaseManager.get_user_password_and_2fa_secret(session['user_id'])
        if not result:
            return jsonify({'success': False, 'message': 'User không tồn tại'})

        stored_password_hash, two_fa_secret = result

        # Kiểm tra password
        password_valid = False
        if stored_password_hash:
            if stored_password_hash.startswith('$2'):  # Hashed password
                password_valid = check_password_hash(stored_password_hash, password)
            else:  # Plain text password (old records)
                password_valid = (stored_password_hash == password)

        if not password_valid:
            return jsonify({'success': False, 'message': 'Mật khẩu không chính xác'})

        # Kiểm tra 2FA code
        if two_fa_secret:  # TwoFASecret exists
            totp = pyotp.TOTP(two_fa_secret)
            is_valid = totp.verify(code)

            if not is_valid:
                return jsonify({'success': False, 'message': 'Mã 2FA không chính xác'})

        # Tắt 2FA
        database.DatabaseManager.disable_2fa(session['user_id'])

        return jsonify({
            'success': True,
            'message': '2FA đã được tắt thành công'
        })

    except Exception as e:
        app_logger.error(f"Lỗi disable 2FA: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})

@app.route('/login_2fa', methods=['GET', 'POST'])
def login_2fa():
    """Login với 2FA"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'GET':
        return render_template('login_2fa.html')

    try:
        data = request.get_json()
        code = data.get('code', '').strip()

        if not code or len(code) != 6:
            return jsonify({'success': False, 'message': 'Mã 2FA không hợp lệ'})

        # Lấy secret của user
        secret, enabled = database.DatabaseManager.get_2fa_secret_and_status(session['user_id'])
        
        if not secret or not enabled:
            return jsonify({'success': False, 'message': '2FA chưa được kích hoạt'})

        # Xác thực code
        totp = pyotp.TOTP(secret)
        is_valid = totp.verify(code)

        if is_valid:
            # Đánh dấu 2FA đã xác thực trong session
            session['2fa_verified'] = True

            return jsonify({
                'success': True,
                'message': 'Xác thực 2FA thành công',
                'redirect': url_for('index')
            })
        else:
            return jsonify({'success': False, 'message': 'Mã 2FA không chính xác'})

    except Exception as e:
        app_logger.error(f"Lỗi login 2FA: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})

@app.route('/check_2fa_status')
def check_2fa_status():
    """Kiểm tra trạng thái 2FA của user"""
    if 'user_id' not in session:
        return jsonify({'enabled': False})

    try:
        enabled = database.DatabaseManager.is_2fa_enabled(session['user_id'])

        return jsonify({'enabled': enabled})

    except Exception as e:
        app_logger.error(f"Lỗi check 2FA status: {e}")
        return jsonify({'enabled': False})


# Analytics System
@app.route('/analytics')
def analytics_dashboard():
    """Analytics dashboard"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return redirect(url_for('login'))

    return render_template('analytics.html')


@app.route('/analytics/overview')
def analytics_overview():
    """Tổng quan analytics"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return jsonify({'success': False, 'message': 'Không có quyền truy cập'})

    try:
        stats = database.DatabaseManager.get_analytics_overview()
        return jsonify({'success': True, 'stats': stats})

    except Exception as e:
        app_logger.error(f"Lỗi analytics overview: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@app.route('/analytics/user_activity')
def analytics_user_activity():
    """Thống kê hoạt động user"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return jsonify({'success': False, 'message': 'Không có quyền truy cập'})

    try:
        days = int(request.args.get('days', 30))
        activity_data = database.DatabaseManager.get_analytics_user_activity(days)
        return jsonify({'success': True, **activity_data})

    except Exception as e:
        app_logger.error(f"Lỗi user activity analytics: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@app.route('/analytics/room_stats')
def analytics_room_stats():
    """Thống kê phòng chat"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return jsonify({'success': False, 'message': 'Không có quyền truy cập'})

    try:
        days = int(request.args.get('days', 30))
        room_stats = database.DatabaseManager.get_analytics_room_stats(days)
        return jsonify({'success': True, **room_stats})

    except Exception as e:
        app_logger.error(f"Lỗi room stats analytics: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@app.route('/analytics/file_stats')
def analytics_file_stats():
    """Thống kê file"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return jsonify({'success': False, 'message': 'Không có quyền truy cập'})

    try:
        days = int(request.args.get('days', 30))
        file_stats = database.DatabaseManager.get_analytics_file_stats(days)
        return jsonify({'success': True, **file_stats})

    except Exception as e:
        app_logger.error(f"Lỗi file stats analytics: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@app.route('/analytics/export')
def analytics_export():
    """Xuất analytics data"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return jsonify({'success': False, 'message': 'Không có quyền truy cập'})

    try:
        export_type = request.args.get('type', 'users')

        data = database.DatabaseManager.get_analytics_data(export_type)

        if data is None:
            return jsonify({'success': False, 'message': 'Loại export không hợp lệ'})

        # Convert to CSV format
        output = StringIO()
        writer = csv.writer(output)

        if data:
            # Write headers based on export type
            if export_type == 'users':
                writer.writerow(['UserID', 'FullName', 'Username', 'Email', 'Status', 'CreatedAt'])
            elif export_type == 'messages':
                writer.writerow(['MessageID', 'Content', 'MessageType', 'SentAt', 'SenderName'])
            elif export_type == 'rooms':
                writer.writerow(['RoomID', 'RoomName', 'IsGroup', 'CreatedAt'])
            elif export_type == 'files':
                writer.writerow(['FileID', 'FileName', 'FileType', 'FileSize', 'UploadedAt', 'UploaderName'])

            # Write data
            for row in data:
                writer.writerow(row)

        output.seek(0)

        return send_file(
            BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'analytics_{export_type}_{datetime.now().strftime("%Y%m%d")}.csv'
        )

    except Exception as e:
        app_logger.error(f"Lỗi analytics export: {e}")
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})

@app.route('/google4e20d9f91e4489f6.html')
def google_verification():
    return send_from_directory('.', 'google4e20d9f91e4489f6.html')
if __name__ == "__main__":

    database.DatabaseManager.init_db_from_file()

    port = int(os.environ.get("PORT", 10000))

    print("=== CHATAI APPLICATION ===")

    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=False
    )