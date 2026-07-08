import asyncio
from urllib.parse import quote_plus, urlparse, urlunparse
from playwright.async_api import async_playwright

try:
    from parsers.base_scraper import BaseScraper
except Exception:
    class BaseScraper:
        def __init__(self, portal_name):
            self.portal_name = portal_name


class LokerIDParser(BaseScraper):
    def __init__(self, portal_name="Loker.id"):
        super().__init__(portal_name)
        self.base_url = "https://www.loker.id"

    def normalize_url(self, url):
        if not url:
            return ""

        if url.startswith("/"):
            url = self.base_url + url

        parsed = urlparse(url)

        return urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            "",
            "",
            ""
        ))

    def build_search_url(self, keyword):
        encoded_keyword = quote_plus(keyword)
        return f"https://www.loker.id/cari-lowongan-kerja?q={encoded_keyword}"

    def is_invalid_title(self, title):
        title = title.lower().strip()

        invalid_titles = [
            "daftar sebagai pencari kerja",
            "pastikan nomor whatsapp",
            "kembali",
            "login",
            "register",
            "masuk",
            "daftar",
            "pasang lowongan",
            "pasang loker",
            "untuk perusahaan",
            "cari lowongan kerja",
            "lowongan kerja",
            "beranda",
            "home",
            "temukan kandidat",
            "rekrutmen",
            "iklan lowongan"
        ]

        return any(bad in title for bad in invalid_titles)

    def is_invalid_url(self, href):
        href = href.lower()

        invalid_urls = [
            "login",
            "register",
            "daftar",
            "pasang-lowongan",
            "pasang-loker",
            "untuk-perusahaan",
            "cari-lowongan-kerja",
            "category",
            "tag",
            "author",
            "privacy",
            "terms",
            "feed",
            "javascript"
        ]

        return any(bad in href for bad in invalid_urls)

    def is_blocked_content(self, title, company, deskripsi):
        full_text = f"{title} {company} {deskripsi}".lower()

        blocked_words = [
            "pasang lowongan",
            "pasang loker",
            "rekrutmen",
            "temukan kandidat",
            "untuk perusahaan",
            "iklan lowongan",
            "pasang iklan",
            "platform rekrutmen",
            "nomor whatsappmu"
        ]

        return any(word in full_text for word in blocked_words)

    async def extract_detail_data(self, context, href):
        company = "Tidak tersedia"
        lokasi = "Indonesia"
        deskripsi = "Deskripsi tidak tersedia"
        kualifikasi = "Kualifikasi tidak tersedia"

        detail_page = await context.new_page()
        detail_page.set_default_timeout(45000)

        try:
            await detail_page.goto(href, wait_until="domcontentloaded")
            await asyncio.sleep(3)

            body_text = (await detail_page.locator("body").inner_text()).strip()
            lines = [line.strip() for line in body_text.splitlines() if line.strip()]

            location_keywords = [
                "jakarta",
                "bandung",
                "surabaya",
                "bekasi",
                "tangerang",
                "depok",
                "yogyakarta",
                "semarang",
                "medan",
                "bali",
                "makassar",
                "manado",
                "bogor",
                "malang",
                "indonesia",
                "remote"
            ]

            for line in lines:
                low = line.lower()

                if company == "Tidak tersedia" and any(k in low for k in [
                    "pt ",
                    "cv ",
                    "tbk",
                    "yayasan"
                ]):
                    company = line

                if lokasi == "Indonesia" and any(k in low for k in location_keywords):
                    lokasi = line

            useful_lines = []

            skip_words = [
                "login",
                "register",
                "daftar",
                "share",
                "facebook",
                "twitter",
                "whatsapp",
                "copyright",
                "kembali",
                "pasang lowongan",
                "pasang loker",
                "untuk perusahaan",
                "temukan kandidat",
                "iklan lowongan"
            ]

            for line in lines:
                low = line.lower()

                if len(line) < 25:
                    continue

                if any(skip in low for skip in skip_words):
                    continue

                useful_lines.append(line)

            if useful_lines:
                deskripsi = " ".join(useful_lines[:3])[:600]

            qualification_keywords = [
                "sma",
                "smk",
                "d3",
                "s1",
                "sarjana",
                "diploma",
                "pengalaman",
                "minimal",
                "lulusan",
                "usia",
                "mampu"
            ]

            qualification_lines = [
                line for line in useful_lines
                if any(k in line.lower() for k in qualification_keywords)
            ]

            if qualification_lines:
                kualifikasi = " ".join(qualification_lines[:3])[:600]

        except Exception as e:
            print(f"[Loker.id DETAIL ERROR] {e}")

        finally:
            await detail_page.close()

        return company, lokasi, deskripsi, kualifikasi

    async def scrape(self, keyword):
        results = []
        seen_links = set()

        search_url = self.build_search_url(keyword)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)

            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            )

            page = await context.new_page()
            page.set_default_timeout(60000)

            try:
                print(f"[{self.portal_name}] Membuka: {search_url}")

                await page.goto(search_url, wait_until="domcontentloaded")
                await asyncio.sleep(5)

                for _ in range(5):
                    await page.mouse.wheel(0, 2000)
                    await asyncio.sleep(2)

                links = await page.query_selector_all("a")

                print(f"[{self.portal_name}] Total link ditemukan: {len(links)}")

                for link_el in links[:250]:
                    try:
                        title = (await link_el.inner_text()).strip()
                        title = " ".join(title.split())

                        href = await link_el.get_attribute("href")
                        href = self.normalize_url(href)

                        if not title or not href:
                            continue

                        if "loker.id" not in href:
                            continue

                        if self.is_invalid_title(title):
                            continue

                        if self.is_invalid_url(href):
                            continue

                        if href in seen_links:
                            continue

                        if len(title) < 5:
                            continue

                        seen_links.add(href)

                        company, lokasi, deskripsi, kualifikasi = await self.extract_detail_data(
                            context,
                            href
                        )

                        if self.is_blocked_content(title, company, deskripsi):
                            continue

                        results.append({
                            "judul_posisi": title,
                            "nama_perusahaan": company,
                            "lokasi": lokasi,
                            "pendidikan": "",
                            "deskripsi": deskripsi,
                            "kualifikasi": kualifikasi if kualifikasi != "Kualifikasi tidak tersedia" else keyword,
                            "link_lowongan": href,
                            "portal_sumber": self.portal_name,
                            "keyword_sumber": keyword
                        })

                        print(f"[DATA] {title} | {company} | {lokasi}")

                        if len(results) >= 12:
                            break

                    except Exception as e:
                        print(f"[LINK ERROR] {e}")
                        continue

                print(f"[{self.portal_name}] Total data unik: {len(results)}")

                await browser.close()
                return results

            except Exception as e:
                print(f"[ERROR] {self.portal_name}: {e}")

                await browser.close()
                return []