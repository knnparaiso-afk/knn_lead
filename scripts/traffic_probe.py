"""Mede visitas e carga GET sem criar campanhas, usuários ou bancos de teste.

Uso: python scripts/traffic_probe.py visit http://127.0.0.1:5000/
     python scripts/traffic_probe.py load http://127.0.0.1:5000/ --users 20
"""

import argparse
import gzip
import math
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


USER_AGENT = "KNN-traffic-probe/1.0 (GET-only)"
CSS_URL = re.compile(r"url\(\s*['\"]?([^)'\"]+)", re.IGNORECASE)


def percentile(values, fraction):
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def same_origin(base, candidate):
    base_parts = urlparse(base)
    parts = urlparse(candidate)
    return parts.scheme in ("http", "https") and parts.netloc == base_parts.netloc


def get(url, timeout, validators=None):
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
    if validators:
        headers.update(validators)
    started = time.perf_counter()
    try:
        with urlopen(Request(url, headers=headers), timeout=timeout) as response:
            body = response.read()
            return {
                "url": url,
                "status": response.status,
                "headers": response.headers,
                "body": body,
                "ms": (time.perf_counter() - started) * 1000,
                "completed_at": time.monotonic(),
                "error": None,
            }
    except HTTPError as error:
        body = error.read()
        return {
            "url": url,
            "status": error.code,
            "headers": error.headers,
            "body": body,
            "ms": (time.perf_counter() - started) * 1000,
            "completed_at": time.monotonic(),
            "error": None,
        }
    except (URLError, TimeoutError, OSError) as error:
        return {
            "url": url,
            "status": 0,
            "headers": {},
            "body": b"",
            "ms": (time.perf_counter() - started) * 1000,
            "completed_at": time.monotonic(),
            "error": str(error),
        }


def decoded_text(result):
    body = result["body"]
    if result["headers"].get("Content-Encoding", "").lower() == "gzip":
        body = gzip.decompress(body)
    return body.decode("utf-8", errors="replace")


class AssetParser(HTMLParser):
    def __init__(self, base):
        super().__init__()
        self.base = base
        self.urls = set()
        self.in_style = False
        self.inline_css = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "style":
            self.in_style = True
        if tag in ("script", "img", "source") and values.get("src"):
            self.urls.add(urljoin(self.base, values["src"]))
        if tag == "link" and values.get("href"):
            rel = (values.get("rel") or "").lower().split()
            if any(value in rel for value in ("stylesheet", "preload", "icon")):
                self.urls.add(urljoin(self.base, values["href"]))
        if values.get("srcset"):
            for candidate in values["srcset"].split(","):
                parts = candidate.strip().split()
                if parts:
                    self.urls.add(urljoin(self.base, parts[0]))
        if values.get("style"):
            self.inline_css.append(values["style"])

    def handle_endtag(self, tag):
        if tag == "style":
            self.in_style = False

    def handle_data(self, data):
        if self.in_style:
            self.inline_css.append(data)


def css_assets(css, base):
    return {urljoin(base, match) for match in CSS_URL.findall(css)}


def fresh_for_repeat(result):
    cache_control = result["headers"].get("Cache-Control", "").lower()
    if "no-cache" in cache_control or "no-store" in cache_control:
        return False
    match = re.search(r"(?:^|,)\s*max-age=(\d+)", cache_control)
    return bool(match and int(match.group(1)) > 0)


def validators_for(result):
    headers = result["headers"]
    validators = {}
    if headers.get("ETag"):
        validators["If-None-Match"] = headers["ETag"]
    if headers.get("Last-Modified"):
        validators["If-Modified-Since"] = headers["Last-Modified"]
    return validators


def visit(base, timeout):
    cache = {}
    dependencies = {}
    had_errors = False
    for label in ("nova", "repetida"):
        page = get(base, timeout, validators_for(cache[base]) if base in cache else None)
        fetched = [page]
        skipped = 0
        if page["status"] not in (200, 304):
            print(f"Visita {label}: HTTP {page['status']} ({page['error'] or 'sem HTML'}).")
            return 1
        if page["status"] == 200:
            cache[base] = page
        parser = AssetParser(base)
        parser.feed(decoded_text(cache[base]))
        queue = list(parser.urls | css_assets("\n".join(parser.inline_css), base))
        seen = set()
        while queue:
            url = queue.pop()
            if url in seen or not same_origin(base, url) or url.startswith("data:"):
                continue
            seen.add(url)
            cached = cache.get(url)
            if cached and fresh_for_repeat(cached):
                skipped += 1
                queue.extend(dependencies.get(url, ()))
                continue
            result = get(url, timeout, validators_for(cached) if cached else None)
            fetched.append(result)
            if result["status"] == 200:
                cache[url] = result
                if "text/css" in result["headers"].get("Content-Type", ""):
                    dependencies[url] = css_assets(decoded_text(result), url)
                    queue.extend(dependencies[url])
        errors = [result for result in fetched if result["status"] not in (200, 304)]
        had_errors |= bool(errors)
        bytes_received = sum(len(result["body"]) for result in fetched)
        print(
            f"Visita {label}: {len(fetched)} requisições, "
            f"{skipped} recursos aproveitados do cache, "
            f"{bytes_received / 1024:.1f} KiB transferidos, {len(errors)} erros."
        )
        for result in errors[:5]:
            print(f"  HTTP {result['status']} {result['url']} {result['error'] or ''}")
    print("Escopo: HTML, CSS, JS e imagens referenciados no HTML/CSS; modelos 3D acionados pelo JavaScript não entram nesta conta.")
    return 1 if had_errors else 0


