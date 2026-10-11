import os
import sys
import time
import re
import random
import zipfile
import tempfile
import logging
import asyncio
from webdriver_manager.chrome import ChromeDriverManager
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, CallbackContext,
)

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ============================================================
# CONFIG
# ============================================================
BOT_TOKEN = "8801623186:AAGm3xw0ARg62cuEMdxZpytNHdgK5u0dzw0"

PROXY_HOST = "gw.dataimpulse.com"
PROXY_PORT = "823"
PROXY_USER = "f6c1b50689f8a8276d68__cr.mx"
PROXY_PASS = "b193ed8db470e6bb"

# Optional: path to chrome.exe if not auto-detected
CHROME_BINARY = None  # e.g. r"C:\Program Files\Google\Chrome\Application\chrome.exe"

MAX_CONCURRENT = 3  # how many links to generate in parallel

# ============================================================
# LOGGING (cross-platform)
# ============================================================
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ============================================================
# PROXY EXTENSION
# ============================================================
def create_proxy_extension():
    manifest_json = """
    {"version":"1.0.0","manifest_version":2,"name":"Proxy","permissions":["proxy","tabs","storage","<all_urls>","webRequest","webRequestBlocking"],"background":{"scripts":["bg.js"]},"minimum_chrome_version":"22.0.0"}
    """
    background_js = f"""
    var config={{mode:"fixed_servers",rules:{{singleProxy:{{scheme:"http",host:"{PROXY_HOST}",port:parseInt({PROXY_PORT})}},bypassList:["localhost"]}}}};chrome.proxy.settings.set({{value:config,scope:"regular"}},function(){{}});function cb(d){{return{{authCredentials:{{username:"{PROXY_USER}",password:"{PROXY_PASS}"}}}};}}chrome.webRequest.onAuthRequired.addListener(cb,{{urls:["<all_urls>"]}},["blocking"]);
    """
    path = os.path.join(tempfile.gettempdir(), f"proxy_auth_{random.randint(1000,9999)}.zip")
    with zipfile.ZipFile(path, "w") as zp:
        zp.writestr("manifest.json", manifest_json)
        zp.writestr("bg.js", background_js)
    return path


def build_driver():
    """Create a Chrome driver with proxy + stealth options."""
    ext = create_proxy_extension()
    options = Options()
    options.add_extension(ext)
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    if CHROME_BINARY:
        options.binary_location = CHROME_BINARY

    # webdriver-manager auto-downloads and caches the correct chromedriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(60)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def _find_send(driver, selectors, value=None, click=False, wait=None):
    """Try each selector, send keys or click, return True on success."""
    for sel in selectors:
        try:
            el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel))) if wait else driver.find_element(By.CSS_SELECTOR, sel)
            if click:
                el.click()
            elif value is not None:
                el.clear()
                el.send_keys(value)
            return True
        except Exception:
            continue
    return False


# ============================================================
# LINK GENERATOR
# ============================================================
def generate_one_link():
    """Generate one Spotify offer link. Returns link or None. Never raises."""
    logger.info("→ Generating one link...")
    driver = None
    try:
        driver = build_driver()

        # 1. Temp email
        logger.info("  → Getting temp email...")
        driver.get("https://temp-mail.io/en/")
        time.sleep(5)
        email = None
        for sel in ["#email", ".email-address", "input#email"]:
            try:
                val = driver.find_element(By.CSS_SELECTOR, sel).get_attribute("value") or ""
                if "@" in val:
                    email = val
                    break
            except Exception:
                pass
        if not email:
            m = re.search(
                r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                driver.page_source,
            )
            email = m.group(0) if m else None
        if not email:
            logger.warning("  ✗ No email found on temp-mail.io")
            return None
        logger.info(f"  ✓ Email: {email}")

        password = f"AutoPass_{random.randint(100000, 999999)}!@#"

        # 2. Register
        logger.info("  → Registering...")
        driver.get("https://www2.hm.com/en_in/register")
        time.sleep(5)
        _find_send(driver, ['input#email', 'input[name="email"]', 'input[type="email"]'], value=email)
        _find_send(driver, ['input#password', 'input[name="password"]', 'input[type="password"]'], value=password)
        _find_send(driver, ['button[type="submit"]', 'input[type="submit"]'], click=True)
        time.sleep(5)
        logger.info("  ✓ Register step done")

        # 3. Login
        logger.info("  → Logging in...")
        driver.get("https://www2.hm.com/en_in/login")
        time.sleep(5)
        wait = WebDriverWait(driver, 20)
        _find_send(driver, ['input#email', 'input[name="email"]', 'input[type="email"]'], value=email, wait=wait)
        _find_send(driver, ['input#password', 'input[name="password"]', 'input[type="password"]'], value=password)
        _find_send(driver, ['button[type="submit"]', 'input[type="submit"]'], click=True)
        time.sleep(5)
        logger.info("  ✓ Login step done")

        # 4. Account page
        logger.info("  → Opening account page...")
        driver.get("https://www2.hm.com/en_in/account")
        time.sleep(5)
        page_source = driver.page_source

        if "Access Denied" in page_source:
            logger.warning("  ✗ Access Denied page returned (proxy IP blocked?)")
            return None

        # 5. Extract code
        offer_code = None
        q_matches = re.findall(r"q[A-Za-z0-9]{9,11}", page_source)
        if q_matches:
            offer_code = q_matches[0]
        if not offer_code:
            m = re.search(r"[Oo]ffer code\s*[:]\s*([A-Za-z0-9]{8,12})", page_source)
            if m:
                offer_code = m.group(1)
        if not offer_code:
            for m in re.findall(r"[A-Z][A-Za-z0-9]{9,11}", page_source):
                if m.lower() not in ("razorpay", "spotify", "https", "www2hm", "permission"):
                    offer_code = m
                    break

        if not offer_code:
            logger.warning("  ✗ No offer code found on account page")
            return None

        link = f"https://www.spotify.com/mx/ppt/hm/?code={offer_code}"
        logger.info(f"  ✅ Link generated: {link}")
        return link

    except Exception as e:
        logger.exception(f"  ✗ generate_one_link failed: {e}")
        return None
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


