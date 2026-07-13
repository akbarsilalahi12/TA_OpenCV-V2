from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === RTSP ===
    rtsp_url: str = "rtsp://admin:L2E1141F@10.134.84.205:554/cam/realmonitor?channel=1&subtype=0"

    # === Detection ===
    detection_threshold: float = 0.22
    detection_hysteresis_margin: float = 0.03
    ratio_ema_alpha: float = 0.70
    preprocess_threshold_mode: str = "adaptive"
    preprocess_use_clahe: bool = True
    preprocess_manual_threshold: int = 150
    preprocess_adaptive_c: int = 7
    frame_width: int = 1280
    frame_height: int = 720
    detect_interval_ms: int = 200
    summary_interval_sec: int = 60

    # === Shadow Removal ===
    remove_shadows: bool = False
    shadow_v_low: int = 0
    shadow_v_high: int = 45

    # === Adaptive Threshold (lighting-aware) ===
    adaptive_threshold_enabled: bool = True
    adaptive_threshold_min: float = 0.20
    adaptive_threshold_max: float = 0.35

    # === Morphological ===
    close_ksize: int = 3
    dilate_iterations: int = 1

    # === Noise Filter ===
    min_object_area: int = 200

    # === Database (SQLite default, no MySQL needed) ===
    database_url: str = "sqlite:///parking.db"

    # === API ===
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # === Logging ===
    log_level: str = "INFO"
    log_file: str = "logs/app.log"


settings = Settings()
