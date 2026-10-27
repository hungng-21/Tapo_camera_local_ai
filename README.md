# Tapo Camera Local AI (`tapo_local_ai`)

Bộ tích hợp tùy chỉnh (**Custom Component**) dành cho **Home Assistant**, giúp kết nối **100% nội bộ (Local)** các dòng camera thông minh **TP-Link Tapo** (C125, C200, C210, C220, C225, C310, C320WS, C325WB, C500, C510W, C520WS, C560WS...).

Điểm nổi bật nhất của tích hợp là khả năng giải mã và đưa **toàn bộ sự kiện AI trên camera** — đặc biệt là các sự kiện âm thanh AI như **Phát hiện tiếng khóc trẻ em (Baby Cry)**, **Tiếng chó sủa (Dog Bark)**, **Tiếng mèo kêu (Cat Meow)**, **Tiếng kính vỡ (Glass Break)** vốn không được đẩy qua giao thức ONVIF tiêu chuẩn — lên thành các thực thể `binary_sensor` độc lập để kích hoạt tự động hóa (Automation) tức thì mà không cần đám mây (Cloud).

## Tính năng nổi bật

* **Kiến trúc Hybrid Local (ONVIF PullPoint + Local API Polling)**:
  * **ONVIF PullPoint (Cổng `2020`)**: Lắng nghe luồng sự kiện đẩy nội bộ thời gian thực (`< 1 giây`) cho chuyển động, phát hiện người, thú cưng và phương tiện mà không cần mở cổng Webhook.
  * **Local API Polling (`searchDetectionList` qua cổng `443`)**: Quét trực tiếp bộ nhớ sự kiện AI trên camera (tự động bù độ lệch múi giờ qua `getTimeCorrection()`) và giải mã chính xác mã `alarm_type` cùng cờ bitmask `events_1` (Bit 19 xác thực người bằng mạng nơ-ron nội bộ trên camera).
* **Tự động phát hiện phần cứng xoay PTZ (Pan / Tilt)**:
  * Tự động kiểm tra khả năng điều khiển motor (`isSupportingPresets` / `getMotorCapability`) của từng mẫu camera.
  * Trên các dòng camera có xoay (như **Tapo C225, C220, C520WS**): Tự động khởi tạo bộ nút xoay 4 hướng (`Move Up`, `Move Down`, `Move Left`, `Move Right`), nút hiệu chuẩn (`Calibrate`), thanh trượt chỉnh góc xoay mỗi bước (`Movement Angle`), danh sách điểm nhớ góc quay (`Move to Preset`), chế độ tuần tra (`Patrol Mode`) và công tắc bám đuổi mục tiêu (`Auto Track`).
  * Trên các dòng camera cố định (như **Tapo C125, C320WS**): Tự động ẩn các thực thể xoay PTZ để giữ giao diện gọn gàng.
* **Đồng bộ trạng thái công tắc 2 chiều theo thời gian thực (`~3 giây`)**:
  * Sử dụng cơ chế gom lệnh `multipleRequest` giúp đọc và đồng bộ toàn bộ công tắc cấu hình (`Privacy Mode`, `LED`, `Auto Track`, `Baby Cry`, `Dog Bark`, `Cat Meow`, `Glass Break`, `Person`, `Pet`, `Vehicle`, `Motion`) chỉ trong 1 gói tin HTTP duy nhất (~50ms). Khi bật/tắt trên ứng dụng Tapo điện thoại, trạng thái trên Home Assistant tự động cập nhật theo sau vài giây.
* **Xác thực đa phương thức tự động (Multi-Auth Fallback)**:
  * Tự động tương thích với cả firmware cũ (Camera Account) lẫn firmware mới sử dụng mã hóa `KLAP` / `TPAP` / `SPAKE2+` (`admin` + `cloud_password`), kèm cơ chế chống khóa IP tạm thời.
* **Luồng Video RTSP Nội bộ**:
  * Cung cấp sẵn 2 thực thể camera `HD Stream` (`stream1`) và `SD Stream` (`stream2`) cùng các dịch vụ (Actions) `tapo_local_ai.ptz_move` và `tapo_local_ai.ptz_goto_preset`.

