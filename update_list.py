import requests
import json

sources = [
    "https://iptv-org.github.io/iptv/countries/ir.m3u",
    "https://iptv-org.github.io/iptv/countries/tr.m3u",
    "https://onureroz.com/indirmeler/turk/index.m3u"
]

live_channels = []

for url in sources:
    try:
        r = requests.get(url, timeout=10)
        lines = r.text.split('\n')
        current_item = {}
        for line in lines:
            if line.startswith('#EXTINF'):
                title = line.split(',')[-1].strip()
                logo = line.split('tvg-logo="')[1].split('"')[0] if 'tvg-logo="' in line else ""
                cat = line.split('group-title="')[1].split('"')[0] if 'group-title="' in line else "General"
                current_item = {"title": title, "logo": logo, "cat": cat}
            elif line.startswith('http') and "title" in current_item:
                stream_url = line.strip()
                try:
                    # Only add if the stream actually responds in 3 seconds
                    if requests.get(stream_url, timeout=3, stream=True).status_code == 200:
                        current_item["url"] = stream_url
                        live_channels.append(current_item)
                except: pass
                current_item = {} # Reset for next channel
    except: continue

with open("live_channels.json", "w", encoding="utf-8") as f:
    json.dump(live_channels, f, indent=4)
