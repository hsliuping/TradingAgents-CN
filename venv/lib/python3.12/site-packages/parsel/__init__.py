"""
Parsel lets you extract text from XML/HTML documents using XPath
or CSS selectors
"""

__author__ = "Scrapy project"
__email__ = "info@scrapy.org"
__version__ = "1.10.0"
__all__ = [
    "Selector",
    "SelectorList",
    "css2xpath",
    "xpathfuncs",
]

from parsel import xpathfuncs  # NOQA
from parsel.csstranslator import css2xpath  # NOQA
from parsel.selector import Selector, SelectorList  # NOQA

xpathfuncs.setup()
