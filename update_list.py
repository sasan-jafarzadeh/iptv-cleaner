import requests
import json
import re

SOURCES = [
    {"name": "Iran", "url": "https://iptv-org.github.io/iptv/countries/ir.m3u"},
    {"name": "Turkey", "url": "https://onureroz.com/indirmeler/turk/index.m3u"}
]

def check_stream(url):
    try:
        # Pings the server; if no answer in 1.5s, we skip it
        r = requests.head(url, timeout=1.5, allow_redirects=True)
        return r.status_code == 200
    except:
        return False

def main():
    clean_data = []
    for source in SOURCES:
        print(f"Scanning {source['name']}...")
        try:
            r = requests.get(source['url'], timeout=10)
            lines = r.text.splitlines()
            name, logo = "", ""
            for line in lines:
                if line.startswith("#EXTINF"):
                    name_match = re.search(r',([^,]+)$', line)
                    if name_match: name = name_match.group(1).strip()
                    logo_match = re.search(r'tvg-logo="([^"]+)"', line)
                    if logo_match: logo = logo_match.group(1)
                elif line.startswith("http") and name:
                    if check_stream(line):
                        clean_data.append({"title": name, "url": line, "cat": source['name'], "logo": logo})
                    name, logo = "", ""
        except: continue
    with open("live_channels.json", "w") as f:
        json.dump(clean_data, f, indent=4)

if __name__ == "__main__":
    main()