## Danh sách các thực thể được tạo tự động

### 1. Cảm biến sự kiện AI (`binary_sensor`)

| Thực thể (`entity_id`) | Tên hiển thị | Mã `alarm_type` | Cờ `events_1` / Trường ONVIF | `device_class` |
| :--- | :--- | :---: | :--- | :--- |
| `binary_sensor.<cam>_baby_cry` | Phát hiện tiếng khóc trẻ em (Baby Cry) | `7` | `IsBabyCry` / `bcd` | `sound` |
| `binary_sensor.<cam>_bark` | Phát hiện tiếng chó sủa (Dog Bark) | `11` | `IsBark` / `bark` | `sound` |
| `binary_sensor.<cam>_meow` | Phát hiện tiếng mèo kêu (Cat Meow) | `12` | `IsMeow` / `meow` | `sound` |
| `binary_sensor.<cam>_glass_break` | Phát hiện tiếng kính vỡ (Glass Break) | `13` | `IsGlassBreak` / `glass` | `sound` |
| `binary_sensor.<cam>_person` | Phát hiện người (AI Person) | `6` | Bit 19 (`524288`) / `IsPeople` | `occupancy` |
| `binary_sensor.<cam>_pet` | Phát hiện thú cưng (AI Pet) | `9` | `IsPet` (`TPSmartEvent`) | `motion` |
| `binary_sensor.<cam>_vehicle` | Phát hiện phương tiện (AI Vehicle) | `8` | `IsVehicle` (`TPSmartEvent`) | `motion` |
| `binary_sensor.<cam>_motion` | Phát hiện chuyển động (Motion) | `2` | Bit 1 (`2`) / `IsMotion` | `motion` |
| `binary_sensor.<cam>_line_crossing` | Vượt hàng rào ảo (Line Crossing) | `4` | Bit 8 (`256`) / `IsLineCross` | `motion` |
| `binary_sensor.<cam>_area_intrusion` | Xâm nhập vùng cấm (Area Intrusion) | `5` | `IsIntrusion` | `tamper` |
| `binary_sensor.<cam>_tamper` | Che khuất / Phá hoại camera (Tamper) | `3` | `IsTamper` | `tamper` |
| `binary_sensor.<cam>_package` | Phát hiện bưu kiện (Package) | `15`, `16` | `IsPackage` | `occupancy` |

### 2. Công tắc cấu hình AI & Hệ thống (`switch`)

| Thực thể | Chức năng | Ghi chú |
| :--- | :--- | :--- |
| **Bật AI Phát hiện tiếng khóc** | Bật/tắt nhận diện tiếng khóc trẻ em (`setBCDConfig`) | Mọi camera hỗ trợ |
| **Bật AI Phát hiện chó sủa** | Bật/tắt nhận diện tiếng chó sủa (`setBarkDetectionConfig`) | Mọi camera hỗ trợ |
| **Bật AI Phát hiện mèo kêu** | Bật/tắt nhận diện tiếng mèo kêu (`setMeowDetectionConfig`) | Mọi camera hỗ trợ |
| **Bật AI Phát hiện kính vỡ** | Bật/tắt nhận diện tiếng kính vỡ (`setGlassDetectionConfig`) | Mọi camera hỗ trợ |
| **Bật AI Phát hiện người** | Bật/tắt nhận diện người (`setPersonDetectionConfig`) | Mọi camera hỗ trợ |
| **Bật AI Phát hiện thú cưng** | Bật/tắt nhận diện thú cưng (`setPetDetectionConfig`) | Mọi camera hỗ trợ |
| **Bật AI Phát hiện xe cộ** | Bật/tắt nhận diện xe cộ (`setVehicleDetectionConfig`) | Mọi camera hỗ trợ |
| **Bật Phát hiện chuyển động** | Bật/tắt phát hiện chuyển động (`setDetectionConfig`) | Mọi camera hỗ trợ |
| **Chế độ riêng tư (Privacy)** | Đóng/mở ống kính riêng tư (`setLensMaskConfig`) | Mọi camera hỗ trợ |
| **Đèn trạng thái LED** | Bật/tắt đèn báo trạng thái trên thân camera (`setLedStatus`) | Mọi camera hỗ trợ |
| **Tự động xoay theo chuyển động (Auto Track)** | Bật/tắt xoay bám đuổi mục tiêu (`setTargetTrackConfig`) | Chỉ hiện trên camera có PTZ |

