from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.crawlers.fetch import fetch_page
from app.crawlers.parsers.fallback_parser import FallbackParser
from app.crawlers.parsers.html_list_parser import HTMLListParser
from app.crawlers.parsers.legal_notice_parser import LegalNoticeParser
from app.crawlers.parsers.table_parser import TableParser
from app.models.crawl_runs import CrawlRun
from app.models.registry_sources import RegistrySource


@dataclass
class CrawlResult:
    status: str
    records_found: int
    records_promoted: int


PARSER_MAP = {
    'HTML page': HTMLListParser,
    'Notice page': LegalNoticeParser,
    'Portal listing': TableParser,
    'PDF notice': FallbackParser,
    'Calendar': TableParser,
    'Manual review': FallbackParser,
}



def run_source_crawl(db: Session, source: RegistrySource) -> CrawlResult:
    crawl_run = CrawlRun(
        source_id=source.source_id,
        crawl_stage='notice_discovery',
        trigger_type='manual',
        status='success',
        parser_used=source.parser_hint,
        source_url_checked=source.effective_notice_entry_url,
    )
    db.add(crawl_run)
    db.commit()
    db.refresh(crawl_run)

    parser_cls = PARSER_MAP.get(source.parser_hint, FallbackParser)
    html = fetch_page(source.effective_notice_entry_url)
    parser = parser_cls()
    items = parser.extract_items(html, source)

    crawl_run.records_found = len(items)
    crawl_run.records_promoted = 0
    db.commit()

    return CrawlResult(status='success', records_found=len(items), records_promoted=0)
