from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    KAFKA_BROKER: str
    MINER_NUMBER: str = "1"
    MINING_JOBS_TOPIC: str = "mining_jobs"
    FOUND_BLOCKS_TOPIC: str = "found_blocks"
    DIFFICULTY: int = 4

    @property
    def MINER_ID(self) -> str:
        return f"miner{self.MINER_NUMBER}"


settings = Settings()
