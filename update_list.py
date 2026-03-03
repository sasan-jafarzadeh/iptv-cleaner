import requests
import json

# Your list of M3U sources
sources = [
    "https://iptv-org.github.io/iptv/countries/ir.m3u",
    "https://iptv-org.github.io/iptv/countries/tr.m3u"
]

live_channels = []

print("Starting scan...")

for url in sources:
    try:
        r = requests.get(url, timeout=10)
        lines = r.text.split('\n')
        
        current_item = {}
        for line in lines:
            if line.startswith('#EXTINF'):
                # Extract Title
                title = line.split(',')[-1].strip()
                # Extract Logo
                logo = ""
                if 'tvg-logo="' in line:
                    logo = line.split('tvg-logo="')[1].split('"')[0]
                # Extract Category
                cat = "General"
                if 'group-title="' in line:
                    cat = line.split('group-title="')[1].split('"')[0]
                
                current_item = {"title": title, "logo": logo, "cat": cat}
            
            elif line.startswith('http'):
                stream_url = line.strip()
                # Verification: Ping the stream to see if it's alive
                try:
                    check = requests.get(stream_url, timeout=3, stream=True)
                    if check.status_code == 200:
                        current_item["url"] = stream_url
                        live_channels.append(current_item)
                        print(f"Added: {current_item['title']}")
                except:
                    pass
    except:
        continue

# 1. SAVE AS JSON (For your Roku)
with open("live_channels.json", "w", encoding="utf-8") as f:
    json.dump(live_channels, f, indent=4)

# 2. SAVE AS M3U (For other players)
with open("live_list.m3u", "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    for ch in live_channels:
        f.write(f'#EXTINF:-1 tvg-logo="{ch["logo"]}" group-title="{ch["cat"]}",{ch["title"]}\n')
        f.write(f'{ch["url"]}\n')

print(f"Finished! Found {len(live_channels)} live channels.")
