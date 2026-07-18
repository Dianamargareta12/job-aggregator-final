import asyncio
from urllib.parse import quote_plus
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


class JobstreetParser:
    def __init__(self, portal_name="Jobstreet"):
        self.portal_name = portal_name
        self.base_url = "https://id.jobstreet.com"

    def build_search_url(self, keyword):
        encoded_keyword = quote_plus(keyword)
        return f"https://id.jobstreet.com/id/jobs?keywords={encoded_keyword}"

    async def safe_text(self, element, selector, default="Tidak tersedia"):
        try:
            target = await element.query_selector(selector)
            if target:
                text = (await target.inner_text()).strip()
                return text if text else default
        except Exception:
            pass
        return default

    async def scrape(self, keyword: str):
        results = []
        search_url = self.build_search_url(keyword)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
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

                for _ in range(4):
                    await page.mouse.wheel(0, 1200)
                    await asyncio.sleep(2)

                job_cards = await page.query_selector_all("article[data-automation='normalJobCard']")
                if not job_cards:
                    job_cards = await page.query_selector_all("article")

                seen = set()

                for card in job_cards[:30]:
                    try:
                        title_el = await card.query_selector("a[data-automation='jobTitle']")
                        if not title_el:
                            title_el = await card.query_selector("a[href*='/job/']")

                        if not title_el:
                            continue

                        title = (await title_el.inner_text()).strip()
                        href = await title_el.get_attribute("href")

                        if not title or not href:
                            continue

                        if href.startswith("/"):
                            href = self.base_url + href

                        if href in seen:
                            continue

                        seen.add(href)

                        company = await self.safe_text(
                            card,
                            "a[data-automation='jobCompany'], span[data-automation='jobCompany'], [data-automation='jobCompany']"
                        )

                        lokasi = await self.safe_text(
                            card,
                            "[data-automation='jobLocation']",
                            "Indonesia"
                        )

                        description = await self.safe_text(
                            card,
                            "[data-automation='jobShortDescription'], [data-automation='jobDescription'], ul, p",
                            "Deskripsi tidak tersedia"
                        )

                        results.append({
                            "judul_posisi": title,
                            "nama_perusahaan": company,
                            "lokasi": lokasi,
                            "pendidikan": "",
                            "deskripsi": description,
                            "kualifikasi": keyword,
                            "link_lowongan": href,
                            "portal_sumber": self.portal_name,
                            "keyword_sumber": keyword
                        })

                    except Exception as e:
                        print(f"[{self.portal_name} CARD ERROR] {e}")
                        continue

                print(f"[{self.portal_name}] Total data: {len(results)}")
                await browser.close()
                return results

            except Exception as e:
                print(f"[ERROR] {self.portal_name}: {e}")
                await browser.close()
                return []