def generate_links_sync(count: int):
    """Generate `count` links sequentially. Returns (links, success, fail)."""
    links, success, fail = [], 0, 0
    logger.info(f"🔄 Generating {count} links...")
    for i in range(count):
        logger.info(f"📌 Link {i + 1}/{count}")
        link = generate_one_link()
        if link:
            links.append(link)
            success += 1
        else:
            fail += 1
        if i < count - 1:
            wait_time = random.uniform(10, 20)
            logger.info(f"⏳ Waiting {wait_time:.0f}s before next...")
            time.sleep(wait_time)
    logger.info(f"✅ Done! Success: {success}, Failed: {fail}")
    return links, success, fail


# ============================================================
# TELEGRAM HANDLERS
# ============================================================
async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    logger.info(f"📱 /start from {user.id} ({user.username})")
    await update.message.reply_text(
        "🎵 <b>Spotify Link Generator</b>\n\n"
        "Send me a number (1–10) and I'll generate that many links.\n\n"
        "⚠️ Each link takes ~1–2 minutes.",
        parse_mode="HTML",
    )


async def help_command(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "🎵 <b>Spotify Link Generator</b>\n\n"
        "Send a number (1–10) to generate that many Spotify links.\n\n"
        "Commands:\n"
        "/start – Start\n/help – Help\n/cancel – Cancel",
        parse_mode="HTML",
    )


async def cancel(update: Update, context: CallbackContext):
    await update.message.reply_text("❌ Cancelled. Send /start to restart.")


async def handle_message(update: Update, context: CallbackContext):
    user = update.effective_user
    text = (update.message.text or "").strip()
    logger.info(f"📱 Message from {user.id}: {text}")

    if not text.isdigit():
        await update.message.reply_text("❌ Send a valid number (e.g. <code>5</code>)", parse_mode="HTML")
        return
    count = int(text)
    if not (1 <= count <= 10):
        await update.message.reply_text("❌ Send a number between 1 and 10.")
        return

    status = await update.message.reply_text(
        f"🔄 Generating {count} link(s)...\n"
        f"⏳ Roughly {count * 2} minutes. I'll send the file when done."
    )

    # Run blocking selenium work in a thread so the bot stays responsive
    loop = asyncio.get_running_loop()
    try:
        links, success, fail = await loop.run_in_executor(
            context.application.bot_data.setdefault(
                "_executor", ThreadPoolExecutor(max_workers=MAX_CONCURRENT)
            ),
            generate_links_sync,
            count,
        )
    except Exception as e:
        logger.exception(f"generate_links_sync crashed: {e}")
        await status.edit_text("❌ Generation crashed. Check bot.log.")
        return

    logger.info(
        f"generate_links({count}) → success={success}, fail={fail}, links={len(links)}"
    )

    if not links:
        logger.warning(f"❌ No links generated for user {user.id}")
        await status.edit_text(
            "❌ Failed to generate any links.\n"
            "Check bot.log on the server for the exact error.\n\n"
            "Common causes:\n"
            "• chromedriver path wrong\n"
            "• Proxy blocked / expired\n"
            "• H&M layout changed"
        )
        return

    # Write file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write("🎵 Spotify Links\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 50 + "\n\n")
        for idx, link in enumerate(links, 1):
            f.write(f"{idx}. {link}\n")
        file_path = f.name

    try:
        with open(file_path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=f'spotify_links_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt',
                caption=(
                    f"✅ Generated {len(links)} links\n"
                    f"✅ Success: {success}\n"
                    f"❌ Failed: {fail}"
                ),
            )
    finally:
        try:
            os.unlink(file_path)
        except OSError:
            pass

    preview = "\n".join(links[:5])
    if len(links) > 5:
        preview += f"\n\n... and {len(links) - 5} more in the file"
    await update.message.reply_text(
        f"🎵 <b>Your Links:</b>\n\n{preview}", parse_mode="HTML"
    )

    try:
        await status.delete()
    except Exception:
        pass


# ============================================================
# MAIN
# ============================================================
def main():
    logger.info("🚀 Starting Spotify Link Generator Bot...")

    if not BOT_TOKEN or BOT_TOKEN == "PASTE_YOUR_NEW_TOKEN_HERE":
        logger.error("❌ Set BOT_TOKEN in the file first.")
        sys.exit(1)

    logger.info(f"Bot Token: {BOT_TOKEN[:10]}...")
    logger.info("Using webdriver-manager (auto-downloads chromedriver)")

    app = (
    Application.builder()
    .token(BOT_TOKEN)
    .read_timeout(30)
    .write_timeout(30)
    .connect_timeout(30)
    .pool_timeout(30)
    .build()
)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("✅ Bot is running. Send /start in Telegram.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped.")
        sys.exit(0)
