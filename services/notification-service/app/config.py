from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    rabbitmq_url: str = ""
    jwt_secret: str = ""
    service_name: str = "notification-service"
    service_port: int = 8000

    model_config = {"env_file": ".env"}


settings = Settings()
