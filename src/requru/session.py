from collections.abc import Callable

import requests
import time
from requests.models import Response

from .proxy_provider import ProxyProvider, ProviderParadigm
from .proxyrack import Proxyrack
from .nordvpn import Nordvpn


class Session(requests.Session):
    def __init__(self, sticky_proxies=False) -> None:
        super().__init__()
        self.proxy_providers: list[ProxyProvider] = [Proxyrack, Nordvpn]
        self._last_successful_provider: ProxyProvider = None
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
        proxies: dict = None,
        hooks=None,
        stream=None,
        verify=None,
        cert=None,
        json=None,
        retry_on_failure=True,
        max_retries: int = 3,
        is_successful_response: Callable[[Response], bool] = lambda _r: 200
        <= _r.status_code
        < 300,
        sticky_proxies: bool = False,
        proxy_providers: list[ProxyProvider] = None,
        retry_backoff_seconds: int = 30,
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
        proxy_providers_ = proxy_providers or self.proxy_providers
        if proxies and proxy_providers_:
            raise ValueError(
                "Cannot specify both proxies and proxy_providers at the same time"
            )
        retries = 0
        _sticky_proxies = sticky_proxies or self.sticky_proxies
        print(f"Using sticky proxies: {_sticky_proxies}")
        if self._last_successful_provider and _sticky_proxies:
            print(f"Using last successful provider {self._last_successful_provider}")
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
            retries += 1
            if is_successful_response(r):
                print(
                    f"Last successful provider worked with status code {r.status_code}"
                )
                return r

        if proxy_providers_:
            print(f"Using {proxy_providers_} as proxy providers")
            sorted_providers: list[ProxyProvider] = sorted(
                proxy_providers_, key=lambda p: p.strength, reverse=True
            )
            print(f"Sorted providers: {sorted_providers}")
            for provider in sorted_providers:
                provider_retries = 0
                print(f"Trying provider {provider.__name__}")

                print("Getting new proxy")
                proxy = provider.get_proxy(sticky=_sticky_proxies)
                self.proxies.update({"http": proxy, "https": proxy})

                while True:
                    print(f"Request attempt {retries + 1}")
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
                    provider_retries += 1
                    retries += 1
                    success = is_successful_response(r)
                    if success:
                        print(
                            f"Response successful with status code {r.status_code}. Setting last successful provider to {provider.__name__}"
                        )
                        self._last_successful_provider = provider
                    else:
                        print(f"Response unsuccessful with status code {r.status_code}")
                    if not retry_on_failure or retries >= max_retries or success:
                        return r
                    if provider_retries >= provider.max_retries:
                        print(
                            f"Provider {provider.__name__} exhausted. Moving on to next provider"
                        )
                        self.proxies = {}
                        time.sleep(retry_backoff_seconds)
                        # go to next provider
                        break

                    # If we are using sticky proxies, we need to get a new sticky proxy.
                    # if we are not using sticky proxies, but the provider paradigm is DIRECT, we
                    # also need to get a new proxy.
                    if (_sticky_proxies) or (
                        not _sticky_proxies
                        and provider.paradigm == ProviderParadigm.DIRECT
                    ):
                        print("Getting new proxy")
                        proxy = provider.get_proxy(sticky=_sticky_proxies)
                        self.proxies.update({"http": proxy, "https": proxy})
                    time.sleep(retry_backoff_seconds)

        while retries < max_retries:
            print("Using no proxy providers")
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
            retries += 1
            if not retry_on_failure or is_successful_response(r):
                return r
            time.sleep(retry_backoff_seconds)

        return r
