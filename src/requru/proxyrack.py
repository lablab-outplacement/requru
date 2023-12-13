import os
import requests

from .proxy_provider import ProxyProvider


class Proxyrack(ProxyProvider):
    strength = 0.8
    sticky = True
    random = True
    USER = os.getenv("PROXYRACK_USER")
    API_KEY = os.getenv("PROXYRACK_API_KEY")
    AVAILABLE_OPTIONS: dict = {}
    DNS = "premium.residential.proxyrack.net"
    random_port = 9000
    sticky_ports = [i for i in range(10000, 14000)]
    _sticky_ports_index = 0
    max_retries = 20

    @staticmethod
    def get_proxy(sticky: bool = False, **options: dict) -> str:
        option_str = (
            "-" + "-".join([f"{k}-{v}" for k, v in options.items()]) if options else ""
        )
        port = Proxyrack.random_port
        if sticky:
            port = Proxyrack.sticky_ports[Proxyrack._sticky_ports_index]
            Proxyrack._sticky_ports_index = (Proxyrack._sticky_ports_index + 1) % len(
                Proxyrack.sticky_ports
            )
        proxy = f"http://{Proxyrack.USER}{option_str}:{Proxyrack.API_KEY}@{Proxyrack.DNS}:{port}"
        print(f"Using {'sticky' if sticky else 'random'} proxy {proxy}")
        return proxy

    @staticmethod
    def get_stats(proxy: str) -> dict:
        r = requests.get(f"http://api.proxyrack.net/stats", proxies={"http": proxy})
        return r.json()
