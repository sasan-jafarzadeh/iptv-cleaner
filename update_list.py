import requests
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==============================
# CONFIGURATION - Updated 2026
# ==============================
PLAYLIST_URLS = [
    "https://iptv-org.github.io/iptv/countries/tr.m3u",
    "https://iptv-org.github.io/iptv/countries/ir.m3u",
    "https://iptv-org.github.io/iptv/languages/tur.m3u",
    "https://iptv-org.github.io/iptv/languages/fas.m3u",
    "https://onureroz.com/indirmeler/turk/index.m3u",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
}

PLAYLIST_TIMEOUT = 25
STREAM_TIMEOUT = 12
MAX_THREADS = 20
MAX_RETRIES = 2

OUTPUT_M3U = "live_list.m3u"
OUTPUT_JSON = "live_channels.json"

# ==============================
# PARSER (حفظ کامل اطلاعات برای پلیر)
# ==============================
def parse_m3u(text):
    channels = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            # Extract full attributes
            match = re.search(r'#EXTINF:(-?\d+)(.*),(.*)', line)
            if match:
                duration = match.group(1)
                attrs_str = match.group(2)
                name = match.group(3).strip()

                attrs = {}
                for m in re.finditer(r'(\w+(?:-\w+)*)=["\']([^"\']+)["\']', attrs_str):
                    attrs[m.group(1)] = m.group(2)

                if i + 1 < len(lines):
                    url = lines[i + 1].strip()
                    if url.startswith("http"):
                        channels.append({
                            "name": name,
                            "url": url,
                            "extinf": line,
                            "tvg_id": attrs.get("tvg-id", ""),
                            "tvg_logo": attrs.get("tvg-logo", ""),
                            "group_title": attrs.get("group-title", "Uncategorized")
                        })
        i += 1
    return channels

# ==============================
# STREAM CHECKER
# ==============================
def is_stream_alive(url):
    for attempt in range(MAX_RETRIES + 1):
        try:
            session = requests.Session()
            session.headers.update(HEADERS)
            is_hls = any(x in url.lower() for x in [".m3u8", "playlist", "/stream", "/segment"])

            if is_hls:
                r = session.get(url, timeout=STREAM_TIMEOUT, allow_redirects=True, stream=True)
                if r.status_code in (200, 206):
                    content = r.content[:1500].decode("utf-8", errors="ignore")
                    if "#EXTM3U" in content or "#EXT-X-" in content:
                        return True
            else:
                r = session.head(url, timeout=STREAM_TIMEOUT, allow_redirects=True)
                if r.status_code in (200, 206, 301, 302):
                    return True
                r = session.get(url, timeout=STREAM_TIMEOUT, stream=True, allow_redirects=True)
                if r.status_code in (200, 206):
                    return True
            return False
        except:
            if attempt == MAX_RETRIES:
                return False
            time.sleep(0.8 * (attempt + 1))

# ==============================
# MAIN
# ==============================
def main():
    print("🚀 شروع چک‌کننده IPTV...\n")
    all_channels = []

    for url in PLAYLIST_URLS:
        print(f"📥 در حال دانلود: {url}")
        try:
            r = requests.get(url, headers=HEADERS, timeout=PLAYLIST_TIMEOUT)
            if r.status_code == 200 and "#EXTM3U" in r.text:
                parsed = parse_m3u(r.text)
                print(f"   ✅ {len(parsed)} کانال پیدا شد")
                all_channels.extend(parsed)
            else:
                print("   ❌ ناموفق")
        except Exception as e:
            print(f"   ❌ خطا: {e}")

    print(f"\n🔍 تعداد کل کانال برای تست: {len(all_channels)}")

    live_channels = []
    seen = set()

    def check(ch):
        if is_stream_alive(ch["url"]):
            key = ch.get("tvg_id") or ch["name"].lower() + ch.get("group_title", "")
            if key not in seen:
                seen.add(key)
                return ch
        return None

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = [executor.submit(check, ch) for ch in all_channels]
        for future in as_completed(futures):
            result = future.result()
            if result:
                live_channels.append(result)

    # مرتب‌سازی
    live_channels.sort(key=lambda x: (x.get("group_title", ""), x["name"]))

    # ذخیره M3U
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for ch in live_channels:
            f.write(f"{ch['extinf']}\n{ch['url']}\n")

    # ذخیره JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(live_channels, f, indent=2, ensure_ascii=False)

    print(f"\n🎉 تمام! {len(live_channels)} کانال زنده پیدا شد")
    print(f"فایل‌ها ذخیره شدند:\n   → {OUTPUT_M3U}  (برای پخش در VLC, TiviMate و ...)")
    print(f"   → {OUTPUT_JSON}")

if __name__ == "__main__":
    main()
