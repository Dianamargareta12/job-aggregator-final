import asyncio
import re
from urllib.parse import quote_plus, urlparse, urlunparse
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


class GlintsParser:
    def __init__(self, portal_name="Glints"):
        self.portal_name = portal_name
        self.base_url = "https://glints.com"

    def normalize_url(self, url):
        if not url:
            return ""

        if url.startswith("/"):
            url = self.base_url + url

        parsed = urlparse(url)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

    def build_search_url(self, keyword):
        encoded_keyword = quote_plus(keyword)
        return f"https://glints.com/id/opportunities/jobs/explore?keyword={encoded_keyword}"

    def is_location_text(self, text):
        low = text.lower()

        locations = [
            "jakarta", "bandung", "surabaya", "tangerang", "bekasi", "depok",
            "yogyakarta", "semarang", "medan", "bali", "bogor", "makassar",
            "manado", "malang", "batam", "palembang", "pekanbaru", "solo",
            "denpasar", "kediri", "indonesia", "remote"
        ]

        return any(location in low for location in locations)

    def detect_education(self, text):
        low = str(text).lower()

        if "smk" in low:
            return "SMK"
        if "sma" in low:
            return "SMA"
        if "d3" in low or "diploma" in low:
            return "D3"
        if "s1" in low or "sarjana" in low:
            return "S1"

        return ""

    def clean_line(self, text):
        return re.sub(r"\s+", " ", str(text).strip())

    def parse_card_text(self, text):
        lines = [self.clean_line(line) for line in text.splitlines() if self.clean_line(line)]

        title = lines[0] if len(lines) > 0 else "Tidak tersedia"
        company = "Tidak tersedia"
        lokasi = "Indonesia"
        description_parts = []

        ignored_words = [
            "rp", "bulan", "tahun", "hari", "minggu", "remote", "onsite",
            "hybrid", "penuh waktu", "paruh waktu", "magang", "kontrak",
            "lamar", "simpan", "bagikan", "gaji"
        ]

        for line in lines[1:]:
            low = line.lower()

            if self.is_location_text(line):
                lokasi = line
                continue

            if company == "Tidak tersedia" and not any(word in low for word in ignored_words):
                company = line
                continue

            description_parts.append(line)

        description = " ".join(description_parts[:4]) if description_parts else "Deskripsi tidak tersedia"

        return title, company, lokasi, description

    async def get_text_from_selectors(self, page, selectors):
        for selector in selectors:
            try:
                element = await page.query_selector(selector)

                if element:
                    text = await element.inner_text()
                    text = self.clean_line(text)

                    if text:
                        return text
            except Exception:
                continue

        return ""

    async def parse_detail_page(self, context, href, fallback_data):
        detail = {
            "judul_posisi": fallback_data.get("judul_posisi", "Tidak tersedia"),
            "nama_perusahaan": fallback_data.get("nama_perusahaan", "Tidak tersedia"),
            "lokasi": fallback_data.get("lokasi", "Indonesia"),
            "pendidikan": fallback_data.get("pendidikan", ""),
            "deskripsi": fallback_data.get("deskripsi", "Deskripsi tidak tersedia"),
            "kualifikasi": fallback_data.get("kualifikasi", ""),
        }

        page = await context.new_page()
        page.set_default_timeout(45000)

        try:
            await page.goto(href, wait_until="domcontentloaded")
            await asyncio.sleep(3)

            # Ambil judul dari halaman detail
            title = await self.get_text_from_selectors(page, [
                "h1",
                "[data-testid*='job-title']",
                "[class*='JobTitle']",
            ])

            if title:
                detail["judul_posisi"] = title

            # Ambil nama perusahaan dari halaman detail.
            # Di Glints, nama perusahaan sering berada dekat judul atau link company.
            company = await self.get_text_from_selectors(page, [
                "a[href*='/companies/']",
                "a[href*='/company/']",
                "[data-testid*='company']",
                "[class*='Company']",
                "[class*='company']",
            ])

            # Fallback: baca beberapa baris awal halaman detail dan pilih baris setelah judul.
            if not company or company.lower() in ["daftar", "masuk", "untuk perusahaan"]:
                body_text = await page.inner_text("body")
                lines = [self.clean_line(line) for line in body_text.splitlines() if self.clean_line(line)]

                if detail["judul_posisi"] in lines:
                    idx = lines.index(detail["judul_posisi"])
                    for candidate in lines[idx + 1: idx + 8]:
                        low = candidate.lower()

                        if (
                            len(candidate) >= 3
                            and not self.is_location_text(candidate)
                            and not any(word in low for word in [
                                "gaji", "tidak menampilkan gaji", "pendidikan", "penuh waktu",
                                "kerja di lokasi", "minimal", "tahun pengalaman", "lamar",
                                "simpan", "bagikan", "pekerjaan", "lokasi"
                            ])
                        ):
                            company = candidate
                            break

            if company and len(company) >= 3:
                detail["nama_perusahaan"] = company

            # Ambil lokasi
            location = await self.get_text_from_selectors(page, [
                "[data-testid*='location']",
                "[class*='Location']",
                "[class*='location']",
            ])

            if not location:
                body_text = await page.inner_text("body")
                lines = [self.clean_line(line) for line in body_text.splitlines() if self.clean_line(line)]

                for line in lines[:80]:
                    if self.is_location_text(line):
                        location = line
                        break

            if location:
                detail["lokasi"] = location

            # Ambil deskripsi dari area persyaratan/deskripsi jika tersedia
            body_text = await page.inner_text("body")
            body_text_clean = self.clean_line(body_text)

            if body_text_clean and len(body_text_clean) > 50:
                detail["deskripsi"] = body_text_clean[:1000]

            education_text = f"{detail['judul_posisi']} {detail['deskripsi']} {detail['kualifikasi']}"
            detected_education = self.detect_education(education_text)

            if detected_education:
                detail["pendidikan"] = detected_education

        except Exception as e:
            print(f"[{self.portal_name} DETAIL ERROR] {href} -> {e}")

        finally:
            await page.close()

        return detail

    async def scrape(self, keyword: str):
        results = []
        seen_links = set()
        seen_jobs = set()
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
                await page.goto(search_url, 
                wait_until="domcontentloaded")
                await asyncio.sleep(5)

                try:
                    search_input = await page.query_selector(
                        "input[placeholder*='Cari'], input[placeholder*='Search'], input[name*='keyword']"
                    )
                    if search_input:
                        await search_input.fill(keyword)
                        await page.keyboard.press("Enter")
                        await asyncio.sleep(5)
                except Exception:
                    pass

                for selector in [
                    "button[aria-label='Close']",
                    "button[aria-label='close']",
                    "button:has-text('Nanti saja')",
                    "button:has-text('Tidak, Terima Kasih')",
                    "button:has-text('Lewati')",
                ]:
                    try:
                        btn = await page.query_selector(selector)
                        if btn:
                            await btn.click()
                            await asyncio.sleep(1)
                            break
                    except Exception:
                        pass

                for _ in range(5):
                    await page.mouse.wheel(0, 1200)
                    await asyncio.sleep(2)

                links = await page.query_selector_all(
                    "a[href*='/id/opportunities/jobs/'], a[href*='/opportunities/jobs/']"
                )

                print(f"[{self.portal_name}] Link terdeteksi: {len(links)}")

                for link_el in links:
                    try:
                        raw_href = await link_el.get_attribute("href")
                        href = self.normalize_url(raw_href)

                        if not href or "recommended" in href:
                            continue

                        if href in seen_links:
                            continue

                        text = await link_el.inner_text()

                        if not text.strip():
                            continue

                        title, company, lokasi, description = self.parse_card_text(text)

                        if len(title) < 3 or title.lower() in ["jobs", "lowongan", "explore"]:
                            continue

                        fallback_data = {
                            "judul_posisi": title,
                            "nama_perusahaan": company,
                            "lokasi": lokasi,
                            "pendidikan": self.detect_education(f"{keyword} {title} {description}"),
                            "deskripsi": description,
                            "kualifikasi": keyword,
                        }

                        detail_data = await self.parse_detail_page(context, href, fallback_data)

                        job_key = f"{detail_data['judul_posisi'].lower()}|{detail_data['nama_perusahaan'].lower()}|{href}"

                        if job_key in seen_jobs:
                            continue

                        seen_links.add(href)
                        seen_jobs.add(job_key)

                        results.append({
                            "judul_posisi": detail_data["judul_posisi"],
                            "nama_perusahaan": detail_data["nama_perusahaan"],
                            "lokasi": detail_data["lokasi"],
                            "pendidikan": detail_data["pendidikan"],
                            "deskripsi": detail_data["deskripsi"],
                            "kualifikasi": detail_data["kualifikasi"],
                            "link_lowongan": href,
                            "portal_sumber": self.portal_name,
                            "keyword_sumber": keyword
                        })

                        if len(results) >= 20:
                            break

                    except Exception as e:
                        print(f"[{self.portal_name} CARD ERROR] {e}")
                        continue

                print(f"[{self.portal_name}] Total data unik: {len(results)}")
                await browser.close()

                return results

            except Exception as e:
                print(f"[ERROR] {self.portal_name}: {e}")
                await browser.close()

                return []
