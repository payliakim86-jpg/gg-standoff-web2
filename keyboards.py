# keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from config import RARITY_COLORS

def get_main_keyboard():
    kb = [
        [KeyboardButton(text="👤 Профіль"), KeyboardButton(text="💰 Баланс")],
        [KeyboardButton(text="📦 Кейси"), KeyboardButton(text="🎒 Інвентар")],
        [KeyboardButton(text="🏪 Маркет"), KeyboardButton(text="⚔️ Дуелі")],
        [KeyboardButton(text="🏆 Турнір"), KeyboardButton(text="🎰 Ігри")],
        [KeyboardButton(text="👥 Соціальне"), KeyboardButton(text="📋 Команди")],
        [KeyboardButton(text="💳 Поповнити баланс"), KeyboardButton(text="💸 Вивести кошти")],
        [KeyboardButton(text="🎁 Щоденний бонус")],
        [KeyboardButton(text="⚙️ Налаштування")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_admin_keyboard():
    kb = [
        [KeyboardButton(text="👤 Профіль"), KeyboardButton(text="💰 Баланс")],
        [KeyboardButton(text="📦 Кейси"), KeyboardButton(text="🎒 Інвентар")],
        [KeyboardButton(text="🏪 Маркет"), KeyboardButton(text="⚔️ Дуелі")],
        [KeyboardButton(text="🏆 Турнір"), KeyboardButton(text="🎰 Ігри")],
        [KeyboardButton(text="👥 Соціальне"), KeyboardButton(text="📋 Команди")],
        [KeyboardButton(text="💳 Поповнити баланс"), KeyboardButton(text="💸 Вивести кошти")],
        [KeyboardButton(text="🎁 Щоденний бонус")],
        [KeyboardButton(text="🛡 Адмін панель"), KeyboardButton(text="💳 Платежі"), KeyboardButton(text="📋 Пропозиції")],
        [KeyboardButton(text="🏆 Топ заносів")],
        [KeyboardButton(text="⚙️ Налаштування")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_moderator_keyboard():
    kb = [
        [KeyboardButton(text="👤 Профіль"), KeyboardButton(text="💰 Баланс")],
        [KeyboardButton(text="📦 Кейси"), KeyboardButton(text="🎒 Інвентар")],
        [KeyboardButton(text="🏪 Маркет"), KeyboardButton(text="⚔️ Дуелі")],
        [KeyboardButton(text="🏆 Турнір"), KeyboardButton(text="🎰 Ігри")],
        [KeyboardButton(text="👥 Соціальне"), KeyboardButton(text="📋 Команди")],
        [KeyboardButton(text="💳 Поповнити баланс"), KeyboardButton(text="💸 Вивести кошти")],
        [KeyboardButton(text="🎁 Щоденний бонус")],
        [KeyboardButton(text="🛡 Модератор панель")],
        [KeyboardButton(text="⚙️ Налаштування")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_settings_keyboard(notify_bonus: bool, notify_market: bool):
    bonus_emoji = "✅" if notify_bonus else "❌"
    market_emoji = "✅" if notify_market else "❌"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🎁 Щоденний бонус {bonus_emoji}", callback_data="toggle_bonus")],
        [InlineKeyboardButton(text=f"🏪 Нові лоти на маркеті {market_emoji}", callback_data="toggle_market")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    return kb

def get_cases_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Standard Case", callback_data="select_case_Standard_Case")],
        [InlineKeyboardButton(text="🔮 Rare Case", callback_data="select_case_Rare_Case")],
        [InlineKeyboardButton(text="🎁 Mystery Case", callback_data="select_case_Mystery_Case")],
        [InlineKeyboardButton(text="👑 Legendary Case", callback_data="select_case_Legendary_Case")],
        [InlineKeyboardButton(text="🧤 Glove Case", callback_data="select_case_Glove_Case")],
        [InlineKeyboardButton(text="🎨 Sticker Case", callback_data="select_case_Sticker_Case")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    return kb

def get_case_actions_keyboard(case_key: str, discount: int, free_left: int = 0):
    safe_key = case_key.replace(' ', '_')
    buttons = []
    if free_left > 0:
        buttons.append([InlineKeyboardButton(text=f"🎁 Безкоштовно ({free_left})", callback_data=f"open_free_{safe_key}_1")])
    buttons.append([InlineKeyboardButton(text="🔓 Відкрити 1", callback_data=f"open_case_{safe_key}_1")])
    buttons.append([InlineKeyboardButton(text="🔓 Відкрити 2", callback_data=f"open_case_{safe_key}_2")])
    buttons.append([InlineKeyboardButton(text="🔓 Відкрити 5", callback_data=f"open_case_{safe_key}_5")])
    buttons.append([InlineKeyboardButton(text="🔓 Відкрити 10", callback_data=f"open_case_{safe_key}_10")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад до кейсів", callback_data="back_to_cases")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_case_animation_keyboard(case_key: str):
    safe_key = case_key.replace(' ', '_')
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Відкрити ще", callback_data=f"select_case_{safe_key}")],
        [InlineKeyboardButton(text="🔙 До кейсів", callback_data="back_to_cases")]
    ])
    return kb

def get_inventory_keyboard(inventory: list, page: int):
    kb = []
    start = page * 5
    end = start + 5
    for item in inventory[start:end]:
        kb.append([InlineKeyboardButton(text=f"{item['skin_name'][:30]} (#{item['id']})", callback_data=f"view_skin_{item['id']}")])
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"inv_page_{page-1}"))
    if end < len(inventory):
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"inv_page_{page+1}"))
    if nav_buttons:
        kb.append(nav_buttons)
    kb.append([InlineKeyboardButton(text="💰 Продати все", callback_data="sell_all_inventory")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_skin_actions_keyboard(skin_id: int):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖼️ Збільшити", callback_data=f"zoom_skin_{skin_id}")],
        [InlineKeyboardButton(text="💰 Продати", callback_data=f"sell_skin_{skin_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_inventory")]
    ])
    return kb

def get_confirm_sell_all_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Так, продати все", callback_data="confirm_sell_all")],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_sell_all")]
    ])
    return kb

