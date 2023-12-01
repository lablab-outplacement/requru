from .session import Session


def request(method, url, **kwargs):
    with Session() as session:
        return session.request(method=method, url=url, **kwargs)


def get(url, params=None, **kwargs):
    return request("get", url, params=params, **kwargs)


def options(url, **kwargs):
    r"""Sends an OPTIONS request.

    :param url: URL for the new :class:`Request` object.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """

    return request("options", url, **kwargs)


def head(url, **kwargs):
    r"""Sends a HEAD request.

    :param url: URL for the new :class:`Request` object.
    :param \*\*kwargs: Optional arguments that ``request`` takes. If
        `allow_redirects` is not provided, it will be set to `False` (as
        opposed to the default :meth:`request` behavior).
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """

    kwargs.setdefault("allow_redirects", False)
    return request("head", url, **kwargs)


def post(url, data=None, json=None, **kwargs):
    r"""Sends a POST request.

    :param url: URL for the new :class:`Request` object.
    :param data: (optional) Dictionary, list of tuples, bytes, or file-like
        object to send in the body of the :class:`Request`.
    :param json: (optional) A JSON serializable Python object to send in the body of the :class:`Request`.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """

    return request("post", url, data=data, json=json, **kwargs)


def put(url, data=None, **kwargs):
    r"""Sends a PUT request.

    :param url: URL for the new :class:`Request` object.
    :param data: (optional) Dictionary, list of tuples, bytes, or file-like
        object to send in the body of the :class:`Request`.
    :param json: (optional) A JSON serializable Python object to send in the body of the :class:`Request`.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """

    return request("put", url, data=data, **kwargs)


def patch(url, data=None, **kwargs):
    r"""Sends a PATCH request.

    :param url: URL for the new :class:`Request` object.
    :param data: (optional) Dictionary, list of tuples, bytes, or file-like
        object to send in the body of the :class:`Request`.
    :param json: (optional) A JSON serializable Python object to send in the body of the :class:`Request`.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """

    return request("patch", url, data=data, **kwargs)


def delete(url, **kwargs):
    r"""Sends a DELETE request.

    :param url: URL for the new :class:`Request` object.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """

    return request("delete", url, **kwargs)
