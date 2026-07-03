"""
Konfigurasi global aplikasi.
Membaca file .env dan mengeksposnya sebagai objek typed.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === RTSP ===
    rtsp_url: str = "rtsp://admin:admin@192.168.1.100:554/stream"

    # === Detection ===
    detection_threshold: float = 0.18
    detection_hysteresis_margin: float = 0.04
    ratio_ema_alpha: float = 0.30
    preprocess_threshold_mode: str = "adaptive"  # adaptive / otsu / manual
    preprocess_use_clahe: bool = True
    preprocess_manual_threshold: int = 150
    frame_width: int = 1280
    frame_height: int = 720
    detect_interval_ms: int = 200
    summary_interval_sec: int = 60

    # === MySQL ===
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "parking_user"
    mysql_password: str = "parking_pass"
    mysql_database: str = "parking_db"

    # === API ===
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # === Logging ===
    log_level: str = "INFO"
    log_file: str = "logs/app.log"

    @property
    def database_url(self) -> str:
        """Build SQLAlchemy connection URL untuk MySQL via PyMySQL."""
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            f"?charset=utf8mb4"
        )


# Singleton: import settings dari module ini di mana saja butuh.
settings = Settings()