### 3. Bảng điều khiển xoay PTZ & Tác vụ (`button`, `select`, `number`)

| Thực thể | Loại | Hiển thị trên | Chức năng |
| :--- | :--- | :--- | :--- |
| **Move Up / Down / Left / Right** | `button` | Camera PTZ | Quay camera Lên, Xuống, Trái, Phải theo góc bước |
| **Calibrate (Hiệu chuẩn xoay)** | `button` | Camera PTZ | Hiệu chuẩn lại vị trí gốc của motor |
| **Move to Preset (Điểm nhớ góc quay)** | `select` | Camera PTZ | Chọn và di chuyển tới các góc quay đã lưu trong app Tapo |
| **Patrol Mode (Chế độ tuần tra)** | `select` | Camera PTZ | Chế độ tuần tra liên tục (`Off`, `Horizontal`, `Vertical`) |
| **Movement Angle (Góc xoay mỗi bước)** | `number` | Camera PTZ | Điều chỉnh số độ mỗi lần bấm nút quay (`5°` – `360°`, mặc định `15°`) |
| **Manual Alarm Start / Stop** | `button` | Mọi camera | Kích hoạt hoặc tắt còi hú báo động khẩn cấp trên camera |
| **Reboot (Khởi động lại Camera)** | `button` | Mọi camera | Khởi động lại camera từ xa |

## Cấu trúc thư mục chuẩn trên GitHub (HACS Ready)

Để kho lưu trữ GitHub của bạn có thể thêm trực tiếp vào **HACS (Custom Repositories)**, hãy sắp xếp cấu trúc tệp ở thư mục gốc của repo như sau:

```text
tapo-local-ai/
├── README.md
├── hacs.json
└── custom_components/
    └── tapo_local_ai/
        ├── __init__.py
        ├── binary_sensor.py
        ├── button.py
        ├── camera.py
        ├── config_flow.py
        ├── const.py
        ├── coordinator.py
        ├── manifest.json
        ├── number.py
        ├── select.py
        ├── strings.json
        ├── switch.py
        ├── brand/
        │   ├── icon.png
        │   └── logo.png
        └── translations/
            ├── en.json
            └── vi.json
```

Nội dung tệp `hacs.json` đặt ở thư mục gốc của GitHub repo:

```json
{
  "name": "Tapo Camera Local AI",
  "render_readme": true,
  "homeassistant": "2024.6.0"
}
```

## Chuẩn bị trên ứng dụng Tapo

1. **Tạo tài khoản Camera nội bộ (Camera Account)**:
   Mở ứng dụng **Tapo** trên điện thoại → chọn Camera → **Cài đặt (Settings)** → **Cài đặt nâng cao (Advanced Settings)** → **Tài khoản Camera (Camera Account)** và thiết lập `Username` / `Password`.
2. **Bật tương thích bên thứ ba (Third-Party Compatibility)**:
   Tại ứng dụng **Tapo** → vào tab **Tôi (Me)** → **Dịch vụ của bên thứ ba (Third-Party Services)** → bật **Third-Party Compatibility**.
3. **Thẻ nhớ microSD**:
   Để camera ghi nhận nhật ký sự kiện âm thanh AI (`searchDetectionList` cho tiếng khóc trẻ em, chó sủa, mèo kêu, kính vỡ), camera cần được lắp thẻ nhớ microSD.

## Hướng dẫn cài đặt vào Home Assistant

### Cách 1: Cài đặt qua HACS (Custom Repository)

1. Mở **HACS** trên Home Assistant → chọn mục **Integrations**.
2. Nhấn vào biểu tượng menu 3 chấm (`⋮`) ở góc trên bên phải → chọn **Custom repositories**.
3. Dán đường dẫn URL GitHub repository của bạn vào ô **Repository**, chọn phân loại **Integration** rồi nhấn **Add**.
4. Tìm **Tapo Camera Local AI** trong danh sách, nhấn **Download** và khởi động lại Home Assistant.

