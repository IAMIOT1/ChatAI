# ChatAI

Ứng dụng chat Flask + Socket.IO với:
- Đăng ký / đăng nhập bằng email
- Xác thực email
- Quên mật khẩu / đặt lại mật khẩu
- OAuth Google và Facebook
- Deploy bằng Docker / Heroku

## Cài đặt

1. Tạo môi trường ảo Python và cài dependencies:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Tạo file `.env` từ `.env.example` và cập nhật thông tin:
   - `MAIL_USERNAME` / `MAIL_PASSWORD`
   - `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`
   - `FACEBOOK_OAUTH_CLIENT_ID`, `FACEBOOK_OAUTH_CLIENT_SECRET`

3. Chạy ứng dụng:
   ```bash
   python app.py
   ```

## OAuth

### Google OAuth
1. Truy cập [Google Cloud Console](https://console.cloud.google.com/)
2. Tạo project mới hoặc chọn project có sẵn
3. Enable Google+ API và Google OAuth2 API
4. Tạo OAuth 2.0 Client ID:
   - Application type: Web application
   - Authorized redirect URIs: `http://localhost:8888/login/google/authorized`
5. Lấy Client ID và Client Secret, thêm vào `.env`

### Facebook OAuth  
1. Truy cập [Facebook Developers](https://developers.facebook.com/)
2. Tạo App mới hoặc chọn App có sẵn
3. Thêm product "Facebook Login"
4. Cấu hình OAuth redirect URI: `http://localhost:8888/login/facebook/authorized`
5. Lấy App ID và App Secret, thêm vào `.env`

### Redirect URLs (Quan trọng!)
Trong Facebook App Settings và Google Cloud Console, cấu hình các redirect URLs sau:
- Google: `http://localhost:8888/login/google/authorized`
- Facebook: `http://localhost:8888/login/facebook/authorized`

**Lưu ý:** Redirect URLs phải khớp chính xác với các route trong app.py

## Deploy

- Docker:
  ```bash
  docker build -t chatai-app .
  docker run -p 8888:8888 --env-file .env chatai-app
  ```

- Heroku:
  ```bash
  heroku create
  git push heroku main
  heroku config:set SECRET_KEY=... MAIL_SERVER=... MAIL_USERNAME=... MAIL_PASSWORD=...
  ```

## Lưu ý

Nếu muốn email hoạt động, bạn cần dùng thông tin SMTP hợp lệ và cho phép đăng nhập qua ứng dụng bên thứ ba nếu dùng Gmail.
