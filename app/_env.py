from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    client_id: str
    database_url: str
    init_admin_password: str
    client_secret: str
    redirect_uri: str
    secret_key: str
    algorithm: str = "HS256"
    frontend_url: str


SETTINGS = Settings()
