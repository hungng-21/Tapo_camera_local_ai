# Tapo Camera Local AI — Ultimate Edition (v2.0.0)

[Version](https://www.google.com/search?q=https://github.com/hungng-21/Tapo_camera_local_ai)
[](https://www.home-assistant.io/)
[](https://www.home-assistant.io/)

**Tapo Camera Local AI (v2.0.0 Ultimate Edition)** là bộ tích hợp (Custom Component) toàn diện nhất dành cho camera **TP-Link Tapo** trên **Home Assistant**, hoạt động **100% nội bộ (Local LAN)** không phụ thuộc đám mây, kết hợp hoàn hảo giữa:
1. **Toàn bộ hệ thống AI Detection, Điều khiển PTZ, Còi hú (Siren) & Phần cứng nội bộ** (`tapo_local_ai`).
2. **Hệ thống Nhận diện Khuôn mặt AI (Face Recognition) & Bảng điều khiển "Tapo Face Manager" trên Sidebar** (hợp nhất từ dự án [tapo-c260-face](https://www.google.com/search?q=https://github.com/quangtienhn/tapo-c260-face) của `@quangtienhn`), dùng chung **duy nhất 1 phiên kết nối Local** để loại bỏ hoàn toàn xung đột kết nối cổng 443.

---

## Điểm mới nổi bật trong phiên bản v2.0.0 (Ultimate Edition)

### 1. Nhận diện Khuôn mặt AI & Bảng điều khiển "Tapo Face Manager" (Sidebar Panel)
- **Tự động phát hiện và phân loại khuôn mặt**: Đọc trực tiếp dữ liệu `event_info.face_id` từ chip AI trên camera (đặc biệt trên **Tapo C260** và các dòng hỗ trợ Face AI), đối chiếu với danh sách người quen hoặc tự động ghi nhận vào danh sách **Người lạ (Unknown Faces)**.
- **Bảng điều khiển "Tapo Face Manager" trực tiếp trên thanh bên (Sidebar)**:
  - **Tab Người quen (Known)**: Thêm mới, đổi tên, sửa mã Face ID (tự động gộp lịch sử cũ sang ID mới) hoặc xóa người quen.
  - **Tab Người lạ (Unknown)**: Liệt kê toàn bộ các mã Face ID lạ mà camera đã bắt gặp (kèm thời gian gặp lần đầu, lần cuối và tổng số lần xuất hiện). Hỗ trợ bấm **"+ Thêm người"** để đặt tên ngay chỉ với 1 cú nhấp chuột, hoặc **"Bỏ qua"** để xóa.
  - **Tab Lịch sử ngày (Day History)**: Biểu đồ vạch 24h trực quan hiển thị chính xác từng người xuất hiện vào những khung giờ nào trong ngày.
  - **Tab Thống kê (Statistics)**: Biểu đồ cột và bảng thống kê tần suất xuất hiện của người quen / người lạ theo 7 ngày, 30 ngày, 90 ngày, ngày cao điểm và danh sách người lạ xuất hiện nhiều nhất.
  - **Tab Cài đặt & Thẻ Sức khỏe kết nối (Health Card)**: Theo dõi độ trễ phản hồi (ms), trạng thái kết nối, số sự kiện xử lý và tùy chỉnh nhanh chu kỳ quét, thời gian chống lặp (Dedup), giới hạn lưu trữ ngay trên giao diện Web (hỗ trợ song ngữ **Tiếng Việt / Tiếng Anh**).

### 2. Hệ thống Thực thể Nhận diện Khuôn mặt & Chẩn đoán mới
Tất cả được gom chung vào **cùng 1 Thiết bị Camera duy nhất** trong Home Assistant:
- **Cảm biến (Sensors)**:
  - `sensor.<ten_camera>_face_name`: Tên người vừa nhận diện (hoặc `Stranger`).
  - `sensor.<ten_camera>_face_id`: Mã số Face ID hiện tại.
  - `sensor.<ten_camera>_last_seen`: Thời điểm nhận diện khuôn mặt gần nhất.
  - `sensor.<ten_camera>_known_faces`: Tổng số khuôn mặt người quen đã khai báo.
  - `sensor.<ten_camera>_unknown_faces`: Tổng số khuôn mặt người lạ đã phát hiện.
  - `sensor.<ten_camera>_unknown_today`: Số lần người lạ xuất hiện trong ngày hôm nay.
  - `sensor.<ten_camera>_last_unknown_seen`: Thời điểm cuối cùng thấy người lạ.
  - Các cảm biến chẩn đoán (Diagnostic): `Last Successful Poll`, `Response Time (ms)`, `Polling Errors`, `Connection Mode`, `Dedup Skipped`.
- **Cảm biến nhị phân Khuôn mặt & Kết nối (Binary Sensors)**:
  - `binary_sensor.<ten_camera>_face_recognized`: Bật `ON` khi khuôn mặt hiện tại là người quen.
  - `binary_sensor.<ten_camera>_stranger_detected`: Bật `ON` ngay khi phát hiện người lạ và tự động tắt sau `stranger_clear_seconds` (mặc định 30 giây).
  - `binary_sensor.<ten_camera>_connection`: Trạng thái kết nối thực tế tới camera.
- **Thực thể Sự kiện (Event Entity) & Event Bus**:
  - `event.<ten_camera>_face_event`: Dùng làm Trigger trực tiếp trên giao diện Automation (`face_recognized` / `face_unknown`).
  - Phát đồng thời sự kiện `tapo_local_ai_face_detected` và `tapo_c260_face_detected` lên Home Assistant Event Bus.

---

## Tổng hợp toàn bộ tính năng có sẵn

| Nhóm tính năng | Thực thể cung cấp trong Home Assistant |
| :--- | :--- |
| **Luồng hình ảnh RTSP** | 2 thực thể `camera` (**Luồng chính HD/2K/4K** `stream1` & **Luồng phụ SD** `stream2`), hỗ trợ PTZ qua dịch vụ `onvif.ptz` |
| **15 Cảm biến nhị phân AI & Khuôn mặt (`binary_sensor`)** | Tiếng khóc trẻ em (`baby_cry`), Chó sủa (`bark`), Mèo kêu (`meow`), Kính vỡ (`glass_break`), Người (`person`), Thú cưng (`pet`), Phương tiện (`vehicle`), Chuyển động (`motion`), Vượt rào ảo (`line_crossing`), Xâm nhập vùng cấm (`area_intrusion`), Che khuất camera (`tamper`), Bưu kiện (`package`), **Người quen (`face_recognized`)**, **Người lạ (`stranger_detected`)**, **Kết nối (`connection`)** |
| **17 Công tắc AI & Phần cứng (`switch`)** | Bật/tắt từng loại AI Detection, Tự động xoay theo chuyển động (`auto_track_switch`), Chế độ riêng tư (`privacy_mode_switch`), Đèn LED (`led_indicator_switch`), Đảo ngược ảnh 180° (`flip`), Khử cong góc rộng (`lens_distortion`), Ghi hình thẻ nhớ (`record_to_sd`), Tắt Micro (`microphone_mute`), Tự động hú còi (`auto_alarm_switch`) |
| **Thanh trượt Độ nhạy 10 mức (`number`)** | Dành riêng cho 4 cảm biến Hình ảnh & Chuyển động có thang 1–10 trong app Tapo: **Motion**, **Person**, **Pet**, **Vehicle** (cùng Âm lượng Loa 0–100%, Âm lượng Micro 0–100%, Thời lượng hú còi 0–300s, Góc xoay PTZ 5°–360°) |
| **Hộp chọn Độ nhạy 3 mức (`select`)** | Dành riêng cho 5 cảm biến Âm thanh & Tamper chỉ có 3 mức (`low` / `normal` / `high`): **Baby Cry**, **Dog Bark**, **Cat Meow**, **Glass Break**, **Tamper** (cùng Chế độ nhìn đêm `Infrared`/`Full-Color`/`Smart`, Tần số chống nhấp nháy `Auto`/`50Hz`/`60Hz`, Kiểu báo động `sound`/`light`/`both`, Âm lượng còi `low`/`normal`/`high`, Điểm nhớ Preset & Tuần tra PTZ) |
| **Còi báo động (`siren`) & Nút bấm (`button`)** | Thực thể `siren` gốc (hỗ trợ `siren.turn_on` kèm `duration` và `volume_level`) + 4 nút xoay PTZ (`Lên`, `Xuống`, `Trái`, `Phải`), `Hiệu chuẩn PTZ`, `Hú còi`, `Tắt còi`, `Khởi động lại camera` |

---

## Hướng dẫn Cài đặt & Cập nhật

1. Giải nén file **`tapo_local_ai.zip`**.
2. Sao chép thư mục `custom_components/tapo_local_ai` vào thư mục `/config/custom_components/` của Home Assistant (ghi đè lên bản cũ nếu đang dùng v1.x — toàn bộ cấu hình camera đang có sẽ được **giữ nguyên 100%**).
3. Khởi động lại Home Assistant.
4. Nhấn **Ctrl + F5** trên trình duyệt để tải giao diện **Tapo Face Manager** ở thanh bên trái (Sidebar) của Home Assistant.

---

## Ví dụ Automation mẫu với Nhận diện Khuôn mặt

### Chào người quen khi về nhà (có chống lặp thông báo)
```yaml
alias: "Chào người quen qua Camera Tapo"
trigger:
  - platform: event
    event_type: tapo_local_ai_face_detected
    event_data:
      recognized: true
action:
  - service: notify.mobile_app_dien_thoai
    data:
      title: "🏠 Người nhà vừa về"
      message: "Camera {{ trigger.event.data.camera }} vừa nhận diện {{ trigger.event.data.name }} (ID: {{ trigger.event.data.face_id }})"
```

### Cảnh báo ngay khi phát hiện Người lạ
```yaml
alias: "Cảnh báo phát hiện người lạ"
trigger:
  - platform: state
    entity_id: binary_sensor.tapo_c260_stranger_detected
    to: "on"
action:
  - service: notify.mobile_app_dien_thoai
    data:
      title: "⚠️ Cảnh báo Người lạ!"
      message: "Camera vừa phát hiện khuôn mặt lạ (Mã Face ID: {{ states('sensor.tapo_c260_face_id') }})"
```
