import requests
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm  # pip install tqdm (optional but recommended)

# ==============================
# CONFIGURATION
# ==============================
PLAYLIST_URLS = [
    "https://iptv-org.github.io/iptv/countries/tr.m3u",
    "https://iptv-org.github.io/iptv/countries/ir.m3u",
    "https://iptv-org.github.io/iptv/languages/tur.m3u",
    "https://iptv-org.github.io/iptv/languages/fas.m3u",
    "https://onureroz.com/indirmeler/turk/index.m3u",
    "https://raw.githubusercontent.com/hodhodfarsi/iptv-for-iran/refs/heads/main/ir2.m3u"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Connection": "keep-alive"
}

PLAYLIST_TIMEOUT = 20
STREAM_TIMEOUT = 10
MAX_THREADS = 25
MAX_RETRIES = 2
OUTPUT_M3U = "live_list.m3u"
OUTPUT_JSON = "live_channels.json"

# ==============================
# FULL M3U PARSER (Real Player Format)
# ==============================
def parse_extinf(line):
    if not line.startswith("#EXTINF:"):
        return None
    rest = line[8:].strip()
    comma_pos = rest.rfind(",")
    if comma_pos == -1:
        return None
    params = rest[:comma_pos].strip()
    name = rest[comma_pos + 1:].strip()

    # Duration
    dur_match = re.match(r"(-?\d+)", params)
    duration = dur_match.group(1) if dur_match else "-1"

    # All attributes (tvg-id, tvg-logo, group-title, etc.)
    attr_part = params[len(duration):].strip() if dur_match else params
    attrs = {}
    for m in re.finditer(r'(\w+(?:-\w+)*)=["\']?([^"\']+)["\']?', attr_part):
        attrs[m.group(1)] = m.group(2)

    return {
        "duration": duration,
        "name": name,
        "attrs": attrs
    }

def parse_m3u(text):
    channels = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            parsed = parse_extinf(line)
            if parsed and i + 1 < len(lines):
                url = lines[i + 1].strip()
                if url.startswith(("http://", "https://")):
                    ch = {
                        "name": parsed["name"],
                        "url": url,
                        "extinf": line,                    # ← Full original line (CRITICAL for players)
                        "tvg_id": parsed["attrs"].get("tvg-id", ""),
                        "tvg_logo": parsed["attrs"].get("tvg-logo", ""),
                        "group_title": parsed["attrs"].get("group-title", "Uncategorized"),
                        "attrs": parsed["attrs"]
                    }
                    channels.append(ch)
        i += 1
    return channels

# ==============================
# IMPROVED STREAM CHECKER
# ==============================
def is_stream_alive(url):
    for attempt in range(MAX_RETRIES + 1):
        try:
            url_lower = url.lower()
            is_hls = any(x in url_lower for x in [".m3u8", "/stream?", "playlist.m3u", "/segment?"])

            session = requests.Session()
            session.headers.update(HEADERS)

            if is_hls:
                r = session.get(url, timeout=STREAM_TIMEOUT, allow_redirects=True, stream=True)
                if r.status_code not in (200, 206):
                    raise Exception("Bad status")
                content = r.content[:2000].decode("utf-8", errors="ignore")
                if any(tag in content for tag in ["#EXTM3U", "#EXT-X-", "#EXTINF"]):
                    return True
                ct = r.headers.get("content-type", "").lower()
                if "mpegurl" in ct or "m3u" in ct:
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
            time.sleep(0.5 * (attempt + 1))  # backoff

# ==============================
# MAIN
# ==============================
def main():
    print("🔥 Starting BEST IPTV Checker 2026...\n")
    all_channels = []

    # Fetch playlists
    for url in PLAYLIST_URLS:
        print(f"📥 Fetching: {url}")
        try:
            r = requests.get(url, headers=HEADERS, timeout=PLAYLIST_TIMEOUT, allow_redirects=True)
            if r.status_code == 200 and "#EXTM3U" in r.text[:200]:
                parsed = parse_m3u(r.text)
                print(f"   → {len(parsed):,} channels loaded")
                all_channels.extend(parsed)
            else:
                print("   → Failed or empty")
        except Exception as e:
            print(f"   → Error: {e}")

    print(f"\n🔍 Total channels to check: {len(all_channels):,}")

    # Deduplication key
    def get_key(ch):
        if ch["tvg_id"]:
            return f"tvg:{ch['tvg_id']}"
        return f"name:{ch['name'].strip().lower()}:{ch['group_title'].lower()}"

    # Check streams
    live_channels = []
    seen = set()

    def check_channel(ch):
        if is_stream_alive(ch["url"]):
            return ch
        return None

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = [executor.submit(check_channel, ch) for ch in all_channels]
        for future in tqdm(as_completed(futures), total=len(futures), desc="✅ Checking live streams"):
            result = future.result()
            if result:
                key = get_key(result)
                if key not in seen:
                    seen.add(key)
                    live_channels.append(result)

    # Sort like a real player
    live_channels.sort(key=lambda x: (x["group_title"], x["name"]))

    # Save M3U (perfect for any IPTV player)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for ch in live_channels:
            f.write(f"{ch['extinf']}\n{ch['url']}\n")

    # Save JSON (for your own apps)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump([{
            "name": ch["name"],
            "url": ch["url"],
            "group": ch["group_title"],
            "logo": ch["tvg_logo"],
            "tvg_id": ch["tvg_id"]
        } for ch in live_channels], f, indent=2, ensure_ascii=False)

    print(f"\n🎉 DONE! {len(live_channels):,} LIVE channels saved")
    print(f"   📁 {OUTPUT_M3U}  ← Load this in any IPTV player")
    print(f"   📁 {OUTPUT_JSON}  ← Structured data")
    print("\nNo issues. Real player ready. Enjoy! 🔥")

if __name__ == "__main__":
    main()
