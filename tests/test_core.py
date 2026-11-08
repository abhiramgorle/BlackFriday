import json
from pathlib import Path

from dealwatch.models import Deal, UrlWatch, WatchItem, parse_price
from dealwatch.sources import page, slickdeals, walmart
from dealwatch.state import State

ITEM = WatchItem(
    name="Ninja Creami", match=["ninja", "creami"], exclude=["restored", "extra pint"], max_price=170, min_price=80
)


def test_parse_price():
    assert parse_price("Ninja CREAMi $149.99 + Free Shipping") == 149.99
    assert parse_price("Bambu Lab P2S Combo $1,049") == 1049.0
    assert parse_price("no price here") is None


def test_title_matching_and_price_gate():
    assert ITEM.title_matches("Ninja CREAMi 7-in-1 Ice Cream Maker NC301")
    assert not ITEM.title_matches("Restored Ninja Creami Deluxe")
    assert not ITEM.title_matches("Ninja Creami Extra Pint Containers 2-pack")
    assert ITEM.price_ok(149.0) and not ITEM.price_ok(199.0) and not ITEM.price_ok(None)
    assert not ITEM.price_ok(16.63)  # accessory / book
    assert WatchItem(name="x", match=["a"]).price_ok(None)


def test_slickdeals_feed():
    xml = """<?xml version="1.0"?><rss version="2.0"><channel>
      <item><title>Ninja CREAMi NC301 Ice Cream Maker $149 at Walmart + Free Shipping</title>
            <link>https://slickdeals.net/f/123-ninja</link><guid>https://slickdeals.net/f/123-ninja</guid></item>
      <item><title>Something else</title><link>https://slickdeals.net/f/9</link></item>
      <item><title>Ninja Creami old $99</title><link>https://slickdeals.net/f/1</link>
            <pubDate>Sun, 18 Oct 2026 15:50:12 +0000</pubDate></item>
    </channel></rss>"""
    deals = slickdeals.parse_feed(xml, ITEM, now=1794095472.0)  # 2026-11-08
    assert len(deals) == 2  # the 3-week-old post is dropped
    d = deals[0]
    assert d.price == 149.0 and d.store == "Walmart" and d.deal_id == "123-ninja"
    assert ITEM.title_matches(d.title) and not ITEM.title_matches(deals[1].title)


def test_walmart_next_data():
    product = {
        "usItemId": "990079514",
        "name": "Ninja NC301 CREAMi Ice Cream Maker",
        "canonicalUrl": "/ip/Ninja-NC301/990079514",
        "sellerName": "Walmart.com",
        "isOutOfStock": False,
        "price": 149,
        "priceInfo": {"priceDetails": {"priceLines": [{"lineType": "DISCOUNTED_PRICE", "values": [{"key": "PRICE", "value": "149.00"}]}]}},
    }
    html = '<html><script id="__NEXT_DATA__" type="application/json">' + json.dumps(
        {"props": {"pageProps": {"initialData": {"searchResult": {"itemStacks": [{"items": [product]}]}}}}}
    ) + "</script></html>"
    deals = walmart.parse_search(html, ITEM)
    assert deals and deals[0].price == 149.0 and deals[0].url.endswith("/ip/Ninja-NC301/990079514")
    assert walmart.parse_search("<html>Robot or human?</html>", ITEM) is None


def test_page_jsonld_product_group_variant_filter():
    ld = {
        "@context": "https://schema.org/",
        "@type": "ProductGroup",
        "name": "Bambu Lab P2S",
        "hasVariant": [
            {"@type": "Product", "name": "Bambu Lab P2S - P2S", "sku": "1",
             "offers": {"@type": "Offer", "price": 449, "availability": "https://schema.org/InStock", "url": "https://x/p2s?id=1"}},
            {"@type": "Product", "name": "Bambu Lab P2S - P2S Combo", "sku": "2",
             "offers": {"@type": "Offer", "price": 649, "availability": "https://schema.org/InStock", "url": "https://x/p2s?id=2"}},
            {"@type": "Product", "name": "Bambu Lab P2S - Combo Sold Out", "sku": "3",
             "offers": {"@type": "Offer", "price": 1, "availability": "https://schema.org/OutOfStock"}},
        ],
    }
    html = f'<html><script type="application/ld+json">{json.dumps(ld)}</script></html>'
    item = WatchItem(name="P2S Combo", urls=[UrlWatch(url="https://x/p2s", variant="Combo")], max_price=800)
    deals = page.parse_page(html, item.urls[0], item)
    assert [d.price for d in deals] == [649.0]
    assert deals[0].url == "https://x/p2s?id=2"


def test_state_dedup_and_price_drop(tmp_path: Path):
    st = State(tmp_path / "state.json")
    d = Deal(source="walmart", deal_id="1", title="t", url="u", price=149.0, item=ITEM)
    assert st.should_alert(d)
    st.record(d)
    st.save()
    st2 = State(tmp_path / "state.json")
    assert not st2.should_alert(d)
    cheaper = Deal(source="walmart", deal_id="1", title="t", url="u", price=129.0, item=ITEM)
    assert st2.should_alert(cheaper)