def load(base, users, duration, think_time, timeout):
    barrier = threading.Barrier(users + 1)
    start_at = time.monotonic() + 0.25
    deadline = start_at + duration

    def user():
        results = []
        barrier.wait()
        time.sleep(max(0, start_at - time.monotonic()))
        while time.monotonic() < deadline:
            results.append(get(base, timeout))
            if think_time:
                time.sleep(think_time)
        return results

    with ThreadPoolExecutor(max_workers=users) as executor:
        futures = [executor.submit(user) for _ in range(users)]
        barrier.wait()
        time.sleep(max(0, start_at - time.monotonic()))
        started = time.monotonic()
        results = [result for future in futures for result in future.result()]
        elapsed = time.monotonic() - started

    latencies = [result["ms"] for result in results]
    errors = [result for result in results if result["status"] < 200 or result["status"] >= 400]
    status_counts = {}
    for result in results:
        status_counts[result["status"]] = status_counts.get(result["status"], 0) + 1
    print(
        f"{users} usuários, {elapsed:.1f}s, {len(results)} GET, "
        f"{len(results) / elapsed:.1f} req/s, {len(errors)} erros"
    )
    print(
        f"Latência: p50 {percentile(latencies, 0.50):.0f} ms; "
        f"p95 {percentile(latencies, 0.95):.0f} ms; "
        f"máximo {max(latencies, default=0):.0f} ms"
    )
    print(f"Transferência: {sum(len(result['body']) for result in results) / 1024:.1f} KiB; HTTP {status_counts}")
    windows = {}
    for result in results:
        window = max(0, int((result["completed_at"] - started) // 10))
        windows.setdefault(window, []).append(result)
    for window, batch in sorted(windows.items()):
        window_errors = sum(result["status"] < 200 or result["status"] >= 400 for result in batch)
        print(
            f"  {window * 10:02d}–{(window + 1) * 10:02d}s: "
            f"{len(batch)} GET, p95 {percentile([result['ms'] for result in batch], 0.95):.0f} ms, "
            f"{window_errors} erros"
        )
    for result in errors[:5]:
        print(f"  HTTP {result['status']} {result['error'] or result['url']}")
    return 1 if errors else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("visit", "load"))
    parser.add_argument("url", help="URL pública de leitura (GET) a medir")
    parser.add_argument("--allow-remote", action="store_true", help="Permite URL remota; faça carga apenas em ambiente de teste")
    parser.add_argument("--test-environment", action="store_true", help="Confirma que a carga remota vai para um serviço de teste")
    parser.add_argument("--users", type=int, default=20)
    parser.add_argument("--duration", type=float, default=15)
    parser.add_argument("--think-time", type=float, default=1)
    parser.add_argument("--timeout", type=float, default=10)
    args = parser.parse_args()
    target = urlparse(args.url)
    if target.scheme not in ("http", "https") or not target.netloc or target.username or target.password:
        parser.error("Informe uma URL HTTP(S) sem credenciais.")
    if target.hostname not in ("localhost", "127.0.0.1", "::1") and not args.allow_remote:
        parser.error("URL remota exige --allow-remote; faça carga apenas em ambiente de teste.")
    if args.mode == "load" and target.hostname not in ("localhost", "127.0.0.1", "::1") and not args.test_environment:
        parser.error("Carga remota exige --test-environment; não use no site publicado.")
    if args.users < 1 or args.users > 50 or args.duration <= 0 or args.think_time < 0 or args.timeout <= 0:
        parser.error("Use 1–50 usuários e duração/timeout positivos.")
    return visit(args.url, args.timeout) if args.mode == "visit" else load(
        args.url, args.users, args.duration, args.think_time, args.timeout
    )


if __name__ == "__main__":
    raise SystemExit(main())
