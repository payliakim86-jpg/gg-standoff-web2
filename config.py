# config.py

# Кейси та їх параметри
CASES = {
    "Standard Case": {
        "name": "📦 Standard Case",
        "price": 800,
        "emoji": "📦",
        "description": "Звичайний кейс з базовими скінами"
    },
    "Rare Case": {
        "name": "🔮 Rare Case",
        "price": 2400,
        "emoji": "🔮",
        "description": "Рідкісний кейс зі збільшеним шансом на рідкісні скіни"
    },
    "Mystery Case": {
        "name": "🎁 Mystery Case",
        "price": 4000,
        "emoji": "🎁",
        "description": "Загадковий кейс з унікальними скінами"
    },
    "Legendary Case": {
        "name": "👑 Legendary Case",
        "price": 8000,
        "emoji": "👑",
        "description": "Елітний кейс з найвищими шансами на легендарні скіни"
    },
    "Glove Case": {
        "name": "🧤 Glove Case",
        "price": 6400,
        "emoji": "🧤",
        "description": "Кейс з рідкісними рукавицями (перчатками)"
    },
    "Sticker Case": {
        "name": "🎨 Sticker Case",
        "price": 4800,
        "emoji": "🎨",
        "description": "Кейс зі скінами, прикрашеними наліпками"
    }
}

# Скіни за рідкістю
SKINS = {
    "Consumer Grade": [
        "Glock-18 | Boreal Forest",
        "USP-S | Forest Leaves",
        "MAG-7 | Silver",
        "Negev | Desert-Strike",
        "P250 | Sticker Paper",
        "MP7 | Graffiti",
        "SSG 08 | Spray Paint",
        "FAMAS | Tagged"
    ],
    "Industrial Grade": [
        "M4A4 | Faded Zebra",
        "AWP | Worm God",
        "AK-47 | Safari Mesh",
        "Desert Eagle | Mudder",
        "UMP-45 | Sticker Bomb",
        "Galil AR | Vandal",
        "MAC-10 | Capsule",
        "SG 553 | Hologram"
    ],
    "Mil-Spec": [
        "AK-47 | Elite Build",
        "M4A1-S | Flashback",
        "AWP | Phobos",
        "Desert Eagle | Naga",
        "★ Hand Wraps | Leather",
        "★ Driver Gloves | Racing Green",
        "★ Moto Gloves | Smoke Out",
        "★ Specialist Gloves | Forest"
    ],
    "Restricted": [
        "AK-47 | Frontside Misty",
        "M4A4 | Dragon King",
        "AWP | Fever Dream",
        "Desert Eagle | Directive",
        "★ Hand Wraps | Spruce DDPAT",
        "★ Driver Gloves | King Snake",
        "★ Moto Gloves | Cool Mint",
        "★ Specialist Gloves | Crimson Web"
    ],
    "Classified": [
        "AK-47 | Neon Rider",
        "M4A1-S | Mecha Industries",
        "AWP | Oni Taiji",
        "Desert Eagle | Code Red",
        "★ Hand Wraps | Cobalt Skulls",
        "★ Driver Gloves | Imperial Plaid",
        "★ Moto Gloves | Polygon",
        "★ Specialist Gloves | Emerald Web"
    ],
    "Covert": [
        "AK-47 | Fire Serpent",
        "M4A4 | Howl",
        "AWP | Dragon Lore",
        "Desert Eagle | Blaze",
        "★ Hand Wraps | Slaughter",
        "★ Driver Gloves | Crimson Kimono",
        "★ Moto Gloves | Boom!",
        "★ Specialist Gloves | Fade"
    ],
    "Rare Special": [
        "★ Karambit | Doppler",
        "★ M9 Bayonet | Fade",
        "★ Butterfly Knife | Crimson Web",
        "★ Bayonet | Slaughter",
        "★ Hand Wraps | Gold Weave",
        "★ Driver Gloves | Diamondback",
        "★ Moto Gloves | Eclipse",
        "★ Specialist Gloves | Tiger Strike"
    ]
}

# Базові шанси випадіння рідкостей
RARITY_CHANCES = {
    "Consumer Grade": 40,
    "Industrial Grade": 30,
    "Mil-Spec": 15,
    "Restricted": 8,
    "Classified": 4,
    "Covert": 2,
    "Rare Special": 1
}

# Кольори для рідкостей (HTML)
RARITY_COLORS = {
    "Consumer Grade": "#b0c3d9",
    "Industrial Grade": "#5e98d9",
    "Mil-Spec": "#4b69ff",
    "Restricted": "#8847ff",
    "Classified": "#d32ce6",
    "Covert": "#eb4b4b",
    "Rare Special": "#ffd700"
}

# Модифікатори шансів для конкретних кейсів
CASE_RARITY_MODIFIERS = {
    "Rare Case": {
        "Classified": 1.5,
        "Covert": 2,
        "Rare Special": 1.5
    },
    "Mystery Case": {
        "Covert": 3,
        "Rare Special": 2
    },
    "Legendary Case": {
        "Covert": 2.5,
        "Rare Special": 3
    },
    "Glove Case": {
        "Mil-Spec": 1.2,
        "Restricted": 1.5,
        "Classified": 2,
        "Covert": 2.5,
        "Rare Special": 3
    },
    "Sticker Case": {
        "Consumer Grade": 0.8,
        "Industrial Grade": 1.2,
        "Mil-Spec": 1.5,
        "Restricted": 2,
        "Classified": 2.5
    }
}

# Ціни продажу скінів (% від вартості кейсу)
SELL_PRICES = {
    "Consumer Grade": 0.33,
    "Industrial Grade": 0.44,
    "Mil-Spec": 0.55,
    "Restricted": 0.66,
    "Classified": 0.77,
    "Covert": 0.88,
    "Rare Special": 0.99
}

# ID адміністраторів (числа) – замініть на реальні
ADMINS = [123456789, 987654321, 5254893784]

# Платіжні реквізити (Ощадбанк)
PAYMENT_DETAILS = {
    "oschad": "💳 **Ощадбанк**\n\n🏦 Банк: Ощадбанк\n💳 Карта: 5168 7521 2596 0602\n👤 Отримувач: Отримувач\n\nПісля оплати надішліть скріншот у цей чат.",
    "mono": "💳 **Monobank**\n\n🏦 Банк: Monobank\n💳 Карта: 4441 1110 0773 5594\n👤 Отримувач: Паулі А\n\nПісля оплати надішліть скріншот у цей чат.",
    "crypto": "₿ **Криптовалюта**\n\nРеквізити: BTC: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
}

# КУРС ОБМІНУ: 1 грн = X монет
EXCHANGE_RATE = 10

# Мінімальна сума виведення в гривнях
MIN_WITHDRAWAL_UAH = 250

# Налаштування заносів (великих виграшів)
BIG_WIN_THRESHOLD = 1000
BIG_WIN_MULTIPLIER = 10
CHANNEL_ID = None

# Стартовий баланс
START_BALANCE = 1000