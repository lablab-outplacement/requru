from enum import Enum, auto


class ProviderParadigm(Enum):
    DNS = auto()
    DIRECT = auto()


class ProxyProvider:
    strength: float = 0
    paradigm: ProviderParadigm = ProviderParadigm.DNS

    def get_new_proxy() -> str:
        return ""

    def close(self):
        pass
