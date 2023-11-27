from abc import ABC, abstractmethod
from enum import Enum, auto


class ProviderParadigm(Enum):
    DNS = auto()
    DIRECT = auto()


class ProxyProvider(ABC):
    strength: float = 0
    max_retries: int = 3
    paradigm: ProviderParadigm = ProviderParadigm.DNS

    @staticmethod
    @abstractmethod
    def get_proxy(sticky=False) -> str:
        pass
