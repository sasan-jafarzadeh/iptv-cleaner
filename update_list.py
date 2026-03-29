import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==============================
# CONFIGURATION
# ==============================

PLAYLIST_URLS = [
    "https://iptv-org.github.io/iptv/countries/tr.m3u",
    "https://onureroz.com/indirmeler/turk/index.m3u",
    "https://raw.githubusercontent.com/hodhodfarsi/iptv-for-iran/refs/heads/main/ir2.m3u",
    "https://iptv-org.github.io/iptv/languages/fas.m3u"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Referer": "https://www.google.com/",
}

PLAYLIST_TIMEOUT = 15
STREAM_TIMEOUT   = 8
OUTPUT_FILE      = "live_list.m3u"
OUTPUT_JSON      = "live_channels.json"
MAX_THREADS      = 20

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
# CHECK STREAM (ALL FORMAT SUPPORT)
# ==============================

def is_stream_alive(url):
    try:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=STREAM_TIMEOUT,
            stream=True,
            allow_redirects=True
        )

        if r.status_code not in (200, 206):
            return False

        ct = r.headers.get("content-type", "").lower()

        # انواع قابل قبول IPTV
        valid_types = [
            "video", "audio",
            "mpegurl", "m3u",
            "mp2t", "mp4", "webm",
            "ogg", "dash", "octet-stream"
        ]

        if any(v in ct for v in valid_types):
            return True

        # fallback برای HLS
        try:
            chunk = r.raw.read(512, decode_content=True)
            if b"#EXTM3U" in chunk or b"#EXT-X-" in chunk:
                return True
        except:
            pass

        return True  # بعضی سرورها content-type درست نمی‌دن

    except:
        return False

# ==============================
# PARSE M3U (ROBUST)
# ==============================

def parse_m3u(text):
    channels = []
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    for i in range(len(lines)):
        if lines[i].startswith("#EXTINF"):
            if i + 1 < len(lines):
                url = lines[i + 1]
                if url.startswith("http"):
                    name = lines[i].split(",")[-1].strip() or "Unknown"
                    channels.append({
                        "name": name,
                        "extinf": lines[i],
                        "url": url
                    })
    return channels

# ==============================
# NORMALIZE NAME (UNCHANGED LOGIC)
# ==============================

def normalize_name(name):
    return name.strip().lower()

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
        if is_stream_alive(ch["url"]):
            return ch
        return None

    live_channels = []
    seen_names = set()  # 👈 همون منطق خودت

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {executor.submit(check_channel, ch): ch for ch in all_channels}
        for future in as_completed(futures):
            ch = future.result()
            if ch:
                name_norm = normalize_name(ch["name"])

                # 👇 منطق duplicate دست نخورده
                if name_norm not in seen_names:
                    live_channels.append(ch)
                    seen_names.add(name_norm)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for ch in live_channels:
            f.write(f"{ch['extinf']}\n{ch['url']}\n")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(live_channels, f, indent=2, ensure_ascii=False)

    print(f"\nTotal live channels: {len(live_channels)}")
    print("Script completed successfully.")

if __name__ == "__main__":
    main()