### Cách 2: Cài đặt thủ công (Manual)

1. Tải mã nguồn về và chép thư mục `custom_components/tapo_local_ai` vào đường dẫn `/config/custom_components/tapo_local_ai` trên máy chủ Home Assistant.
2. Khởi động lại Home Assistant (**Developer Tools → YAML → Restart**).

## Thiết lập thiết bị

1. Vào **Settings → Devices & Services → Add Integration** → tìm kiếm **Tapo Camera Local AI**.
2. Điền thông tin kết nối:
   * **Địa chỉ IP Camera (Host)**: Địa chỉ IP tĩnh của camera trong mạng LAN (ví dụ `192.168.2.167`).
   * **Tài khoản & Mật khẩu Camera**: Tài khoản Camera Account dùng cho luồng RTSP/ONVIF.
   * **Mật khẩu TP-Link Cloud**: Mật khẩu đăng nhập tài khoản TP-Link/Tapo chính của bạn (bắt buộc đối với các dòng camera đời mới như C125, C225 chạy giao thức mã hóa nội bộ KLAP/TPAP).
   * **Chu kỳ quét sự kiện AI Local**: Mặc định `3 giây`.
   * **Thời gian giữ trạng thái ON cho Binary Sensor**: Mặc định `15 giây`.
3. Bạn có thể bấm vào biểu tượng bánh răng **Configure (`⚙️`)** hoặc menu **Reconfigure** bất kỳ lúc nào để thay đổi IP, mật khẩu hoặc chu kỳ quét.

## Ví dụ Automation tự động hóa

### 1. Gửi thông báo điện thoại khi phát hiện tiếng em bé khóc hoặc tiếng chó sủa

```yaml
alias: "Cảnh báo AI: Phát hiện tiếng em bé khóc hoặc chó sủa"
description: "Gửi thông báo tức thì khi binary_sensor AI của camera Tapo chuyển sang ON"
triggers:
  - trigger: state
    entity_id:
      - binary_sensor.tapo_c225_baby_cry
      - binary_sensor.tapo_c125_baby_cry
      - binary_sensor.tapo_c225_bark
    from: "off"
    to: "on"
actions:
  - action: notify.mobile_app_iphone
    data:
      title: >
        {% if 'baby_cry' in trigger.entity_id %}
          👶 Phát hiện tiếng em bé khóc!
        {% else %}
          🐕 Phát hiện tiếng chó sủa!
        {% endif %}
      message: >
        Phát hiện bởi {{ state_attr(trigger.entity_id, 'friendly_name') }}
        lúc {{ now().strftime('%H:%M:%S') }}.
mode: queued
```

### 2. Bắt sự kiện trực tiếp từ Event Bus (`tapo_local_ai_event`)

Ngoài `binary_sensor`, mỗi khi phát hiện sự kiện AI mới, tích hợp cũng bắn một sự kiện `tapo_local_ai_event` lên Event Bus của Home Assistant:

```yaml
alias: "Theo dõi toàn bộ sự kiện AI từ Camera Tapo"
triggers:
  - trigger: event
    event_type: tapo_local_ai_event
actions:
  - action: system_log.write
    data:
      message: >
        Camera {{ trigger.event.data.device_name }} ({{ trigger.event.data.host }})
        vừa phát hiện sự kiện {{ trigger.event.data.event_type }}
        qua nguồn {{ trigger.event.data.source }}.
      level: info
```

## Giấy phép & Tham khảo

* Giao thức truyền thông nội bộ dựa trên thư viện mã nguồn mở [pytapo](https://github.com/JurajNyiri/pytapo) và [onvif-zeep-async](https://github.com/hunterjm/python-onvif-zeep-async).
* Phân tích mã sự kiện `alarm_type` và bitmask `events_1` tham khảo từ cộng đồng [HomeAssistant-Tapo-Control](https://github.com/jurajnyiri/homeassistant-tapo-control) và [pytapo Issue #198](https://github.com/JurajNyiri/pytapo/issues/198).
