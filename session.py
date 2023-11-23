import os
import time
import random
import requests
from abc import ABC, abstractmethod
from collections.abc import Callable
from enum import StrEnum
from json.decoder import JSONDecodeError
from requests.models import Response
from urllib.parse import urlparse


class ProxyProviderName(StrEnum):
    PROXYRACK = "PROXYRACK"
    NORDVPN = "NORDVPN"


class ProxyProvider(ABC):
    @abstractmethod
    def get_proxy(self) -> str:
        pass


class Proxyrack(ProxyProvider):
    USER = os.getenv("PROXYRACK_USER")
    API_KEY = os.getenv("PROXYRACK_API_KEY")
    AVAILABLE_OPTIONS: dict = {}
    DNS = "premium.residential.proxyrack.net"
    random_port = 9000
    sticky_ports = [i for i in range(10000, 14000)]
    _sticky_ports_index = 0

    @staticmethod
    def get_proxy(sticky: bool = False, options: dict = {}) -> str:
        option_str = (
            "-" + "-".join([f"{k}-{v}" for k, v in options.items()]) if options else ""
        )
        port = Proxyrack.random_port
        if sticky:
            port = Proxyrack.sticky_ports[Proxyrack._sticky_ports_index]
            Proxyrack._sticky_ports_index = (Proxyrack._sticky_ports_index + 1) % len(
                Proxyrack.proxy_domains
            )

        return f"http://{Proxyrack.USER}{option_str}:{Proxyrack.API_KEY}@{Proxyrack.DNS}{port}"

    @staticmethod
    def get_stats(proxy: str) -> dict:
        r = requests.get(f"http://api.proxyrack.net/stats", proxies={"http": proxy})
        return r.json()


class Nordvpn(ProxyProvider):
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
    def get_proxy() -> str:
        Nordvpn.get_best_server_domains()
        host = Nordvpn.proxy_domains[Nordvpn._index]
        print(f"Using server {host}")
        Nordvpn._index = (Nordvpn._index + 1) % len(Nordvpn.proxy_domains)
        proxy_url = (
            f"https://{Nordvpn.USER}:{Nordvpn.PASSWORD}@{host}:{Nordvpn.DEFAULT_PORT}"
        )
        return proxy_url


class Session(requests.Session):
    def __init__(
        self,
        retry_on_failure=False,
        is_successful: Callable[[Response], bool] = None,
        sticky_proxies: bool = False,
        proxy_providers: list[ProxyProvider] = None,
    ):
        super().__init__()
        self.retry_on_failure = retry_on_failure
        self.success_conditions = is_successful
        self.proxyProviders = proxy_providers or [
            provider for provider in ProxyProvider.__subclasses__()
        ]
        self.sticky_proxies = sticky_proxies

    def request(
        self,
        method,
        url,
        params=None,
        data=None,
        headers=None,
        cookies=None,
        files=None,
        auth=None,
        timeout=None,
        allow_redirects=True,
        proxies=None,
        hooks=None,
        stream=None,
        verify=None,
        cert=None,
        json=None,
    ) -> Response:
        """Constructs a :class:`Request <Request>`, prepares it and sends it.
        Returns :class:`Response <Response>` object.

        :param method: method for the new :class:`Request` object.
        :param url: URL for the new :class:`Request` object.
        :param params: (optional) Dictionary or bytes to be sent in the query
            string for the :class:`Request`.
        :param data: (optional) Dictionary, list of tuples, bytes, or file-like
            object to send in the body of the :class:`Request`.
        :param json: (optional) json to send in the body of the
            :class:`Request`.
        :param headers: (optional) Dictionary of HTTP Headers to send with the
            :class:`Request`.
        :param cookies: (optional) Dict or CookieJar object to send with the
            :class:`Request`.
        :param files: (optional) Dictionary of ``'filename': file-like-objects``
            for multipart encoding upload.
        :param auth: (optional) Auth tuple or callable to enable
            Basic/Digest/Custom HTTP Auth.
        :param timeout: (optional) How long to wait for the server to send
            data before giving up, as a float, or a :ref:`(connect timeout,
            read timeout) <timeouts>` tuple.
        :type timeout: float or tuple
        :param allow_redirects: (optional) Set to True by default.
        :type allow_redirects: bool
        :param proxies: (optional) Dictionary mapping protocol or protocol and
            hostname to the URL of the proxy.
        :param stream: (optional) whether to immediately download the response
            content. Defaults to ``False``.
        :param verify: (optional) Either a boolean, in which case it controls whether we verify
            the server's TLS certificate, or a string, in which case it must be a path
            to a CA bundle to use. Defaults to ``True``. When set to
            ``False``, requests will accept any TLS certificate presented by
            the server, and will ignore hostname mismatches and/or expired
            certificates, which will make your application vulnerable to
            man-in-the-middle (MitM) attacks. Setting verify to ``False``
            may be useful during local development or testing.
        :param cert: (optional) if String, path to ssl client cert file (.pem).
            If Tuple, ('cert', 'key') pair.
        :rtype: requests.Response
        """
        print(f"Requru: Requesting with proxies {self.proxies}")

        for provider in self.proxyProviders:
            proxy = provider.get_proxy()
            r = super().request(
                method,
                url,
                params,
                data,
                headers,
                cookies,
                files,
                auth,
                timeout,
                allow_redirects,
                proxies,
                hooks,
                stream,
                verify,
                cert,
                json,
            )
            if self.success_conditions(r):
                break

        print(f"Proxy used: {r.headers.get('x-proxy-id')}")
        return r
