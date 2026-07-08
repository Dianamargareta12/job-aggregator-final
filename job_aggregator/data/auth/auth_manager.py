import asyncio
from playwright.async_api import async_playwright

PORTALS = {
    "glints": "https://glints.com/id",
    "jobstreet": "https://id.jobstreet.com",
    "lokerid": "https://www.loker.id"
}


async def save_login(portal_name, url):

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=False
        )

        context = await browser.new_context()

        page = await context.new_page()

        await page.goto(url)

        print(f"\nLOGIN MANUAL KE: {portal_name.upper()}")
        print("Setelah selesai login, tekan ENTER di terminal...\n")

        input()

        await context.storage_state(
            path=f"data/auth/{portal_name}.json"
        )

        print(f"Session {portal_name} berhasil disimpan.")

        await browser.close()


async def main():

    for portal_name, url in PORTALS.items():

        await save_login(
            portal_name,
            url
        )


if __name__ == "__main__":
    asyncio.run(main())