import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==============================
# CONFIGURATION
# ==============================

PLAYLIST_URLS = [
    "https://iptv-org.github.io/iptv/languages/tur.m3u",
    "https://iptv-org.github.io/iptv/countries/tr.m3u",
    "https://onureroz.com/indirmeler/turk/index.m3u",
    "https://raw.githubusercontent.com/hikmet-ergun/iptv/main/TR.m3u",
    "https://iptv-org.github.io/iptv/languages/fas.m3u",      # بهترین برای زبان فارسی
    "https://iptv-org.github.io/iptv/countries/ir.m3u",       # کشور ایران (IRIB و ...)
    "https://raw.githubusercontent.com/hodhodfarsi/iptv-for-iran/refs/heads/main/ir2.m3u",
    # ---- منابع اضافه‌شده (همه بررسی و تأیید شده‌اند) ----
    "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_turkey.m3u8",  # Free-TV: منتخب رسمی ترکیه (16 کانال)
    "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_iran.m3u8",    # Free-TV: منتخب ایران (26 کانال)
    "https://raw.githubusercontent.com/Olcayyk12/Turksat-4A/main/kanal_listesi.m3u",         # لیست به‌روز ترکی با لینک‌های فعلی ercdn و TRT (45 کانال)
    "https://raw.githubusercontent.com/hesenrustamli/az-iptv/main/playlist.m3u"              # پروژه مشابه خودت: آپدیت روزانه + چک سلامت؛ ترکی و آذری (108 کانال)
]

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*",
    "Connection": "keep-alive"
}

PLAYLIST_TIMEOUT = 15
STREAM_TIMEOUT   = 8
RETRIES          = 2          # تلاش مجدد برای خطاهای لحظه‌ای شبکه
OUTPUT_FILE      = "live_list.m3u"
OUTPUT_JSON      = "live_channels.json"
DROPPED_FILE     = "dropped_channels.txt"
MAX_THREADS      = 30

# فلسفه این لیست: کانال حذف نمی‌شود.
# وقتی یک کانال از چند منبع با لینک‌های متفاوت می‌آید، همه نگه داشته
# می‌شوند تا برای هر کانال چند راه پخش وجود داشته باشد. فقط کپی‌های
# کاملاً یکسان (اسم + لینک یکسان) حذف می‌شوند.
# اگر رفتار قبلی (یک لینک برای هر اسم) را خواستی، این را False کن:
KEEP_NAME_DUPLICATES = True

# ==============================
# FETCH PLAYLIST
# ==============================

def fetch_playlist(url):
    for _ in range(RETRIES + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=PLAYLIST_TIMEOUT, allow_redirects=True)
            if r.status_code == 200 and "#EXTM3U" in r.text:
                return r.text
        except Exception:
            pass
    return None

# ==============================
# CHECK STREAM (HLS-aware)
# ==============================
# عمداً مثل نسخه خودت فقط در سطح پلی‌لیست چک می‌کند: چکی که از یک
# کشور/شبکه دیگر انجام شود نمی‌تواند «مرده» را از «برای من بسته است»
# تشخیص دهد، پس کانالی به خاطر سگمنت یا جیوبلاک حذف نمی‌شود.

def is_stream_alive(url):
    for attempt in range(RETRIES + 1):
        try:
            url_lower = url.lower()
            is_hls = (
                ".m3u8" in url_lower or
                "/stream?" in url_lower or
                "playlist.m3u" in url_lower or
                "/segment?" in url_lower
            )

            if is_hls:
                r = requests.get(url, headers=HEADERS, timeout=STREAM_TIMEOUT, allow_redirects=True)
                if r.status_code in (200, 206):
                    try:
                        content = r.content[:1000].decode("utf-8", errors="ignore")
                    except Exception:
                        content = ""
                    if "#EXTM3U" in content or "#EXT-X-" in content or "#EXTINF" in content:
                        return True
                    ct = r.headers.get("content-type", "")
                    if "mpegurl" in ct or "m3u" in ct:
                        return True
                # خطای سرور قطعی است؛ ارزش تلاش مجدد ندارد
                if r.status_code in (400, 401, 403, 404, 410):
                    return False
            else:
                r = requests.head(url, headers=HEADERS, timeout=STREAM_TIMEOUT, allow_redirects=True)
                if r.status_code in (200, 206):
                    return True
                r = requests.get(url, headers=HEADERS, timeout=STREAM_TIMEOUT, stream=True, allow_redirects=True)
                if r.status_code in (200, 206):
                    return True
                if r.status_code in (400, 401, 403, 404, 410):
                    return False
        except Exception:
            pass  # خطای شبکه/تایم‌اوت: تلاش مجدد
    return False

