from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    elasticsearch_url: str = "http://elasticsearch:9200"
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    service_name: str = "analytics-service"
    service_port: int = 8000

    # Index-navne prefixes så integrationstests kan isolere sig på et delt
    # cluster (tom streng i drift).
    es_index_prefix: str = ""

    # Kilder til engangs-backfill (app/tools/backfill.py) — ikke brugt af
    # request-flowet, som alene læser fra Elasticsearch.
    transaction_service_url: str = "http://transaction-service:8002"
    account_service_url: str = "http://account-service:8003"
    categorization_service_url: str = "http://categorization-service:8005"
    goal_service_url: str = "http://goal-service:8006"

    model_config = {"env_file": ".env"}


settings = Settings()
