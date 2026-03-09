import os
import re
import html
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

INPUT_FOLDER = "cleaned_infobox_html"
OUTPUT_FOLDER = "xml_output"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def clean_text(text: str) -> str:
    """Normalize textual content while keeping it readable."""
    if not text:
        return ""

    text = html.unescape(text)
    replacements = {
        "Â°": "°",
        "â€²": "′",
        "â€³": "″",
        "â€¢": "•",
        "â€“": "–",
        "â€”": "—",
        "ï»؟": "",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)

    text = text.replace("\xa0", " ")
    text = text.replace("\u200b", "")
    text = text.replace("\ufeff", "")

    # Drop thousands separators inside numbers (1,234 -> 1234)
    text = re.sub(r"(?<=\d),(?=\d)", "", text)

    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_ordinal(token: str) -> bool:
    return re.fullmatch(r"\d+(st|nd|rd|th)", token.lower()) is not None


def normalize_value_text(text: str, label: str) -> str:
    text = clean_text(text)

    # Remove coordinates from capital fields
    if "capital" in label.lower():
        parts = list(filter(None, re.split(r"\d+(?:\.\d+)?\s*°", text, maxsplit=1)))
        if parts:
            text = parts[0].strip()

    text = text.replace("\u200b", "").replace("\ufeff", "")
    return clean_text(text)


def tokenize_text(text: str) -> list[str]:
    text = clean_text(text)
    if not text:
        return []

    # Remove punctuation that should not be separate tokens
    text = re.sub(r"[(){}\[\],;]", " ", text)

    tokens = re.findall(
        r"\.[A-Za-z\u0600-\u06FF0-9-]+"
        r"|[A-Za-z\u0600-\u06FF]+(?:[-'][A-Za-z\u0600-\u06FF]+)*"
        r"|[+-]?\d+(?:[./:]\d+)*(?:/[A-Za-z0-9\u0600-\u06FF]+)?"
        r"|[A-Za-z\u0600-\u06FF]+[+]\d+(?::\d+)?",
        text
    )

    cleaned_tokens = []
    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue
        if is_ordinal(tok):
            continue
        # Skip purely numeric tokens (project focuses on textual content)
        if re.fullmatch(r"[0-9][0-9,./:-]*", tok):
            continue
        cleaned_tokens.append(tok)

    return cleaned_tokens


def prettify_xml(elem: ET.Element, level: int = 0) -> None:
    indent = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "  "
        for child in elem:
            prettify_xml(child, level + 1)
            if not child.tail or not child.tail.strip():
                # indent siblings at the parent level (root siblings need two spaces too)
                child.tail = indent + "  "
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent


def add_tokens(parent: ET.Element, text: str) -> int:
    """
    Add one <token> child per token. Returns number of tokens added.
    """
    tokens = tokenize_text(text)
    for tok in tokens:
        t = ET.SubElement(parent, "token")
        t.text = tok
    return len(tokens)


def extract_country_name_from_filename(filename: str) -> str:
    return os.path.splitext(filename)[0]


def slugify(label: str) -> str:
    """
    Turn an arbitrary label into a safe XML tag:
    - lowercase
    - spaces/punctuation -> _
    - leading digits prefixed with f_
    - collapse duplicate underscores
    """
    tag = re.sub(r"[^A-Za-z0-9]+", "_", label.lower()).strip("_")
    tag = re.sub(r"__+", "_", tag)
    if not tag:
        tag = "field"
    if tag[0].isdigit():
        tag = f"f_{tag}"
    return tag


def unique_child_tag(parent: ET.Element, base: str) -> str:
    """Ensure tag name is unique among parent's children."""
    if not any(child.tag == base for child in parent):
        return base
    i = 2
    while True:
        candidate = f"{base}_{i}"
        if not any(child.tag == candidate for child in parent):
            return candidate
        i += 1


def get_first_meaningful_text(td) -> str:
    for s in td.stripped_strings:
        s = clean_text(s)
        if s:
            return s
    return ""


def build_xml_tree_from_html(html: str, country_name: str) -> ET.Element:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find_all("tr")

    root = ET.Element("country")

    country_name_elem = ET.SubElement(root, "name")
    add_tokens(country_name_elem, country_name)

    current_section = None
    first_header_skipped = False

    for row in rows:
        th = row.find("th")
        td = row.find("td")

        if not th and not td:
            continue

        # Skip the very first infobox title row (country long name / native names)
        if th and not td and not first_header_skipped:
            first_header_skipped = True
            continue

        # Section row
        if th and not td:
            section_name = clean_text(th.get_text(" ", strip=True))
            if not section_name:
                continue

            section_tag = unique_child_tag(root, slugify(section_name))
            current_section = ET.SubElement(root, section_tag)
            continue

        # Regular field row
        if th and td:
            raw_label = th.get_text(" ", strip=True)
            label = clean_text(re.sub(r"^\s*•\s*", "", raw_label))

            if not label:
                continue

            is_subfield = raw_label.strip().startswith("•")

            if "capital" in label.lower():
                value = get_first_meaningful_text(td)
            else:
                value = clean_text(td.get_text(" ", strip=True))

            value = normalize_value_text(value, label)

            if not value:
                continue

            if current_section is not None and is_subfield:
                parent = current_section
            else:
                parent = root
                if current_section is not None and not is_subfield:
                    current_section = None

            tag = unique_child_tag(parent, slugify(label))
            field_elem = ET.SubElement(parent, tag)
            added = add_tokens(field_elem, value)

            # If no textual tokens remain, drop the field entirely
            if added == 0:
                parent.remove(field_elem)

    return root


def process_all_files() -> None:
    for filename in os.listdir(INPUT_FOLDER):
        if not filename.endswith(".html"):
            continue

        input_path = os.path.join(INPUT_FOLDER, filename)

        with open(input_path, "r", encoding="utf-8") as f:
            html = f.read()

        country_name = extract_country_name_from_filename(filename)
        root = build_xml_tree_from_html(html, country_name)
        prettify_xml(root)

        output_path = os.path.join(OUTPUT_FOLDER, f"{country_name}.xml")
        tree = ET.ElementTree(root)
        tree.write(output_path, encoding="utf-8", xml_declaration=True)

        print(f"Saved XML: {output_path}")


if __name__ == "__main__":
    process_all_files()
