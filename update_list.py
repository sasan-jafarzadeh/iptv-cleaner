import requests
import time

# ==============================
# CONFIG
# ==============================

PLAYLIST_URLS = [
    "https://iptv-org.github.io/iptv/countries/ir.m3u",
    "https://iptv-org.github.io/iptv/countries/tr.m3u",
    "https://onureroz.com/indirmeler/turk/index.m3u"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "/",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Referer": "https://onureroz.com/"
}

PLAYLIST_TIMEOUT = 15
STREAM_TIMEOUT = 8

OUTPUT_FILE = "live_list_cleaned.m3u"


# ==============================
# FETCH PLAYLIST
# ==============================

def fetch_playlist(url):
    try:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=PLAYLIST_TIMEOUT,
            allow_redirects=True
        )

        if r.status_code == 200 and "#EXTM3U" in r.text:
            print(f"[OK] Playlist fetched: {url}")
            return r.text

        print(f"[FAILED] Playlist blocked or invalid: {url} (Status {r.status_code})")
        return None

    except Exception as e:
        print(f"[ERROR] Fetch playlist {url}: {e}")
        return None


# ==============================
# CHECK STREAM
# ==============================

def is_stream_alive(url):
    try:
        # First try HEAD (lighter + faster)
        r = requests.head(
            url,
            headers=HEADERS,
            timeout=STREAM_TIMEOUT,
            allow_redirects=True
        )

        if r.status_code in (200, 206):
            return True

        # Fallback to GET if HEAD fails
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=STREAM_TIMEOUT,
            stream=True,
            allow_redirects=True
        )

        if r.status_code in (200, 206):
            return True

        return False

    except requests.RequestException:
        return False


# ==============================
# PARSE M3U
# ==============================

def parse_m3u(text):
    channels = []
    lines = text.splitlines()

    for i in range(len(lines)):
        line = lines[i].strip()

        if line.startswith("#EXTINF"):
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                if url.startswith("http"):
                    name = line.split(",")[-1].strip()
                    channels.append({
                        "name": name,
                        "extinf": line,
                        "url": url
                    })

    return channels


# ==============================
# MAIN
# ==============================

def main():
    all_live_channels = []

    for playlist_url in PLAYLIST_URLS:
        playlist_text = fetch_playlist(playlist_url)

        if not playlist_text:
            continue

        channels = parse_m3u(playlist_text)
        print(f"Found {len(channels)} channels in {playlist_url}")

        for channel in channels:
            print(f"Checking: {channel['name']}")

            if is_stream_alive(channel["url"]):
                print(f"  ✔ LIVE")
                all_live_channels.append(channel)
            else:
                print(f"  ✖ DEAD")

            time.sleep(0.05)  # small delay to avoid blocking

    # Write cleaned playlist
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for ch in all_live_channels:
            f.write(f"{ch['extinf']}\n")
            f.write(f"{ch['url']}\n")

    print("\n================================")
    print(f"Total live channels: {len(all_live_channels)}")
    print(f"Saved to: {OUTPUT_FILE}")
    print("================================")


if _name_ == "_main_":
    main()
