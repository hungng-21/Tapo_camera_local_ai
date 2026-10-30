# Tapo Camera Local AI — v2.0.1

[](https://github.com/hacs/default)
[GitHub release (latest by date)](https://www.google.com/search?q=https://github.com/hungng-21/Tapo_camera_local_ai/releases)
[License: MIT](https://www.google.com/search?q=LICENSE)

**Tapo Camera Local AI** là giải pháp Custom Component toàn diện và tối ưu nhất để kết nối, điều khiển và khai thác toàn bộ sức mạnh AI của camera **TP-Link Tapo** trên **Home Assistant**.

Tích hợp hoạt động **100% nội bộ (Local LAN)** không thông qua máy chủ đám mây (Cloud), không tốn phí thuê bao (No Subscription), đảm bảo tốc độ phản hồi mili-giây và bảo mật dữ liệu riêng tư tuyệt đối.

---

## 🚀 Điểm mới & Bản vá lỗi trong phiên bản v2.0.1

Bản cập nhật v2.0.1 tập trung tối ưu độ ổn định cao nhất khi triển khai đồng thời nhiều camera trong gia đình (đặc biệt các dòng có màn trập vật lý như **C125** và dòng xoay quét như **C225**):

* **Sửa lỗi `NameError: CONF_FACES` khi thêm camera PTZ**: Khắc phục triệt để lỗi crash luồng kiểm tra quyền sidebar khi kết nối camera thứ 2 (như C225, C200, C500...).
* **Bổ sung `services.yaml` chuẩn hóa**: Khai báo đầy đủ 2 entity service điều khiển xoay quét (`tapo_local_ai.ptz_move` và `tapo_local_ai.ptz_goto_preset`), loại bỏ hoàn toàn cảnh báo thiếu file dịch vụ trong nhật ký Home Assistant.
* **Đồng bộ tức thì Chế độ riêng tư (Privacy Mode / Màn trập vật lý)**: 
  * Tách riêng luồng đọc trực tiếp `getLensMaskConfig` / `getPrivacyMode()` ở đầu mỗi chu kỳ 3 giây.
  * Khi bạn bật/tắt Privacy Mode trên ứng dụng Tapo hoặc bấm nút vật lý trên thân camera C125/C225, công tắc trên Home Assistant sẽ cập nhật trạng thái ngay lập tức.
  * Tự động bảo vệ không bao giờ đưa các hàm cốt lõi vào danh sách đen khi camera đang che ống kính.
* **Triệt tiêu hoàn toàn lỗi ngắt kết nối 5 phút (300s Lockout / `-40404`)**:
  * Lưu cố định phương thức xác thực thành công (`_working_auth`), ưu tiên làm mới token phiên (`refreshStok`) thay vì thử lại các tổ hợp mật khẩu khác nhau gây kích hoạt bộ đếm khóa IP brute-force của camera.
  * Tắt hoàn toàn luồng thử nghiệm C260 đối với các dòng camera không có Face AI (C125, C225, C200...).
  * Giảm 75% tải gói tin API trong các chu kỳ rảnh rỗi và tự động tạm dừng truy vấn module hình ảnh khi màn trập vật lý đang đóng.
* **Giao diện Cấu hình Thích ứng Thông minh (Dynamic UI)**:
  * Khi bấm nút bánh răng (Cấu hình) trên các camera thường (C125, C225), hệ thống mở thẳng vào bảng cài đặt kết nối mạng/tài khoản/chu kỳ poll thay vì hiển thị menu 10 mục Face ID của C260.
  * Bảng điều khiển **Tapo Face Manager** trên thanh bên (Sidebar) tự động ẩn đi nếu trong nhà không có camera Face AI, giữ giao diện Home Assistant luôn gọn gàng.

---

## 🌟 Tính năng cốt lõi của dòng Ultimate Edition

* **Hợp nhất Nhận diện Khuôn mặt (Face Recognition) & Bảng điều khiển "Tapo Face Manager"**: Tích hợp toàn bộ hệ thống quản lý khuôn mặt thông minh từ dự án `tapo-c260-face` (của `@quangtienhn`), gom vào **duy nhất 1 phiên kết nối Local** giúp loại bỏ xung đột phiên.
* **Tự nhận diện phần cứng thông minh (Hardware Auto-Detection)**:
  * Camera xoay quét (PTZ) $\rightarrow$ Tự kích hoạt 4 nút điều hướng, hiệu chuẩn motor, thanh trượt góc xoay, điểm nhớ Preset và chế độ tuần tra (Cruise). Camera cố định $\rightarrow$ Tự ẩn sạch nút xoay.
  * Camera có Face AI (như **Tapo C260**) $\rightarrow$ Tự kích hoạt cảm biến khuôn mặt, lịch sử xuất hiện và bảng điều khiển Sidebar. Camera thường (C100, C110, C120, C125, C200, C210, C310, C500...) $\rightarrow$ Tự ẩn toàn bộ entity khuôn mặt thừa.
* **Tách biệt chuẩn hóa Độ nhạy AI (AI Sensitivity Separation)**:
  * **4 thanh trượt 10 mức (`number`)**: Dành riêng cho các cảm biến hình ảnh 1–10 trong app Tapo (**Motion**, **Person**, **Pet**, **Vehicle**).
  * **5 hộp chọn 3 mức (`select`)**: Dành riêng cho các cảm biến âm thanh 3 mức trong app Tapo (**Baby Cry**, **Dog Bark**, **Cat Meow**, **Glass Break**, **Tamper** với 3 giá trị: `low`, `normal`, `high`).
* **Hỗ trợ còi báo động (`siren`) & điều khiển âm thanh 2 chiều**: Bật/tắt còi kèm độ dài thời gian hú (`duration`) và âm lượng (`volume_level`), thanh trượt âm lượng Loa/Micro (0–100%), công tắc ngắt Micro phần cứng.
* **Độc lập đa luồng**: Luồng RTSP Video (cổng 554) và ONVIF (cổng 2020) chạy độc lập; các truy vấn công tắc và độ nhạy được gộp thành 1 request duy nhất (`multipleRequest`), phản hồi cực nhanh ~50ms.

---

## 📸 Bảng điều khiển "Tapo Face Manager" (Sidebar)

Khi hệ thống có camera hỗ trợ nhận diện khuôn mặt (**Tapo C260**), Home Assistant sẽ tự động xuất hiện mục **Tapo Face Manager** trên thanh bên:

* **Tab Người quen (Known)**: Danh sách người nhà đã nhận diện, hỗ trợ đổi tên, cập nhật mã Face ID và tự động chuyển tiếp lịch sử cũ sang ID mới.
* **Tab Người lạ (Unknown)**: Lưu giữ các khuôn mặt lạ mà camera phát hiện, hiển thị số lần xuất hiện, lần đầu và lần cuối nhìn thấy. Hỗ trợ bấm **"+ Thêm người"** để đặt tên tức thì chỉ với 1 cú click.
* **Tab Lịch sử ngày (Day History)**: Biểu đồ thời gian thực (24 giờ) trực quan từng phút từng giây ai đã xuất hiện trước camera.
* **Tab Thống kê (Statistics)**: Biểu đồ cột tổng hợp tần suất người quen / người lạ theo 7 ngày, 30 ngày, 90 ngày.
* **Tab Cài đặt & Thẻ Sức khỏe kết nối (Health Diagnostics)**: Đo thời gian phản hồi (ms), số lỗi liên tiếp và cho phép tinh chỉnh chu kỳ quét, thời gian chống lặp (Dedup cooldown), thời gian tự tắt cảm biến người lạ trực tiếp trên Web.

> [!NOTE]
> Bảng điều khiển Face Manager hỗ trợ song ngữ **Tiếng Việt / Tiếng Anh**, tự động lưu tùy chọn ngôn ngữ và cho phép chuyển đổi tức thì.

---

## 📦 Danh mục thực thể cung cấp (Entities)

Toàn bộ các thực thể được gom chung vào **1 Thiết bị Camera duy nhất** trên Home Assistant:

### 1. Luồng Video Trực tiếp (`camera`)
* `camera.<ten_cam>_hd_stream`: Luồng chính chất lượng cao (HD / 2K / 4K - RTSP `stream1`).
* `camera.<ten_cam>_sd_stream`: Luồng phụ mượt mà, tốn cực ít tài nguyên CPU (SD - RTSP `stream2`).
* Hỗ trợ gọi dịch vụ xoay quét góc tương đối (`tapo_local_ai.ptz_move`) và xoay tới điểm nhớ (`tapo_local_ai.ptz_goto_preset`).

### 2. Cảm biến nhị phân AI & Sự kiện (`binary_sensor`)
* `Phát hiện tiếng khóc trẻ em` (`baby_cry`)
* `Phát hiện chó sủa` (`bark`)
* `Phát hiện mèo kêu` (`meow`)
* `Phát hiện kính vỡ` (`glass_break`)
* `Phát hiện người (AI Person)` (`person`)
* `Phát hiện thú cưng (AI Pet)` (`pet`)
* `Phát hiện phương tiện (AI Vehicle)` (`vehicle`)
* `Phát hiện chuyển động` (`motion`)
* `Vượt hàng rào ảo` (`line_crossing`)
* `Xâm nhập vùng cấm` (`area_intrusion`)
* `Che khuất / Phá hoại camera` (`tamper`)
* `Phát hiện bưu kiện` (`package`)
* `Nhận diện người quen` (`face_recognized` — chỉ hiện trên C260)
* `Phát hiện người lạ` (`stranger_detected` — chỉ hiện trên C260, tự tắt sau 30s)
* `Trạng thái kết nối Camera` (`connection`)

### 3. Cảm biến thông tin & Chẩn đoán (`sensor`)
* **Nhóm Khuôn mặt (C260)**: `Tên khuôn mặt (Face Name)`, `Mã khuôn mặt (Face ID)`, `Lần nhận diện gần nhất (Last Seen)`, `Số người quen (Known Faces)`, `Số người lạ (Unknown Faces)`, `Số người lạ hôm nay (Unknown Today)`, `Lần gặp người lạ gần nhất (Last Unknown Seen)`, `Số lần bỏ qua lặp khuôn mặt (Dedup Skipped)`.
* **Nhóm Chẩn đoán kết nối**: `Lần quét thành công gần nhất (Last Poll)`, `Thời gian phản hồi Camera (Response Time ms)`, `Số lỗi quét liên tiếp (Polling Errors)`, `Chế độ kết nối (Connection Mode)`.

### 4. Thực thể Sự kiện (`event`)
* `event.<ten_cam>_face_event`: Bắn sự kiện với 2 kiểu `face_recognized` và `face_unknown` để viết Automation trực tiếp trong giao diện UI của Home Assistant.
* Bắn đồng thời 2 sự kiện `tapo_local_ai_face_detected` và `tapo_c260_face_detected` lên Home Assistant Event Bus.

### 5. Còi báo động (`siren`) & Nút bấm (`button`)
* `siren.<ten_cam>_siren`: Còi hú tích hợp (hỗ trợ bật/tắt thủ công kèm `duration` tính bằng giây và `volume_level`).
* `button.<ten_cam>_ptz_move_up / down / left / right`: 4 nút xoay PTZ theo góc bước cài đặt.
* `button.<ten_cam>_ptz_calibrate`: Hiệu chuẩn lại motor xoay quét.
* `button.<ten_cam>_manual_alarm_start / stop`: Nút kích hoạt / dừng còi hú khẩn cấp.
* `button.<ten_cam>_reboot`: Khởi động lại camera từ xa qua mạng nội bộ.

### 6. Công tắc AI & Phần cứng (`switch`)
* 10 công tắc bật/tắt từng tính năng AI Detection riêng biệt.
* `Tự động xoay theo chuyển động` (`auto_track_switch` — chỉ có trên camera PTZ).
* `Chế độ riêng tư (Privacy Mode)` (`privacy_mode_switch` — cụp ống kính / đóng màn trập).
* `Đèn trạng thái LED` (`led_indicator_switch`).
* `Đảo ngược hình ảnh 180°` (`flip`).
* `Khử cong viền góc rộng` (`lens_distortion`).
* `Ghi hình thẻ nhớ microSD` (`record_to_sd`).
* `Tắt Micro phần cứng` (`microphone_mute`).
* `Tự động hú còi khi phát hiện AI` (`auto_alarm_switch`).

### 7. Thanh trượt số (`number`) & Hộp chọn (`select`)
* **Thanh trượt độ nhạy 10 mức (1–10)**: Độ nhạy chuyển động (`motion_sensitivity`), Người (`person_sensitivity`), Thú cưng (`pet_sensitivity`), Xe cộ (`vehicle_sensitivity`).
* **Hộp chọn độ nhạy 3 mức (`low`/`normal`/`high`)**: Tiếng khóc (`baby_cry_sensitivity`), Chó sủa (`bark_sensitivity`), Mèo kêu (`meow_sensitivity`), Kính vỡ (`glass_break_sensitivity`), Che khuất camera (`tamper_sensitivity`).
* **Điều khiển phần cứng**: Âm lượng Loa (0–100%), Âm lượng Micro (0–100%), Thời lượng hú còi (0–300s), Góc xoay mỗi bước (5°–360°), Chế độ nhìn đêm (`Infrared`/`Full-Color`/`Smart`), Tần số chống chớp đèn (`Auto`/`50Hz`/`60Hz`), Kiểu báo động (`sound`/`light`/`both`), Mức âm lượng còi (`low`/`normal`/`high`), Điểm nhớ Preset và Chế độ tuần tra PTZ.

---

## 🚀 Hướng dẫn Cài đặt

### Cách 1: Cài đặt tự động qua HACS (Khuyên dùng)
1. Mở Home Assistant $\rightarrow$ chọn **HACS** ở thanh bên trái.
2. Nhấp vào dấu **3 chấm** ở góc trên bên phải $\rightarrow$ chọn **Custom repositories (Kho lưu trữ tùy chỉnh)**.
3. Dán đường dẫn sau vào ô Repository:
   ```
   https://github.com/hungng-21/Tapo_camera_local_ai
   ```
4. Chọn danh mục: **Integration** $\rightarrow$ bấm **Add**.
5. Tìm kiếm `Tapo Camera Local AI` $\rightarrow$ bấm **Download** phiên bản mới nhất (`v2.0.1`).
6. Khởi động lại Home Assistant.

### Cách 2: Cài đặt thủ công (Manual)
1. Tải file `tapo_local_ai_v2.0.1_fixed.zip` từ trang [Releases](https://www.google.com/search?q=https://github.com/hungng-21/Tapo_camera_local_ai/releases).
2. Giải nén file, sao chép toàn bộ thư mục `tapo_local_ai` vào đường dẫn `/config/custom_components/` của Home Assistant (đường dẫn đầy đủ: `/config/custom_components/tapo_local_ai/`).
3. Khởi động lại Home Assistant.

---

## ⚙️ Cấu hình thêm Camera vào Home Assistant

1. Mở ứng dụng **Tapo** trên điện thoại: vào mục cài đặt camera $\rightarrow$ **Cài đặt nâng cao (Advanced Settings)** $\rightarrow$ **Tài khoản Camera (Camera Account)** $\rightarrow$ Tạo tài khoản cục bộ (Username & Password).
2. Trên Home Assistant: Vào **Cài đặt (Settings)** $\rightarrow$ **Thiết bị & Dịch vụ (Devices & Services)** $\rightarrow$ **Thêm tích hợp (Add Integration)** $\rightarrow$ Tìm kiếm **Tapo Camera Local AI**.
3. Điền các thông số:
   * **Host**: Địa chỉ IP nội bộ của camera (ví dụ `192.168.1.100`, nên gán IP tĩnh trong router).
   * **Username**: Tên tài khoản Camera Account vừa tạo ở Bước 1.
   * **Password**: Mật khẩu Camera Account vừa tạo ở Bước 1.
   * **Cloud Password (Tùy chọn)**: Mật khẩu tài khoản TP-Link Cloud (cần thiết đối với dòng **Tapo C260** hoặc firmware mới dùng mã hóa bảo mật KLAP/TPAP).
   * Các cổng mặc định: Điều khiển HTTPS (`443`), ONVIF (`2020`), RTSP (`554`).
4. Bấm **Gửi (Submit)**. Camera sẽ được kết nối ngay lập tức!
5. Nhấn **Ctrl + F5** trên trình duyệt máy tính để nạp bảng điều khiển **Tapo Face Manager** ở thanh bên (nếu camera có hỗ trợ Face AI).

---

## 💡 Ví dụ Automation thông minh mẫu

### 1. Chào đón người nhà khi về đến cửa (Nhận diện khuôn mặt C260)
```yaml
alias: "Camera C260 - Chào người quen"
trigger:
  - platform: event
    event_type: tapo_local_ai_face_detected
    event_data:
      recognized: true
action:
  - service: tts.speak
    target:
      entity_id: media_player.loa_phong_khach
    data:
      media_player_entity_id: media_player.loa_phong_khach
      message: "Chào mừng {{ trigger.event.data.name }} đã về nhà!"
```

### 2. Báo động ngay lập tức khi phát hiện người lạ
```yaml
alias: "Camera C260 - Cảnh báo Người lạ"
trigger:
  - platform: state
    entity_id: binary_sensor.tapo_c260_stranger_detected
    to: "on"
action:
  - service: notify.mobile_app_dien_thoai
    data:
      title: "⚠️ Cảnh báo an ninh!"
      message: "Phát hiện khuôn mặt người lạ tại camera {{ trigger.to_state.name }}!"
      data:
        image: "/api/camera_proxy/camera.tapo_c260_hd_stream"
```

### 3. Tự động bật đèn khi phát hiện tiếng em bé khóc vào ban đêm
```yaml
alias: "Trông trẻ - Bật đèn khi bé khóc"
trigger:
  - platform: state
    entity_id: binary_sensor.tapo_camera_baby_cry
    to: "on"
condition:
  - condition: time
    after: "21:00:00"
    before: "06:00:00"
action:
  - service: light.turn_on
    target:
      entity_id: light.den_ngu
    data:
      brightness_pct: 20
```

---

## ❓ Câu hỏi thường gặp (FAQ)

&lt;details&gt;
&lt;summary&gt;&lt;b&gt;1. Tôi cập nhật từ v2.0.0 lên v2.0.1 thì camera đang có sẵn có bị ảnh hưởng không?&lt;/b&gt;&lt;/summary&gt;
Hoàn toàn &lt;b&gt;KHÔNG&lt;/b&gt;. Bản v2.0.1 tương thích ngược 100%. Tất cả Entity ID, tên gọi, các thẻ trên Dashboard và Automation bạn đã tạo từ trước đều được giữ nguyên vẹn.
&lt;/details&gt;

&lt;details&gt;
&lt;summary&gt;&lt;b&gt;2. Camera của tôi là C125 / C225 thì bấm nút bánh răng có bị hiện menu Face ID thừa không?&lt;/b&gt;&lt;/summary&gt;
&lt;b&gt;KHÔNG&lt;/b&gt;. Bản v2.0.1 tự động phát hiện mã phần cứng camera. Với C125/C225, bấm nút bánh răng sẽ mở thẳng vào form chỉnh IP/kết nối; thanh bên Face Manager cũng tự động ẩn đi để giao diện Home Assistant luôn sạch sẽ.
&lt;/details&gt;

&lt;details&gt;
&lt;summary&gt;&lt;b&gt;3. Tại sao camera C125 trước đây bị mất kết nối 5 phút rồi tự có lại?&lt;/b&gt;&lt;/summary&gt;
Đó là cơ chế bảo mật khóa IP 300 giây (mã lỗi &lt;code&gt;-40404&lt;/code&gt;) của firmware Tapo khi có nhiều lần thử mật khẩu sai liên tiếp. Bản v2.0.1 đã lưu cố định thông tin xác thực thành công và tắt luồng C260 thừa, chấm dứt hoàn toàn tình trạng này.
&lt;/details&gt;

---

## 🤝 Đóng góp & Bản quyền

Dự án được phát triển và duy trì bởi [@hungng-21](https://www.google.com/search?q=https://github.com/hungng-21) cùng sự đóng góp giải pháp Nhận diện khuôn mặt từ [@quangtienhn](https://www.google.com/search?q=https://github.com/quangtienhn).

Phát hành theo giấy phép mã nguồn mở **MIT License**.
