import requests
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==============================
# CONFIGURATION
# ==============================
PLAYLIST_URLS = [
    "https://iptv-org.github.io/iptv/countries/ir.m3u",
    "https://iptv-org.github.io/iptv/countries/tr.m3u",
    "https://onureroz.com/indirmeler/turk/index.m3u",
    "https://raw.githubusercontent.com/hodhodfarsi/iptv-for-iran/refs/heads/main/ir2.m3u",
    "https://iptv-org.github.io/iptv/languages/fas.m3u"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*",
    "Connection": "keep-alive"
}

PLAYLIST_TIMEOUT = 15
STREAM_TIMEOUT = 8
OUTPUT_FILE = "live_list.m3u"
OUTPUT_JSON = "live_channels.json"

MAX_THREADS = 20  # تعداد همزمان برای سرعت

# ==============================
# FETCH PLAYLIST
# ==============================
def fetch_playlist(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=PLAYLIST_TIMEOUT, allow_redirects=True)
        if r.status_code == 200 and "#EXTM3U" in r.text:
            return r.text
        return None
    except:
        return None

# ==============================
# CHECK STREAM
# ==============================
def is_stream_alive(url):
    try:
        r = requests.head(url, headers=HEADERS, timeout=STREAM_TIMEOUT, allow_redirects=True)
        if r.status_code in (200, 206):
            return True
        r = requests.get(url, headers=HEADERS, timeout=STREAM_TIMEOUT, stream=True, allow_redirects=True)
        if r.status_code in (200, 206):
            return True
        return False
    except:
        return False

# ==============================
# PARSE M3U
# ==============================
def parse_m3u(text):
    channels = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith("#EXTINF") and i+1 < len(lines):
            url = lines[i+1].strip()
            if url.startswith("http"):
                channels.append({
                    "extinf": line,
                    "url": url
                })
    return channels

# ==============================
# MAIN
# ==============================
def main():
    all_channels = []

    for url in PLAYLIST_URLS:
        text = fetch_playlist(url)
        if text:
            all_channels.extend(parse_m3u(text))

    # ==============================
    # MULTI-THREAD CHECK
    # ==============================
    def check_channel(ch):
        if is_stream_alive(ch["url"]):
            return ch
        return None

    live_channels = []
    seen_urls = set()

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {executor.submit(check_channel, ch): ch for ch in all_channels}
        for future in as_completed(futures):
            ch = future.result()
            if ch and ch["url"] not in seen_urls:
                live_channels.append(ch)
                seen_urls.add(ch["url"])

    # ==============================
    # WRITE M3U
    # ==============================
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for ch in live_channels:
            f.write(f"{ch['extinf']}\n{ch['url']}\n")

    # ==============================
    # WRITE JSON
    # ==============================
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(live_channels, f, indent=2, ensure_ascii=False)

    print(f"Total live channels: {len(live_channels)}")
    print("Script completed successfully.")

if __name__ == "__main__":
    main()