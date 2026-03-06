from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = ""
    rabbitmq_url: str = ""
    jwt_secret: str = ""
    service_name: str = "budget-service"
    service_port: int = 8000

    model_config = {"env_file": ".env"}


settings = Settings()
