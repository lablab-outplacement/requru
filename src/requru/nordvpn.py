import os
import random
import requests
import time

from json import JSONDecodeError

from .proxy_provider import ProviderParadigm, ProxyProvider


class Nordvpn(ProxyProvider):
    strength = 0.2
    _index = 0
    updated_at = 0
    TTL = 3600
    API_URL = "https://api.nordvpn.com/v1/servers/recommendations?filters[country_id]=43,179&filters[servers_groups][identifier]=legacy_standard&filters[servers_technologies][identifier]=proxy_ssl&limit=15"
    proxy_domains = []
    DEFAULT_PORT = 89
    USER = os.getenv("NORDVPN_USER")
    PASSWORD = os.getenv("NORDVPN_PASSWORD")
    EXAMPLE_PROXY_URLS = [
        "cl33.nordvpn.com",
        "cl34.nordvpn.com",
        "cl35.nordvpn.com",
        "cl36.nordvpn.com",
        "cl37.nordvpn.com",
        "ar56.nordvpn.com",
        "ar58.nordvpn.com",
    ]
    paradigm = ProviderParadigm.DIRECT

    def __init__(self, max_tries_per_request: int = 10) -> None:
        self.max_tries_per_request = max_tries_per_request

    @staticmethod
    def get_best_server_domains(min_load: int = 1, max_load: int = 60):
        if (
            not Nordvpn.proxy_domains
            or (time.time() - Nordvpn.updated_at) > Nordvpn.TTL
        ):
            try:
                resp = requests.get(Nordvpn.API_URL).json()
                filtered_servers = [
                    s
                    for s in resp
                    if s["status"] == "online" and min_load <= s["load"] <= max_load
                ]
                Nordvpn.proxy_domains = [s["hostname"] for s in filtered_servers]

            except JSONDecodeError:
                print(
                    "JSONDecodeError when fetching updated server list. Falling back to hardcoded list"
                )
                Nordvpn.proxy_domains = Nordvpn.EXAMPLE_PROXY_URLS
            finally:
                random.shuffle(Nordvpn.proxy_domains)
                print(f"Pool now has {len(Nordvpn.proxy_domains)} servers")
                Nordvpn.updated_at = time.time()
                Nordvpn._index = 0

    @staticmethod
    def get_new_proxy() -> str:
        Nordvpn.get_best_server_domains()
        host = Nordvpn.proxy_domains[Nordvpn._index]
        print(f"Using server {host}")
        Nordvpn._index = (Nordvpn._index + 1) % len(Nordvpn.proxy_domains)
        proxy_url = (
            f"https://{Nordvpn.USER}:{Nordvpn.PASSWORD}@{host}:{Nordvpn.DEFAULT_PORT}"
        )
        return proxy_url

    def should_get_new_proxy_after_failed_request(self) -> bool:
        return True
