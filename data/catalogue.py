"""
data/catalogue.py
Real product catalogue for ShopSmart India.
Replaces synthetic SKU data with actual products, prices, margins,
elasticities, and competitor mappings.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Product:
    id: str
    name: str
    brand: str
    category: str
    subcategory: str
    base_price: float           # Your current selling price (INR)
    cost_price: float           # What you paid for it
    mrp: float                  # Max retail price printed on product
    reorder_point: int          # Reorder when stock falls below this
    initial_stock: int
    price_elasticity: float     # Negative: how sensitive demand is to price
    competitor_urls: list       # Competitor product pages to scrape
    tags: list = field(default_factory=list)
    description: str = ""

    @property
    def margin_pct(self) -> float:
        return round((self.base_price - self.cost_price) / self.base_price * 100, 1)

    @property
    def discount_from_mrp(self) -> float:
        return round((self.mrp - self.base_price) / self.mrp * 100, 1)


# ── Electronics ───────────────────────────────────────────────────────────────

ELECTRONICS = [
    Product(
        id="ELEC-001",
        name="Samsung 65\" Crystal 4K UHD Smart TV (UA65CUE60)",
        brand="Samsung",
        category="Electronics",
        subcategory="Televisions",
        base_price=54999,
        cost_price=44000,
        mrp=74900,
        reorder_point=3,
        initial_stock=12,
        price_elasticity=-2.1,
        competitor_urls=[
            "https://www.flipkart.com/samsung-163-cm-65-inch-ultra-hd-4k-led-smart-tizen-tv",
            "https://www.amazon.in/Samsung-Crystal-inches-UA65CUE60AKLXL",
        ],
        tags=["tv", "samsung", "4k", "smart-tv"],
        description="65-inch 4K Crystal UHD with PurColor, HDR, and Tizen OS",
    ),
    Product(
        id="ELEC-002",
        name="boAt Rockerz 450 Bluetooth Headphones",
        brand="boAt",
        category="Electronics",
        subcategory="Headphones",
        base_price=1299,
        cost_price=620,
        mrp=3990,
        reorder_point=15,
        initial_stock=5,
        price_elasticity=-2.0,
        competitor_urls=[
            "https://www.amazon.in/boAt-Rockerz-450-Bluetooth-Headphone",
            "https://www.flipkart.com/boat-rockerz-450-bluetooth-headphone",
        ],
        tags=["headphones", "boat", "bluetooth", "wireless"],
        description="40mm drivers, 15hr battery, foldable design",
    ),
    Product(
        id="ELEC-003",
        name="Redmi Note 13 5G (Graphite Black, 8GB RAM)",
        brand="Xiaomi",
        category="Electronics",
        subcategory="Smartphones",
        base_price=16999,
        cost_price=13500,
        mrp=19999,
        reorder_point=10,
        initial_stock=28,
        price_elasticity=-2.3,
        competitor_urls=[
            "https://www.flipkart.com/redmi-note-13-5g-graphite-black-8-gb",
            "https://www.amazon.in/Redmi-Note-13-5G-Graphite",
        ],
        tags=["smartphone", "redmi", "5g", "xiaomi"],
        description="Snapdragon 685, 108MP camera, 5000mAh battery",
    ),
    Product(
        id="ELEC-004",
        name="Lenovo IdeaPad Slim 3 15\" Laptop (i5, 16GB, 512GB SSD)",
        brand="Lenovo",
        category="Electronics",
        subcategory="Laptops",
        base_price=49990,
        cost_price=41000,
        mrp=64990,
        reorder_point=2,
        initial_stock=7,
        price_elasticity=-1.9,
        competitor_urls=[
            "https://www.flipkart.com/lenovo-ideapad-slim-3",
            "https://www.amazon.in/Lenovo-IdeaPad-Slim-3",
        ],
        tags=["laptop", "lenovo", "i5", "student"],
        description="Intel Core i5-12th Gen, FHD display, Windows 11",
    ),
]

# ── Fashion ───────────────────────────────────────────────────────────────────

FASHION = [
    Product(
        id="FASH-001",
        name="Nike Air Max 270 (Men's, Black/White, Size 9)",
        brand="Nike",
        category="Footwear",
        subcategory="Sports Shoes",
        base_price=8995,
        cost_price=4200,
        mrp=12995,
        reorder_point=5,
        initial_stock=34,
        price_elasticity=-1.6,
        competitor_urls=[
            "https://www.flipkart.com/nike-air-max-270",
            "https://www.myntra.com/sports-shoes/nike/air-max-270",
        ],
        tags=["nike", "running", "airmax", "sports"],
        description="Max Air cushioning, mesh upper, lifestyle running shoe",
    ),
    Product(
        id="FASH-002",
        name="Levi's 511 Slim Fit Jeans (Men's, Dark Indigo)",
        brand="Levi's",
        category="Clothing",
        subcategory="Jeans",
        base_price=2999,
        cost_price=1200,
        mrp=4999,
        reorder_point=8,
        initial_stock=8,
        price_elasticity=-1.3,
        competitor_urls=[
            "https://www.myntra.com/jeans/levis/511-slim-fit",
            "https://www.flipkart.com/levis-511-slim-jeans",
        ],
        tags=["levis", "jeans", "denim", "slim-fit"],
        description="Stretch denim, slim through thigh and leg opening",
    ),
    Product(
        id="FASH-003",
        name="Manyavar Kurta Set (Men's, Royal Blue, XL)",
        brand="Manyavar",
        category="Clothing",
        subcategory="Ethnic Wear",
        base_price=3499,
        cost_price=1400,
        mrp=5999,
        reorder_point=4,
        initial_stock=19,
        price_elasticity=-0.9,
        competitor_urls=[
            "https://www.myntra.com/kurta-sets/manyavar",
            "https://www.flipkart.com/manyavar-kurta-set",
        ],
        tags=["manyavar", "ethnic", "kurta", "festive"],
        description="Premium silk-blend fabric, festive occasion kurta set",
    ),
]

# ── Grocery & FMCG ────────────────────────────────────────────────────────────

GROCERY = [
    Product(
        id="GROC-001",
        name="Nescafé Classic Instant Coffee 200g",
        brand="Nestlé",
        category="Grocery",
        subcategory="Beverages",
        base_price=349,
        cost_price=220,
        mrp=430,
        reorder_point=30,
        initial_stock=210,
        price_elasticity=-0.8,
        competitor_urls=[
            "https://www.bigbasket.com/pd/40075376/nescafe-classic-instant-coffee",
            "https://www.jiomart.com/p/nescafe-classic-instant-coffee-200g",
        ],
        tags=["nescafe", "coffee", "nestle", "instant"],
        description="Pure soluble coffee, rich aroma, 200g jar",
    ),
    Product(
        id="GROC-002",
        name="Tata Salt Lite Low Sodium 1kg",
        brand="Tata",
        category="Grocery",
        subcategory="Staples",
        base_price=29,
        cost_price=18,
        mrp=35,
        reorder_point=100,
        initial_stock=850,
        price_elasticity=-0.4,
        competitor_urls=[
            "https://www.bigbasket.com/pd/tata-salt-lite",
            "https://www.jiomart.com/p/tata-salt-lite-1kg",
        ],
        tags=["tata", "salt", "staple", "low-sodium"],
        description="25% less sodium, iodised, 1kg pack",
    ),
    Product(
        id="GROC-003",
        name="Amul Butter 500g",
        brand="Amul",
        category="Grocery",
        subcategory="Dairy",
        base_price=275,
        cost_price=210,
        mrp=310,
        reorder_point=50,
        initial_stock=120,
        price_elasticity=-0.6,
        competitor_urls=[
            "https://www.bigbasket.com/pd/amul-butter-500g",
            "https://www.jiomart.com/p/amul-butter-500g",
        ],
        tags=["amul", "butter", "dairy", "breakfast"],
        description="Pasteurised butter, 500g, refrigerated",
    ),
]

# ── Home & Kitchen ────────────────────────────────────────────────────────────

HOME = [
    Product(
        id="HOME-001",
        name="Prestige Deluxe Alpha Pressure Cooker 5L",
        brand="Prestige",
        category="Kitchen",
        subcategory="Pressure Cookers",
        base_price=1899,
        cost_price=1100,
        mrp=2995,
        reorder_point=5,
        initial_stock=22,
        price_elasticity=-1.1,
        competitor_urls=[
            "https://www.amazon.in/Prestige-Deluxe-Alpha-Pressure-Cooker",
            "https://www.flipkart.com/prestige-deluxe-alpha-pressure-cooker",
        ],
        tags=["prestige", "pressure-cooker", "kitchen", "induction"],
        description="Hard anodised aluminium, induction compatible, 5 litre",
    ),
    Product(
        id="HOME-002",
        name="Philips Air Purifier AC1215/20 (360sq.ft.)",
        brand="Philips",
        category="Home Appliances",
        subcategory="Air Purifiers",
        base_price=8499,
        cost_price=5800,
        mrp=13995,
        reorder_point=3,
        initial_stock=9,
        price_elasticity=-1.4,
        competitor_urls=[
            "https://www.flipkart.com/philips-air-purifier-ac1215",
            "https://www.amazon.in/Philips-Air-Purifier-AC1215",
        ],
        tags=["philips", "air-purifier", "hepa", "home"],
        description="HEPA filter, removes 99.97% pollutants, 360° intake",
    ),
    Product(
        id="HOME-003",
        name="Wipro Garnet 9W LED Bulb Pack of 6",
        brand="Wipro",
        category="Home",
        subcategory="Lighting",
        base_price=299,
        cost_price=160,
        mrp=480,
        reorder_point=40,
        initial_stock=340,
        price_elasticity=-0.7,
        competitor_urls=[
            "https://www.amazon.in/Wipro-Garnet-LED-Bulb",
            "https://www.flipkart.com/wipro-garnet-led-bulb-pack-6",
        ],
        tags=["wipro", "led", "bulb", "energy-saving"],
        description="9W = 75W equivalent, 6500K cool white, 2-yr warranty",
    ),
]

# ── Sports & Fitness ──────────────────────────────────────────────────────────

SPORTS = [
    Product(
        id="SPRT-001",
        name="Yonex Mavis 350 Shuttlecocks (Pack of 6)",
        brand="Yonex",
        category="Sports",
        subcategory="Badminton",
        base_price=549,
        cost_price=310,
        mrp=750,
        reorder_point=20,
        initial_stock=88,
        price_elasticity=-1.5,
        competitor_urls=[
            "https://www.amazon.in/Yonex-Mavis-350-Shuttlecocks",
            "https://www.flipkart.com/yonex-mavis-350-shuttlecock",
        ],
        tags=["yonex", "badminton", "shuttlecock", "sports"],
        description="Nylon feather simulation, medium speed, 6-pack",
    ),
    Product(
        id="SPRT-002",
        name="Boldfit Yoga Mat 6mm Non-Slip with Carry Strap",
        brand="Boldfit",
        category="Sports",
        subcategory="Yoga & Fitness",
        base_price=599,
        cost_price=250,
        mrp=1299,
        reorder_point=10,
        initial_stock=56,
        price_elasticity=-1.7,
        competitor_urls=[
            "https://www.amazon.in/Boldfit-Yoga-Mat-6mm",
            "https://www.flipkart.com/boldfit-yoga-mat",
        ],
        tags=["yoga", "fitness", "mat", "boldfit"],
        description="6mm thick TPE foam, anti-slip, 183 x 61 cm",
    ),
]

# ── Beauty & Personal Care ────────────────────────────────────────────────────

BEAUTY = [
    Product(
        id="BEAU-001",
        name="Mamaearth Ubtan Face Wash 100ml",
        brand="Mamaearth",
        category="Beauty",
        subcategory="Face Care",
        base_price=249,
        cost_price=110,
        mrp=399,
        reorder_point=25,
        initial_stock=145,
        price_elasticity=-0.9,
        competitor_urls=[
            "https://www.nykaa.com/mamaearth-ubtan-face-wash",
            "https://www.amazon.in/Mamaearth-Ubtan-Face-Wash",
        ],
        tags=["mamaearth", "face-wash", "ubtan", "natural"],
        description="Turmeric & saffron, toxin-free, suitable all skin types",
    ),
    Product(
        id="BEAU-002",
        name="Lakme Absolute Mousse Foundation (Ivory Fair)",
        brand="Lakme",
        category="Beauty",
        subcategory="Makeup",
        base_price=549,
        cost_price=270,
        mrp=799,
        reorder_point=15,
        initial_stock=67,
        price_elasticity=-1.0,
        competitor_urls=[
            "https://www.nykaa.com/lakme-absolute-mousse-foundation",
            "https://www.amazon.in/Lakme-Absolute-Mousse-Foundation",
        ],
        tags=["lakme", "foundation", "makeup", "beauty"],
        description="SPF 8, 24hr wear, lightweight mousse formula, 25ml",
    ),
]

# ── Full catalogue ────────────────────────────────────────────────────────────

ALL_PRODUCTS: list[Product] = (
    ELECTRONICS + FASHION + GROCERY + HOME + SPORTS + BEAUTY
)

PRODUCT_MAP: dict[str, Product] = {p.id: p for p in ALL_PRODUCTS}

CATEGORIES = list({p.category for p in ALL_PRODUCTS})

def get_product(product_id: str) -> Optional[Product]:
    return PRODUCT_MAP.get(product_id)

def get_by_category(category: str) -> list[Product]:
    return [p for p in ALL_PRODUCTS if p.category == category]