def get_payment_methods_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Ощадбанк", callback_data="pay_oschad")],
        [InlineKeyboardButton(text="💳 Monobank", callback_data="pay_mono")],
        [InlineKeyboardButton(text="₿ Криптовалюта", callback_data="pay_crypto")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    return kb

def get_payment_amount_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="50 грн", callback_data="amount_50"),
         InlineKeyboardButton(text="100 грн", callback_data="amount_100")],
        [InlineKeyboardButton(text="200 грн", callback_data="amount_200"),
         InlineKeyboardButton(text="500 грн", callback_data="amount_500")],
        [InlineKeyboardButton(text="1000 грн", callback_data="amount_1000"),
         InlineKeyboardButton(text="2000 грн", callback_data="amount_2000")],
        [InlineKeyboardButton(text="💸 Інша сума", callback_data="amount_custom")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_payment_methods")]
    ])
    return kb

def get_payments_list_keyboard(payments: list, page: int = 0):
    kb = []
    items_per_page = 5
    start = page * items_per_page
    end = start + items_per_page
    for p in payments[start:end]:
        kb.append([InlineKeyboardButton(
            text=f"#{p['id']} | {p['user_id']} | {p['amount_uah']} грн",
            callback_data=f"view_payment_{p['id']}"
        )])
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"payments_page_{page-1}"))
    if end < len(payments):
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"payments_page_{page+1}"))
    if nav_buttons:
        kb.append(nav_buttons)
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_payment_action_keyboard(payment_id: int):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"confirm_payment_{payment_id}"),
         InlineKeyboardButton(text="❌ Скасувати", callback_data=f"cancel_payment_{payment_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_payments")]
    ])
    return kb

