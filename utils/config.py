"""
Configurações globais da aplicação (valores padrão, preferências do usuário).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AppConfig:
    preview_max_dim: int = 2048
    default_percentile_low: float = 2.0
    default_percentile_high: float = 98.0
    theme: str = "light"

    @classmethod
    def load_default(cls) -> "AppConfig":
        """Carrega configuração padrão. Futuramente pode ler de arquivo JSON/YAML."""
        return cls()