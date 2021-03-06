# -*- coding: utf-8 -*-
# This file is part of Viper - https://github.com/viper-framework/viper
# See the file 'LICENSE' for copying permission.

import os
from pathlib import Path
import logging
from urllib.parse import urlparse
from typing import List, Iterator
from scrapy import Spider  # type: ignore
from scrapy.linkextractors import LinkExtractor  # type: ignore
from scrapy.crawler import CrawlerProcess, Crawler  # type: ignore
from scrapy import signals  # type: ignore
from scrapy_splash import SplashRequest, SplashJsonResponse  # type: ignore


class ScrapySplashWrapperCrawler():

    class ScrapySplashWrapperSpider(Spider):
        name = 'ScrapySplashWrapperSpider'

        def __init__(self, url: str, useragent: str, cookies: List[dict]=[], log_level: str='WARNING', *args, **kwargs):
            logger = logging.getLogger('scrapy')
            logger.setLevel(log_level)
            super().__init__(*args, **kwargs)
            self.start_url: str = url
            self.useragent: str = useragent
            self.allowed_domains: List[str] = []
            self.cookies: List[dict] = cookies
            hostname = urlparse(self.start_url).hostname
            if hostname:
                self.allowed_domains = ['.'.join(hostname.split('.')[-2:])]
            realpath = Path(os.path.realpath(__file__)).parent
            with (realpath / 'crawl.lua').open() as _crawl:
                self.script = _crawl.read()

        def start_requests(self):
            yield SplashRequest(self.start_url, self.parse, endpoint='execute',
                                args={'wait': 15, 'resource_timeout': 40,
                                      'timeout': 60,
                                      'useragent': self.useragent,
                                      'cookies': self.cookies,
                                      'lua_source': self.script
                                      })

        def parse(self, response: SplashJsonResponse) -> Iterator[dict]:
            le = LinkExtractor(allow_domains=self.allowed_domains)
            for link in le.extract_links(response):
                yield SplashRequest(link.url, self.parse, endpoint='execute',
                                    args={'wait': 10, 'resource_timeout': 20,
                                          'useragent': self.useragent,
                                          'cookies': response.data['cookies'],
                                          'lua_source': self.script
                                          })
            yield response.data

    def __init__(self, splash_url: str, useragent: str, cookies: List[dict]=[], depth: int=1, log_enabled: bool=False, log_level: str='WARNING'):
        self.useragent = useragent
        self.cookies = cookies
        self.log_level = log_level
        self.process = CrawlerProcess({'LOG_ENABLED': log_enabled})
        self.crawler = Crawler(self.ScrapySplashWrapperSpider, {
            'LOG_ENABLED': log_enabled,
            'LOG_LEVEL': log_level,
            'SPLASH_URL': splash_url,
            'DOWNLOADER_MIDDLEWARES': {'scrapy_splash.SplashCookiesMiddleware': 723,
                                       'scrapy_splash.SplashMiddleware': 725,
                                       'scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware': 810,
                                       },
            'SPIDER_MIDDLEWARES': {'scrapy_splash.SplashDeduplicateArgsMiddleware': 100,
                                   'scrapysplashwrapper.ScrapySplashWrapperDepthMiddleware': 110},
            'DUPEFILTER_CLASS': 'scrapy_splash.SplashAwareDupeFilter',
            'DEPTH_LIMIT': depth
        })

    def crawl(self, url):
        crawled_items = []

        def add_item(item):
            crawled_items.append(item)

        self.crawler.signals.connect(add_item, signals.item_scraped)
        self.process.crawl(self.crawler, url=url, useragent=self.useragent, cookies=self.cookies, log_level=self.log_level)
        self.process.start()
        return crawled_items
