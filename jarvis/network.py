"""Public HTTPS fetches with exact-host allowlists and DNS-pinned connections."""

from __future__ import annotations

import asyncio
import http.client
import ipaddress
import socket
import ssl
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from jarvis.security import Denied


class Extractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.in_title = False
        self.title: list[str] = []
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.hidden = max(0, self.hidden - 1)
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host: str, ip: str, timeout: float):
        self.tls_context = ssl.create_default_context()
        super().__init__(host, port=443, timeout=timeout, context=self.tls_context)
        self.ip = ip

    def connect(self) -> None:
        # Connect to the validated address, while verifying TLS against the original host.
        sock = socket.create_connection((self.ip, 443), self.timeout)
        try:
            self.sock = self.tls_context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


class Web:
    def __init__(self, hosts: list[str]):
        self.hosts = hosts

    def validate(self, url: str) -> tuple[str, str, str]:
        if len(url) > 4096 or any(ord(c) < 32 for c in url):
            raise Denied("Invalid URL")
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.port not in {None, 443}
            or parsed.username
            or parsed.password
        ):
            raise Denied("Only public HTTPS URLs on port 443 are allowed")
        host = parsed.hostname.lower().rstrip(".")
        if host not in self.hosts:
            raise Denied(f"Host {host} is not in Settings → allowed network hosts")
        addresses = {
            result[4][0] for result in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        }
        if not addresses or any(
            not ipaddress.ip_address(address).is_global for address in addresses
        ):
            raise Denied("Private, local, reserved, and mixed DNS answers are blocked")
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        return host, str(sorted(addresses)[0]), path

    def fetch_bytes(self, url: str, limit: int = 2_000_000) -> tuple[str, str, bytes]:
        started = time.monotonic()
        for _ in range(5):
            host, address, path = self.validate(url)
            connection = PinnedHTTPS(host, address, timeout=10)
            try:
                connection.request(
                    "GET",
                    path,
                    headers={
                        "Host": host,
                        "User-Agent": "JarvisAI/0.1",
                        "Accept-Encoding": "identity",
                    },
                )
                response = connection.getresponse()
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.getheader("Location")
                    if not location:
                        raise ValueError("Redirect has no destination")
                    url = urljoin(url, location)
                    continue
                if response.status != 200:
                    raise ValueError(f"Source returned HTTP {response.status}")
                chunks = []
                size = 0
                while True:
                    if time.monotonic() - started > 20:
                        raise TimeoutError("Fetch exceeded its total time budget")
                    chunk = response.read(min(65536, limit + 1 - size))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > limit:
                        raise ValueError("Source exceeds download size budget")
                return (
                    url,
                    response.getheader("Content-Type", "application/octet-stream"),
                    b"".join(chunks),
                )
            finally:
                connection.close()
        raise ValueError("Too many redirects")

    async def read(self, url: str) -> dict:
        final_url, content_type, body = await asyncio.to_thread(self.fetch_bytes, url)
        if not any(
            kind in content_type for kind in ("text/", "application/json", "application/xml")
        ):
            raise ValueError("Source is not text; use a supported document workflow")
        text = body.decode("utf-8", errors="replace")
        title = final_url
        if "html" in content_type:
            parser = Extractor()
            parser.feed(text)
            title = " ".join(parser.title) or final_url
            text = "\n".join(parser.parts)
        return {
            "url": final_url,
            "title": title[:500],
            "text": text[:24000],
            "retrieved_at": time.time(),
            "truncated": len(text) > 24000,
            "trust": "untrusted_external_content",
        }
