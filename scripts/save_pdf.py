import asyncio
import sys
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

async def save_webpage_as_pdf(url: str, output_path: str = "output.pdf"):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        page = await context.new_page()

        print(f"Loading {url}...")
        await page.wait_for_timeout(2000)

        async with Stealth().use_async(page):
            await page.goto(url, wait_until="networkidle")
            await page.wait_for_timeout(2000)

            await page.pdf(
                path=output_path,
                format="A4",
                print_background=True,
                margin={"top": "1cm", "bottom": "1cm", "left": "1cm", "right": "1cm"}
            )

        await browser.close()
        print(f"Saved PDF to: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python save_pdf.py <url> [output.pdf]")
        sys.exit(1)

    url = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else "output.pdf"

    asyncio.run(save_webpage_as_pdf(url, output))