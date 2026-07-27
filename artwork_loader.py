import pygame as pg
import urllib.request
import urllib.parse
import ssl
import io
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from settings import (
    TEXTURE_SIZE,
    GALLERY_PAGINATION_FORMAT,
    GALLERY_START_PAGE,
    GALLERY_BATCH_SIZE,
    GALLERY_MAX_PAGES_PER_BATCH,
    ARTWORK_FIRST_TEXTURE_ID,
)

FRAME_COLOR = (190, 150, 70)   # warm gold
FRAME_INNER = (60, 40, 10)     # dark inner lip
FRAME_WIDTH = 20               # px on each side of the 256×256 texture

FIRST_ARTWORK_ID = ARTWORK_FIRST_TEXTURE_ID

# SSL context that skips certificate verification — acceptable for a local
# gallery tool, avoids failures caused by expired/missing CA certs.
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _open(url: str, timeout: int = 10):
    """urllib.request.urlopen with a consistent User-Agent and relaxed SSL."""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    return urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX)


class _PageParser(HTMLParser):
    """
    Collect <img> src URLs and a single rel="next" link from an HTML page.
    Handles both <link rel="next" href="..."> and <a rel="next" href="...">.
    """
    def __init__(self):
        super().__init__()
        self.img_urls: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'img':
            src = a.get('src') or a.get('data-src') or a.get('data-lazy-src')
            if src:
                self.img_urls.append(src)
def _build_page_url(base_url: str, page_number: int, pagination_format: str) -> str:
    if '{}' in pagination_format:
        suffix = pagination_format.format(page_number)
    else:
        suffix = f'{pagination_format}{page_number}'
    return urllib.parse.urljoin(base_url, suffix)


def scrape_page_image_urls(page_url: str) -> list[str]:
    with _open(page_url) as resp:
        html = resp.read().decode('utf-8', errors='replace')
        base_url = resp.url if hasattr(resp, 'url') else page_url

    parser = _PageParser()
    parser.feed(html)

    skip_exts = ('.svg', '.gif', '.ico', '.webp')
    urls = []
    for raw_url in parser.img_urls:
        if raw_url.startswith('data:'):
            continue
        if any(raw_url.lower().endswith(ext) for ext in skip_exts):
            continue
        urls.append(urllib.parse.urljoin(base_url, raw_url))
    return urls


def _draw_frame(surface: pg.Surface) -> None:
    size = surface.get_width()
    f = FRAME_WIDTH
    pg.draw.rect(surface, FRAME_COLOR, (0, 0, size, size), f)
    pg.draw.rect(surface, FRAME_INNER, (f - 2, f - 2, size - 2 * (f - 2), size - 2 * (f - 2)), 2)
    pg.draw.rect(surface, (220, 190, 110), (1, 1, size - 2, size - 2), 1)


def _fallback_surface() -> pg.Surface:
    surf = pg.Surface((TEXTURE_SIZE, TEXTURE_SIZE)).convert()
    surf.fill((70, 70, 80))
    _draw_frame(surf)
    return surf


def _fetch_bytes(url: str) -> bytes:
    with _open(url) as resp:
        return resp.read()


class ArtworkStream:
    def __init__(
        self,
        base_url: str,
        pagination_format: str = GALLERY_PAGINATION_FORMAT,
        start_page: int = GALLERY_START_PAGE,
    ):
        self.base_url = base_url
        self.pagination_format = pagination_format
        self.next_page = start_page
        self.next_texture_id = FIRST_ARTWORK_ID
        self.seen_urls: set[str] = set()
        self.exhausted = False

    def _decode_to_surface(self, data: bytes | None) -> pg.Surface:
        if data is None:
            return _fallback_surface()
        try:
            image = pg.image.load(io.BytesIO(data)).convert()
            image = pg.transform.scale(image, (TEXTURE_SIZE, TEXTURE_SIZE))
            _draw_frame(image)
            return image
        except Exception as exc:
            print(f'[artwork_loader] decode failed: {exc}')
            return _fallback_surface()

    def load_next_batch(
        self,
        target_images: int = GALLERY_BATCH_SIZE,
        max_pages_per_batch: int = GALLERY_MAX_PAGES_PER_BATCH,
    ) -> dict[int, pg.Surface]:
        if self.exhausted:
            return {}

        unique_urls: list[str] = []
        pages_scraped = 0
        while len(unique_urls) < target_images and pages_scraped < max_pages_per_batch:
            page_url = _build_page_url(self.base_url, self.next_page, self.pagination_format)
            print(f'[artwork_loader] scraping page {self.next_page}: {page_url}')
            try:
                page_urls = scrape_page_image_urls(page_url)
            except Exception as exc:
                print(f'[artwork_loader] failed to scrape page {self.next_page}: {exc}')
                self.exhausted = True
                break

            pages_scraped += 1
            self.next_page += 1

            new_on_page = 0
            for url in page_urls:
                if url not in self.seen_urls:
                    self.seen_urls.add(url)
                    unique_urls.append(url)
                    new_on_page += 1
                    if len(unique_urls) >= target_images:
                        break

            if not page_urls or new_on_page == 0:
                # Treat repeated/no-image pages as end of useful pagination.
                self.exhausted = True
                break

        if not unique_urls:
            return {}

        raw: dict[int, bytes | None] = {}
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(_fetch_bytes, url): idx for idx, url in enumerate(unique_urls)}
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    raw[idx] = future.result()
                except Exception as exc:
                    print(f'[artwork_loader] fetch failed for image {idx}: {exc}')
                    raw[idx] = None

        results: dict[int, pg.Surface] = {}
        for idx in range(len(unique_urls)):
            texture_id = self.next_texture_id
            self.next_texture_id += 1
            results[texture_id] = self._decode_to_surface(raw.get(idx))

        print(f'[artwork_loader] loaded {len(results)} artwork(s); next page={self.next_page}')
        return results
