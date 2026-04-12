from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/nj_bid_registry"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 10000
    log_level: str = "info"
    default_registry_workbook: str = "data/imports/nj_statewide_transportation_bid_source_registry_built_2026-04-11.xlsx"
    default_registry_sheet: str = "Master Registry"
    default_registry_csv_export: str = "data/imports/master_registry_export.csv"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
