from sf_apartment_aggregator.normalize import canonicalize_url


def test_canonicalize_url_strips_utm_and_normalizes_host() -> None:
    url = "HTTPS://WWW.Example.com/listing/1/?utm_source=abc&z=2&a=1"
    assert canonicalize_url(url) == "https://example.com/listing/1?a=1&z=2"
