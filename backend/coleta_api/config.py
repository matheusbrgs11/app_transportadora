from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    token_minutes: int = 60

    @classmethod
    def from_env(cls):
        secret = os.environ.get('JWT_SECRET', '')
        if len(secret) < 32:
            raise RuntimeError('Configure JWT_SECRET com pelo menos 32 caracteres aleatórios.')
        return cls(os.environ['DATABASE_URL'], secret)
