# 📷 Tapo Camera Local AI (v1.2.3)

**Home Assistant Custom Component** kết nối **100% nội bộ (Local LAN)** cho các dòng camera TP-Link Tapo (C125, C200, C210, C220, C225, C310, C320WS, C325WB, C500, C510W, C520WS, C560WS...), hỗ trợ đầy đủ các cảm biến sự kiện AI, bộ nút điều khiển xoay PTZ và luồng hình ảnh RTSP.

[version](https://www.google.com/url?sa=E&source=gmail&q=https://github.com/hungng-21/Tapo_camera_local_ai)
[](https://hacs.xyz/)
[](https://www.home-assistant.io/)

## 🌟 Giới thiệu

Tích hợp này cung cấp giải pháp kết nối **hoàn toàn cục bộ (100% Local)** giữa camera Tapo và Home Assistant, không phụ thuộc vào kết nối Internet hay dịch vụ đám mây TP-Link Cloud khi vận hành.

**Giải quyết triệt để điểm nghẽn lớn nhất của camera Tapo trên Home Assistant**: Firmware gốc của Tapo không phát sự kiện âm thanh AI (Tiếng khóc trẻ em, Tiếng chó sủa, Mèo kêu, Kính vỡ) qua luồng ONVIF tiêu chuẩn. Bằng kiến trúc **Hybrid Local** kết hợp giữa quét sự kiện nội bộ `searchDetectionList` và luồng đẩy `ONVIF PullPoint`, tích hợp đưa toàn bộ các sự kiện AI này lên thành các thực thể `binary_sensor` độc lập để kích hoạt các kịch bản tự động hóa trong tích tắc.

## ✨ Tính năng nổi bật

* 🎯 **Nhận diện trọn bộ sự kiện AI (AI Detection Sensors)**: Tự động tạo cảm biến cho **Tiếng em bé khóc (Baby Cry)**, **Tiếng chó sủa (Dog Bark)**, **Tiếng mèo kêu (Cat Meow)**, **Kính vỡ (Glass Break)**, **Phát hiện người (AI Person)**, **Thú cưng (AI Pet)**, **Phương tiện (AI Vehicle)**, **Chuyển động**, **Vượt hàng rào ảo** và **Che khuất camera (Tamper)**.
* 🔄 **Tự động nhận diện & Điều khiển xoay PTZ**: Tự động kiểm tra phần cứng motor camera. Đối với các dòng xoay như **C225, C220, C520WS**, tích hợp tự động tạo cụm nút bấm 4 hướng (`Move Up`, `Move Down`, `Move Left`, `Move Right`), nút hiệu chuẩn (`Calibrate`), thanh trượt góc xoay (`Movement Angle`), menu thả xuống danh sách góc quay nhớ (`Move to Preset`) và chế độ tuần tra (`Patrol Mode`). Đối với camera cố định như **C125**, các nút xoay sẽ tự động ẩn để giữ giao diện gọn gàng.
* ⚡ **Đồng bộ công tắc 2 chiều siêu tốc (`~3 giây`)**: Gom toàn bộ trạng thái công tắc cấu hình (`Chế độ riêng tư Privacy`, `Đèn LED`, `Auto Track`, `Bật/Tắt các bộ nhận diện AI`) vào **1 gói tin HTTP duy nhất (`multipleRequest`)** mỗi 3 giây. Bật/tắt trên app Tapo điện thoại thì Home Assistant lập tức nhảy trạng thái theo mà không cần Reload entry.
* 🔒 **Tự động dò xác thực đa phương thức (Multi-Auth Fallback)**: Tự động tương thích với cả firmware cũ lẫn firmware đời mới sử dụng mã hóa nội bộ `KLAP` / `TPAP` / `SPAKE2+` (`admin` + `cloud_password`), tích hợp cơ chế chống khóa IP camera.
* 📹 **2 Luồng Video RTSP & Chụp ảnh tức thì**: Cung cấp sẵn 2 thực thể camera `HD Stream` (`stream1`) và `SD Stream` (`stream2`) kết nối trực tiếp hoặc chuyển tiếp qua `go2rtc` mượt mà.

## 🛠️ Yêu cầu hệ thống

1. Đã cài đặt **Home Assistant** (phiên bản `2024.6.0` trở lên).
2. Camera Tapo đã tạo tài khoản nội bộ (**Camera Account**) trong ứng dụng Tapo (*Cài đặt nâng cao → Tài khoản Camera*).
3. Đã lắp **thẻ nhớ microSD** trên camera (bắt buộc để camera kích hoạt ghi nhật ký sự kiện âm thanh AI nội bộ `searchDetectionList`).
4. Đã bật tính năng **Khả năng tương thích của bên thứ ba (Third-Party Compatibility)** trong app Tapo (*Tôi → Dịch vụ bên thứ ba*).

## 📊 Bảng ánh xạ các thực thể AI

| Thực thể (`entity_id`) | Tên hiển thị | Mã `alarm_type` | Cờ nhận diện AI | `device_class` |
| :--- | :--- | :---: | :--- | :--- |
| `binary_sensor.<cam>_baby_cry` | Phát hiện tiếng khóc trẻ em | `7` | `IsBabyCry` / `bcd` | `sound` |
| `binary_sensor.<cam>_bark` | Phát hiện tiếng chó sủa | `11` | `IsBark` / `bark` | `sound` |
| `binary_sensor.<cam>_meow` | Phát hiện tiếng mèo kêu | `12` | `IsMeow` / `meow` | `sound` |
| `binary_sensor.<cam>_glass_break` | Phát hiện tiếng kính vỡ | `13` | `IsGlassBreak` / `glass` | `sound` |
| `binary_sensor.<cam>_person` | Phát hiện người (AI Person) | `6` | Bit 19 (`524288`) / `IsPeople` | `occupancy` |
| `binary_sensor.<cam>_pet` | Phát hiện thú cưng | `9` | `IsPet` (`TPSmartEvent`) | `motion` |
| `binary_sensor.<cam>_vehicle` | Phát hiện phương tiện | `8` | `IsVehicle` (`TPSmartEvent`) | `motion` |
| `binary_sensor.<cam>_motion` | Phát hiện chuyển động | `2` | Bit 1 (`2`) / `IsMotion` | `motion` |
| `binary_sensor.<cam>_line_crossing` | Vượt hàng rào ảo | `4` | Bit 8 (`256`) / `IsLineCross` | `motion` |
| `binary_sensor.<cam>_tamper` | Che khuất / Phá hoại camera | `3` | `IsTamper` | `tamper` |

## 🚀 Hướng dẫn Cài đặt

### Cách 1: Cài đặt qua HACS (Khuyên dùng)

1. Mở **HACS** trên Home Assistant → chọn mục **Integrations**.
2. Nhấn vào biểu tượng menu 3 chấm (`⋮`) ở góc trên bên phải → chọn **Custom repositories**.
3. Dán URL GitHub repository của bạn:
   ```text
   https://github.com/hungng-21/Tapo_camera_local_ai
   ```
4. Chọn phân loại (Category) là **Integration** rồi nhấn **Add**.
5. Tìm kiếm **Tapo Camera Local AI**, nhấn **Download** và khởi động lại Home Assistant.

### Cách 2: Cài đặt thủ công (Manual)

1. Tải toàn bộ mã nguồn repository về máy tính.
2. Sao chép thư mục `custom_components/tapo_local_ai` vào thư mục `/config/custom_components/tapo_local_ai` trên máy chủ Home Assistant của bạn.
3. Khởi động lại Home Assistant (**Developer Tools → YAML → Restart**).

## ⚙️ Cấu hình thiết bị

1. Trong Home Assistant, vào **Settings → Devices & Services → Add Integration**.
2. Tìm kiếm **Tapo Camera Local AI** và nhập các thông tin:
   * **Địa chỉ IP Camera (Host)**: Ví dụ `192.168.2.167`.
   * **Camera Account Username**: Tên tài khoản Camera nội bộ (ví dụ `Tapoc125`).
   * **Camera Account Password**: Mật khẩu Camera nội bộ.
   * **Mật khẩu TP-Link Cloud**: Mật khẩu tài khoản TP-Link/Tapo chính (cần thiết cho các dòng C125/C225 firmware mới).
   * **Chu kỳ quét sự kiện AI Local**: Mặc định `3 giây`.
   * **Thời gian giữ trạng thái ON cho Binary Sensor**: Mặc định `15 giây`.
3. Bấm **Submit** để hoàn tất kết nối. Bạn có thể bấm vào biểu tượng bánh răng **Configure (`⚙️`)** hoặc menu **Reconfigure** bất kỳ lúc nào để chỉnh sửa lại thông tin.

## 🤖 Kịch bản Tự động hóa mẫu (Automations)

### Cảnh báo loa & gửi ảnh khi phát hiện tiếng em bé khóc hoặc chó sủa

```yaml
alias: "Cảnh báo AI: Phát hiện tiếng em bé khóc hoặc chó sủa"
description: "Gửi thông báo điện thoại tức thì khi phát hiện âm thanh AI từ camera Tapo"
triggers:
  - trigger: state
    entity_id:
      - binary_sensor.tapo_c225_baby_cry
      - binary_sensor.tapo_c125_baby_cry
      - binary_sensor.tapo_c225_bark
    from: "off"
    to: "on"
actions:
  - action: notify.mobile_app_dien_thoai
    data:
      title: >
        {% if 'baby_cry' in trigger.entity_id %}
          👶 Cảnh báo: Phát hiện tiếng em bé khóc!
        {% else %}
          🐕 Cảnh báo: Phát hiện tiếng chó sủa!
        {% endif %}
      message: >
        Phát hiện âm thanh bất thường từ {{ state_attr(trigger.entity_id, 'friendly_name') }}
        vào lúc {{ now().strftime('%H:%M:%S') }}.
mode: queued
```

## 📜 Giấy phép & Lời cảm ơn

* Giấy phép mã nguồn mở: **MIT License**.
* Giao thức truyền thông nội bộ được phát triển dựa trên thư viện [pytapo](https://github.com/JurajNyiri/pytapo) và [onvif-zeep-async](https://github.com/hunterjm/python-onvif-zeep-async).
* Trân trọng cảm ơn cộng đồng [HomeAssistant-Tapo-Control](https://github.com/jurajnyiri/homeassistant-tapo-control) với các nghiên cứu phân tích mã `alarm_type` và cờ sự kiện AI camera Tapo.