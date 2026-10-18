"""Импорт и экспорт списка лент в формате OPML."""
import xml.etree.ElementTree as ET


def export_opml(feeds, path: str) -> None:
    """Записать ленты (список dict'ов из Database.list_feeds) в OPML-файл."""
    root = ET.Element("opml", version="2.0")
    head = ET.SubElement(root, "head")
    ET.SubElement(head, "title").text = "RSS Reader — экспорт лент"
    ET.SubElement(head, "dateCreated").text = "export"

    body = ET.SubElement(root, "body")
    for f in feeds:
        attrs = {
            "type": "rss",
            "text": f.get("title") or f["url"],
            "xmlUrl": f["url"],
        }
        if f.get("title"):
            attrs["title"] = f["title"]
        if f.get("site_url"):
            attrs["htmlUrl"] = f["site_url"]
        ET.SubElement(body, "outline", attrs)

    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def import_opml(path: str):
    """Прочитать OPML-файл, вернуть список пар (url, title|None)."""
    tree = ET.parse(path)
    found = []
    for outline in tree.getroot().iter("outline"):
        url = (outline.get("xmlUrl") or outline.get("xmlurl") or "").strip()
        if not url:
            continue
        title = (outline.get("title") or outline.get("text") or "").strip() or None
        found.append((url, title))
    if not found:
        raise ValueError("в файле не найдено RSS-лент (outline с атрибутом xmlUrl)")

    seen = set()
    result = []
    for url, title in found:
        if url not in seen:
            seen.add(url)
            result.append((url, title))
    return result
