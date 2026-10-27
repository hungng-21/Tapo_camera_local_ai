"""Constants for the Tapo Camera Local AI integration."""
from __future__ import annotations

from dataclasses import dataclass
from homeassistant.components.binary_sensor import BinarySensorDeviceClass

DOMAIN = "tapo_local_ai"

CONF_CLOUD_PASSWORD = "cloud_password"
CONF_CONTROL_PORT = "control_port"
CONF_ONVIF_PORT = "onvif_port"
CONF_RTSP_PORT = "rtsp_port"
CONF_POLL_INTERVAL = "poll_interval"
CONF_HOLD_SECONDS = "hold_seconds"
CONF_ENABLE_ONVIF = "enable_onvif"

DEFAULT_CONTROL_PORT = 443
DEFAULT_ONVIF_PORT = 2020
DEFAULT_RTSP_PORT = 554
DEFAULT_POLL_INTERVAL = 3
DEFAULT_HOLD_SECONDS = 15
DEFAULT_ENABLE_ONVIF = True
DEFAULT_PTZ_STEP_ANGLE = 15

EVENT_TAPO_AI_DETECTED = f"{DOMAIN}_event"

# Known PTZ & Fixed model keywords for fallback detection
PTZ_MODEL_KEYWORDS = (
    "C200", "C201", "C206", "C210", "C211", "C212", "C216",
    "C220", "C225", "C230", "C236", "C260",
    "C500", "C510", "C520", "C530", "C560", "C610",
    "TC40", "TC41", "TC70", "TC71", "TC72", "TC73", "TC74",
)
FIXED_MODEL_KEYWORDS = (
    "C100", "C110", "C111", "C120", "C125",
    "C310", "C320", "C325", "C400", "C402", "C410", "C420", "C425",
    "TC60", "TC65", "TC82", "TC85", "D130", "D210", "D230", "D235",
)

# Tapo searchDetectionList alarm_type IDs (local API getEvents)
ALARM_TYPE_MOTION = 2
ALARM_TYPE_TAMPER = 3
ALARM_TYPE_LINE_CROSSING = 4
ALARM_TYPE_AREA_INTRUSION = 5
ALARM_TYPE_PERSON = 6
ALARM_TYPE_BABY_CRY = 7
ALARM_TYPE_VEHICLE = 8
ALARM_TYPE_PET = 9
ALARM_TYPE_BARK = 11
ALARM_TYPE_MEOW = 12
ALARM_TYPE_GLASS_BREAK = 13
ALARM_TYPE_SMOKE = 14
ALARM_TYPE_PACKAGE_DELIVERED = 15
ALARM_TYPE_PACKAGE_PICKED_UP = 16
ALARM_TYPE_FACE = 20
ALARM_TYPE_LOITERING = 32

# Undocumented events_1 bitmask flags returned by searchDetectionList (pytapo issue #198)
BITMASK_MOTION = 1 << 1          # 2: Basic motion trigger
BITMASK_PIR_VEHICLE = 1 << 5     # 32: PIR / Vehicle auxiliary flag
BITMASK_LINE_CROSSING = 1 << 8   # 256: Line crossing detection
BITMASK_PERSON_AI = 1 << 19      # 524288: On-device neural network confirmed person


@dataclass(frozen=True)
class TapoAIBinarySensorSpec:
    """Specification for a Tapo AI detection binary sensor."""

    key: str
    translation_key: str
    name_vi: str
    name_en: str
    device_class: BinarySensorDeviceClass
    icon: str
    alarm_types: tuple[int, ...]
    bitmask_flags: tuple[int, ...] = ()
    onvif_data_keys: tuple[str, ...] = ()
    enabled_by_default: bool = True


