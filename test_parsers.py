from app.crawlers.parsers.html_list_parser import HtmlListParser


def test_html_list_parser_extracts_link():
    html = "<html><body><a href='https://example.com/bid'>Bridge Improvements</a></body></html>"
    items = HtmlListParser().extract_items(html, None)
    assert len(items) == 1
    assert items[0].title == "Bridge Improvements"
