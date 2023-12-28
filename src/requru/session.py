from collections.abc import Callable

import requests
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Union
from requests.models import Response
from requests.exceptions import (
    SSLError,
    ProxyError,
    ChunkedEncodingError,
    ConnectionError,
)
from requests.adapters import HTTPAdapter

from .proxy_provider import ProxyProvider, ProviderParadigm
from .proxyrack import ProxyrackProvider
from .nordvpn import Nordvpn


@dataclass
class ProxyConfig:
    providers: list[ProxyProvider] = field(
        default_factory=lambda: [ProxyrackProvider()]
    )
    freeze_after_first_successful_request: bool = False
    # TODO: freeze should not be used with DNS providers using random ports. Validate.


@dataclass
class RetryConfig:
    retry_on_failure: bool = True
    backoff_seconds: int = 30
    max_tries: int = 3
    is_successful_response: Callable[[Response], bool] = (
        lambda _r: 200 <= _r.status_code < 300
    )


class Session(requests.Session):
    def __init__(
        self,
        proxy_config: ProxyConfig = ProxyConfig(),
        retry_config: RetryConfig = RetryConfig(),
    ) -> None:
        super().__init__()
        self.proxy_config = proxy_config
        self.retry_config = retry_config
        self.verify = False
        self._successful_requests = 0
        self._tries: int = 0
        self._proxies_frozen: bool = False
        # current request params. Set by request method
        self._super_request_params: tuple = ()
        self.reset_adapters()

    def reset_adapters(self):
        self.adapters.clear()
        self.mount("https://", HTTPAdapter(max_retries=3))
        self.mount("http://", HTTPAdapter(max_retries=3))

    def should_get_new_proxy_after_failed_request(self, provider: ProxyProvider):
        """
        Determine whether we should get a new proxy after a failed request.
        we should get a new proxy if session proxies are not frozen and either
        provider paradigm is DNS and it is using sticky ports or provider
        paradigm is DIRECT.
        :param provider: ProxyProvider instance from which the new proxy is to
        be fetched
        """
        return not self._proxies_frozen and (
            provider.paradigm == ProviderParadigm.DIRECT
            or (provider.paradigm == ProviderParadigm.DNS and provider.use_sticky_ports)
        )

    def try_super_request_and_handle_exceptions(self):
        response: Response | None = None
        try:
            response = super().request(*self._super_request_params)
        except ConnectionError as e:
            print(e)
            print("ConnectionError encountered. Resetting adapters")
            self.reset_adapters()
        except ChunkedEncodingError as e:
            print(e)
            print("ChunkedEncodingError encountered. Resetting adapters")
            self.reset_adapters()
        return response

    def request_with_providers(self):
        url = self._super_request_params[1]
        print(f"Using {self.proxy_config.providers} as proxy providers")
        sorted_providers: list[ProxyProvider] = sorted(
            self.proxy_config.providers, key=lambda p: p.strength, reverse=True
        )
        print(f"Sorted providers: {sorted_providers}")
        response: Response | None = None
        for provider in sorted_providers:
            provider_tries = 0
            print(f"Trying provider {provider.__class__.__name__}")
            print(f"Provider max tries: {provider.max_tries_per_request}")

            print("Getting new proxy")
            proxy = provider.get_new_proxy()
            self.proxies.update({"http": proxy, "https": proxy})
            print(f"Using proxy {proxy}")

            while provider_tries < provider.max_tries_per_request:
                print(f"Request attempt {self._tries + 1} to url {url}")
                response = self.try_super_request_and_handle_exceptions()
                provider_tries += 1
                self._tries += 1
                success = (
                    self.retry_config.is_successful_response(response)
                    if response is not None
                    else False
                )
                if success:
                    self._successful_requests += 1
                    print(
                        f"Request to {url} successful with status code {response.status_code}. Successful requests in session: {self._successful_requests}"
                    )
                    if (
                        self._successful_requests == 1
                        and self.proxy_config.freeze_after_first_successful_request
                    ):
                        print(
                            f"First successful request. Freezing proxy {proxy} for future requests"
                        )
                        self._proxies_frozen = True
                else:
                    print(
                        f"Response unsuccessful with status code {response.status_code if response is not None else None}"
                    )
                if (
                    not self.retry_config.retry_on_failure
                    or self._tries >= self.retry_config.max_tries
                    or success
                ):
                    return response
                elif self.should_get_new_proxy_after_failed_request(provider):
                    print(f"Getting new proxy after unsusccessful request to {url}")
                    proxy = provider.get_new_proxy()
                    self.proxies.update({"http": proxy, "https": proxy})
                    print(f"Using proxy {proxy}")
                time.sleep(self.retry_config.backoff_seconds)
            else:
                print(
                    f"Provider {provider.__class__.__name__} exhausted. Moving on to next provider"
                )

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
        self._super_request_params = super_request_params
        if proxies and self.proxy_config.providers:
            raise ValueError(
                "Cannot specify both proxies and proxy_providers at the same time"
            )
        self._tries = 0  # reset tries
        r: Response | None = None

        if self.proxy_config.providers and not self._proxies_frozen:
            r = self.request_with_providers()
        else:
            print(f"Proxies frozen: {self._proxies_frozen}. Proxies: {self.proxies}")
            while self._tries < self.retry_config.max_tries:
                r = self.try_super_request_and_handle_exceptions()
                self._tries += 1
                success = (
                    self.retry_config.is_successful_response(r)
                    if r is not None
                    else False
                )
                if not self.retry_config.retry_on_failure or (success):
                    return r
                time.sleep(self.retry_config.backoff_seconds)
            else:
                print(
                    f"Exhausted all tries. Last response status code: {r.status_code if r is not None else None}"
                )

        return r

    def get(self, url, **kwargs):
        return self.request("get", url, **kwargs)

    def post(self, url, data=None, json=None, **kwargs):
        return self.request("POST", url, data=data, json=json, **kwargs)

    def close(self) -> None:
        if self.proxy_config.providers:
            for provider in self.proxy_config.providers:
                provider.close()
        return super().close()

    def __exit__(self, *args):
        self.close()