AI_BINARY_SENSORS: tuple[TapoAIBinarySensorSpec, ...] = (
    TapoAIBinarySensorSpec(
        key="baby_cry",
        translation_key="baby_cry",
        name_vi="Phát hiện tiếng khóc trẻ em (Baby Cry)",
        name_en="Baby Crying Detection",
        device_class=BinarySensorDeviceClass.SOUND,
        icon="mdi:baby-face-outline",
        alarm_types=(ALARM_TYPE_BABY_CRY,),
        onvif_data_keys=("IsBabyCry", "BabyCry", "bcd"),
        enabled_by_default=True,
    ),
    TapoAIBinarySensorSpec(
        key="bark",
        translation_key="bark",
        name_vi="Phát hiện tiếng chó sủa (Dog Bark)",
        name_en="Dog Bark Detection",
        device_class=BinarySensorDeviceClass.SOUND,
        icon="mdi:dog-side",
        alarm_types=(ALARM_TYPE_BARK,),
        onvif_data_keys=("IsBark", "Bark", "bark"),
        enabled_by_default=True,
    ),
    TapoAIBinarySensorSpec(
        key="meow",
        translation_key="meow",
        name_vi="Phát hiện tiếng mèo kêu (Cat Meow)",
        name_en="Cat Meow Detection",
        device_class=BinarySensorDeviceClass.SOUND,
        icon="mdi:cat",
        alarm_types=(ALARM_TYPE_MEOW,),
        onvif_data_keys=("IsMeow", "Meow", "meow"),
        enabled_by_default=True,
    ),
    TapoAIBinarySensorSpec(
        key="glass_break",
        translation_key="glass_break",
        name_vi="Phát hiện tiếng kính vỡ (Glass Break)",
        name_en="Glass Break Detection",
        device_class=BinarySensorDeviceClass.SOUND,
        icon="mdi:glass-fragile",
        alarm_types=(ALARM_TYPE_GLASS_BREAK,),
        onvif_data_keys=("IsGlassBreak", "GlassBreak", "glass"),
        enabled_by_default=True,
    ),
    TapoAIBinarySensorSpec(
        key="person",
        translation_key="person",
        name_vi="Phát hiện người (AI Person)",
        name_en="Person Detection",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        icon="mdi:account-alert-outline",
        alarm_types=(ALARM_TYPE_PERSON,),
        bitmask_flags=(BITMASK_PERSON_AI,),
        onvif_data_keys=("IsPeople", "People"),
        enabled_by_default=True,
    ),
    TapoAIBinarySensorSpec(
        key="pet",
        translation_key="pet",
        name_vi="Phát hiện thú cưng (AI Pet)",
        name_en="Pet Detection",
        device_class=BinarySensorDeviceClass.MOTION,
        icon="mdi:paw",
        alarm_types=(ALARM_TYPE_PET,),
        onvif_data_keys=("IsPet", "Pet"),
        enabled_by_default=True,
    ),
    TapoAIBinarySensorSpec(
        key="vehicle",
        translation_key="vehicle",
        name_vi="Phát hiện phương tiện (AI Vehicle)",
        name_en="Vehicle Detection",
        device_class=BinarySensorDeviceClass.MOTION,
        icon="mdi:car-info",
        alarm_types=(ALARM_TYPE_VEHICLE,),
        onvif_data_keys=("IsVehicle", "Vehicle"),
        enabled_by_default=True,
    ),
    TapoAIBinarySensorSpec(
        key="motion",
        translation_key="motion",
        name_vi="Phát hiện chuyển động (Motion)",
        name_en="Motion Detection",
        device_class=BinarySensorDeviceClass.MOTION,
        icon="mdi:motion-sensor",
        alarm_types=(ALARM_TYPE_MOTION,),
        bitmask_flags=(BITMASK_MOTION,),
        onvif_data_keys=("IsMotion", "Motion"),
        enabled_by_default=True,
    ),
    TapoAIBinarySensorSpec(
        key="line_crossing",
        translation_key="line_crossing",
        name_vi="Vượt hàng rào ảo (Line Crossing)",
        name_en="Line Crossing Detection",
        device_class=BinarySensorDeviceClass.MOTION,
        icon="mdi:vector-line",
        alarm_types=(ALARM_TYPE_LINE_CROSSING,),
        bitmask_flags=(BITMASK_LINE_CROSSING,),
        onvif_data_keys=("IsLineCross", "LineCross"),
        enabled_by_default=True,
    ),
    TapoAIBinarySensorSpec(
        key="area_intrusion",
        translation_key="area_intrusion",
        name_vi="Xâm nhập vùng cấm (Area Intrusion)",
        name_en="Area Intrusion Detection",
        device_class=BinarySensorDeviceClass.TAMPER,
        icon="mdi:shield-alert-outline",
        alarm_types=(ALARM_TYPE_AREA_INTRUSION,),
        onvif_data_keys=("IsIntrusion", "Intrusion"),
        enabled_by_default=False,
    ),
    TapoAIBinarySensorSpec(
        key="tamper",
        translation_key="tamper",
        name_vi="Che khuất / Phá hoại camera (Tamper)",
        name_en="Camera Tamper Detection",
        device_class=BinarySensorDeviceClass.TAMPER,
        icon="mdi:camera-off-outline",
        alarm_types=(ALARM_TYPE_TAMPER,),
        onvif_data_keys=("IsTamper", "Tamper"),
        enabled_by_default=True,
    ),
    TapoAIBinarySensorSpec(
        key="package",
        translation_key="package",
        name_vi="Phát hiện bưu kiện (Package)",
        name_en="Package Detection",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        icon="mdi:package-variant-closed-check",
        alarm_types=(ALARM_TYPE_PACKAGE_DELIVERED, ALARM_TYPE_PACKAGE_PICKED_UP),
        onvif_data_keys=("IsPackage", "Package"),
        enabled_by_default=False,
    ),
)


