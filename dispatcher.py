from app.crawlers.parsers.fallback_parser import FallbackParser
from app.crawlers.parsers.html_list_parser import HtmlListParser
from app.crawlers.parsers.legal_notice_parser import LegalNoticeParser
from app.crawlers.parsers.table_parser import TableParser


def get_parser(parser_hint: str):
    mapping = {
        "html_list": HtmlListParser(),
        "html_table": TableParser(),
        "legal_notice": LegalNoticeParser(),
        "portal_link": HtmlListParser(),
        "manual_review": FallbackParser(),
    }
    return mapping.get(parser_hint, FallbackParser())
