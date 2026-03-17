import requests
import json
import re
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
        if line.startswith("#EXTINF") and i + 1 < len(lines):
            url = lines[i + 1].strip()
            if url.startswith("http"):
                try:
                    tvg_id_match = re.search(r'tvg-id="([^"]+)"', line)
                except:
                    tvg_id_match = None
                channels.append({
                    "name": line.split(",")[-1].strip() or "Unknown",
                    "extinf": line,
                    "url": url,
                    "tvg-id": tvg_id_match
                })
    return channels

# ==============================
# NORMALIZE NAME
# ==============================
def normalize_name(name):
    name = name.lower()
    name = re.sub(r'\b(hd|sd|720p|1080p|2160p|4k)\b', '', name)
    name = re.sub(r'\s+', ' ', name)
    return name.strip()

# ==============================
# EXTRACT RESOLUTION
# ==============================
def get_resolution(name):
    match = re.search(r'(\d{3,4})p', name.lower())
    return int(match.group(1)) if match else 0

# ==============================
# MAIN
# ==============================
def main():
    all_channels = []

    # جمع‌آوری همه کانال‌ها
    for url in PLAYLIST_URLS:
        text = fetch_playlist(url)
        if text:
            all_channels.extend(parse_m3u(text))

    # ==============================
    # MULTI-THREAD STREAM CHECK
    # ==============================
    def check_channel(ch):
        if is_stream_alive(ch["url"]):
            return ch
        return None

    checked_channels = []
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {executor.submit(check_channel, ch): ch for ch in all_channels}
        for future in as_completed(futures):
            ch = future.result()
            if ch:
                checked_channels.append(ch)

    # ==============================
    # DEDUP + KEEP HIGHEST RESOLUTION (SAFE)
    # ==============================
    unique_channels = {}

    for ch in checked_channels:
        try:
            key = ch["tvg-id"].group(1).lower() if ch["tvg-id"] else normalize_name(ch["name"])
        except:
            key = normalize_name(ch["name"])

        res = get_resolution(ch["name"])
        if key not in unique_channels:
            unique_channels[key] = ch
        else:
            existing_res = get_resolution(unique_channels[key]["name"])
            if res > existing_res:
                unique_channels[key] = ch

    final_channels = list(unique_channels.values())

    # ==============================
    # WRITE M3U
    # ==============================
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for ch in final_channels:
            f.write(f"{ch['extinf']}\n{ch['url']}\n")

    # ==============================
    # WRITE JSON
    # ==============================
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(final_channels, f, indent=2, ensure_ascii=False)

    print(f"Total live channels: {len(final_channels)}")
    print("Script completed successfully.")

if __name__ == "__main__":
    main()