@dataclass(frozen=True)
class TapoAISwitchSpec:
    """Specification for a Tapo AI detection or control configuration switch."""

    key: str
    name_vi: str
    name_en: str
    icon: str
    get_method: str
    get_module: str
    get_section: str
    set_method: str
    set_module: str
    set_section: str
    ptz_only: bool = False


AI_DETECTION_SWITCHES: tuple[TapoAISwitchSpec, ...] = (
    TapoAISwitchSpec(
        key="auto_track_switch",
        name_vi="Tự động xoay theo chuyển động (Auto Track)",
        name_en="Auto Track Target",
        icon="mdi:radar",
        get_method="getTargetTrackConfig",
        get_module="target_track",
        get_section="target_track_info",
        set_method="setTargetTrackConfig",
        set_module="target_track",
        set_section="target_track_info",
        ptz_only=True,
    ),
    TapoAISwitchSpec(
        key="baby_cry_detection_switch",
        name_vi="Bật AI Phát hiện tiếng khóc",
        name_en="Enable Baby Cry Detection",
        icon="mdi:baby-face-outline",
        get_method="getBCDConfig",
        get_module="sound_detection",
        get_section="bcd",
        set_method="setBCDConfig",
        set_module="sound_detection",
        set_section="bcd",
    ),
    TapoAISwitchSpec(
        key="bark_detection_switch",
        name_vi="Bật AI Phát hiện chó sủa",
        name_en="Enable Dog Bark Detection",
        icon="mdi:dog-side",
        get_method="getBarkDetectionConfig",
        get_module="bark_detection",
        get_section="detection",
        set_method="setBarkDetectionConfig",
        set_module="bark_detection",
        set_section="detection",
    ),
    TapoAISwitchSpec(
        key="meow_detection_switch",
        name_vi="Bật AI Phát hiện mèo kêu",
        name_en="Enable Cat Meow Detection",
        icon="mdi:cat",
        get_method="getMeowDetectionConfig",
        get_module="meow_detection",
        get_section="detection",
        set_method="setMeowDetectionConfig",
        set_module="meow_detection",
        set_section="detection",
    ),
    TapoAISwitchSpec(
        key="glass_break_detection_switch",
        name_vi="Bật AI Phát hiện kính vỡ",
        name_en="Enable Glass Break Detection",
        icon="mdi:glass-fragile",
        get_method="getGlassDetectionConfig",
        get_module="glass_detection",
        get_section="detection",
        set_method="setGlassDetectionConfig",
        set_module="glass_detection",
        set_section="detection",
    ),
    TapoAISwitchSpec(
        key="person_detection_switch",
        name_vi="Bật AI Phát hiện người",
        name_en="Enable Person Detection",
        icon="mdi:account-check-outline",
        get_method="getPersonDetectionConfig",
        get_module="people_detection",
        get_section="detection",
        set_method="setPersonDetectionConfig",
        set_module="people_detection",
        set_section="detection",
    ),
    TapoAISwitchSpec(
        key="pet_detection_switch",
        name_vi="Bật AI Phát hiện thú cưng",
        name_en="Enable Pet Detection",
        icon="mdi:paw",
        get_method="getPetDetectionConfig",
        get_module="pet_detection",
        get_section="detection",
        set_method="setPetDetectionConfig",
        set_module="pet_detection",
        set_section="detection",
    ),
    TapoAISwitchSpec(
        key="vehicle_detection_switch",
        name_vi="Bật AI Phát hiện xe cộ",
        name_en="Enable Vehicle Detection",
        icon="mdi:car",
        get_method="getVehicleDetectionConfig",
        get_module="vehicle_detection",
        get_section="detection",
        set_method="setVehicleDetectionConfig",
        set_module="vehicle_detection",
        set_section="detection",
    ),
    TapoAISwitchSpec(
        key="motion_detection_switch",
        name_vi="Bật Phát hiện chuyển động",
        name_en="Enable Motion Detection",
        icon="mdi:motion-sensor",
        get_method="getDetectionConfig",
        get_module="motion_detection",
        get_section="motion_det",
        set_method="setDetectionConfig",
        set_module="motion_detection",
        set_section="motion_det",
    ),
    TapoAISwitchSpec(
        key="privacy_mode_switch",
        name_vi="Chế độ riêng tư (Privacy)",
        name_en="Privacy Mode",
        icon="mdi:eye-outline",
        get_method="getLensMaskConfig",
        get_module="lens_mask",
        get_section="lens_mask_info",
        set_method="setLensMaskConfig",
        set_module="lens_mask",
        set_section="lens_mask_info",
    ),
    TapoAISwitchSpec(
        key="led_indicator_switch",
        name_vi="Đèn trạng thái LED",
        name_en="LED Indicator",
        icon="mdi:led-on",
        get_method="getLedStatus",
        get_module="led",
        get_section="config",
        set_method="setLedStatus",
        set_module="led",
        set_section="config",
    ),
)
