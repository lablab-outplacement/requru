from collections.abc import Callable

import requests
import time
from requests.models import Response
from requests.exceptions import (
    SSLError,
    ProxyError,
    ChunkedEncodingError,
    ConnectionError,
)
from requests.adapters import HTTPAdapter

from .proxy_provider import ProxyProvider, ProviderParadigm
from .proxyrack import Proxyrack
from .nordvpn import Nordvpn


class Session(requests.Session):
    def __init__(
        self,
        sticky_proxies=False,
        is_successful_response: Callable[[Response], bool] = lambda _r: 200
        <= _r.status_code
        < 300,
        retry_on_failure=True,
        retry_backoff_seconds=30,
        proxy_providers: list[ProxyProvider] = [Proxyrack, Nordvpn],
        max_retries: int = 3,
        country: str = None,
    ) -> None:
        super().__init__()
        self.proxy_providers: list[ProxyProvider] = proxy_providers
        self.is_successful_response = is_successful_response
        self.sticky_proxies = sticky_proxies
        self.retry_on_failure = retry_on_failure
        self.retry_backoff_seconds = retry_backoff_seconds
        self.verify = False
        self.max_retries = max_retries
        self.country = country
        self._retries: int = 0
        self._last_successful_provider: ProxyProvider = None
        self.reset_adapters()

    def reset_adapters(self):
        self.adapters.clear()
        self.mount("https://", HTTPAdapter(max_retries=3))
        self.mount("http://", HTTPAdapter(max_retries=3))

    def request_with_providers(
        self,
        super_request_params,
    ):
        get_proxy_options = dict(country=self.country) if self.country else {}
        url = super_request_params[1]
        print(f"Using {self.proxy_providers} as proxy providers")
        sorted_providers: list[ProxyProvider] = sorted(
            self.proxy_providers, key=lambda p: p.strength, reverse=True
        )
        print(f"Sorted providers: {sorted_providers}")
        r = None
        for provider in sorted_providers:
            provider_retries = 0
            print(f"Trying provider {provider.__name__}")
            print(f"Provider max retries: {provider.max_retries}")

            print("Getting new proxy")
            proxy = provider.get_proxy(sticky=self.sticky_proxies, **get_proxy_options)
            self.proxies.update({"http": proxy, "https": proxy})
            print(f"Using proxy {proxy}")

            while True:
                print(f"Request attempt {self._retries + 1} to url {url}")
                try:
                    r: Response = super().request(*super_request_params)
                except ConnectionError as e:
                    print(e)
                    print("ConnectionError encountered. Resetting adapters")
                    self.reset_adapters()
                except ChunkedEncodingError as e:
                    print(e)
                    print("ChunkedEncodingError encountered. Resetting adapters")
                    self.reset_adapters()
                provider_retries += 1
                self._retries += 1
                success = self.is_successful_response(r) if r is not None else False
                if success:
                    print(
                        f"Request to {url} successful with status code {r.status_code}. Setting last successful provider to {provider.__name__}"
                    )
                    self._last_successful_provider = provider
                else:
                    print(
                        f"Response unsuccessful with status code {r.status_code if r is not None else None}"
                    )
                if (
                    not self.retry_on_failure
                    or self._retries >= self.max_retries
                    or success
                ):
                    return r
                if provider_retries >= provider.max_retries:
                    print(
                        f"Provider {provider.__name__} exhausted. Moving on to next provider"
                    )
                    self.proxies = {}
                    time.sleep(self.retry_backoff_seconds)
                    # go to next provider
                    break

                # If we are using sticky proxies, we need to get a new sticky proxy (because reaching this point implies
                # (self.retry_on_failure and self._retries < self.max_retries and not success and provider_retries < provider.max_retries)).
                # If we are not using sticky proxies, but the provider paradigm is DIRECT, we
                # also need to get a new proxy.
                if (self.sticky_proxies) or (
                    not self.sticky_proxies
                    and provider.paradigm == ProviderParadigm.DIRECT
                ):
                    print(f"Getting new proxy after unsusccessful request to {url}")
                    proxy = provider.get_proxy(
                        sticky=self.sticky_proxies, **get_proxy_options
                    )
                    self.proxies.update({"http": proxy, "https": proxy})
                    print(f"Using proxy {proxy}")
                time.sleep(self.retry_backoff_seconds)

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
        proxies: dict = None,
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
        if proxies and self.proxy_providers:
            raise ValueError(
                "Cannot specify both proxies and proxy_providers at the same time"
            )
        self._retries = 0  # reset retries
        r = None

        super_request_params = (
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
        print(f"Using sticky proxies: {self.sticky_proxies}")

        # We do not need to get a new proxy if we are using
        # sticky proxies and we have a last successful provider used in the session
        if self._last_successful_provider and self.sticky_proxies:
            print(
                f"Using last successful provider {self._last_successful_provider}. self.proxies: {self.proxies}"
            )
            try:
                print(f"Making request to {url}")
                r = super().request(*super_request_params)
            except ConnectionError as e:
                print(e)
                print("ConnectionError encountered. Resetting adapters")
                self.reset_adapters()
            except ChunkedEncodingError as e:
                print(e)
                print("ChunkedEncodingError encountered. Resetting adapters")
                self.reset_adapters()
            self._retries += 1
            if r and self.is_successful_response(r):
                print(
                    f"Last successful provider {self._last_successful_provider} worked for url {url}. Status code {r.status_code}"
                )
                return r
            else:
                print(
                    f"Last successful provider {self._last_successful_provider} did not work with status code {r.status_code if r else None}. Setting last successful provider to None"
                )
                self._last_successful_provider = None

        if self.proxy_providers:
            r = self.request_with_providers(super_request_params)

        while self._retries < self.max_retries and not self.proxy_providers:
            print("Using no proxy providers")
            try:
                r = super().request(*super_request_params)
            except ConnectionError as e:
                print(e)
                print("ConnectionError encountered. Resetting adapters")
                self.reset_adapters()
            except ChunkedEncodingError as e:
                print(e)
                print("ChunkedEncodingError encountered. Resetting adapters")
                self.reset_adapters()
            self._retries += 1
            if not self.retry_on_failure or (r and self.is_successful_response(r)):
                return r
            time.sleep(self.retry_backoff_seconds)

        return r

    def get(self, url, **kwargs):
        return self.request("get", url, **kwargs)

    def post(self, url, data=None, json=None, **kwargs):
        return self.request("POST", url, data=data, json=json, **kwargs)
