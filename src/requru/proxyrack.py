import os
import requests
from dataclasses import dataclass, asdict, field
from uuid import uuid4

from .proxy_provider import ProviderParadigm, ProxyProvider


@dataclass
class ProxyrackOptions:

    """Options that are specified next to the Proxyrack user.
    They must be in camelCase, as that is how Proxyrack expects them."""

    country: str = None
    refreshMinutes: int = 60 * 24
    session: str = field(default_factory=lambda: str(uuid4()).replace("-", ""))


class ProxyrackProvider(ProxyProvider):
    strength = 0.8
    USER = os.getenv("PROXYRACK_USER")
    API_KEY = os.getenv("PROXYRACK_API_KEY")
    DNS = "premium.residential.proxyrack.net"
    random_port = 9000
    sticky_ports = [i for i in range(10000, 14000)]
    _sticky_ports_index = 0
    paradigm = ProviderParadigm.DNS

    def __init__(
        self,
        max_tries_per_request: int = 10,
        use_sticky_ports: bool = False,
        force_port: int = None,
        options: ProxyrackOptions = ProxyrackOptions(),
    ) -> None:
        self.max_tries_per_request = max_tries_per_request
        self.use_sticky_ports = use_sticky_ports
        self.options = options
        self.force_port = force_port
        self._proxies: list[str] = []

    def get_new_proxy(self) -> str:
        options_dict = asdict(self.options)
        option_str = "-".join(
            [f"{k}-{v}" for k, v in options_dict.items() if v is not None]
        )
        if option_str:
            final_option_str = f"-{option_str}"

        if self.force_port:
            print("WARNING: Using forced port")
            port = self.force_port
        elif self.use_sticky_ports:
            port = ProxyrackProvider.sticky_ports[ProxyrackProvider._sticky_ports_index]
            ProxyrackProvider._sticky_ports_index = (
                ProxyrackProvider._sticky_ports_index + 1
            ) % len(ProxyrackProvider.sticky_ports)
        else:
            port = ProxyrackProvider.random_port

        proxy = f"http://{ProxyrackProvider.USER}{final_option_str}:{ProxyrackProvider.API_KEY}@{ProxyrackProvider.DNS}:{port}"
        print(f"Using {'sticky' if self.use_sticky_ports else 'random'} proxy {proxy}")
        self._proxies.append(proxy)
        return proxy

    def close(self):
        if self.use_sticky_ports:
            for proxy in self._proxies:
                r = requests.get(
                    f"http://api.proxyrack.net/release", proxies={"http": proxy}
                )
                print(f"Released proxy {self._proxies}")

    @staticmethod
    def get_stats(proxy: str) -> dict:
        r = requests.get(f"http://api.proxyrack.net/stats", proxies={"http": proxy})
        return r.json()
