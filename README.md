# WEBAI – Study Platform (bản đã vá)

## Cài đặt (PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```
Mở `.env` và điền:
```env
SECRET_KEY=<chuỗi từ lệnh bên dưới>
GEMINI_API_KEY=<key Gemini MỚI từ Google AI Studio>
FLASK_DEBUG=0
```
Tạo SECRET_KEY (chạy lệnh trong terminal rồi dán KẾT QUẢ vào `.env`):
```powershell
.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```
Chạy:
```powershell
.venv\Scripts\python.exe run.py
```
Nếu thiếu hoặc yếu SECRET_KEY, app dừng và báo lỗi rõ ràng.

## Tài khoản mẫu (chỉ để demo, đổi mật khẩu trước khi dùng thật)
admin@example.com / admin123 · teacher@example.com / teacher123 · student@example.com / student123

## Những gì đã sửa
1. SECRET_KEY bắt buộc, không còn giá trị mặc định; debug chỉ bật khi FLASK_DEBUG=1.
2. Đề đang làm lưu ở server (bảng `quiz_attempt`), cookie chỉ giữ id. Có hạn giờ, không nộp 2 lần, F5 không reset đồng hồ.
3. Một công thức chấm cho bài tập / kiểm tra / đề AI: điểm = số câu đúng × 10 / tổng số câu.
4. CSRF (Flask-WTF) cho mọi form POST; đăng xuất đổi sang POST.
5. Gemini lỗi → báo "AI đang bận", KHÔNG còn câu giả và không lưu gì. Đề AI có kiểm tra chặt, xáo đáp án.
6. Đề có trạng thái nháp / đã duyệt: học sinh chỉ thấy đề đã duyệt. Giáo viên bấm Duyệt ở trang Bài kiểm tra.
7. `seed.py` không còn ghi đè nội dung / ngân hàng đề mỗi lần khởi động.
8. Học sinh không mở được bài khác khối lớp; admin xóa tài khoản dọn sạch dữ liệu liên quan; xóa môn còn nội dung bị chặn;
   giáo viên sửa học sinh kiểm tra trùng email; đăng ký / tạo tài khoản yêu cầu mật khẩu >= 6 ký tự.

## QUAN TRỌNG: ngân hàng đề
Đề cũ (câu mẫu sinh bằng template) đã bị loại. Mọi đề đang ở trạng thái **Nháp** nên học sinh chưa thấy bài kiểm tra nào
cho tới khi bạn sinh đề mới và duyệt:
```powershell
# thử 1 môn / 1 khối trước
.venv\Scripts\python.exe -m tools.build_bank --subject Toán --grade 10
```
Mỗi chương: Gemini sinh câu bám nội dung bài học → tự giải lại để kiểm tra đáp án → lưu 30 câu ở trạng thái Nháp.
Giáo viên đọc lại (nút Sửa), rồi bấm Duyệt. Chạy lại được nhiều lần (tự bỏ qua chương đã sinh).
Gói miễn phí của Gemini có giới hạn request mỗi ngày nên có thể phải chia nhiều ngày.

## Dùng lại database cũ
Chép file `study_platform.db` cũ vào thư mục `instance/`. App tự thêm cột `review_status`, giữ nguyên tài khoản và lịch sử bài nộp.
Không có DB thì app tự tạo mới và nạp bài học / bài tập khối 6–12.