def get_help_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Кейси", callback_data="help_cases"),
         InlineKeyboardButton(text="💰 Фінанси", callback_data="help_finance")],
        [InlineKeyboardButton(text="🎒 Інвентар", callback_data="help_inventory"),
         InlineKeyboardButton(text="🏪 Маркет", callback_data="help_market")],
        [InlineKeyboardButton(text="⚔️ Дуелі", callback_data="help_duels"),
         InlineKeyboardButton(text="📊 Статистика", callback_data="help_stats")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    return kb

def get_tournament_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Долучитися", callback_data="join_tournament")],
        [InlineKeyboardButton(text="📊 Таблиця", callback_data="tournament_leaderboard")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    return kb

def get_games_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Слоти", callback_data="game_slots")],
        [InlineKeyboardButton(text="🎲 Рулетка", callback_data="game_roulette")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="game_stats")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    return kb

def get_slots_bet_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="10", callback_data="slots_bet_10"),
         InlineKeyboardButton(text="50", callback_data="slots_bet_50"),
         InlineKeyboardButton(text="100", callback_data="slots_bet_100")],
        [InlineKeyboardButton(text="200", callback_data="slots_bet_200"),
         InlineKeyboardButton(text="500", callback_data="slots_bet_500"),
         InlineKeyboardButton(text="1000", callback_data="slots_bet_1000")],
        [InlineKeyboardButton(text="✏️ Інша сума", callback_data="slots_bet_custom")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_games")]
    ])
    return kb

def get_roulette_bet_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 Червоне (x2)", callback_data="roulette_red")],
        [InlineKeyboardButton(text="⚫ Чорне (x2)", callback_data="roulette_black")],
        [InlineKeyboardButton(text="🟢 Зелене (x36)", callback_data="roulette_green")],
        [InlineKeyboardButton(text="🔢 Число (x36)", callback_data="roulette_number_choose")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_games")]
    ])
    return kb

def get_roulette_number_keyboard():
    rows = []
    nums = list(range(0, 37))
    for i in range(0, 37, 5):
        row = []
        for j in range(i, min(i+5, 37)):
            row.append(InlineKeyboardButton(text=str(j), callback_data=f"roulette_number_{j}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="game_roulette")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_back_to_games_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад до ігор", callback_data="back_to_games")]
    ])
    return kb

def get_custom_bet_keyboard(game: str):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Скасувати", callback_data=f"{game}_cancel")]
    ])
    return kb

def get_play_again_keyboard(game: str, bet: int):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Зіграти ще", callback_data=f"{game}_again_{bet}"),
         InlineKeyboardButton(text="✏️ Змінити ставку", callback_data=f"{game}_change")],
        [InlineKeyboardButton(text="🔙 Вийти", callback_data="back_to_games")]
    ])
    return kb

def get_social_keyboard():
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👥 Друзі"), KeyboardButton(text="💬 Пропозиції")],
        [KeyboardButton(text="🏆 Приватні турніри")],
        [KeyboardButton(text="🔙 Назад")]
    ], resize_keyboard=True)
    return kb

def get_roulette_amount_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="50", callback_data="roulette_amount_50"),
         InlineKeyboardButton(text="100", callback_data="roulette_amount_100"),
         InlineKeyboardButton(text="200", callback_data="roulette_amount_200")],
        [InlineKeyboardButton(text="✏️ Інша сума", callback_data="roulette_amount_custom")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="roulette_cancel")]
    ])
    return kb

def get_rarity_emoji(rarity: str) -> str:
    emoji_map = {
        "Consumer Grade": "⚪",
        "Industrial Grade": "🔵",
        "Mil-Spec": "🟣",
        "Restricted": "🟡",
        "Classified": "🟠",
        "Covert": "🔴",
        "Rare Special": "💎"
    }
    return emoji_map.get(rarity, "⚪")