import asyncio
import re
from urllib.parse import quote_plus, urljoin

from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)


class JobstreetParser:
    def __init__(self, portal_name: str = "Jobstreet"):
        self.portal_name = portal_name
        self.base_url = "https://id.jobstreet.com"

    def detect_education(self, *values: str) -> str:
        """
        Mendeteksi jenjang pendidikan dari judul, deskripsi,
        kualifikasi, atau isi halaman detail lowongan.
        """
        combined_text = " ".join(
            str(value or "") for value in values
        ).lower()

        combined_text = re.sub(r"\s+", " ", combined_text).strip()

        patterns = [
            (
                "SMA/SMK",
                [
                    r"\bsma\s*/\s*smk\b",
                    r"\bsmk\s*/\s*sma\b",
                    r"\bsma\s+atau\s+smk\b",
                    r"\bminimal\s+sma\b",
                    r"\bminimal\s+smk\b",
                    r"\bsma\s+sederajat\b",
                    r"\bsmk\s+sederajat\b",
                    r"\bslta\b",
                ],
            ),
            (
                "D3",
                [
                    r"\bd3\b",
                    r"\bdiploma\s*3\b",
                    r"\bdiploma\s*iii\b",
                    r"\bminimal\s+diploma\b",
                ],
            ),
            (
                "S1",
                [
                    r"\bs1\b",
                    r"\bsarjana\b",
                    r"\bbachelor(?:'s)?\b",
                    r"\bstrata\s*1\b",
                ],
            ),
        ]

        detected = []

        for education, education_patterns in patterns:
            if any(
                re.search(pattern, combined_text, re.IGNORECASE)
                for pattern in education_patterns
            ):
                detected.append(education)

        if not detected:
            return ""

        order = ["SMA/SMK", "D3", "S1"]
        detected = [
            education
            for education in order
            if education in detected
        ]

        return ", ".join(detected)

    async def extract_detail_information(
        self,
        detail_page,
        job_url: str,
    ) -> tuple[str, str, str]:
        """
        Membuka halaman detail untuk mengambil deskripsi,
        kualifikasi, dan pendidikan yang lebih lengkap.
        """
        try:
            response = await detail_page.goto(
                job_url,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            if response and response.status >= 400:
                return "", "", ""

            await asyncio.sleep(2)

            detail_selectors = [
                "[data-automation='jobAdDetails']",
                "[data-automation='jobDescription']",
                "[data-automation='job-detail-description']",
                "section:has(h2:has-text('Deskripsi'))",
                "section:has(h2:has-text('Kualifikasi'))",
                "main",
            ]

            detail_text = await self.safe_text(
                detail_page,
                detail_selectors,
                "",
            )

            if not detail_text:
                try:
                    detail_text = (
                        await detail_page.locator("body").inner_text()
                    ).strip()
                except Exception:
                    detail_text = ""

            detail_text = re.sub(
                r"\s+",
                " ",
                detail_text,
            ).strip()

            education = self.detect_education(detail_text)

            return detail_text, detail_text, education

        except Exception as error:
            print(
                f"[{self.portal_name}] "
                f"Gagal membuka detail {job_url}: {error}"
            )
            return "", "", ""

    def build_search_url(self, keyword: str) -> str:
        encoded_keyword = quote_plus(keyword.strip())

        return (
            f"{self.base_url}/id/jobs"
            f"?keywords={encoded_keyword}"
        )

    async def safe_text(
        self,
        element,
        selectors: list[str],
        default: str = "Tidak tersedia",
    ) -> str:
        """
        Mengambil teks dari selector pertama yang ditemukan.
        """

        for selector in selectors:
            try:
                target = element.locator(selector).first

                if await target.count() > 0:
                    text = (await target.inner_text()).strip()

                    if text:
                        return text

            except Exception:
                continue

        return default

    async def close_cookie_banner(self, page) -> None:
        """
        Menutup banner cookie apabila muncul.
        """

        cookie_selectors = [
            "button:has-text('Terima semua')",
            "button:has-text('Terima')",
            "button:has-text('Setuju')",
            "button:has-text('Accept all')",
            "button:has-text('Accept')",
        ]

        for selector in cookie_selectors:
            try:
                button = page.locator(selector).first

                if await button.count() > 0:
                    await button.click(timeout=3000)
                    await asyncio.sleep(1)

                    print(
                        f"[{self.portal_name}] "
                        "Banner cookie ditutup."
                    )

                    return

            except Exception:
                continue

    async def detect_blocked_page(self, page) -> bool:
        """
        Memeriksa apakah halaman berisi indikasi anti-bot.
        """

        try:
            body_text = (
                await page.locator("body").inner_text()
            ).lower()

        except Exception:
            return False

        blocked_markers = [
            "access denied",
            "captcha",
            "verify you are human",
            "verifikasi bahwa anda manusia",
            "unusual traffic",
            "automated access",
            "robot",
            "temporarily blocked",
            "request blocked",
            "security check",
        ]

        return any(
            marker in body_text
            for marker in blocked_markers
        )

    async def scrape(self, keyword: str) -> list[dict]:
        results: list[dict] = []
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
                    "--disable-background-networking",
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
                viewport={
                    "width": 1366,
                    "height": 900,
                },
                extra_http_headers={
                    "Accept-Language": (
                        "id-ID,id;q=0.9,"
                        "en-US;q=0.8,en;q=0.7"
                    ),
                },
            )

            page = await context.new_page()
            page.set_default_timeout(60000)

            detail_page = await context.new_page()
            detail_page.set_default_timeout(60000)

            try:
                print(
                    f"[{self.portal_name}] "
                    f"Membuka: {search_url}"
                )

                response = await page.goto(
                    search_url,
                    wait_until="domcontentloaded",
                    timeout=90000,
                )

                if response:
                    print(
                        f"[{self.portal_name}] "
                        f"HTTP status: {response.status}"
                    )

                print(
                    f"[{self.portal_name}] "
                    f"URL akhir: {page.url}"
                )

                print(
                    f"[{self.portal_name}] "
                    f"Judul halaman: {await page.title()}"
                )

                await asyncio.sleep(5)

                await self.close_cookie_banner(page)

                # Scroll untuk memuat lebih banyak kartu lowongan.
                for scroll_number in range(6):
                    await page.mouse.wheel(0, 1400)
                    await asyncio.sleep(1.5)

                    print(
                        f"[{self.portal_name}] "
                        f"Scroll {scroll_number + 1}/6"
                    )

                if await self.detect_blocked_page(page):
                    print(
                        f"[{self.portal_name}] "
                        "Halaman kemungkinan diblokir "
                        "oleh sistem anti-bot."
                    )

                    body_text = (
                        await page.locator("body").inner_text()
                    )

                    print(
                        f"[{self.portal_name}] "
                        f"Cuplikan halaman: "
                        f"{body_text[:600]}"
                    )

                    return []

                try:
                    await page.locator(
                        "a[href*='/job/']"
                    ).first.wait_for(
                        state="attached",
                        timeout=30000,
                    )

                except PlaywrightTimeoutError:
                    print(
                        f"[{self.portal_name}] "
                        "Link lowongan tidak ditemukan."
                    )

                    body_text = (
                        await page.locator("body").inner_text()
                    )

                    print(
                        f"[{self.portal_name}] "
                        f"Cuplikan halaman: "
                        f"{body_text[:600]}"
                    )

                    return []

                card_selectors = [
                    "article[data-automation='normalJobCard']",
                    "article:has(a[href*='/job/'])",
                    "[data-automation='jobCard']",
                ]

                job_cards = None
                selected_card_selector = None

                for selector in card_selectors:
                    locator = page.locator(selector)
                    card_count = await locator.count()

                    if card_count > 0:
                        job_cards = locator
                        selected_card_selector = selector
                        break

                if job_cards is None:
                    print(
                        f"[{self.portal_name}] "
                        "Kartu lowongan tidak ditemukan."
                    )

                    return []

                total_cards = await job_cards.count()

                print(
                    f"[{self.portal_name}] "
                    f"Selector kartu: "
                    f"{selected_card_selector}"
                )

                print(
                    f"[{self.portal_name}] "
                    f"Kartu ditemukan: {total_cards}"
                )

                seen_links: set[str] = set()

                maximum_cards = min(total_cards, 30)

                for index in range(maximum_cards):
                    card = job_cards.nth(index)

                    try:
                        title_selectors = [
                            "a[data-automation='jobTitle']",
                            "a[href*='/job/']",
                        ]

                        title_element = None

                        for selector in title_selectors:
                            locator = card.locator(selector).first

                            if await locator.count() > 0:
                                title_element = locator
                                break

                        if title_element is None:
                            continue

                        title = (
                            await title_element.inner_text()
                        ).strip()

                        href = await title_element.get_attribute(
                            "href"
                        )

                        if not title or not href:
                            continue

                        full_url = urljoin(
                            self.base_url,
                            href,
                        )

                        if full_url in seen_links:
                            continue

                        seen_links.add(full_url)

                        company = await self.safe_text(
                            card,
                            [
                                "[data-automation='jobCompany']",
                                "a[data-automation='jobCompany']",
                                "span[data-automation='jobCompany']",
                                "a[href*='/companies/']",
                            ],
                            "Perusahaan tidak tersedia",
                        )

                        location = await self.safe_text(
                            card,
                            [
                                "[data-automation='jobLocation']",
                                "a[data-automation='jobLocation']",
                                "span[data-automation='jobLocation']",
                                "a[href*='jobs/in-']",
                            ],
                            "Indonesia",
                        )

                        description = await self.safe_text(
                            card,
                            [
                                "[data-automation='jobShortDescription']",
                                "[data-automation='jobDescription']",
                                "[data-automation='jobDescriptionSnippet']",
                                "ul",
                                "p",
                            ],
                            "Deskripsi tidak tersedia",
                        )

                        education = self.detect_education(
                            title,
                            description,
                            keyword,
                        )

                        qualification = keyword
                        detail_description = ""

                        if not education:
                            (
                                detail_description,
                                detail_qualification,
                                detail_education,
                            ) = await self.extract_detail_information(
                                detail_page,
                                full_url,
                            )

                            if detail_description:
                                description = detail_description

                            if detail_qualification:
                                qualification = detail_qualification

                            if detail_education:
                                education = detail_education

                            await asyncio.sleep(1)

                        # Fallback terakhir untuk keyword pendidikan utama.
                        if not education:
                            education = self.detect_education(keyword)

                        results.append(
                            {
                                "judul_posisi": title,
                                "nama_perusahaan": company,
                                "lokasi": location,
                                "pendidikan": education,
                                "deskripsi": description,
                                "kualifikasi": qualification,
                                "link_lowongan": full_url,
                                "portal_sumber": self.portal_name,
                                "keyword_sumber": keyword,
                            }
                        )

                    except Exception as error:
                        print(
                            f"[{self.portal_name} "
                            f"CARD ERROR {index + 1}] "
                            f"{error}"
                        )

                print(
                    f"[{self.portal_name}] "
                    f"Total data: {len(results)}"
                )

                return results

            except Exception as error:
                print(
                    f"[ERROR] {self.portal_name}: "
                    f"{error}"
                )

                try:
                    print(
                        f"[{self.portal_name}] "
                        f"URL ketika error: {page.url}"
                    )

                    print(
                        f"[{self.portal_name}] "
                        f"Judul halaman: "
                        f"{await page.title()}"
                    )

                    body_text = (
                        await page.locator("body").inner_text()
                    )

                    print(
                        f"[{self.portal_name}] "
                        f"Cuplikan halaman: "
                        f"{body_text[:600]}"
                    )

                except Exception:
                    pass

                return []

            finally:
                await context.close()
                await browser.close()