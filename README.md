# 📷 Tapo Camera Local AI (v1.3.1)

**Home Assistant Custom Component** kết nối **100% nội bộ (Local LAN)** cho các dòng camera TP-Link Tapo (C125, C200, C210, C220, C225, C310, C320WS, C325WB, C500, C510W, C520WS, C560WS...), hỗ trợ đầy đủ cảm biến sự kiện AI, điều chỉnh độ nhạy AI (chuẩn 10 mức cho hình ảnh & 3 mức cho âm thanh), còi báo động Siren, xử lý hình ảnh & bảo mật phần cứng, bộ điều khiển xoay PTZ và luồng video RTSP.

[version](https://www.google.com/url?sa=E&source=gmail&q=https://github.com/hungng-21/Tapo_camera_local_ai)
[](https://hacs.xyz/)
[](https://www.home-assistant.io/)

## 🌟 Giới thiệu

Tích hợp này cung cấp giải pháp kết nối **hoàn toàn cục bộ (100% Local)** giữa camera Tapo và Home Assistant, không phụ thuộc vào kết nối Internet hay dịch vụ đám mây TP-Link Cloud khi vận hành.

**Giải quyết triệt để điểm nghẽn lớn nhất của camera Tapo trên Home Assistant**: Firmware gốc của Tapo không phát sự kiện âm thanh AI (Tiếng khóc trẻ em, Tiếng chó sủa, Mèo kêu, Kính vỡ) qua luồng ONVIF tiêu chuẩn. Bằng kiến trúc **Hybrid Local** kết hợp giữa quét sự kiện nội bộ `searchDetectionList` và luồng đẩy `ONVIF PullPoint`, tích hợp đưa toàn bộ các sự kiện AI này lên thành các thực thể `binary_sensor` độc lập để kích hoạt các kịch bản tự động hóa trong tích tắc.

## ✨ Tính năng nổi bật

* 🎯 **Nhận diện trọn bộ sự kiện AI (`binary_sensor`)**: Tự động tạo cảm biến cho **Tiếng em bé khóc (Baby Cry)**, **Tiếng chó sủa (Dog Bark)**, **Tiếng mèo kêu (Cat Meow)**, **Kính vỡ (Glass Break)**, **Phát hiện người (AI Person)**, **Thú cưng (AI Pet)**, **Phương tiện (AI Vehicle)**, **Chuyển động**, **Vượt hàng rào ảo** và **Che khuất camera (Tamper)**.
* 🎚️ **Chỉnh độ nhạy AI chuẩn theo từng loại cảm biến**:
  * **Nhóm AI Hình ảnh & Chuyển động (`number` kéo 10 mức `1` – `10`)**: Dành cho **Phát hiện chuyển động (Motion)**, **AI Phát hiện người (Person)**, **AI Thú cưng (Pet)** và **AI Phương tiện (Vehicle)**.
  * **Nhóm AI Âm thanh & Tamper (`select` chọn 3 mức `low` / `normal` / `high`)**: Dành cho **Tiếng khóc trẻ em (Baby Cry)**, **Tiếng chó sủa (Dog Bark)**, **Tiếng mèo kêu (Cat Meow)**, **Tiếng kính vỡ (Glass Break)** và **Che khuất camera (Tamper)**.
* 🚨 **Thực thể Còi hú chuẩn HA (`siren`) & Âm thanh**: Tích hợp thực thể `siren.<cam>_siren` hỗ trợ bật/tắt còi kèm thời lượng (`duration`) và âm lượng (`volume_level`), đi kèm bộ chọn **Mức âm lượng còi (`low` / `normal` / `high`)**, **Kiểu báo động (`sound` / `light` / `both`)**, thanh trượt **Thời gian hú còi (`0-300s`)**, **Âm lượng loa ngoài (`0-100%`)** và **Âm lượng thu Micro (`0-100%`)**.
* 🛡️ **Xử lý Hình ảnh & Bảo mật phần cứng (`switch` & `select`)**:
  * `switch.<cam>_flip`: Đảo ngược hình ảnh 180° (khi lắp camera treo ngược trần nhà).
  * `switch.<cam>_lens_distortion`: Khử cong viền hình ảnh góc rộng (Lens Distortion Correction).
  * `switch.<cam>_record_to_sd`: Bật/tắt chế độ ghi hình vào thẻ nhớ microSD (giữ nguyên lịch trình ghi hình trong tuần).
  * `switch.<cam>_microphone_mute`: Tắt micro phần cứng (bảo vệ quyền riêng tư tuyệt đối khi ở nhà).
  * `select.<cam>_night_vision_mode`: Chuyển chế độ nhìn đêm: `Infrared` (Hồng ngoại) / `Full-Color` (Có màu) / `Smart` (Tự động bật sáng khi có chuyển động).
  * `select.<cam>_light_frequency`: Chỉnh tần số `Auto` / `50Hz` / `60Hz` (khử hiện tượng đèn LED trong phòng bị chớp nháy sọc đen khi quay video).
* 🔄 **Tự động nhận diện & Điều khiển xoay PTZ**: Đối với các dòng xoay như **C225, C220, C520WS**, tích hợp tự động tạo cụm nút bấm 4 hướng (`Move Up`, `Move Down`, `Move Left`, `Move Right`), nút hiệu chuẩn (`Calibrate`), thanh trượt góc xoay (`Movement Angle`), menu góc quay nhớ (`Move to Preset`) và chế độ tuần tra (`Patrol Mode`). Đối với camera cố định như **C125**, các nút xoay tự động ẩn để giữ giao diện gọn gàng.
* ⚡ **Đồng bộ 2 chiều siêu tốc (`~3 giây`)**: Gom toàn bộ trạng thái công tắc, độ nhạy AI, cấu hình hình ảnh và âm thanh vào **1 gói tin HTTP duy nhất (`multipleRequest`)** mỗi 3 giây.
* 🔒 **Tự động dò xác thực đa phương thức (Multi-Auth Fallback)**: Tương thích với cả firmware cũ lẫn firmware đời mới sử dụng mã hóa nội bộ `KLAP` / `TPAP` / `SPAKE2+` (`admin` + `cloud_password`), tích hợp cơ chế chống khóa IP camera.

## 🛠️ Yêu cầu hệ thống

1. Đã cài đặt **Home Assistant** (phiên bản `2024.6.0` trở lên).
2. Camera Tapo đã tạo tài khoản nội bộ (**Camera Account**) trong ứng dụng Tapo (*Cài đặt nâng cao → Tài khoản Camera*).
3. Đã lắp **thẻ nhớ microSD** trên camera (bắt buộc để camera kích hoạt ghi nhật ký sự kiện âm thanh AI nội bộ `searchDetectionList`).
4. Đã bật tính năng **Khả năng tương thích của bên thứ ba (Third-Party Compatibility)** trong app Tapo (*Tôi → Dịch vụ bên thứ ba*).

## 📊 Bảng ánh xạ các thực thể chính

### 1. Cảm biến sự kiện AI (`binary_sensor`)

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

### 2. Nhóm Độ nhạy AI, Còi hú Siren & Phần cứng (`siren`, `number`, `select`, `switch`)

| Nhóm chức năng | Thực thể (`entity_id`) | Phạm vi / Tùy chọn | Mô tả |
| :--- | :--- | :--- | :--- |
| **Độ nhạy AI Hình ảnh (10 mức)** | `number.<cam>_motion_sensitivity`<br>`number.<cam>_person_sensitivity`<br>`number.<cam>_pet_sensitivity`<br>`number.<cam>_vehicle_sensitivity` | Thanh trượt `1` – `10` | Chỉnh độ nhạy 10 mức cho Chuyển động, AI Người, AI Thú cưng, AI Xe cộ |
| **Độ nhạy AI Âm thanh & Tamper (3 mức)** | `select.<cam>_baby_cry_sensitivity`<br>`select.<cam>_bark_sensitivity`<br>`select.<cam>_meow_sensitivity`<br>`select.<cam>_glass_break_sensitivity`<br>`select.<cam>_tamper_sensitivity` | `low` / `normal` / `high` | Chọn 3 mức độ nhạy cho Tiếng khóc trẻ em, Chó sủa, Mèo kêu, Kính vỡ và Che khuất camera |
| **Còi báo động** | `siren.<cam>_siren` | `turn_on` / `turn_off` | Bật/tắt còi hú trực tiếp, hỗ trợ truyền `duration` và `volume_level` |
| **Cấu hình Còi hú** | `select.<cam>_siren_volume_level`<br>`number.<cam>_siren_duration`<br>`select.<cam>_alarm_mode` | `low` / `normal` / `high`<br>Thời gian `0–300s`<br>`sound` / `light` / `both` | Cài đặt mức âm lượng còi, thời gian hú tự ngắt và chế độ kết hợp đèn/còi |
| **Âm lượng Đàm thoại** | `number.<cam>_speaker_volume`<br>`number.<cam>_microphone_volume` | `0%` – `100%` | Điều chỉnh âm lượng loa ngoài và độ nhạy thu âm của Micro |
| **Hình ảnh & Bảo mật** | `switch.<cam>_flip`<br>`switch.<cam>_lens_distortion`<br>`switch.<cam>_record_to_sd`<br>`switch.<cam>_microphone_mute` | `ON` / `OFF` | Lật ảnh 180°, Khử cong ống kính, Ghi hình thẻ nhớ SD, Tắt Micro phần cứng |
| **Chế độ Đêm & Tần số** | `select.<cam>_night_vision_mode`<br>`select.<cam>_light_frequency` | `Infrared` / `Full-Color` / `Smart`<br>`Auto` / `50Hz` / `60Hz` | Chuyển chế độ nhìn đêm và khử nhấp nháy đèn điện trong phòng |

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

1. Tải gói `tapo_local_ai.zip` hoặc toàn bộ mã nguồn repository về máy tính.
2. Sao chép thư mục `tapo_local_ai` vào `/config/custom_components/tapo_local_ai` trên máy chủ Home Assistant.
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

### 1. Cảnh báo điện thoại & hú còi 10 giây khi phát hiện người ban đêm

```yaml
alias: "An ninh ban đêm: Phát hiện người & Hú còi Siren 10s"
triggers:
  - trigger: state
    entity_id: binary_sensor.tapo_c225_person
    from: "off"
    to: "on"
conditions:
  - condition: time
    after: "23:00:00"
    before: "05:30:00"
actions:
  - action: siren.turn_on
    target:
      entity_id: siren.tapo_c225_siren
    data:
      duration: 10
      volume_level: 0.8
  - action: notify.mobile_app_dien_thoai
    data:
      title: "🚨 Cảnh báo xâm nhập!"
      message: "Phát hiện người tại {{ state_attr(trigger.entity_id, 'friendly_name') }} lúc {{ now().strftime('%H:%M:%S') }}."
mode: single
```

### 2. Tự động tăng độ nhạy AI vào ban đêm và giảm vào ban ngày

```yaml
alias: "Camera Tapo: Tự động tối ưu độ nhạy AI Ngày/Đêm"
triggers:
  - trigger: time
    at: "22:30:00"
    id: "night_mode"
  - trigger: time
    at: "06:30:00"
    id: "day_mode"
actions:
  - choose:
      - conditions:
          - condition: trigger
            id: "night_mode"
        sequence:
          - action: number.set_value
            target:
              entity_id:
                - number.tapo_c125_person_sensitivity
                - number.tapo_c125_motion_sensitivity
            data:
              value: 9
          - action: select.select_option
            target:
              entity_id:
                - select.tapo_c125_baby_cry_sensitivity
                - select.tapo_c125_bark_sensitivity
            data:
              option: "high"
      - conditions:
          - condition: trigger
            id: "day_mode"
        sequence:
          - action: number.set_value
            target:
              entity_id:
                - number.tapo_c125_person_sensitivity
                - number.tapo_c125_motion_sensitivity
            data:
              value: 5
          - action: select.select_option
            target:
              entity_id:
                - select.tapo_c125_baby_cry_sensitivity
                - select.tapo_c125_bark_sensitivity
            data:
              option: "normal"
```

## 📜 Giấy phép & Lời cảm ơn

* Giấy phép mã nguồn mở: **MIT License**.
* Giao thức truyền thông nội bộ được phát triển dựa trên thư viện [pytapo](https://github.com/JurajNyiri/pytapo) và [onvif-zeep-async](https://github.com/hunterjm/python-onvif-zeep-async).
* Trân trọng cảm ơn cộng đồng [HomeAssistant-Tapo-Control](https://github.com/jurajnyiri/homeassistant-tapo-control) với các nghiên cứu phân tích mã `alarm_type` và cờ sự kiện AI camera Tapo.