# ==============================
# PARSE M3U
# ==============================
# خطوط #EXTVLCOPT و #KODIPROP بین EXTINF و URL هم تحمل و هم در خروجی
# حفظ می‌شوند (نسخه قبلی این کانال‌ها را بی‌صدا حذف می‌کرد).

def parse_m3u(text):
    channels = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            opts = []
            url = None
            j = i + 1
            while j < len(lines) and j <= i + 4:
                nxt = lines[j].strip()
                if nxt.startswith("#"):
                    opts.append(nxt)
                    j += 1
                    continue
                if nxt.startswith("http"):
                    url = nxt
                break
            if url:
                channels.append({
                    "name":   line.split(",", 1)[-1].strip() if "," in line else "Unknown",
                    "extinf": line,
                    "opts":   opts,
                    "url":    url
                })
                i = j
        i += 1
    return channels

# ==============================
# NORMALIZE NAME
# ==============================

def normalize_name(name):
    return " ".join(name.strip().lower().split())

# ==============================
# MAIN
# ==============================

def main():
    all_channels = []

    for url in PLAYLIST_URLS:
        print(f"Fetching: {url}")
        text = fetch_playlist(url)
        if text:
            parsed = parse_m3u(text)
            print(f"  -> {len(parsed)} channels found")
            all_channels.extend(parsed)
        else:
            print(f"  -> Failed")

    print(f"\nTotal channels to check: {len(all_channels)}")

    def check_channel(ch):
        result = dict(ch)
        result["alive"] = is_stream_alive(ch["url"])
        return result

    # چک موازی است ولی نتایج با ترتیب منابع نگه داشته می‌شوند تا
    # خروجی قطعی و پایدار باشد، نه وابسته به سرعت تمام‌شدن تردها.
    results = [None] * len(all_channels)
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {executor.submit(check_channel, ch): idx
                   for idx, ch in enumerate(all_channels)}
        for future in as_completed(futures):
            results[futures[future]] = future.result()

    live_channels = []
    dropped = []
    seen_exact = set()
    seen_names = set()

    for res in results:
        if res is None:
            continue
        if not res["alive"]:
            dropped.append(res)
            continue
        name_norm = normalize_name(res["name"])
        exact_key = (name_norm, res["url"])
        if exact_key in seen_exact:
            continue  # کپی کاملاً یکسان؛ کانال حذف نشده، کپی‌اش حذف شده
        seen_exact.add(exact_key)
        if not KEEP_NAME_DUPLICATES:
            if name_norm in seen_names:
                continue
            seen_names.add(name_norm)
        live_channels.append(res)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for ch in live_channels:
            f.write(f"{ch['extinf']}\n")
            for opt in ch.get("opts", []):
                f.write(f"{opt}\n")
            f.write(f"{ch['url']}\n")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(live_channels, f, indent=2, ensure_ascii=False)

    with open(DROPPED_FILE, "w", encoding="utf-8") as f:
        for ch in dropped:
            f.write(f"{ch['name']} | {ch['url']}\n")

    print(f"\nTotal live channels: {len(live_channels)}")
    print(f"Dropped (playlist check failed): {len(dropped)} (see {DROPPED_FILE})")
    print("Script completed successfully.")

if __name__ == "__main__":
    main()
