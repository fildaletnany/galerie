import pygame as pg
import urllib.request
import urllib.parse
import ssl
import io
import random
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from settings import (
    TEXTURE_SIZE,
    GALLERY_PAGINATION_FORMAT,
    GALLERY_START_PAGE,
    GALLERY_BATCH_SIZE,
    GALLERY_MAX_PAGES_PER_BATCH,
    ARTWORK_FIRST_TEXTURE_ID,
    ARTWORK_TILE_BACKGROUND_TEXTURE,
)

FRAME_COLOR = (190, 150, 70)   # warm gold
FRAME_INNER = (60, 40, 10)     # dark inner lip
FRAME_WIDTH = 20               # px on each side of the 256×256 texture

FIRST_ARTWORK_ID = ARTWORK_FIRST_TEXTURE_ID
_artwork_background_surface: pg.Surface | None = None

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


def _draw_frame(surface: pg.Surface, rect: pg.Rect | None = None) -> None:
    frame_rect = rect if rect is not None else surface.get_rect()
    frame_width = max(2, min(FRAME_WIDTH, min(frame_rect.width, frame_rect.height) // 8))
    pg.draw.rect(surface, FRAME_COLOR, frame_rect, frame_width)

    inner = frame_rect.inflate(-2 * max(1, frame_width - 2), -2 * max(1, frame_width - 2))
    if inner.width > 2 and inner.height > 2:
        pg.draw.rect(surface, FRAME_INNER, inner, 2)
    pg.draw.rect(surface, (220, 190, 110), frame_rect, 1)


def _get_artwork_background_surface() -> pg.Surface:
    global _artwork_background_surface
    if _artwork_background_surface is not None:
        return _artwork_background_surface

    try:
        texture = pg.image.load(ARTWORK_TILE_BACKGROUND_TEXTURE).convert()
        _artwork_background_surface = pg.transform.scale(texture, (TEXTURE_SIZE, TEXTURE_SIZE))
    except Exception as exc:
        print(f'[artwork_loader] failed to load artwork background texture: {exc}')
        fallback = pg.Surface((TEXTURE_SIZE, TEXTURE_SIZE)).convert()
        fallback.fill((25, 25, 25))
        _artwork_background_surface = fallback
    return _artwork_background_surface


def _compose_framed_surface(image: pg.Surface) -> pg.Surface:
    canvas = _get_artwork_background_surface().copy()

    src_w, src_h = image.get_width(), image.get_height()
    if src_w <= 0 or src_h <= 0:
        _draw_frame(canvas)
        return canvas

    # Reserve space for the frame so it doesn't overlap/crop the image content.
    inner_size = TEXTURE_SIZE - 2 * FRAME_WIDTH
    if inner_size <= 0:
        inner_size = TEXTURE_SIZE

    scale = min(inner_size / src_w, inner_size / src_h)
    dst_w = max(1, int(src_w * scale))
    dst_h = max(1, int(src_h * scale))
    scaled = pg.transform.scale(image, (dst_w, dst_h))

    content_x = (TEXTURE_SIZE - dst_w) // 2
    content_y = (TEXTURE_SIZE - dst_h) // 2
    content_rect = pg.Rect(content_x, content_y, dst_w, dst_h)
    canvas.blit(scaled, content_rect.topleft)

    frame_rect = content_rect.inflate(2 * FRAME_WIDTH, 2 * FRAME_WIDTH)
    frame_rect.clamp_ip(canvas.get_rect())
    _draw_frame(canvas, frame_rect)
    return canvas


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

    def _decode_to_surface(self, data: bytes | None) -> pg.Surface:
        if data is None:
            return _fallback_surface()
        try:
            image = pg.image.load(io.BytesIO(data)).convert()
            return _compose_framed_surface(image)
        except Exception as exc:
            print(f'[artwork_loader] decode failed: {exc}')
            return _fallback_surface()

    def load_next_batch(
        self,
        target_images: int = GALLERY_BATCH_SIZE,
        max_pages_per_batch: int = GALLERY_MAX_PAGES_PER_BATCH,
    ) -> dict[int, pg.Surface]:
        unique_urls: list[str] = []
        seen_in_batch: set[str] = set()
        pages_scraped = 0
        while len(unique_urls) < target_images and pages_scraped < max_pages_per_batch:
            page_url = _build_page_url(self.base_url, self.next_page, self.pagination_format)
            print(f'[artwork_loader] scraping page {self.next_page}: {page_url}')
            try:
                page_urls = scrape_page_image_urls(page_url)
            except Exception as exc:
                print(f'[artwork_loader] failed to scrape page {self.next_page}: {exc}')
                page_urls = []

            pages_scraped += 1
            self.next_page += 1

            random.shuffle(page_urls)
            for url in page_urls:
                if url not in seen_in_batch:
                    seen_in_batch.add(url)
                    unique_urls.append(url)
                    if len(unique_urls) >= target_images:
                        break

        if not unique_urls:
            return {}

        random.shuffle(unique_urls)
        unique_urls = unique_urls[:target_images]

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
            texture_id = FIRST_ARTWORK_ID + idx
            results[texture_id] = self._decode_to_surface(raw.get(idx))

        print(f'[artwork_loader] loaded {len(results)} artwork(s); next page={self.next_page}')
        return results
