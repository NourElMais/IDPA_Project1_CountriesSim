import os
from bs4 import BeautifulSoup

input_folder = "infobox_html"
output_folder = "cleaned_infobox_html"

os.makedirs(output_folder, exist_ok=True)

for filename in os.listdir(input_folder):
    if not filename.endswith(".html"):
        continue

    input_path = os.path.join(input_folder, filename)

    with open(input_path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    infobox = soup.find("table")

    if not infobox:
        print(f"No table found in {filename}")
        continue

    # 1) remove citations like [1], [a]
    for tag in infobox.find_all("sup", class_="reference"):
        tag.decompose()

    # 2) remove style/script tags
    for tag in infobox.find_all(["style", "script"]):
        tag.decompose()

    # 3) remove audio tags
    for tag in infobox.find_all(["audio", "source", "track"]):
        tag.decompose()

    # 4) strip images but keep the row text (we need the numeric values beside icons)
    for tag in infobox.find_all("img"):
        tag.decompose()

    # Drop only truly non-text rows (hidden/map/anthem/etc.)
    for row in infobox.find_all("tr"):
        row_text = row.get_text(" ", strip=True).lower()

        has_audio = row.find("audio") is not None
        is_hidden = row.get("style") == "display:none"
        looks_like_map_or_flag = (
            "flag" in row_text
            or "coat of arms" in row_text
            or "location of" in row_text
            or "anthem" in row_text
        )

        if has_audio or is_hidden or looks_like_map_or_flag:
            row.decompose()

    # 5) remove unnecessary attributes from all remaining tags
    allowed_attrs = {
        "th": ["scope", "colspan"],
        "td": ["colspan"],
        "tr": [],
        "table": [],
        "tbody": [],
        "div": [],
        "ul": [],
        "li": [],
        "br": [],
        "span": [],
        "a": ["href"]
    }

    for tag in infobox.find_all(True):
        tag_name = tag.name
        attrs_to_keep = allowed_attrs.get(tag_name, [])
        tag.attrs = {k: v for k, v in tag.attrs.items() if k in attrs_to_keep}

    output_path = os.path.join(output_folder, filename)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(infobox.prettify())

    print(f"Cleaned: {filename}")
