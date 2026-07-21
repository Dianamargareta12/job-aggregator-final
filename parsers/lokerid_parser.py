import asyncio
import re
from urllib.parse import quote_plus, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup
from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

try:
    from parsers.base_scraper import BaseScraper
except Exception:
    class BaseScraper:
        def __init__(self, portal_name):
            self.portal_name = portal_name


class LokerIDParser(BaseScraper):
    """
    Parser Loker.id versi 5.

    Perubahan utama:
    - Membaca hanya card hasil pencarian: article.card[data-id]
    - Tidak lagi mencari semua tautan /job/ atau /lowongan/
    - Mengambil judul, perusahaan, URL, dan teks card dari card yang benar
    - Membuka detail hanya untuk melengkapi lokasi, deskripsi,
      kualifikasi, dan pendidikan
    - Deduplikasi berdasarkan data-id dan URL detail
    """

    def __init__(self, portal_name="Loker.id"):
        super().__init__(portal_name)
        self.base_url = "https://www.loker.id"
        self.max_results = 50

    def build_search_url(self, keyword):
        return (
            f"{self.base_url}/cari-lowongan-kerja"
            f"?q={quote_plus(keyword.strip())}"
        )

    def clean_text(self, value, default=""):
        if value is None:
            return default

        text = re.sub(r"\s+", " ", str(value)).strip()
        return text or default

    def normalize_url(self, url):
        if not url:
            return ""

        full_url = urljoin(self.base_url, str(url).strip())
        parsed = urlparse(full_url)

        return urlunparse(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path.rstrip("/"),
                "",
                "",
                "",
            )
        )

    def is_valid_detail_url(self, url):
        normalized = self.normalize_url(url).lower()

        if not normalized:
            return False

        parsed = urlparse(normalized)

        if parsed.netloc not in {"loker.id", "www.loker.id"}:
            return False

        invalid_fragments = [
            "/cari-lowongan-kerja",
            "/login",
            "/register",
            "/daftar",
            "/pasang-loker",
            "/pasang-lowongan",
            "/tips-loker",
            "/untuk-perusahaan",
            "/privacy",
            "/terms",
            "/feed",
        ]

        if any(fragment in normalized for fragment in invalid_fragments):
            return False

        return parsed.path.endswith(".html")

    def detect_education(self, *values):
        combined = " ".join(
            self.clean_text(value)
            for value in values
            if value is not None
        ).lower()

        groups = [
            (
                "SMA/SMK",
                [
                    r"\bsma\s*/\s*smk\b",
                    r"\bsmk\s*/\s*sma\b",
                    r"\bsma\b",
                    r"\bsmk\b",
                    r"\bslta\b",
                    r"\bsetara\s+sma\b",
                    r"\bsederajat\b",
                ],
            ),
            (
                "D3",
                [
                    r"\bd3\b",
                    r"\bdiploma\s*3\b",
                    r"\bdiploma\s*iii\b",
                ],
            ),
            (
                "S1",
                [
                    r"\bs1\b",
                    r"\bsarjana\b",
                    r"\bstrata\s*1\b",
                    r"\bbachelor(?:'s)?\b",
                ],
            ),
        ]

        detected = []

        for education, patterns in groups:
            if any(re.search(pattern, combined, re.I) for pattern in patterns):
                detected.append(education)

        return ", ".join(detected)

    async def close_cookie_banner(self, page):
        selectors = [
            "button:has-text('Terima semua')",
            "button:has-text('Terima')",
            "button:has-text('Setuju')",
            "button:has-text('Accept all')",
            "button:has-text('Accept')",
        ]

        for selector in selectors:
            try:
                button = page.locator(selector).first

                if await button.count() > 0 and await button.is_visible():
                    await button.click(timeout=2500)
                    await asyncio.sleep(0.7)
                    return

            except Exception:
                continue

    async def click_load_more(self, page):
        selectors = [
            "button:has-text('Muat lebih banyak')",
            "button:has-text('Tampilkan lebih banyak')",
            "button:has-text('Lihat lebih banyak')",
            "button:has-text('Load more')",
            "a:has-text('Muat lebih banyak')",
            "a:has-text('Tampilkan lebih banyak')",
        ]

        for selector in selectors:
            try:
                button = page.locator(selector).first

                if await button.count() > 0 and await button.is_visible():
                    await button.click(timeout=4000)
                    await asyncio.sleep(2)
                    print(
                        f"[{self.portal_name}] "
                        "Tombol muat lebih banyak diklik."
                    )
                    return True

            except Exception:
                continue

        return False

    async def wait_and_scroll_results(self, page):
        card_selector = "article.card[data-id]"

        await page.locator(card_selector).first.wait_for(
            state="attached",
            timeout=20000,
        )

        previous_count = 0
        stagnant_rounds = 0

        for scroll_number in range(12):
            current_count = await page.locator(card_selector).count()

            print(
                f"[{self.portal_name}] "
                f"Scroll {scroll_number + 1}/12 | "
                f"card: {current_count}"
            )

            if current_count >= self.max_results:
                break

            await page.evaluate(
                "window.scrollTo(0, document.body.scrollHeight)"
            )
            await asyncio.sleep(2)

            clicked = await self.click_load_more(page)

            if clicked:
                await asyncio.sleep(2)

            new_count = await page.locator(card_selector).count()

            if new_count <= previous_count:
                stagnant_rounds += 1
            else:
                stagnant_rounds = 0

            previous_count = new_count

            if stagnant_rounds >= 3:
                break

    async def collect_cards(self, page):
        card_selector = "article.card[data-id]"
        cards = page.locator(card_selector)
        total = await cards.count()

        print(
            f"[{self.portal_name}] "
            f"Total card hasil pencarian: {total}"
        )

        candidates = []
        seen_ids = set()
        seen_urls = set()

        for index in range(min(total, self.max_results)):
            card = cards.nth(index)

            try:
                job_id = self.clean_text(
                    await card.get_attribute("data-id")
                )

                title_locator = card.locator("h3").first
                title = self.clean_text(
                    await title_locator.inner_text()
                )

                company = "Perusahaan tidak tersedia"

                company_candidates = [
                    "span.text-sm.text-secondary-600",
                    "span[class*='text-secondary-600']",
                    "span[class*='text-secondary']",
                ]

                for selector in company_candidates:
                    locator = card.locator(selector).first

                    if await locator.count() > 0:
                        text = self.clean_text(
                            await locator.inner_text()
                        )

                        if text:
                            company = text
                            break

                links = card.locator("a[href$='.html']")
                href = ""

                for link_index in range(await links.count()):
                    candidate_href = self.normalize_url(
                        await links.nth(link_index).get_attribute("href")
                    )

                    if self.is_valid_detail_url(candidate_href):
                        href = candidate_href
                        break

                if not title or not href:
                    continue

                if job_id and job_id in seen_ids:
                    continue

                if href in seen_urls:
                    continue

                if job_id:
                    seen_ids.add(job_id)

                seen_urls.add(href)

                card_text = self.clean_text(
                    await card.inner_text()
                )

                candidates.append(
                    {
                        "job_id": job_id,
                        "title": title,
                        "company": company,
                        "href": href,
                        "card_text": card_text,
                    }
                )

                print(
                    f"[CARD {len(candidates)}] "
                    f"{title} | {company} | {href}"
                )

            except Exception as error:
                print(
                    f"[{self.portal_name} CARD WARNING] "
                    f"Index {index}: {error}"
                )

        return candidates

    def extract_detail_from_html(self, html, candidate, keyword):
        soup = BeautifulSoup(html, "html.parser")

        for node in soup(
            ["script", "style", "noscript", "svg", "footer", "nav"]
        ):
            node.decompose()

        main = soup.select_one("main") or soup
        body_text = self.clean_text(
            main.get_text(" ", strip=True)
        )

        title = candidate["title"]
        company = candidate["company"]
        card_text = candidate["card_text"]

        location = "Indonesia"
        description = "Deskripsi tidak tersedia"
        qualification = "Kualifikasi tidak tersedia"

        # Lokasi pada halaman detail biasanya tampil sebagai teks
        # setelah label "Lokasi".
        location_selectors = [
            "[class*='detail-job'] [class*='location']",
            "[class*='detail-job'] [class*='lokasi']",
            "[itemprop='jobLocation']",
            "[class*='location']",
            "[class*='lokasi']",
        ]

        for selector in location_selectors:
            target = soup.select_one(selector)

            if target:
                text = self.clean_text(
                    target.get_text(" ", strip=True)
                )

                if text and len(text) <= 250:
                    location = text
                    break

        # Fallback lokasi dari teks sekitar label Lokasi.
        if location == "Indonesia":
            match = re.search(
                r"\bLokasi\b\s*([A-Za-zÀ-ÿ0-9 .,'/-]{2,80})",
                body_text,
                re.I,
            )

            if match:
                candidate_location = self.clean_text(match.group(1))

                stop_words = [
                    "Tipe Pekerjaan",
                    "Level Pekerjaan",
                    "Fungsi",
                    "Pendidikan",
                    "Gaji",
                ]

                for stop_word in stop_words:
                    if stop_word.lower() in candidate_location.lower():
                        candidate_location = re.split(
                            stop_word,
                            candidate_location,
                            flags=re.I,
                        )[0]

                candidate_location = self.clean_text(candidate_location)

                if candidate_location:
                    location = candidate_location[:150]

        detail_container = (
            soup.select_one("div.detail-job")
            or soup.select_one("[class*='detail-job']")
            or soup.select_one("main")
        )

        if detail_container:
            detail_text = self.clean_text(
                detail_container.get_text(" ", strip=True)
            )

            if len(detail_text) >= 50:
                description = detail_text[:2500]

        # Ambil bagian tanggung jawab dan kualifikasi bila tersedia.
        qualification_patterns = [
            r"Kualifikasi(?:\s+Pekerjaan)?\s*:?\s*(.+)",
            r"Persyaratan(?:\s+Pekerjaan)?\s*:?\s*(.+)",
            r"Requirements?\s*:?\s*(.+)",
        ]

        for pattern in qualification_patterns:
            match = re.search(pattern, body_text, re.I | re.S)

            if match:
                qualification = self.clean_text(match.group(1))[:1800]
                break

        if qualification == "Kualifikasi tidak tersedia":
            qualification = body_text[:1800]

        education = self.detect_education(
            title,
            company,
            card_text,
            description,
            qualification,
            body_text,
            keyword,
        )

        return {
            "judul_posisi": title,
            "nama_perusahaan": company,
            "lokasi": location,
            "pendidikan": education,
            "deskripsi": description,
            "kualifikasi": qualification,
            "link_lowongan": candidate["href"],
            "portal_sumber": self.portal_name,
            "keyword_sumber": keyword,
        }

    async def extract_detail(self, detail_page, candidate, keyword):
        try:
            await detail_page.goto(
                candidate["href"],
                wait_until="domcontentloaded",
                timeout=35000,
            )

            await asyncio.sleep(1.5)

            html = await detail_page.content()

            return self.extract_detail_from_html(
                html,
                candidate,
                keyword,
            )

        except Exception as error:
            print(
                f"[{self.portal_name} DETAIL WARNING] "
                f"{candidate['title']} | {error}"
            )

            education = self.detect_education(
                candidate["title"],
                candidate["card_text"],
                keyword,
            )

            return {
                "judul_posisi": candidate["title"],
                "nama_perusahaan": candidate["company"],
                "lokasi": "Indonesia",
                "pendidikan": education,
                "deskripsi": candidate["card_text"],
                "kualifikasi": candidate["card_text"],
                "link_lowongan": candidate["href"],
                "portal_sumber": self.portal_name,
                "keyword_sumber": keyword,
            }

    async def scrape(self, keyword):
        search_url = self.build_search_url(keyword)

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-extensions",
                    "--disable-blink-features=AutomationControlled",
                ],
            )

            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/124.0.0.0 "
                    "Safari/537.36"
                ),
                locale="id-ID",
                timezone_id="Asia/Jakarta",
                viewport={"width": 1366, "height": 900},
                extra_http_headers={
                    "Accept-Language": (
                        "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7"
                    )
                },
            )

            page = await context.new_page()
            detail_page = await context.new_page()

            page.set_default_timeout(20000)
            detail_page.set_default_timeout(35000)

            try:
                print(
                    f"[{self.portal_name}] "
                    f"Membuka: {search_url}"
                )

                response = await page.goto(
                    search_url,
                    wait_until="domcontentloaded",
                    timeout=45000,
                )

                if response:
                    print(
                        f"[{self.portal_name}] "
                        f"HTTP status: {response.status}"
                    )

                await self.close_cookie_banner(page)
                await asyncio.sleep(4)

                await self.wait_and_scroll_results(page)

                candidates = await self.collect_cards(page)

                print(
                    f"[{self.portal_name}] "
                    f"Lowongan unik ditemukan: {len(candidates)}"
                )

                results = []

                for index, candidate in enumerate(candidates, start=1):
                    result = await self.extract_detail(
                        detail_page,
                        candidate,
                        keyword,
                    )

                    results.append(result)

                    print(
                        f"[DATA {index}/{len(candidates)}] "
                        f"{result['judul_posisi']} | "
                        f"{result['nama_perusahaan']} | "
                        f"{result['lokasi']} | "
                        f"{result['pendidikan'] or 'Pendidikan kosong'}"
                    )

                    # Jeda agar tidak membebani situs dan mengurangi blokir.
                    await asyncio.sleep(1.3)

                print(
                    f"[{self.portal_name}] "
                    f"Total data unik: {len(results)}"
                )

                return results

            except PlaywrightTimeoutError as error:
                print(
                    f"[ERROR] {self.portal_name} timeout: {error}"
                )
                return []

            except Exception as error:
                print(
                    f"[ERROR] {self.portal_name}: {error}"
                )
                return []

            finally:
                await detail_page.close()
                await page.close()
                await context.close()
                await browser.close()