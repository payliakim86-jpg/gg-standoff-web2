# main.py – повністю функціональний
import html
import random
import logging
import os
import asyncio
import re
import glob
from datetime import datetime, timedelta, timezone

from aiogram.types import MenuButtonDefault
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import (
    CASES, SKINS, RARITY_CHANCES, RARITY_COLORS,
    CASE_RARITY_MODIFIERS, SELL_PRICES, ADMINS,
    PAYMENT_DETAILS, EXCHANGE_RATE, MIN_WITHDRAWAL_UAH,
    BIG_WIN_THRESHOLD, BIG_WIN_MULTIPLIER, CHANNEL_ID
)
from database import db
from keyboards import (
    get_main_keyboard, get_cases_keyboard, get_inventory_keyboard,
    get_skin_actions_keyboard, get_rarity_emoji, get_admin_keyboard,
    get_moderator_keyboard, get_help_keyboard,
    get_payment_methods_keyboard, get_payment_amount_keyboard,
    get_payments_list_keyboard, get_payment_action_keyboard,
    get_tournament_keyboard, get_case_actions_keyboard,
    get_confirm_sell_all_keyboard, get_case_animation_keyboard,
    get_games_keyboard, get_slots_bet_keyboard, get_roulette_bet_keyboard,
    get_roulette_number_keyboard, get_back_to_games_keyboard,
    get_custom_bet_keyboard, get_play_again_keyboard,
    get_social_keyboard, get_roulette_amount_keyboard,
    get_settings_keyboard
)

print("=" * 50)
print("🔍 ЗАВАНТАЖЕННЯ БОТА")
print("=" * 50)
print(f"ADMINS: {ADMINS}")
print(f"Курс: 1 грн = {EXCHANGE_RATE} монет")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8160628339:AAGEzJuJtRRKI2zmYipnLoRj39SwBT8Pgmk")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()

# ==================== СТАНИ ДЛЯ FSM ====================
class SlotsState(StatesGroup):
    waiting_for_bet = State()

class RouletteState(StatesGroup):
    waiting_for_bet = State()
    bet_type = State()
    bet_value = State()
    multiplier = State()

class PaymentStates(StatesGroup):
    waiting_for_screenshot = State()
    payment_method = State()
    waiting_for_custom_amount = State()

class WithdrawalStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_bank = State()
    waiting_for_card = State()

# ============= ФУНКЦІЇ ПЕРЕВІРКИ ПРАВ =============
def is_admin(user_id: int) -> bool:
    user_id = int(user_id)
    admin_list = [int(admin_id) for admin_id in ADMINS]
    return user_id in admin_list

def has_moderator_power(user_id: int) -> bool:
    return is_admin(user_id) or db.is_moderator(user_id)

# ============= ОСНОВНІ ФУНКЦІЇ =============
def calculate_rarity(case_name: str) -> str:
    base_chances = RARITY_CHANCES.copy()
    modifiers = CASE_RARITY_MODIFIERS.get(case_name, {})
    for rarity in base_chances:
        if rarity in modifiers:
            base_chances[rarity] *= modifiers[rarity]
    total = sum(base_chances.values())
    normalized = {k: v / total * 100 for k, v in base_chances.items()}
    roll = random.uniform(0, 100)
    cumulative = 0
    for rarity, chance in normalized.items():
        cumulative += chance
        if roll <= cumulative:
            return rarity
    return "Consumer Grade"

def find_skin_image(skin_name: str) -> str | None:
    base_dir = "skin_images"
    if not os.path.exists(base_dir):
        logger.error(f"Папка {base_dir} не існує!")
        return None
    variants = []
    variants.append(re.sub(r'\s*\|\s*', '___', skin_name).replace(' ', '_') + '.png')
    variants.append(skin_name.replace('|', '___').replace(' ', '_') + '.png')
    variants.append(skin_name.replace(' ', '_').replace('|', '_') + '.png')
    variants.append(skin_name.replace('|', '').replace(' ', '_') + '.png')
    variants.append(skin_name + '.png')
    variants.append(skin_name.replace(' ', '_') + '.png')
    lower_variants = [v.lower() for v in variants.copy()]
    variants.extend(lower_variants)
    variants = list(set(variants))
    for variant in variants:
        full_path = os.path.join(base_dir, variant)
        if os.path.exists(full_path):
            return full_path
    first_word = re.split(r'[ |_-]+', skin_name)[0]
    pattern = os.path.join(base_dir, f"*{first_word}*")
    matches = glob.glob(pattern)
    if matches:
        return matches[0]
    logger.warning(f"Зображення для {skin_name} не знайдено")
    return None

# ============= ФУНКЦІЇ ДЛЯ ФОНОВИХ ЗАВДАНЬ =============
async def check_bonus_reminders():
    users = db.get_users_for_reminder()
    for user_id in users:
        try:
            await bot.send_message(
                user_id,
                "🎁 **Нагадування!**\nВи ще не отримали сьогоднішній щоденний бонус. Зайдіть у меню та натисніть кнопку «🎁 Щоденний бонус».",
                parse_mode="Markdown"
            )
        except TelegramForbiddenError:
            pass
        except Exception as e:
            logger.error(f"Помилка при надсиланні нагадування {user_id}: {e}")

async def notify_market_listing(skin_name: str, price: int, seller_username: str = None, seller_id: int = None):
    all_users = db.get_all_users()
    if seller_id:
        recipient_ids = [u['user_id'] for u in all_users if u['user_id'] != seller_id]
    else:
        recipient_ids = [u['user_id'] for u in all_users]
    text = f"🏪 **Новий лот на маркеті!**\n\nСкін: {skin_name}\n💰 Ціна: {price} монет"
    if seller_username:
        text += f"\n👤 Продавець: @{seller_username}"
    text += "\n\nСкоріше заходьте в маркет, поки не купили!"
    for user_id in recipient_ids:
        try:
            await bot.send_message(user_id, text, parse_mode="Markdown")
        except TelegramForbiddenError:
            pass
        except Exception as e:
            logger.error(f"Помилка сповіщення маркету {user_id}: {e}")
        await asyncio.sleep(0.05)

# ============= ОБРОБНИК ДЛЯ ВСІХ ГОЛОВНИХ КНОПОК (скидає стан) =============
@dp.message(F.text.in_([
    "👤 Профіль", "💰 Баланс", "📦 Кейси", "🎒 Інвентар", "🏪 Маркет", "⚔️ Дуелі",
    "🏆 Турнір", "🎰 Ігри", "👥 Соціальне", "📋 Команди", "💳 Поповнити баланс",
    "💸 Вивести кошти", "🎁 Щоденний бонус", "⚙️ Налаштування",
    "🛡 Адмін панель", "💳 Платежі", "📋 Пропозиції", "🏆 Топ заносів"
]))
async def handle_main_menu_buttons(message: Message, state: FSMContext):
    await state.clear()
    text = message.text
    if text == "👤 Профіль":
        await show_profile(message)
    elif text == "💰 Баланс":
        await show_balance(message)
    elif text == "📦 Кейси":
        await show_cases(message)
    elif text == "🎒 Інвентар":
        await show_inventory(message)
    elif text == "🏪 Маркет":
        await cmd_market(message)
    elif text == "⚔️ Дуелі":
        await show_active_duels(message)
    elif text == "🏆 Турнір":
        await cmd_tournament(message)
    elif text == "🎰 Ігри":
        await games_menu(message)
    elif text == "👥 Соціальне":
        await social_menu(message)
    elif text == "📋 Команди":
        await show_commands_panel(message)
    elif text == "💳 Поповнити баланс":
        await cmd_pay_start(message)
    elif text == "💸 Вивести кошти":
        await cmd_withdraw_start(message, state)
    elif text == "🎁 Щоденний бонус":
        await daily_bonus_handler(message)
    elif text == "⚙️ Налаштування":
        await settings_menu(message)
    elif text == "🛡 Адмін панель":
        await show_admin_panel(message)
    elif text == "💳 Платежі":
        await cmd_payments(message)
    elif text == "📋 Пропозиції":
        await show_all_suggestions(message)
    elif text == "🏆 Топ заносів":
        await cmd_top_wins(message)

# ============= ТЕСТОВІ КОМАНДИ =============
@dp.message(Command("testadmin"))
async def test_admin(message: Message):
    user_id = message.from_user.id
    text = (
        f"🔍 **ТЕСТУВАННЯ ПРАВ**\n\n"
        f"Ваш ID: `{user_id}`\n"
        f"Username: @{message.from_user.username}\n"
        f"ADMINS: {ADMINS}\n"
        f"is_admin: {is_admin(user_id)}\n"
        f"is_moderator: {db.is_moderator(user_id)}"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("debug"))
async def debug_command(message: Message):
    user_id = message.from_user.id
    text = (
        f"🔍 **DEBUG**\n\n"
        f"ID: `{user_id}`\n"
        f"is_admin: {is_admin(user_id)}\n"
        f"is_moderator: {db.is_moderator(user_id)}"
    )
    await message.answer(text, parse_mode="Markdown")

# ============= КОМАНДА START =============
@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    logger.info(f"Користувач {user_id} (@{username}) запустив бота")
    user = db.get_or_create_user(user_id, username)
    welcome_text = (
        "👋 **Вітаємо у GGStandoff!**\n\n"
        "Це найкращий симулятор відкриття кейсів та трейдингу. "
        "Вибивай рідкісні скіни, бери участь у турнірах та змагайся з іншими гравцями у дуелях!\n\n"
        "👇 Обирай дію в меню нижче:\n\n"
        f"🤖 **Версія бота:** v2.0 (з підтримкою сповіщень)\n"
        f"💰 **Ваш баланс:** {user['balance']} монет"
    )
    if is_admin(user_id):
        reply_markup = get_admin_keyboard()
    elif db.is_moderator(user_id):
        reply_markup = get_moderator_keyboard()
    else:
        reply_markup = get_main_keyboard()
    await message.answer(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

# ============= ПАНЕЛЬ КОМАНД =============
@dp.message(F.text == "📋 Команди")
@dp.message(Command("help"))
@dp.message(Command("commands"))
async def show_commands_panel(message: Message):
    commands_text = (
        "📋 **ДОСТУПНІ КОМАНДИ**\n\n"
        "🔹 **Основні:**\n"
        "• `/start` - Запустити бота\n"
        "• `/profile` - Профіль\n"
        "• `/balance` - Баланс\n"
        "• `/daily` - Щоденний бонус\n"
        "• `/myid` - Ваш ID\n\n"
        "🔹 **Кейси та скіни:**\n"
        "• `/cases` - Кейси\n"
        "• `/inventory` - Інвентар\n"
        "• `/top` - Таблиця лідерів\n\n"
        "🔹 **Маркет та обмін:**\n"
        "• `/market` - Маркет\n"
        "• `/sell_market [ID] [ціна]` - Продати скін\n"
        "• `/my_listings` - Мої лоти\n"
        "• `/trade [ID_гравця] [ID_скіна]` - Передати скін\n\n"
        "🔹 **Дуелі:**\n"
        "• `/duel [сума]` - Створити дуель\n"
        "• `/duels` - Активні дуелі\n\n"
        "🔹 **Турнір:**\n"
        "• `/tournament` - Інформація про турнір\n\n"
        "🔹 **Промокоди:**\n"
        "• `/promo [код]` - Активувати промокод\n\n"
        f"💳 **Поповнення:**\n"
        f"• Кнопка «💳 Поповнити баланс» (курс: 1 грн = {EXCHANGE_RATE} монет)\n\n"
        f"💸 **Виведення:**\n"
        f"• Кнопка «💸 Вивести кошти» або /withdraw (мін. {MIN_WITHDRAWAL_UAH * EXCHANGE_RATE} монет)\n\n"
        "🔹 **Ігри:**\n"
        "• Кнопка «🎰 Ігри» - Слоти, рулетка\n\n"
        "🔹 **Соціальне:**\n"
        "• Кнопка «👥 Соціальне» - друзі, пропозиції, приватні турніри\n\n"
        "🔹 **ID скінів:**\n"
        "Кожен скін має унікальний ID (наприклад, `#42`)\n"
        "Використовуйте ID для продажу: `/sell_market 42 500`\n\n"
        "💡 **Натисніть на кнопки в меню для швидкого доступу!**"
    )
    await message.answer(commands_text, parse_mode="Markdown")

@dp.message(Command("myid"))
async def show_my_id(message: Message):
    await message.answer(
        f"🆔 **Ваш ID:** `{message.from_user.id}`\n\n"
        f"👤 **Username:** @{message.from_user.username or 'немає'}\n\n"
        f"💡 Використовуйте цей ID для:\n"
        f"• Передачі скінів іншим гравцям\n"
        f"• Отримання скінів від інших\n"
        f"• Звернення до адміністрації",
        parse_mode="Markdown"
    )

# ============= ПРОФІЛЬ =============
@dp.message(Command("profile"))
@dp.message(F.text == "👤 Профіль")
async def show_profile(message: Message):
    user_id = message.from_user.id
    stats = db.get_profile_stats(user_id)
    payments = db.get_user_payments(user_id, 5)

    if is_admin(user_id):
        role = "👑 Адміністратор"
    elif db.is_moderator(user_id):
        role = "🛡 Модератор"
    else:
        role = "👤 Користувач"

    most_expensive = "немає"
    if stats['most_expensive_skin']:
        skin = stats['most_expensive_skin']
        most_expensive = f"{skin['skin_name']} ({skin['rarity']}) - {skin['case_price']} монет"

    payments_text = ""
    if payments:
        payments_text = "\n📅 **Останні поповнення:**\n"
        for p in payments:
            status_emoji = "✅" if p['status'] == 'completed' else "⏳" if p['status'] == 'pending' else "❌"
            payments_text += f"{status_emoji} {p['amount_uah']} грн → {p['amount_coins']} монет ({p['status']})\n"
    else:
        payments_text = "\n📅 Немає поповнень"

    text = (
        f"👤 **ПРОФІЛЬ КОРИСТУВАЧА**\n\n"
        f"🆔 ID: `{stats['user_id']}`\n"
        f"👤 Username: @{stats['username'] or 'немає'}\n"
        f"🛡 Роль: {role}\n\n"
        f"📊 **Прогрес:**\n"
        f"• Рівень: {stats['level']} ⭐\n"
        f"• XP: {stats['xp']}/100\n"
        f"• Знижка: {stats['discount']}%\n"
        f"• До наступного: {stats['xp_to_next']} XP\n\n"
        f"💰 **Фінанси:**\n"
        f"• Баланс: {stats['balance']} монет\n"
        f"• Відкрито кейсів: {stats['cases_opened']}\n\n"
        f"💎 **Найдорожчий скін:**\n"
        f"{most_expensive}\n"
        f"{payments_text}"
    )
    await message.answer(text, parse_mode="Markdown")

# ============= БАЛАНС =============
@dp.message(Command("balance"))
@dp.message(F.text == "💰 Баланс")
async def show_balance(message: Message):
    balance = db.get_user_balance(message.from_user.id)
    if is_admin(message.from_user.id):
        markup = get_admin_keyboard()
    elif db.is_moderator(message.from_user.id):
        markup = get_moderator_keyboard()
    else:
        markup = get_main_keyboard()
    await message.answer(f"💰 **Ваш баланс:** {balance} монет", reply_markup=markup, parse_mode="Markdown")

# ============= ЩОДЕННИЙ БОНУС =============
@dp.message(F.text == "🎁 Щоденний бонус")
@dp.message(Command("daily"))
async def daily_bonus_handler(message: Message):
    user_id = message.from_user.id
    db.get_or_create_user(user_id, message.from_user.username)
    last = db.get_last_daily_bonus(user_id)
    now = datetime.now(timezone.utc)
    if last:
        try:
            last_time = datetime.fromisoformat(last)
            if now - last_time < timedelta(hours=24):
                remaining = timedelta(hours=24) - (now - last_time)
                hours = remaining.seconds // 3600
                minutes = (remaining.seconds % 3600) // 60
                await message.answer(f"⏳ Ви вже отримували бонус. Спробуйте через {hours} год {minutes} хв.")
                return
        except:
            pass
    amount = random.randint(10, 100)
    db.update_balance(user_id, amount)
    db.update_last_daily_bonus(user_id, now.isoformat())
    balance = db.get_user_balance(user_id)
    await message.answer(f"🎁 **Щоденний бонус:** +{amount} монет!\n💰 **Новий баланс:** {balance} монет.")

# ============= КЕЙСИ =============
@dp.message(F.text == "📦 Кейси")
@dp.message(Command("cases"))
async def show_cases(message: Message):
    user_id = message.from_user.id
    level_info = db.get_user_level_info(user_id)
    discount = level_info['discount']
    text = f"📦 **КЕЙСИ** (ваша знижка: {discount}%)\n\n"
    for key, case in CASES.items():
        orig = case['price']
        disc = int(orig * (100 - discount) / 100)
        text += f"{case['name']}\n💵 Ціна: ~~{orig}~~ **{disc}** монет\n📝 {case['description']}\n\n"
    await message.answer(text, reply_markup=get_cases_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("select_case_"))
async def handle_select_case(callback: CallbackQuery):
    await callback.answer()
    case_key = callback.data.replace("select_case_", "").replace('_', ' ')
    if case_key not in CASES:
        await callback.message.answer("❌ Кейс не знайдено")
        return
    user_id = callback.from_user.id
    level_info = db.get_user_level_info(user_id)
    discount = level_info['discount']
    case = CASES[case_key]
    free_left = db.get_free_cases_left(user_id, case_key)

    base_chances = RARITY_CHANCES.copy()
    modifiers = CASE_RARITY_MODIFIERS.get(case_key, {})
    for rarity, mod in modifiers.items():
        if rarity in base_chances:
            base_chances[rarity] *= mod
    total = sum(base_chances.values())
    chances_lines = []
    for rarity, chance in sorted(base_chances.items(), key=lambda x: x[1], reverse=True):
        percent = chance / total * 100
        if percent >= 0.1:
            emoji = get_rarity_emoji(rarity)
            chances_lines.append(f"{emoji} {rarity}: {percent:.2f}%")
    chances_text = "\n".join(chances_lines)

    text = f"📦 **{case['name']}**\n\n"
    text += f"💵 Ціна: ~~{case['price']}~~ **{int(case['price'] * (100 - discount) / 100)}** монет\n"
    text += f"📝 {case['description']}\n\n"
    text += f"📊 **Шанси випадіння:**\n{chances_text}\n\n"
    text += "Оберіть кількість відкриттів:"

    await callback.message.answer(
        text,
        reply_markup=get_case_actions_keyboard(case_key, discount, free_left),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("open_case_"))
async def handle_open_case_multiple(callback: CallbackQuery):
    data = callback.data
    parts = data.split("_")
    use_free = False
    if parts[1] == "free":
        use_free = True
        case_key_parts = parts[2:-1]
        count_str = parts[-1]
    else:
        case_key_parts = parts[2:-1]
        count_str = parts[-1]
    case_key = '_'.join(case_key_parts).replace('_', ' ')
    try:
        count = int(count_str)
    except ValueError:
        await callback.answer("❌ Невірна кількість", show_alert=True)
        return
    if count not in [1, 2, 5, 10]:
        await callback.answer("❌ Можна відкрити 1, 2, 5 або 10 кейсів", show_alert=True)
        return
    if case_key not in CASES:
        await callback.answer("❌ Кейс не знайдено", show_alert=True)
        return
    await callback.answer()

    case = CASES[case_key]
    user_id = callback.from_user.id
    level_info = db.get_user_level_info(user_id)
    discount = level_info['discount']

    anim_msg = await callback.message.answer(
        f"{case['emoji']} **Відкриваємо {count} {case['name']}...**\n\n🔮 Трохи магії...",
        parse_mode="Markdown"
    )
    await asyncio.sleep(1.5)

    result = db.open_multiple_cases(user_id, case_key, case, count, discount, use_free)

    if not result["success"]:
        await anim_msg.edit_text(result["message"])
        return

    results_text = f"🎉 **Результати відкриття {count} {case['name']}** 🎉\n\n"
    total_sell = 0
    for i, item in enumerate(result["results"], 1):
        results_text += f"{i}. {item['emoji']} **{item['skin_name']}** ({item['rarity']})\n"
        results_text += f"   💰 Ціна продажу: {item['sell_price']} монет | 🆔 `{item['skin_id']}`\n\n"
        total_sell += item['sell_price']
        if item['rarity'] in ['Covert', 'Rare Special']:
            db.log_rare_drop(user_id, item['skin_name'], item['rarity'], case['name'])

    results_text += f"💎 **Отримано XP:** {result['total_xp']}\n"
    if result['leveled_up']:
        results_text += f"⭐ **Новий рівень:** {result['new_level']}! Знижка тепер {result['new_discount']}%\n"
    results_text += f"\n💰 **Поточний баланс:** {db.get_user_balance(user_id)} монет"
    results_text += f"\n💼 **Загальна ціна продажу:** {total_sell} монет"

    await anim_msg.delete()

    db.update_daily_stats(user_id, 'cases', count)
    db.update_daily_stats(user_id, 'games', count)

    first_skin = result["results"][0]
    img_path = find_skin_image(first_skin['skin_name'])

    if img_path:
        try:
            photo = FSInputFile(img_path)
            await callback.message.answer_photo(
                photo,
                caption=results_text,
                reply_markup=get_case_animation_keyboard(case_key),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Помилка фото: {e}")
            await callback.message.answer(
                results_text,
                reply_markup=get_case_animation_keyboard(case_key),
                parse_mode="Markdown"
            )
    else:
        await callback.message.answer(
            results_text,
            reply_markup=get_case_animation_keyboard(case_key),
            parse_mode="Markdown"
        )

@dp.callback_query(F.data == "back_to_cases")
async def back_to_cases(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    level_info = db.get_user_level_info(user_id)
    discount = level_info['discount']
    text = f"📦 **КЕЙСИ** (ваша знижка: {discount}%)\n\n"
    for key, case in CASES.items():
        orig = case['price']
        disc = int(orig * (100 - discount) / 100)
        text += f"{case['name']}\n💵 Ціна: ~~{orig}~~ **{disc}** монет\n📝 {case['description']}\n\n"
    await callback.message.answer(text, reply_markup=get_cases_keyboard(), parse_mode="Markdown")

# ============= ІНВЕНТАР =============
@dp.message(F.text == "🎒 Інвентар")
@dp.message(Command("inventory"))
async def show_inventory(message: Message):
    inv = db.get_user_inventory(message.from_user.id)
    if not inv:
        await message.answer("🎒 Ваш інвентар порожній. Відкрийте кейси, щоб отримати скіни!")
        return
    text = f"🎒 **ІНВЕНТАР** (всього: {len(inv)} скінів)\n\n**Останні 5:**\n"
    for item in inv[:5]:
        e = get_rarity_emoji(item['rarity'])
        text += f"• `#{item['id']}` {e} {item['skin_name']} ({item['rarity']})\n"
    text += f"\n🔍 Натисніть на скін для детальної інформації."
    await message.answer(text, reply_markup=get_inventory_keyboard(inv, 0), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("inv_page_"))
async def handle_inventory_page(callback: CallbackQuery):
    page = int(callback.data.replace("inv_page_", ""))
    inv = db.get_user_inventory(callback.from_user.id)
    if not inv:
        await callback.answer("Інвентар порожній", show_alert=True)
        return
    await callback.answer()
    start = page * 5
    text = f"🎒 **ІНВЕНТАР** (стор. {page + 1})\n\n"
    for item in inv[start:start+5]:
        e = get_rarity_emoji(item['rarity'])
        text += f"• `#{item['id']}` {e} {item['skin_name']} ({item['rarity']})\n"
    await callback.message.edit_text(text, reply_markup=get_inventory_keyboard(inv, page), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("view_skin_"))
async def handle_view_skin(callback: CallbackQuery):
    skin_id = int(callback.data.replace("view_skin_", ""))
    user_id = callback.from_user.id
    skin = db.get_skin_by_id(skin_id, user_id)
    if not skin:
        await callback.answer("❌ Скін не знайдено", show_alert=True)
        return
    await callback.answer()

    emoji = get_rarity_emoji(skin['rarity'])
    sell_price = int(skin['case_price'] * SELL_PRICES.get(skin['rarity'], 0.3))
    text = (
        f"🎨 **{skin['skin_name']}**\n\n"
        f"🆔 **ID скіна:** `{skin['id']}`\n"
        f"{emoji} **Рідкість:** {skin['rarity']}\n"
        f"📦 **З кейсу:** {skin['case_name']}\n"
        f"💰 **Ціна продажу:** {sell_price} монет\n"
        f"📅 **Отримано:** {skin['obtained_at'][:16]}\n\n"
        f"💡 **Для продажу використовуйте:**\n"
        f"`/sell_market {skin['id']} [ціна]`"
    )

    img_path = find_skin_image(skin['skin_name'])
    if img_path:
        try:
            photo = FSInputFile(img_path)
            await callback.message.answer_photo(
                photo,
                caption=text,
                reply_markup=get_skin_actions_keyboard(skin_id),
                parse_mode="Markdown"
            )
            await callback.message.delete()
        except Exception as e:
            logger.error(f"Помилка фото: {e}")
            await callback.message.edit_text(
                text,
                reply_markup=get_skin_actions_keyboard(skin_id),
                parse_mode="Markdown"
            )
    else:
        await callback.message.edit_text(
            text,
            reply_markup=get_skin_actions_keyboard(skin_id),
            parse_mode="Markdown"
        )

@dp.callback_query(F.data.startswith("zoom_skin_"))
async def handle_zoom_skin(callback: CallbackQuery):
    skin_id = int(callback.data.replace("zoom_skin_", ""))
    user_id = callback.from_user.id
    skin = db.get_skin_by_id(skin_id, user_id)
    if not skin:
        await callback.answer("❌ Скін не знайдено", show_alert=True)
        return
    await callback.answer()
    img_path = find_skin_image(skin['skin_name'])
    if img_path:
        photo = FSInputFile(img_path)
        await callback.message.answer_photo(photo, caption=f"🖼️ **{skin['skin_name']}**")
    else:
        await callback.answer("❌ Фото не знайдено", show_alert=True)

@dp.callback_query(F.data.startswith("sell_immediate_"))
async def handle_sell_immediate(callback: CallbackQuery):
    skin_id = int(callback.data.replace("sell_immediate_", ""))
    user_id = callback.from_user.id
    skin = db.get_skin_by_id(skin_id, user_id)
    if not skin:
        await callback.answer("❌ Скін не знайдено", show_alert=True)
        return
    sell_price = int(skin['case_price'] * SELL_PRICES.get(skin['rarity'], 0.3))
    db.update_balance(user_id, sell_price)
    db.remove_skin_from_inventory(skin_id, user_id)
    db.log_sale(user_id, skin['skin_name'], skin['rarity'], sell_price, skin['case_price'])
    emoji = get_rarity_emoji(skin['rarity'])
    new_text = f"✅ **Скін продано!**\n\n{emoji} {skin['skin_name']}\n💰 +{sell_price} монет\n💰 Баланс: {db.get_user_balance(user_id)}"
    await callback.answer(f"💰 +{sell_price}")
    try:
        await callback.message.edit_caption(caption=new_text, reply_markup=None, parse_mode="Markdown")
    except:
        try:
            await callback.message.edit_text(new_text, reply_markup=None, parse_mode="Markdown")
        except:
            await callback.message.answer(new_text, parse_mode="Markdown")

@dp.callback_query(F.data == "close_drop")
async def handle_close_drop(callback: CallbackQuery):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except:
        pass
    await callback.answer("✅ Скін збережено")

@dp.callback_query(F.data == "contract_common_rare")
async def handle_contract_common_to_rare(callback: CallbackQuery):
    user_id = callback.from_user.id
    common_count = db.count_skins_by_rarity(user_id, "Consumer Grade")
    if common_count < 10:
        await callback.answer(f"❌ Потрібно 10 Consumer Grade, у вас: {common_count}", show_alert=True)
        return
    await callback.answer()
    removed = db.remove_n_skins_by_rarity(user_id, "Consumer Grade", 10)
    if removed < 10:
        await callback.answer("⚠ Помилка", show_alert=True)
        return
    rare_skins = SKINS.get("Mil-Spec", [])
    skin_name = random.choice(rare_skins)
    skin_id = db.add_skin_to_inventory(user_id, skin_name, "Mil-Spec", "Contract", 0, None)
    await callback.message.answer(
        f"🧾 **Контракт виконано!**\n\n10 Consumer Grade скінів обміняно на:\n🎨 **{skin_name}** (Mil-Spec)\n🆔 ID: `{skin_id}`",
        parse_mode="Markdown"
    )

# ============= ПРОДАЖ ВСЬОГО ІНВЕНТАРЯ =============
@dp.callback_query(F.data == "sell_all_inventory")
async def handle_sell_all_inventory(callback: CallbackQuery):
    inv = db.get_user_inventory(callback.from_user.id)
    if not inv:
        await callback.answer("🎒 Інвентар порожній", show_alert=True)
        return
    await callback.answer()
    total = 0
    for item in inv:
        total += int(item['case_price'] * SELL_PRICES.get(item['rarity'], 0.3))
    text = (
        f"⚠️ **Підтвердження продажу**\n\n"
        f"Ви збираєтеся продати **{len(inv)} скінів**.\n"
        f"💰 **Загальна сума:** {total} монет.\n\n"
        f"Цю дію неможливо скасувати. Продовжити?"
    )
    await callback.message.edit_text(text, reply_markup=get_confirm_sell_all_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data == "confirm_sell_all")
async def handle_confirm_sell_all(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    result = db.sell_all_inventory(user_id)
    if result["success"]:
        await callback.message.edit_text(
            f"✅ **Продаж завершено!**\n\n"
            f"Продано скінів: {result['count']}\n"
            f"💰 Отримано монет: {result['total']}\n\n"
            f"💰 Новий баланс: {db.get_user_balance(user_id)}",
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text(f"❌ {result['message']}", parse_mode="Markdown")

@dp.callback_query(F.data == "cancel_sell_all")
async def handle_cancel_sell_all(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("❌ Продаж скасовано.")

# ============= ТУРНІР =============
@dp.message(F.text == "🏆 Турнір")
@dp.message(Command("tournament"))
async def cmd_tournament(message: Message):
    active = db.get_active_tournament()
    pending = db.get_pending_tournament()
    if active:
        end_time = datetime.fromisoformat(active['end_time']).strftime("%Y-%m-%d %H:%M")
        leaderboard = db.get_tournament_leaderboard(active['id'], 5)
        text = f"🏆 **Активний турнір**\n\n📅 Завершиться: {end_time}\n💰 Призовий фонд: {active['prize_pool']} монет\n\n**Топ-5:**\n"
        for i, p in enumerate(leaderboard, 1):
            text += f"{i}. @{p['username']} — {p['points']} очок\n"
        user_id = message.from_user.id
        db.cursor.execute("SELECT 1 FROM tournament_participants WHERE tournament_id = ? AND user_id = ?", (active['id'], user_id))
        if db.cursor.fetchone():
            text += "\n✅ Ви берете участь! Заробляйте очки: відкривайте кейси (1 очко), вигравайте дуелі (5), продавайте на маркеті (2)."
            await message.answer(text, parse_mode="Markdown")
        else:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Долучитися", callback_data="join_tournament")]])
            await message.answer(text + "\n\n❌ Ви ще не в турнірі.", reply_markup=keyboard, parse_mode="Markdown")
    elif pending:
        start_time = datetime.fromisoformat(pending['start_time']).strftime("%Y-%m-%d %H:%M")
        text = f"🏆 **Майбутній турнір**\n\n📅 Початок: {start_time}\n💰 Призовий фонд: {pending['prize_pool']} монет\n\nПриєднуйтесь!"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔔 Нагадати", callback_data="remind_tournament")]])
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await message.answer("🏆 Наразі немає запланованих турнірів.")

@dp.callback_query(F.data == "join_tournament")
async def join_tournament(callback: CallbackQuery):
    active = db.get_active_tournament()
    if not active:
        await callback.answer("❌ Немає активного турніру", show_alert=True)
        return
    success = db.join_tournament(callback.from_user.id, active['id'])
    if success:
        await callback.message.edit_text("✅ Ви долучилися до турніру! Успіхів!")
    else:
        await callback.answer("❌ Ви вже в турнірі", show_alert=True)
    await callback.answer()

@dp.callback_query(F.data == "remind_tournament")
async def remind_tournament(callback: CallbackQuery):
    await callback.answer("✅ Ми нагадаємо вам за 1 годину до початку!", show_alert=True)

# ============= МАРКЕТ =============
@dp.message(F.text == "🏪 Маркет")
@dp.message(Command("market"))
async def cmd_market(message: Message):
    listings = db.get_market_listings(0, 5)
    if not listings:
        await message.answer("📭 Маркет порожній. Виставте свій скін: /sell_market [ID] [ціна]")
        return
    text = "🛒 **МАРКЕТ**\n\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for l in listings:
        text += (
            f"• **{l['skin_name']}**\n"
            f"  ID лоту: `{l['id']}`\n"
            f"  Рідкість: {get_rarity_emoji(l['rarity'])} {l['rarity']}\n"
            f"  Ціна: 💰 {l['price']} монет\n\n"
        )
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"💰 Купити {l['skin_name'][:20]}", callback_data=f"buy_market_{l['id']}")])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@dp.message(Command("sell_market"))
async def cmd_sell_market(message: Message):
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("ℹ Використання: /sell_market <ID_скіна> <ціна>")
        return
    try:
        skin_id = int(parts[1])
        price = int(parts[2])
    except:
        await message.answer("❌ Числа")
        return
    if price <= 0:
        await message.answer("❌ Ціна > 0")
        return
    result = db.list_skin_on_market(message.from_user.id, skin_id, price)
    if result['success']:
        skin = db.get_skin_by_id(skin_id, message.from_user.id)
        seller_username = message.from_user.username
        await notify_market_listing(skin['skin_name'], price, seller_username, message.from_user.id)
    await message.answer(result['message'])

@dp.message(Command("my_listings"))
async def cmd_my_listings(message: Message):
    listings = db.get_market_listings(0, 100)
    my = [l for l in listings if l['seller_id'] == message.from_user.id]
    if not my:
        await message.answer("📭 У вас немає активних лотів")
        return
    text = "📋 **ВАШІ ЛОТИ**\n\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for l in my:
        text += f"• ID лоту: `{l['id']}` — {l['skin_name']} ({l['rarity']}), ціна {l['price']}\n"
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"❌ Скасувати #{l['id']}", callback_data=f"cancel_listing_{l['id']}")])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("buy_market_"))
async def buy_from_market(callback: CallbackQuery):
    lid = int(callback.data.replace("buy_market_", ""))
    result = db.buy_from_market(callback.from_user.id, lid)
    if result['success']:
        await callback.message.edit_text(f"✅ **Придбано!**\n\n{result['skin_name']}\nСума: {result['price']} монет", parse_mode="Markdown")
    else:
        await callback.answer(result['message'], show_alert=True)
    await callback.answer()

@dp.callback_query(F.data.startswith("cancel_listing_"))
async def cancel_listing(callback: CallbackQuery):
    lid = int(callback.data.replace("cancel_listing_", ""))
    ok = db.cancel_market_listing(callback.from_user.id, lid)
    if ok:
        await callback.message.edit_text("✅ Лот скасовано")
    else:
        await callback.answer("❌ Помилка", show_alert=True)
    await callback.answer()

# ============= ДУЕЛІ =============
@dp.message(F.text == "⚔️ Дуелі")
@dp.message(Command("duels"))
async def show_active_duels(message: Message):
    duels = db.get_active_duels()
    if not duels:
        await message.answer("📭 Немає активних дуелей. Створіть: /duel [сума]")
        return

    text = "⚔️ **АКТИВНІ ДУЕЛІ**\n\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[])

    for d in duels[:5]:
        creator = db.get_or_create_user(d['creator_id'], None)
        name = creator['username'] or f"ID {d['creator_id']}"
        text += f"• Дуель #{d['id']} від @{name}, ставка 💰 {d['bet_amount']} монет\n"
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"⚔️ Прийняти #{d['id']}",
                callback_data=f"accept_duel_{d['id']}"
            )
        ])

    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@dp.message(Command("duel"))
async def cmd_duel(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("ℹ Використання: /duel <сума>")
        return
    try:
        bet = int(parts[1])
    except:
        await message.answer("❌ Число")
        return
    if bet < 10:
        await message.answer("❌ Мінімум 10 монет")
        return
    result = db.create_duel(message.from_user.id, bet)
    if result['success']:
        await message.answer(f"✅ Дуель створено! ID: {result['duel_id']}, ставка {bet} монет")
    else:
        await message.answer(result['message'])

@dp.callback_query(F.data.startswith("accept_duel_"))
async def accept_duel(callback: CallbackQuery):
    did = int(callback.data.replace("accept_duel_", ""))
    res = db.accept_duel(did, callback.from_user.id)
    if res['success']:
        fight = db.fight_duel(did)
        if fight['success']:
            winner_id = fight['winner_id']
            db.update_daily_stats(winner_id, 'duels', 1)
            await callback.message.edit_text(
                f"⚔️ **Дуель завершено!**\n\nПереможець: {fight['winner_name']}\nВиграш: 💰 {fight['total_bank']} монет",
                parse_mode="Markdown"
            )
        else:
            await callback.message.edit_text("❌ Помилка дуелі")
    else:
        await callback.answer(res['message'], show_alert=True)
    await callback.answer()

# ============= ТРЕЙДИ =============
@dp.message(Command("trade"))
async def cmd_trade(message: Message):
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("ℹ Використання: /trade <ID_гравця> <ID_скіна>")
        return
    try:
        to_id = int(parts[1])
        skin_id = int(parts[2])
    except:
        await message.answer("❌ Числа")
        return
    skin = db.get_skin_by_id(skin_id, message.from_user.id)
    if not skin:
        await message.answer("❌ Скін не знайдено у вашому інвентарі")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"confirm_trade_{to_id}_{skin_id}"),
            InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_trade")
        ]
    ])
    await message.answer(
        f"⚠️ **Підтвердження передачі**\n\nВи передаєте: {skin['skin_name']} ({skin['rarity']})\nКористувачу: `{to_id}`",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("confirm_trade_"))
async def confirm_trade(callback: CallbackQuery):
    parts = callback.data.split("_")
    to_id = int(parts[2])
    skin_id = int(parts[3])
    result = db.trade_skin(callback.from_user.id, to_id, skin_id)
    await callback.message.edit_text(result['message'])
    await callback.answer()

@dp.callback_query(F.data == "cancel_trade")
async def cancel_trade(callback: CallbackQuery):
    await callback.message.edit_text("❌ Скасовано")
    await callback.answer()

# ============= АДМІН-ПАНЕЛЬ =============
@dp.message(Command("admin"))
async def cmd_admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав доступу.")
        return

    text = (
        "🛡 <b>АДМІН-ПАНЕЛЬ</b>\n\n"
        "<b>📊 Статистика бота:</b>\n"
        f"• Всього користувачів: {db.get_total_users_count()}\n"
        f"• Всього скінів: {db.get_total_skins_count()}\n"
        f"• Модераторів: {len(db.get_moderators())}\n\n"
        "<b>📋 Команди керування модераторами:</b>\n"
        "• <code>/addmod &lt;id&gt;</code> - додати модератора\n"
        "• <code>/delmod &lt;id&gt;</code> - видалити модератора\n"
        "• <code>/mods</code> - список модераторів\n\n"
        "<b>👥 Команди для роботи з гравцями:</b>\n"
        "• <code>/users [page]</code> - список всіх гравців\n"
        "• <code>/search &lt;текст&gt;</code> - пошук гравця\n"
        "• <code>/userinfo &lt;id&gt;</code> - детальна інформація\n"
        "• <code>/userstats &lt;id&gt;</code> - статистика транзакцій\n"
        "• <code>/modinv &lt;id&gt;</code> - переглянути інвентар\n"
        "• <code>/inspect &lt;id&gt;</code> - інспекція гравця\n"
        "• <code>/delete_user &lt;id&gt;</code> - <b>ПОВНІСТЮ ВИДАЛИТИ ПРОФІЛЬ</b> (з підтвердженням)\n"
        "• <code>/reset_user &lt;id&gt;</code> - <b>СКИНУТИ ПРОГРЕС</b> (видалити інвентар, обнулити статистику, встановити баланс 1000)\n\n"
        "<b>💰 Фінансові команди:</b>\n"
        "• <code>/modaddbal &lt;id&gt; &lt;сума&gt;</code> - нарахувати монети\n"
        "• <code>/modsubbal &lt;id&gt; &lt;сума&gt;</code> - зняти монети\n"
        "• <code>/give &lt;id&gt; &lt;сума&gt;</code> - видати монети (без обмежень)\n\n"
        f"<b>💳 Платежі:</b> (курс: 1 грн = {EXCHANGE_RATE} монет)\n"
        "• <code>/payments</code> - перегляд очікуючих платежів (кнопка «💳 Платежі»)\n\n"
        "<b>📢 Команди розсилки:</b>\n"
        "• <code>/broadcast &lt;текст&gt;</code> - розсилка всім (звіт про помилки)\n\n"
        "<b>🎰 Промокоди:</b>\n"
        "• <code>/create_promo &lt;назва&gt; &lt;нагорода&gt; &lt;ліміт&gt;</code> - створити промокод\n"
        "• <code>/promos</code> - список промокодів\n\n"
        "<b>🎰 Безкоштовні кейси:</b>\n"
        "• <code>/give_free_cases &lt;кейс&gt; &lt;кількість&gt;</code> - надати всім гравцям безкоштовні відкриття\n\n"
        "<b>💸 Виведення коштів:</b>\n"
        "• Заявки на виведення з'являються в чаті з кнопками підтвердження.\n\n"
        "<b>📋 Пропозиції:</b>\n"
        "• Кнопка «📋 Пропозиції» - перегляд всіх пропозицій від гравців.\n\n"
        "<b>📊 Статистика та лідери:</b>\n"
        "• <code>/stats</code> - статистика бота\n"
        "• <code>/top</code> - таблиця лідерів\n"
        "• <code>/top_daily</code> - топ за день\n"
        "• <code>/top_alltime</code> - топ за весь час\n\n"
        "<b>⚔️ Дуелі:</b>\n"
        "• <code>/duel &lt;сума&gt;</code> - створити дуель\n"
        "• <code>/duels</code> - список активних дуелей\n\n"
        "<b>🏪 Маркет:</b>\n"
        "• <code>/market</code> - ринок скінів\n"
        "• <code>/sell_market &lt;id&gt; &lt;ціна&gt;</code> - виставити скін\n"
        "• <code>/my_listings</code> - мої лоти\n\n"
        "<b>🤝 Трейди:</b>\n"
        "• <code>/trade &lt;id&gt; &lt;id_скіна&gt;</code> - передати скін\n\n"
        "<b>🏆 Турнір:</b>\n"
        "• <code>/tournament</code> - інформація про турнір\n\n"
        "<b>🎮 Ігри:</b>\n"
        "• Кнопка «🎰 Ігри» - Слоти, рулетка\n\n"
        "<b>👥 Соціальне:</b>\n"
        "• <code>/suggest</code> - надіслати пропозицію\n"
        "• <code>/mysuggestions</code> - переглянути свої пропозиції\n"
        "• <code>/friends</code> - меню друзів\n"
        "• <code>/addfriend &lt;id&gt;</code> - додати друга\n"
        "• <code>/acceptfriend &lt;id&gt;</code> - прийняти запит\n"
        "• <code>/myfriends</code> - список друзів\n"
        "• <code>/create_tournament</code> - створити приватний турнір\n"
        "• <code>/join_tournament &lt;id&gt;</code> - долучитися до турніру\n\n"
        "<b>📊 Адмін-статистика:</b>\n"
        "• <code>/adminstats</code> - детальна статистика\n"
        "• <code>/check_rare_drops</code> - перевірити рідкісні випадіння"
    )
    await message.answer(text, reply_markup=get_admin_keyboard(), parse_mode="HTML")

@dp.message(F.text == "🛡 Адмін панель")
async def show_admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав доступу.")
        return
    await cmd_admin_panel(message)

@dp.message(Command("moderator"))
async def cmd_moderator_panel(message: Message):
    if not has_moderator_power(message.from_user.id):
        await message.answer("❌ У вас немає прав доступу.")
        return
    if is_admin(message.from_user.id):
        await message.answer("❌ Використовуйте /admin")
        return

    text = (
        "🛡 <b>ПАНЕЛЬ МОДЕРАТОРА</b>\n\n"
        "<b>📊 Статистика:</b>\n"
        f"• Користувачів: {db.get_total_users_count()}\n"
        f"• Скінів: {db.get_total_skins_count()}\n\n"
        "<b>📋 Команди:</b>\n"
        "• <code>/users</code> - Список гравців\n"
        "• <code>/search &lt;текст&gt;</code> - Пошук гравця\n"
        "• <code>/userinfo &lt;id&gt;</code> - Інформація про гравця\n"
        "• <code>/inspect &lt;id&gt;</code> - Детальна інспекція\n"
        "• <code>/modinv &lt;id&gt;</code> - Інвентар гравця\n"
        "• <code>/userstats &lt;id&gt;</code> - Статистика транзакцій\n"
        "• <code>/modaddbal &lt;id&gt; &lt;сума&gt;</code> - Нарахувати монети\n"
        "• <code>/modsubbal &lt;id&gt; &lt;сума&gt;</code> - Зняти монети\n"
        "• <code>/stats</code> - Статистика бота\n"
        "• <code>/tournament</code> - Турнір\n\n"
        "<b>⚠️ Обмеження:</b> не можна змінювати баланс адмінам/модераторам/собі\n\n"
        "<b>🎮 Ігри:</b>\n"
        "• Кнопка «🎰 Ігри» - Слоти, рулетка\n\n"
        "<b>👥 Соціальне:</b>\n"
        "• Доступні всі соціальні команди"
    )
    await message.answer(text, reply_markup=get_moderator_keyboard(), parse_mode="HTML")

@dp.message(F.text == "🛡 Модератор панель")
async def show_moderator_panel(message: Message):
    if not has_moderator_power(message.from_user.id):
        await message.answer("❌ У вас немає прав доступу.")
        return
    if is_admin(message.from_user.id):
        await message.answer("❌ Використовуйте /admin")
        return
    await cmd_moderator_panel(message)

# ============= КОМАНДИ ДЛЯ МОДЕРАТОРІВ/АДМІНІВ =============
import html

@dp.message(Command("users"))
async def cmd_users_list(message: Message):
    if not has_moderator_power(message.from_user.id):
        await message.answer("❌ У вас немає прав.")
        return
    parts = message.text.split()
    page = 0
    if len(parts) > 1:
        try:
            page = int(parts[1]) - 1
            if page < 0: page = 0
        except:
            pass
    users = db.get_all_users()
    if not users:
        await message.answer("📭 Немає гравців")
        return
    items_per_page = 20
    total_pages = (len(users) + items_per_page - 1) // items_per_page
    if page >= total_pages:
        page = total_pages - 1 if total_pages > 0 else 0
    start = page * items_per_page
    end = start + items_per_page
    page_users = users[start:end]

    text = f"<b>📋 СПИСОК ГРАВЦІВ</b> (стор. {page+1}/{total_pages})\n\n"
    for i, u in enumerate(page_users, start=start+1):
        role = "👑" if u['user_id'] in ADMINS else "🛡" if db.is_moderator(u['user_id']) else "👤"
        username = html.escape(u['username'] or 'немає')
        text += f"{i}. {role} <code>{u['user_id']}</code> | @{username} | 💰 {u['balance']}\n"

    kb = None
    if total_pages > 1:
        buttons = []
        if page > 0:
            buttons.append(InlineKeyboardButton(text="◀️ Попередня", callback_data=f"users_page_{page-1}"))
        if page < total_pages - 1:
            buttons.append(InlineKeyboardButton(text="Наступна ▶️", callback_data=f"users_page_{page+1}"))
        if buttons:
            kb = InlineKeyboardMarkup(inline_keyboard=[buttons])

    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("users_page_"))
async def users_page_handler(callback: CallbackQuery):
    if not has_moderator_power(callback.from_user.id):
        await callback.answer("❌ Немає прав", show_alert=True)
        return
    page = int(callback.data.replace("users_page_", ""))
    callback.message.text = f"/users {page+1}"
    await cmd_users_list(callback.message)
    await callback.answer()

@dp.message(Command("search"))
async def cmd_search_user(message: Message):
    if not has_moderator_power(message.from_user.id):
        await message.answer("❌ У вас немає прав.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("ℹ Використання: /search <текст>")
        return
    query = parts[1].lower()
    users = db.get_all_users()
    results = []
    try:
        uid = int(query)
        for u in users:
            if u['user_id'] == uid:
                results = [u]
                break
    except:
        for u in users:
            if u['username'] and query in u['username'].lower():
                results.append(u)
    if not results:
        await message.answer(f"❌ Нічого не знайдено за запитом '{query}'")
        return
    text = f"🔍 **Результати пошуку** для '{query}':\n\n"
    for u in results:
        role = "👑" if u['user_id'] in ADMINS else "🛡" if db.is_moderator(u['user_id']) else "👤"
        text += f"{role} `{u['user_id']}` | @{u['username'] or 'немає'} | 💰 {u['balance']}\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("userinfo"))
async def cmd_user_info(message: Message):
    if not has_moderator_power(message.from_user.id):
        await message.answer("❌ У вас немає прав.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("ℹ Використання: /userinfo <id>")
        return
    try:
        target = int(parts[1])
    except:
        await message.answer("❌ ID має бути числом")
        return
    if not is_admin(message.from_user.id) and target in ADMINS:
        await message.answer("❌ Ви не можете переглядати інформацію про адмінів")
        return
    user = db.get_or_create_user(target, None)
    stats = db.get_profile_stats(target)
    role = "👑 Адмін" if target in ADMINS else "🛡 Модератор" if db.is_moderator(target) else "👤 Гравець"
    text = (
        f"📋 **Інформація про гравця** `{target}`\n\n"
        f"👤 Username: @{user['username'] or 'немає'}\n"
        f"🛡 Роль: {role}\n"
        f"💰 Баланс: {stats['balance']} монет\n"
        f"📊 Рівень: {stats['level']} | XP: {stats['xp']}/100\n"
        f"📦 Відкрито кейсів: {stats['cases_opened']}\n"
        f"🎒 Скінів: {len(db.get_user_inventory(target))}"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("inspect"))
async def cmd_inspect_user(message: Message):
    if not has_moderator_power(message.from_user.id):
        await message.answer("❌ У вас немає прав.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("ℹ Використання: /inspect <id>")
        return
    try:
        target = int(parts[1])
    except:
        await message.answer("❌ ID має бути числом")
        return
    if not is_admin(message.from_user.id) and target in ADMINS:
        await message.answer("❌ Ви не можете інспектувати адмінів")
        return
    stats = db.get_profile_stats(target)
    inv = db.get_user_inventory(target)
    role = "👑 Адмін" if target in ADMINS else "🛡 Модератор" if db.is_moderator(target) else "👤 Гравець"
    text = (
        f"🔍 **ІНСПЕКЦІЯ ГРАВЦЯ** `{target}`\n\n"
        f"👤 Username: @{stats['username'] or 'немає'}\n"
        f"🛡 Роль: {role}\n"
        f"💰 Баланс: {stats['balance']}\n"
        f"📊 Рівень: {stats['level']} | XP: {stats['xp']}/100\n"
        f"📦 Відкрито кейсів: {stats['cases_opened']}\n"
        f"🎒 Всього скінів: {len(inv)}\n\n"
        f"🛒 Покупок: {stats['transactions']['purchases']['count']} на {stats['transactions']['purchases']['total_value']} монет\n"
        f"💰 Продажів: {stats['transactions']['sales']['count']} на {stats['transactions']['sales']['total_value']} монет\n"
        f"🤝 Трейдів: відправлено {stats['transactions']['trades']['sent']}, отримано {stats['transactions']['trades']['received']}\n"
        f"🏪 Маркет: куплено {stats['transactions']['market']['purchases_count']}, продано {stats['transactions']['market']['sales_count']}"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("modinv"))
async def cmd_moderator_view_inventory(message: Message):
    if not has_moderator_power(message.from_user.id):
        await message.answer("❌ У вас немає прав.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("ℹ Використання: /modinv <id>")
        return
    try:
        target = int(parts[1])
    except:
        await message.answer("❌ ID має бути числом")
        return
    if not is_admin(message.from_user.id) and target in ADMINS:
        await message.answer("❌ Ви не можете переглядати інвентар адмінів")
        return
    inv = db.get_user_inventory(target)
    if not inv:
        await message.answer(f"🎒 Інвентар користувача {target} порожній.")
        return
    user = db.get_or_create_user(target, None)
    text = f"🎒 **Інвентар користувача** `{target}` (@{user['username'] or 'немає'})\n\n"
    for i, item in enumerate(inv[:20], 1):
        e = get_rarity_emoji(item['rarity'])
        text += f"{i}. `#{item['id']}` {e} {item['skin_name']} ({item['rarity']})\n"
    if len(inv) > 20:
        text += f"\n... та ще {len(inv)-20} скінів."
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("userstats"))
async def cmd_user_stats(message: Message):
    if not has_moderator_power(message.from_user.id):
        await message.answer("❌ У вас немає прав.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("ℹ Використання: /userstats <id>")
        return
    try:
        target = int(parts[1])
    except:
        await message.answer("❌ ID має бути числом")
        return
    if not is_admin(message.from_user.id) and target in ADMINS:
        await message.answer("❌ Ви не можете переглядати статистику адмінів")
        return
    stats = db.get_profile_stats(target)
    text = (
        f"📊 **СТАТИСТИКА ТРАНЗАКЦІЙ** `{target}`\n\n"
        f"🛒 Покупок: {stats['transactions']['purchases']['count']} на {stats['transactions']['purchases']['total_value']} монет\n"
        f"💰 Продажів: {stats['transactions']['sales']['count']} на {stats['transactions']['sales']['total_value']} монет\n"
        f"🤝 Трейдів: відправлено {stats['transactions']['trades']['sent']}, отримано {stats['transactions']['trades']['received']}\n"
        f"🏪 Маркет: куплено {stats['transactions']['market']['purchases_count']} на {stats['transactions']['market']['purchases_value']} монет, продано {stats['transactions']['market']['sales_count']} на {stats['transactions']['market']['sales_value']} монет"
    )
    await message.answer(text, parse_mode="Markdown")

# ============= ФІНАНСОВІ КОМАНДИ =============
@dp.message(Command("modaddbal"))
async def cmd_moderator_add_balance(message: Message):
    if not has_moderator_power(message.from_user.id):
        await message.answer("❌ У вас немає прав.")
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("ℹ Використання: /modaddbal <id> <сума>")
        return
    try:
        target = int(parts[1])
        amount = int(parts[2])
    except ValueError:
        await message.answer("❌ Числа мають бути цілими.")
        return
    if not is_admin(message.from_user.id):
        if target in ADMINS or db.is_moderator(target) or target == message.from_user.id:
            await message.answer("❌ Не можна змінювати баланс адмінам/модераторам/собі")
            return
    if not db.user_exists(target):
        await message.answer(f"❌ Користувача з ID {target} не знайдено в базі.")
        return
    db.update_balance(target, amount)
    await message.answer(f"✅ +{amount} монет користувачу {target}")

@dp.message(Command("modsubbal"))
async def cmd_moderator_sub_balance(message: Message):
    if not has_moderator_power(message.from_user.id):
        await message.answer("❌ У вас немає прав.")
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("ℹ Використання: /modsubbal <id> <сума>")
        return
    try:
        target = int(parts[1])
        amount = int(parts[2])
    except ValueError:
        await message.answer("❌ Числа мають бути цілими.")
        return
    if not is_admin(message.from_user.id):
        if target in ADMINS or db.is_moderator(target) or target == message.from_user.id:
            await message.answer("❌ Не можна змінювати баланс адмінам/модераторам/собі")
            return
    if not db.user_exists(target):
        await message.answer(f"❌ Користувача з ID {target} не знайдено в базі.")
        return
    db.update_balance(target, -amount)
    await message.answer(f"✅ -{amount} монет з користувача {target}")

@dp.message(Command("give"))
async def cmd_give_balance(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав.")
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("ℹ Використання: /give <id> <сума>")
        return
    try:
        target = int(parts[1])
        amount = int(parts[2])
    except ValueError:
        await message.answer("❌ Числа мають бути цілими.")
        return
    if not db.user_exists(target):
        await message.answer(f"❌ Користувача з ID {target} не знайдено в базі.")
        return
    db.update_balance(target, amount)
    await message.answer(f"✅ +{amount} монет користувачу {target}")

# ============= КОМАНДИ ДЛЯ АДМІНІВ =============
@dp.message(Command("addmod"))
async def cmd_add_moderator(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("ℹ Використання: /addmod <id>")
        return
    try:
        target = int(parts[1])
    except:
        await message.answer("❌ Число")
        return
    db.get_or_create_user(target, None)
    db.add_moderator(target)
    await message.answer(f"✅ Користувач {target} тепер модератор")

@dp.message(Command("delmod"))
async def cmd_remove_moderator(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("ℹ Використання: /delmod <id>")
        return
    try:
        target = int(parts[1])
    except:
        await message.answer("❌ Число")
        return
    if db.remove_moderator(target):
        await message.answer(f"✅ Користувач {target} більше не модератор")
    else:
        await message.answer("ℹ Користувач не був модератором")

@dp.message(Command("mods"))
async def cmd_list_moderators(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав.")
        return
    mods = db.get_moderators()
    if not mods:
        await message.answer("ℹ Немає модераторів")
        return
    lines = ["🛡 **МОДЕРАТОРИ**", ""]
    for m in mods:
        lines.append(f"• `{m['user_id']}` (@{m['username'] or 'немає'})")
    await message.answer("\n".join(lines), parse_mode="Markdown")

# ============= КОМАНДА ДЛЯ БЕЗКОШТОВНИХ КЕЙСІВ =============
@dp.message(Command("give_free_cases"))
async def cmd_give_free_cases(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав.")
        return
    case_aliases = {
        "standard": "Standard Case",
        "rare": "Rare Case",
        "mystery": "Mystery Case",
        "legendary": "Legendary Case",
        "glove": "Glove Case",
        "sticker": "Sticker Case"
    }
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer(
            "ℹ Використання: /give_free_cases <назва_кейсу> <кількість>\n"
            "Доступні назви: standard, rare, mystery, legendary, glove, sticker"
        )
        return
    case_alias = parts[1].lower()
    if case_alias not in case_aliases:
        await message.answer(f"❌ Невідома назва кейсу. Доступні: {', '.join(case_aliases.keys())}")
        return
    case_key = case_aliases[case_alias]
    try:
        amount = int(parts[2])
        if amount <= 0:
            await message.answer("❌ Кількість має бути додатною.")
            return
    except ValueError:
        await message.answer("❌ Кількість має бути числом.")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Так", callback_data=f"confirm_free_{case_key}_{amount}"),
            InlineKeyboardButton(text="❌ Ні", callback_data="cancel_free")
        ]
    ])
    await message.answer(
        f"Ви дійсно хочете надати **{amount}** безкоштовних відкриттів кейсу **{case_key}** для **всіх гравців**?",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("confirm_free_"))
async def confirm_free_cases(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Немає прав", show_alert=True)
        return
    parts = callback.data.split("_")
    case_key = parts[2]
    amount = int(parts[3])
    count = db.add_free_cases_to_all(case_key, amount)
    await callback.message.edit_text(f"✅ Надано {amount} безкоштовних відкриттів кейсу {case_key} для {count} гравців.")
    await callback.answer()

@dp.callback_query(F.data == "cancel_free")
async def cancel_free(callback: CallbackQuery):
    await callback.message.edit_text("❌ Операцію скасовано.")
    await callback.answer()

# ============= РОЗСИЛКА =============
@dp.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("ℹ Використання: /broadcast <текст>")
        return
    broadcast_text = parts[1]
    users = db.get_all_users()
    await message.answer(f"📨 Розсилка для {len(users)} користувачів...")

    success = 0
    failed = []

    for u in users:
        try:
            await bot.send_message(u['user_id'], f"📢 **Оголошення:**\n\n{broadcast_text}")
            success += 1
        except TelegramForbiddenError:
            failed.append((u['user_id'], "Користувач заблокував бота"))
        except TelegramBadRequest as e:
            failed.append((u['user_id'], f"BadRequest: {e}"))
        except Exception as e:
            failed.append((u['user_id'], str(e)[:50]))
        await asyncio.sleep(0.05)

    report = f"✅ Успішно: {success}/{len(users)}\n"
    if failed:
        report += "❌ Невдалі спроби:\n"
        for uid, err in failed[:10]:
            report += f"ID {uid}: {err}\n"
        if len(failed) > 10:
            report += f"... та ще {len(failed)-10} помилок."
    else:
        report += "✅ Усі повідомлення доставлено."

    await message.answer(report)

# ============= КОМАНДА ВИДАЛЕННЯ КОРИСТУВАЧА =============
@dp.message(Command("delete_user"))
async def cmd_delete_user(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав адміністратора.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("ℹ Використання: /delete_user <id_користувача>")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("❌ ID має бути числом.")
        return
    if target_id == message.from_user.id:
        await message.answer("❌ Не можна видалити самого себе.")
        return
    if target_id in ADMINS:
        await message.answer("❌ Не можна видалити адміністратора.")
        return
    if not db.user_exists(target_id):
        await message.answer(f"❌ Користувача з ID {target_id} не знайдено.")
        return
    user = db.get_or_create_user(target_id, None)
    username = user.get('username', 'немає')
    safe_username = html.escape(username)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Так, видалити", callback_data=f"confirm_delete_{target_id}"),
            InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_delete")
        ]
    ])
    await message.answer(
        f"⚠️ <b>Ви впевнені, що хочете повністю видалити користувача</b>\n\n"
        f"ID: <code>{target_id}</code>\n"
        f"Username: @{safe_username}\n\n"
        f"Це видалить:\n"
        f"• Профіль та баланс\n"
        f"• Інвентар (скіни)\n"
        f"• Активні лоти на маркеті\n"
        f"• Дуелі\n"
        f"• Історію платежів та промокодів\n"
        f"• Участь у турнірах\n\n"
        f"<b>Цю дію неможливо скасувати!</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Немає прав", show_alert=True)
        return
    target_id = int(callback.data.replace("confirm_delete_", ""))
    if target_id in ADMINS:
        await callback.message.edit_text("❌ Не можна видалити адміністратора.")
        await callback.answer()
        return
    success = db.delete_user_completely(target_id)
    if success:
        text = f"✅ Користувача з ID `{target_id}` успішно видалено."
    else:
        text = f"❌ Помилка при видаленні користувача `{target_id}` (можливо, не існує)."
    await callback.message.edit_text(text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery):
    await callback.message.edit_text("❌ Видалення скасовано.")
    await callback.answer()

# ============= КОМАНДА СКИДАННЯ ПРОГРЕСУ =============
@dp.message(Command("reset_user"))
async def cmd_reset_user(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав адміністратора.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("ℹ Використання: /reset_user <id_користувача>")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("❌ ID має бути числом.")
        return
    if not db.user_exists(target_id):
        await message.answer(f"❌ Користувача з ID {target_id} не знайдено.")
        return
    user = db.get_or_create_user(target_id, None)
    username = html.escape(user.get('username', 'немає'))
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Так, скинути прогрес", callback_data=f"confirm_reset_{target_id}"),
            InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_reset")
        ]
    ])
    await message.answer(
        f"<b>⚠️ Ви впевнені, що хочете повністю скинути прогрес користувача?</b>\n"
        f"ID: <code>{target_id}</code>\n"
        f"Username: @{username}\n\n"
        f"Це призведе до:\n"
        f"• Видалення всього інвентарю (всі скіни)\n"
        f"• Видалення статистики ігор, дуелей, продажів\n"
        f"• Видалення друзів, пропозицій, участі в турнірах\n"
        f"• Скидання балансу до 1000 монет\n"
        f"• Скидання рівня до 1, XP до 0, лічильника кейсів до 0\n\n"
        f"<b>Цю дію неможливо скасувати!</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("confirm_reset_"))
async def confirm_reset_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Немає прав", show_alert=True)
        return
    target_id = int(callback.data.replace("confirm_reset_", ""))
    success = db.reset_user_progress(target_id)
    if success:
        text = f"✅ Прогрес користувача з ID `{target_id}` успішно скинуто."
    else:
        text = f"❌ Помилка при скиданні прогресу користувача `{target_id}` (можливо, не існує)."
    await callback.message.edit_text(text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "cancel_reset")
async def cancel_reset(callback: CallbackQuery):
    await callback.message.edit_text("❌ Скидання скасовано.")
    await callback.answer()

# ============= СТАТИСТИКА =============
@dp.message(F.text == "📊 Статистика")
@dp.message(Command("stats"))
async def show_stats(message: Message):
    if not has_moderator_power(message.from_user.id):
        await message.answer("❌ У вас немає прав.")
        return
    users_count = db.get_total_users_count()
    skins_count = db.get_total_skins_count()
    mods = db.get_moderators()
    rarity_stats = db.get_skins_rarity_stats()
    text = (
        f"📊 **СТАТИСТИКА БОТА**\n\n"
        f"👥 Користувачів: {users_count}\n"
        f"🛡 Модераторів: {len(mods)}\n"
        f"👑 Адміністраторів: {len(ADMINS)}\n\n"
        f"🎒 Скінів: {skins_count}\n"
    )
    if rarity_stats:
        text += "\n**За рідкістю:**\n"
        for r, c in rarity_stats.items():
            e = get_rarity_emoji(r)
            text += f"{e} {r}: {c}\n"
    await message.answer(text, parse_mode="Markdown")

# ============= ТАБЛИЦЯ ЛІДЕРІВ =============
@dp.message(F.text == "🏆 Топ гравців")
@dp.message(Command("top"))
async def cmd_top(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Топ за балансом", callback_data="top_balance")],
        [InlineKeyboardButton(text="🟡 Топ за Rare Special", callback_data="top_rare_special")]
    ])
    await message.answer("🏆 **Оберіть тип таблиці:**", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "top_balance")
async def show_top_balance(callback: CallbackQuery):
    await callback.answer()
    top = db.get_top_balance(10)
    if not top:
        await callback.message.edit_text("📭 Немає гравців")
        return
    text = "🏆 **ТОП-10 ЗА БАЛАНСОМ**\n\n"
    for i, u in enumerate(top, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "▫️"
        name = u['username'] or f"ID {u['user_id']}"
        text += f"{medal} {i}. {name} — 💰 {u['balance']} монет\n"
    await callback.message.edit_text(text)

@dp.callback_query(F.data == "top_rare_special")
async def show_top_rare_special(callback: CallbackQuery):
    await callback.answer()
    top = db.get_top_rare_special(10)
    if not top:
        await callback.message.edit_text("📭 Немає гравців з Rare Special")
        return
    text = "🟡 **ТОП-10 ЗА RARE SPECIAL**\n\n"
    for i, u in enumerate(top, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "▫️"
        name = u['username'] or f"ID {u['user_id']}"
        text += f"{medal} {i}. {name} — 🟡 {u['rare_special_count']} скінів\n"
    await callback.message.edit_text(text)

# ============= ПРОМОКОДИ =============
@dp.message(F.text == "🎰 Промокод")
@dp.message(Command("promo"))
async def cmd_use_promo(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("ℹ Використання: /promo <код>")
        return
    code = parts[1].upper()
    result = db.use_promocode(message.from_user.id, code)
    await message.answer(result['message'])

@dp.message(Command("create_promo"))
async def cmd_create_promo(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав.")
        return
    parts = message.text.split()
    if len(parts) < 4:
        await message.answer("ℹ Використання: /create_promo <код> <сума> <ліміт>")
        return
    code = parts[1].upper()
    try:
        reward = int(parts[2])
        limit = int(parts[3])
    except:
        await message.answer("❌ Числа")
        return
    if db.create_promocode(code, reward, limit, message.from_user.id):
        await message.answer(f"✅ Промокод **{code}** створено!\nНагорода: {reward} монет\nЛіміт: {limit}")
    else:
        await message.answer(f"❌ Промокод **{code}** вже існує")

@dp.message(Command("promos"))
async def cmd_list_promos(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав.")
        return
    promos = db.get_all_promocodes()
    if not promos:
        await message.answer("📭 Немає промокодів")
        return
    text = "📋 **ПРОМОКОДИ**\n\n"
    for p in promos:
        text += f"• **{p['code']}** – {p['reward']} монет, використано {p['used_count']}/{p['max_uses']}\n"
    await message.answer(text, parse_mode="Markdown")

# ============= СИСТЕМА ОПЛАТИ =============
@dp.message(F.text == "💳 Поповнити баланс")
async def cmd_pay_start(message: Message):
    await message.answer(
        f"💳 **Поповнення балансу**\n\n"
        f"Курс: 1 грн = {EXCHANGE_RATE} монет\n\n"
        "Оберіть спосіб оплати:",
        reply_markup=get_payment_methods_keyboard(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("pay_"))
async def process_payment_method(callback: CallbackQuery, state: FSMContext):
    method = callback.data.replace("pay_", "")
    await state.update_data(payment_method=method)
    text = PAYMENT_DETAILS.get(method, "")
    if not text:
        await callback.answer()
        return
    await callback.message.edit_text(
        text + "\n\nТепер оберіть суму поповнення:",
        reply_markup=get_payment_amount_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "back_to_payment_methods")
async def back_to_payment_methods(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        f"💳 **Поповнення балансу**\n\nКурс: 1 грн = {EXCHANGE_RATE} монет\n\nОберіть спосіб оплати:",
        reply_markup=get_payment_methods_keyboard(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "amount_custom")
async def payment_amount_custom(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(PaymentStates.waiting_for_custom_amount)
    await callback.message.edit_text(
        "💸 **Введіть суму в гривнях** (ціле число, мінімум 1 грн):\n\n"
        "Напишіть число у чат.",
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("amount_"))
async def process_payment_amount(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    method = data.get('payment_method', 'privat')
    amount_uah = int(callback.data.replace("amount_", ""))
    result = db.create_payment(callback.from_user.id, amount_uah, method)
    if result['success']:
        await state.update_data(payment_id=result['payment_id'])
        await state.set_state(PaymentStates.waiting_for_screenshot)
        await callback.message.edit_text(
            f"✅ **Заявку створено!**\n\n"
            f"🆔 Номер заявки: `{result['payment_id']}`\n"
            f"💳 Сума: {amount_uah} грн\n"
            f"💰 Отримаєте: {result['amount_coins']} монет\n\n"
            f"📸 **Тепер надішліть скріншот оплати** (фото).\n"
            f"Після перевірки адміністратором кошти будуть зараховані автоматично.",
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text(f"❌ {result['message']}", parse_mode="Markdown")
    await callback.answer()

@dp.message(PaymentStates.waiting_for_custom_amount)
async def process_custom_payment_amount(message: Message, state: FSMContext):
    try:
        amount_uah = int(message.text.strip())
        if amount_uah < 1:
            await message.answer("❌ Мінімальна сума: 1 грн. Спробуйте ще раз.")
            return
    except ValueError:
        await message.answer("❌ Введіть ціле число (кількість гривень).")
        return

    data = await state.get_data()
    method = data.get('payment_method', 'privat')
    result = db.create_payment(message.from_user.id, amount_uah, method)
    if result['success']:
        await state.update_data(payment_id=result['payment_id'])
        await state.set_state(PaymentStates.waiting_for_screenshot)
        await message.answer(
            f"✅ **Заявку створено!**\n\n"
            f"🆔 Номер заявки: `{result['payment_id']}`\n"
            f"💳 Сума: {amount_uah} грн\n"
            f"💰 Отримаєте: {result['amount_coins']} монет\n\n"
            f"📸 **Тепер надішліть скріншот оплати** (фото).\n"
            f"Після перевірки адміністратором кошти будуть зараховані автоматично.",
            parse_mode="Markdown"
        )
    else:
        await message.answer(f"❌ {result['message']}", parse_mode="Markdown")
        await state.clear()

@dp.message(PaymentStates.waiting_for_screenshot, F.photo)
async def handle_payment_screenshot(message: Message, state: FSMContext):
    data = await state.get_data()
    payment_id = data.get('payment_id')
    if not payment_id:
        await message.answer("❌ Помилка: не знайдено активну заявку. Почніть спочатку.")
        await state.clear()
        return

    payment = db.get_payment_by_id(payment_id)
    if not payment:
        await message.answer("❌ Платіж не знайдено.")
        await state.clear()
        return

    photo = message.photo[-1]
    admin_ids = ADMINS
    caption = (
        f"🔔 **Новий платіж очікує підтвердження**\n\n"
        f"👤 Користувач: `{message.from_user.id}` (@{message.from_user.username})\n"
        f"💳 Сума: {payment['amount_uah']} грн\n"
        f"💰 Монет: {payment['amount_coins']}\n"
        f"🆔 Номер заявки: `{payment_id}`"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"confirm_payment_{payment_id}"),
            InlineKeyboardButton(text="❌ Відхилити", callback_data=f"reject_payment_{payment_id}")
        ]
    ])

    for admin_id in admin_ids:
        try:
            await bot.send_photo(
                chat_id=admin_id,
                photo=photo.file_id,
                caption=caption,
                reply_markup=markup,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Не вдалося надіслати адміну {admin_id}: {e}")

    await message.answer("✅ Дякуємо! Скріншот надіслано адміністратору. Очікуйте підтвердження.")
    await state.clear()

@dp.message(PaymentStates.waiting_for_screenshot)
async def payment_screenshot_invalid(message: Message):
    await message.answer("❌ Будь ласка, надішліть фото (скріншот оплати).")

@dp.callback_query(F.data.startswith("confirm_payment_"))
async def admin_confirm_payment(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Немає прав", show_alert=True)
        return
    payment_id = int(callback.data.replace("confirm_payment_", ""))
    result = db.confirm_payment(payment_id, callback.from_user.id)
    if result['success']:
        payment = db.get_payment_by_id(payment_id)
        try:
            await bot.send_message(
                payment['user_id'],
                f"✅ **Ваш платіж #{payment_id} підтверджено!**\n\n"
                f"💰 На ваш баланс зараховано {payment['amount_coins']} монет."
            )
        except Exception as e:
            logger.error(f"Не вдалося повідомити користувача {payment['user_id']}: {e}")
        try:
            await callback.message.edit_caption(
                caption=callback.message.caption + "\n\n✅ **Підтверджено адміністратором**"
            )
            if callback.message.reply_markup:
                await callback.message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                pass
            else:
                logger.error(f"Помилка при редагуванні повідомлення: {e}")
    else:
        await callback.answer(result['message'], show_alert=True)
    await callback.answer()

@dp.callback_query(F.data.startswith("reject_payment_"))
async def admin_reject_payment(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Немає прав", show_alert=True)
        return
    payment_id = int(callback.data.replace("reject_payment_", ""))
    result = db.cancel_payment(payment_id, callback.from_user.id)
    if result['success']:
        payment = db.get_payment_by_id(payment_id)
        try:
            await bot.send_message(
                payment['user_id'],
                f"❌ **Ваш платіж #{payment_id} відхилено.**\n\n"
                f"Зверніться до адміністратора для уточнення."
            )
        except Exception as e:
            logger.error(f"Не вдалося повідомити користувача {payment['user_id']}: {e}")
        try:
            await callback.message.edit_caption(
                caption=callback.message.caption + "\n\n❌ **Відхилено адміністратором**"
            )
            if callback.message.reply_markup:
                await callback.message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                pass
            else:
                logger.error(f"Помилка при редагуванні повідомлення: {e}")
    else:
        await callback.answer(result['message'], show_alert=True)
    await callback.answer()

# ============= ВИВЕДЕННЯ КОШТІВ =============
@dp.message(F.text == "💸 Вивести кошти")
@dp.message(Command("withdraw"))
async def cmd_withdraw_start(message: Message, state: FSMContext):
    await state.set_state(WithdrawalStates.waiting_for_amount)
    min_coins = MIN_WITHDRAWAL_UAH * EXCHANGE_RATE
    await message.answer(
        f"💸 **Виведення коштів**\n\n"
        f"Введіть суму в монетах, яку бажаєте вивести.\n"
        f"Мінімум: {min_coins} монет (≈ {MIN_WITHDRAWAL_UAH} грн):",
        parse_mode="Markdown"
    )

@dp.message(WithdrawalStates.waiting_for_amount)
async def process_withdraw_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text)
    except ValueError:
        await message.answer("❌ Введіть ціле число.")
        return
    min_coins = MIN_WITHDRAWAL_UAH * EXCHANGE_RATE
    if amount < min_coins:
        await message.answer(f"❌ Мінімальна сума виведення: {min_coins} монет (≈ {MIN_WITHDRAWAL_UAH} грн).")
        return
    balance = db.get_user_balance(message.from_user.id)
    if amount > balance:
        await message.answer(f"❌ Недостатньо коштів. Ваш баланс: {balance} монет.")
        return
    await state.update_data(amount=amount)
    await state.set_state(WithdrawalStates.waiting_for_bank)
    await message.answer("Введіть назву вашого банку (наприклад, Ощадбанк, ПриватБанк, Monobank):")

@dp.message(WithdrawalStates.waiting_for_bank)
async def process_withdraw_bank(message: Message, state: FSMContext):
    bank = message.text.strip()
    if len(bank) < 2:
        await message.answer("❌ Назва банку занадто коротка.")
        return
    await state.update_data(bank=bank)
    await state.set_state(WithdrawalStates.waiting_for_card)
    await message.answer("Введіть номер вашої карти (16 цифр):")

@dp.message(WithdrawalStates.waiting_for_card)
async def process_withdraw_card(message: Message, state: FSMContext):
    card = message.text.strip().replace(' ', '')
    if not card.isdigit() or len(card) != 16:
        await message.answer("❌ Номер карти має містити 16 цифр.")
        return
    data = await state.get_data()
    amount = data['amount']
    bank = data['bank']
    user_id = message.from_user.id
    username = message.from_user.username

    withdrawal_id = db.create_withdrawal(user_id, amount, bank, card)

    admin_ids = ADMINS
    caption = (
        f"🔔 **Нова заявка на виведення**\n\n"
        f"👤 Користувач: `{user_id}` (@{username})\n"
        f"💳 Сума: {amount} монет\n"
        f"🏦 Банк: {bank}\n"
        f"💳 Карта: `{card}`\n"
        f"🆔 Номер заявки: `{withdrawal_id}`"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"confirm_withdraw_{withdrawal_id}"),
            InlineKeyboardButton(text="❌ Відхилити", callback_data=f"reject_withdraw_{withdrawal_id}")
        ]
    ])
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, caption, reply_markup=markup, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Не вдалося надіслати адміну {admin_id}: {e}")

    await message.answer(
        f"✅ **Заявку на виведення створено!**\n\n"
        f"🆔 Номер заявки: `{withdrawal_id}`\n"
        f"💳 Сума: {amount} монет\n"
        f"🏦 Банк: {bank}\n"
        f"💳 Карта: `{card}`\n\n"
        f"Очікуйте підтвердження адміністратора. Після підтвердження кошти будуть списані з вашого балансу."
    )
    await state.clear()

@dp.callback_query(F.data.startswith("confirm_withdraw_"))
async def admin_confirm_withdrawal(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Немає прав", show_alert=True)
        return
    wid = int(callback.data.replace("confirm_withdraw_", ""))
    result = db.confirm_withdrawal(wid, callback.from_user.id)
    if result['success']:
        w = db.get_withdrawal_by_id(wid)
        try:
            await bot.send_message(
                w['user_id'],
                f"✅ **Ваше виведення #{wid} підтверджено!**\n\n"
                f"Сума {w['amount']} монет списана з вашого балансу.\n"
                f"Переказ буде здійснено на карту {w['card']} ({w['bank']})."
            )
        except Exception as e:
            logger.error(f"Не вдалося повідомити користувача {w['user_id']}: {e}")
        try:
            await callback.message.edit_text(
                callback.message.text + "\n\n✅ **Підтверджено адміністратором**",
                reply_markup=None
            )
        except Exception as e:
            logger.error(f"Помилка при редагуванні повідомлення: {e}")
    else:
        await callback.answer(result['message'], show_alert=True)
    await callback.answer()

@dp.callback_query(F.data.startswith("reject_withdraw_"))
async def admin_reject_withdrawal(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Немає прав", show_alert=True)
        return
    wid = int(callback.data.replace("reject_withdraw_", ""))
    result = db.cancel_withdrawal(wid, callback.from_user.id)
    if result['success']:
        w = db.get_withdrawal_by_id(wid)
        try:
            await bot.send_message(
                w['user_id'],
                f"❌ **Ваше виведення #{wid} відхилено.**\n\n"
                f"Зверніться до адміністратора для уточнення причин."
            )
        except Exception as e:
            logger.error(f"Не вдалося повідомити користувача {w['user_id']}: {e}")
        try:
            await callback.message.edit_text(
                callback.message.text + "\n\n❌ **Відхилено адміністратором**",
                reply_markup=None
            )
        except Exception as e:
            logger.error(f"Помилка при редагуванні повідомлення: {e}")
    else:
        await callback.answer(result['message'], show_alert=True)
    await callback.answer()

# ============= ПРОПОЗИЦІЇ (для адміна) =============
async def show_all_suggestions(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав.")
        return
    suggestions = db.get_all_suggestions(20)
    if not suggestions:
        await message.answer("📭 Немає жодної пропозиції.")
        return
    text = "📋 **Усі пропозиції**\n\n"
    for s in suggestions:
        status_emoji = {'new': '🆕', 'viewed': '👀', 'replied': '✅'}.get(s['status'], '❓')
        username = s['username'] or f"ID {s['user_id']}"
        text += f"{status_emoji} `#{s['id']}` від {username}: {s['message'][:50]}...\n"
        if s['admin_reply']:
            text += f"   ↪️ {s['admin_reply'][:50]}\n"
        text += "\n"
    if len(text) > 4000:
        for x in range(0, len(text), 3500):
            await message.answer(text[x:x+3500])
    else:
        await message.answer(text)

async def cmd_payments(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав.")
        return
    payments = db.get_pending_payments()
    if not payments:
        await message.answer("📭 Немає очікуючих платежів.")
        return
    text = "💳 **ОЧІКУЮЧІ ПЛАТЕЖІ**\n\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for p in payments:
        text += f"• #{p['id']} | {p['user_id']} | {p['amount_uah']} грн | {p['payment_method']}\n"
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"Переглянути #{p['id']}", callback_data=f"view_payment_{p['id']}")])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("view_payment_"))
async def view_payment(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Немає прав", show_alert=True)
        return
    pid = int(callback.data.replace("view_payment_", ""))
    payment = db.get_payment_by_id(pid)
    if not payment:
        await callback.answer("❌ Платіж не знайдено", show_alert=True)
        return
    text = (
        f"💳 **Платіж #{payment['id']}**\n\n"
        f"👤 Користувач: `{payment['user_id']}`\n"
        f"💳 Сума: {payment['amount_uah']} грн\n"
        f"💰 Монет: {payment['amount_coins']}\n"
        f"🏦 Спосіб: {payment['payment_method']}\n"
        f"📅 Створено: {payment['created_at']}\n"
        f"📌 Статус: {payment['status']}"
    )
    await callback.message.edit_text(text, reply_markup=get_payment_action_keyboard(pid), parse_mode="Markdown")
    await callback.answer()

# ============= ІГРИ =============
@dp.message(F.text == "🎰 Ігри")
async def games_menu(message: Message):
    await message.answer("🎮 **Ігровий зал**\n\nОберіть гру:", reply_markup=get_games_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data == "back_to_games")
async def back_to_games(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("🎮 **Ігровий зал**\n\nОберіть гру:", reply_markup=get_games_keyboard(), parse_mode="Markdown")

# ---------- Слоти ----------
@dp.callback_query(F.data == "game_slots")
async def slots_menu(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "🎰 **Слоти**\n\nВведіть суму ставки (ціле число, мінімум 10):\nАбо оберіть одну з запропонованих ставок:",
        reply_markup=get_slots_bet_keyboard(), parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("slots_bet_"))
async def slots_bet_chosen(callback: CallbackQuery, state: FSMContext):
    bet_str = callback.data.replace("slots_bet_", "")
    if bet_str == "custom":
        await state.set_state(SlotsState.waiting_for_bet)
        await callback.answer()
        await callback.message.edit_text(
            "🎰 **Слоти**\n\nВведіть суму ставки (ціле число, мінімум 10):",
            reply_markup=get_custom_bet_keyboard("slots"), parse_mode="Markdown"
        )
        return
    bet = int(bet_str)
    user_id = callback.from_user.id
    balance = db.get_user_balance(user_id)
    if bet > balance:
        await callback.answer(f"❌ Недостатньо коштів! Ваш баланс: {balance}", show_alert=True)
        return
    await callback.answer()
    await play_slots(callback, user_id, bet, state)

@dp.message(SlotsState.waiting_for_bet)
async def slots_custom_bet(message: Message, state: FSMContext):
    try:
        bet = int(message.text)
    except ValueError:
        await message.answer("❌ Введіть число!")
        return
    if bet < 10:
        await message.answer("❌ Мінімальна ставка: 10 монет")
        return
    user_id = message.from_user.id
    balance = db.get_user_balance(user_id)
    if bet > balance:
        await message.answer(f"❌ Недостатньо коштів! Ваш баланс: {balance}")
        return
    await play_slots(message, user_id, bet, state)

async def play_slots(target, user_id: int, bet: int, state: FSMContext):
    db.update_balance(user_id, -bet)
    symbols = [("🍒",2,35),("🍋",3,30),("🍊",4,25),("7️⃣",10,8),("💎",20,1),("👑",50,1)]
    items = [s[0] for s in symbols]
    weights = [s[2] for s in symbols]
    reels = random.choices(items, weights=weights, k=3)
    win_mult = 0
    if reels[0] == reels[1] == reels[2]:
        for sym, mult, _ in symbols:
            if sym == reels[0]:
                win_mult = mult
                break
    elif reels[0] == reels[1] or reels[1] == reels[2]:
        win_mult = 1.5
    win_amount = int(bet * win_mult) if win_mult > 0 else 0
    db.record_game_result(user_id, "slots", bet, win_amount)
    if win_amount > 0:
        multiplier = win_amount / bet
        if win_amount >= BIG_WIN_THRESHOLD or multiplier >= BIG_WIN_MULTIPLIER:
            win_id = db.log_big_win(user_id, "slots", bet, win_amount)
            user = db.get_or_create_user(user_id, None)
            username = user.get('username', f"ID {user_id}")
            for admin_id in ADMINS:
                try:
                    await bot.send_message(admin_id, f"🔥🔥🔥 **ЗАНОС!** 🔥🔥🔥\n\n👤 Гравець: @{username}\n🎰 Гра: Слоти\n💰 Ставка: {bet}\n💎 Виграш: {win_amount} (×{multiplier:.1f})\n🆔 ID заносу: `{win_id}`", parse_mode="Markdown")
                except:
                    pass
            if CHANNEL_ID:
                try:
                    await bot.send_message(CHANNEL_ID, f"🔥 **НОВИЙ ЗАНОС!** 🔥\n\nГравець @{username} щойно виграв **{win_amount}** монет у слотах!\nСтавка: {bet}, множник: ×{multiplier:.1f}", parse_mode="Markdown")
                except:
                    pass
    db.update_daily_stats(user_id, 'games', 1)
    if win_amount > 0:
        db.update_daily_stats(user_id, 'biggest_win', win_amount)
    if win_amount > 0:
        db.update_balance(user_id, win_amount)
        result_text = f"🎉 **Виграш!**\n\n| {reels[0]} | {reels[1]} | {reels[2]} |\n\nВиграш: {win_amount} монет (x{win_mult})"
    else:
        result_text = f"😢 **Програш**\n\n| {reels[0]} | {reels[1]} | {reels[2]} |\n\nСпробуйте ще раз!"
    new_bal = db.get_user_balance(user_id)
    result_text += f"\n💰 Баланс: {new_bal}"
    await state.update_data(last_slots_bet=bet)
    again_kb = get_play_again_keyboard("slots", bet)
    if isinstance(target, Message):
        await target.answer(result_text, reply_markup=again_kb, parse_mode="Markdown")
    else:
        try:
            await target.message.edit_text(result_text, reply_markup=again_kb, parse_mode="Markdown")
        except:
            await target.message.answer(result_text, reply_markup=again_kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("slots_again_"))
async def slots_again(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_bet = data.get('last_slots_bet')
    if not last_bet:
        await callback.answer("❌ Немає даних для повторної гри", show_alert=True)
        return
    user_id = callback.from_user.id
    balance = db.get_user_balance(user_id)
    if last_bet > balance:
        await callback.answer(f"❌ Недостатньо коштів! Ваш баланс: {balance}", show_alert=True)
        return
    await callback.answer()
    await play_slots(callback.message, user_id, last_bet, state)

@dp.callback_query(F.data == "slots_change")
async def slots_change(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await slots_menu(callback)

@dp.callback_query(F.data == "slots_cancel")
async def slots_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await back_to_games(callback)

# ---------- Рулетка ----------
@dp.callback_query(F.data == "game_roulette")
async def roulette_menu(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("🎲 **Рулетка**\n\nОберіть тип ставки:", reply_markup=get_roulette_bet_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data == "roulette_number_choose")
async def roulette_choose_number(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("🔢 Оберіть число від 0 до 36:", reply_markup=get_roulette_number_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("roulette_") & ~F.data.startswith("roulette_bet_") & ~F.data.startswith("roulette_again_") & ~F.data.startswith("roulette_amount_") & ~F.data.startswith("roulette_change"))
async def roulette_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    data = callback.data
    if data == "roulette_red":
        bet_type, bet_val, mult, type_text = "color", "red", 2, "🔴 Червоне"
    elif data == "roulette_black":
        bet_type, bet_val, mult, type_text = "color", "black", 2, "⚫ Чорне"
    elif data == "roulette_green":
        bet_type, bet_val, mult, type_text = "color", "green", 36, "🟢 Зелене"
    elif data.startswith("roulette_number_"):
        num = int(data.replace("roulette_number_", ""))
        bet_type, bet_val, mult, type_text = "number", num, 36, f"Число {num}"
    else:
        await callback.answer("❌ Невідома ставка", show_alert=True)
        return
    await state.update_data(bet_type=bet_type, bet_value=bet_val, multiplier=mult)
    await state.set_state(RouletteState.waiting_for_bet)
    await callback.answer()
    await callback.message.edit_text(f"🎲 **Рулетка** (обрано: {type_text})\n\nОберіть суму ставки:", reply_markup=get_roulette_amount_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("roulette_amount_"))
async def roulette_amount_chosen(callback: CallbackQuery, state: FSMContext):
    amount_str = callback.data.replace("roulette_amount_", "")
    if amount_str == "custom":
        await callback.answer()
        await callback.message.edit_text(
            "🎲 **Рулетка**\n\nВведіть суму ставки (ціле число, мінімум 10):",
            reply_markup=get_custom_bet_keyboard("roulette"), parse_mode="Markdown"
        )
        return
    bet = int(amount_str)
    user_id = callback.from_user.id
    balance = db.get_user_balance(user_id)
    if bet > balance:
        await callback.answer(f"❌ Недостатньо коштів! Ваш баланс: {balance}", show_alert=True)
        return
    data = await state.get_data()
    bet_type = data.get('bet_type')
    bet_val = data.get('bet_value')
    mult = data.get('multiplier')
    if not bet_type:
        await callback.answer("❌ Ставка не обрана", show_alert=True)
        await state.clear()
        await roulette_menu(callback)
        return
    await callback.answer()
    await play_roulette(callback.message, user_id, bet, bet_type, bet_val, mult, state)

@dp.message(RouletteState.waiting_for_bet)
async def roulette_custom_bet(message: Message, state: FSMContext):
    try:
        bet = int(message.text)
    except ValueError:
        await message.answer("❌ Введіть число!")
        return
    if bet < 10:
        await message.answer("❌ Мінімальна ставка: 10 монет")
        return
    user_id = message.from_user.id
    balance = db.get_user_balance(user_id)
    if bet > balance:
        await message.answer(f"❌ Недостатньо коштів! Ваш баланс: {balance}")
        return
    data = await state.get_data()
    bet_type = data.get('bet_type')
    bet_val = data.get('bet_value')
    mult = data.get('multiplier')
    if not bet_type:
        await message.answer("❌ Ставка не обрана")
        await state.clear()
        await message.answer("Оберіть тип ставки заново:", reply_markup=get_roulette_bet_keyboard())
        return
    await play_roulette(message, user_id, bet, bet_type, bet_val, mult, state)

async def play_roulette(target, user_id: int, bet: int, bet_type: str, bet_val, mult: int, state: FSMContext):
    db.update_balance(user_id, -bet)
    number = random.randint(0, 36)
    color = "green" if number == 0 else ("red" if number in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else "black")
    win = (bet_type == "color" and bet_val == color) or (bet_type == "number" and bet_val == number)
    if win:
        win_amount = bet * mult
        db.update_balance(user_id, win_amount)
        result_text = f"🎉 **Виграш!** Випало {number} ({color}).\nВиграш: {win_amount} монет"
    else:
        win_amount = 0
        result_text = f"😢 **Програш!** Випало {number} ({color})."
    db.record_game_result(user_id, "roulette", bet, win_amount)
    if win_amount > 0:
        multiplier_real = win_amount / bet
        if win_amount >= BIG_WIN_THRESHOLD or multiplier_real >= BIG_WIN_MULTIPLIER:
            win_id = db.log_big_win(user_id, "roulette", bet, win_amount)
            user = db.get_or_create_user(user_id, None)
            username = user.get('username', f"ID {user_id}")
            for admin_id in ADMINS:
                try:
                    await bot.send_message(admin_id, f"🔥🔥🔥 **ЗАНОС!** 🔥🔥🔥\n\n👤 Гравець: @{username}\n🎰 Гра: Рулетка\n💰 Ставка: {bet}\n💎 Виграш: {win_amount} (×{multiplier_real:.1f})\n🆔 ID заносу: `{win_id}`", parse_mode="Markdown")
                except:
                    pass
            if CHANNEL_ID:
                try:
                    await bot.send_message(CHANNEL_ID, f"🔥 **НОВИЙ ЗАНОС!** 🔥\n\nГравець @{username} щойно виграв **{win_amount}** монет у рулетці!\nСтавка: {bet}, множник: ×{multiplier_real:.1f}", parse_mode="Markdown")
                except:
                    pass
    db.update_daily_stats(user_id, 'games', 1)
    if win_amount > 0:
        db.update_daily_stats(user_id, 'biggest_win', win_amount)
    new_bal = db.get_user_balance(user_id)
    result_text += f"\n💰 Баланс: {new_bal}"
    await state.update_data(last_roulette_bet=bet, last_roulette_type=bet_type, last_roulette_value=bet_val, last_roulette_multiplier=mult)
    again_kb = get_play_again_keyboard("roulette", bet)
    if isinstance(target, Message):
        await target.answer(result_text, reply_markup=again_kb, parse_mode="Markdown")
    else:
        await target.answer(result_text, reply_markup=again_kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("roulette_again_"))
async def roulette_again(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_bet = data.get('last_roulette_bet')
    last_type = data.get('last_roulette_type')
    last_val = data.get('last_roulette_value')
    last_mult = data.get('last_roulette_multiplier')
    if not last_bet or not last_type:
        await callback.answer("❌ Немає даних для повторної гри. Оберіть ставку заново.", show_alert=True)
        await roulette_menu(callback)
        return
    user_id = callback.from_user.id
    balance = db.get_user_balance(user_id)
    if last_bet > balance:
        await callback.answer(f"❌ Недостатньо коштів! Ваш баланс: {balance}", show_alert=True)
        return
    await callback.answer()
    await play_roulette(callback.message, user_id, last_bet, last_type, last_val, last_mult, state)

@dp.callback_query(F.data == "roulette_change")
async def roulette_change(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await roulette_menu(callback)

@dp.callback_query(F.data == "roulette_cancel")
async def roulette_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await back_to_games(callback)

# ---------- Статистика ігор ----------
@dp.callback_query(F.data == "game_stats")
async def game_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
    stats = db.get_game_stats(user_id)
    if stats["total_games"] == 0:
        text = "📊 **Статистика ігор**\n\nВи ще не грали в жодну гру."
    else:
        text = (
            f"📊 **Статистика ігор**\n\n"
            f"🎮 Всього ігор: {stats['total_games']}\n"
            f"💰 Загальний прибуток: {stats['total_profit']} монет\n\n"
        )
        game_names = {"slots": "🎰 Слоти", "roulette": "🎲 Рулетка"}
        for game_type, game_name in game_names.items():
            if game_type in stats["by_game"]:
                g = stats["by_game"][game_type]
                text += f"\n{game_name}:\n  • Ігор: {g['games']}\n  • Поставлено: {g['total_bet']}\n  • Виграно: {g['total_win']}\n  • Прибуток: {g['profit']}\n"
            else:
                text += f"\n{game_name}: ще не грали\n"
    await callback.message.edit_text(text, reply_markup=get_back_to_games_keyboard(), parse_mode="Markdown")
    await callback.answer()

# ============= СОЦІАЛЬНЕ МЕНЮ =============
@dp.message(F.text == "👥 Соціальне")
async def social_menu(message: Message):
    await message.answer("👥 **Соціальне меню**\n\nОберіть розділ:", reply_markup=get_social_keyboard(), parse_mode="Markdown")

@dp.message(F.text == "👥 Друзі")
async def social_friends(message: Message):
    await cmd_friends(message)

@dp.message(F.text == "💬 Пропозиції")
async def social_suggestions(message: Message):
    await message.answer("💬 **Пропозиції**\n\nНадіслати пропозицію: /suggest <текст>\nПереглянути свої пропозиції: /mysuggestions", parse_mode="Markdown")

@dp.message(F.text == "🏆 Приватні турніри")
async def social_tournaments(message: Message):
    await message.answer("🏆 **Приватні турніри**\n\nСтворити турнір: /create_tournament\nДолучитися: /join_tournament <ID>", parse_mode="Markdown")

@dp.message(F.text == "🔙 Назад")
async def handle_back_from_social(message: Message):
    user_id = message.from_user.id
    if is_admin(user_id):
        markup = get_admin_keyboard()
    elif db.is_moderator(user_id):
        markup = get_moderator_keyboard()
    else:
        markup = get_main_keyboard()
    await message.answer("Головне меню", reply_markup=markup)

# ---------- Пропозиції (для користувачів) ----------
@dp.message(Command("suggest"))
async def cmd_suggest(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("ℹ Використання: /suggest <текст пропозиції>\nНапишіть свою ідею для покращення бота.")
        return
    text = parts[1]
    db.add_suggestion(message.from_user.id, text)
    await message.answer("✅ Дякуємо за пропозицію! Вона буде розглянута адміністрацією.")

@dp.message(Command("mysuggestions"))
async def cmd_my_suggestions(message: Message):
    suggestions = db.get_suggestions_by_user(message.from_user.id)
    if not suggestions:
        await message.answer("📭 У вас немає відправлених пропозицій.")
        return
    text = "📋 **Ваші пропозиції**\n\n"
    for s in suggestions:
        status_emoji = "🆕" if s['status'] == 'new' else "👀" if s['status'] == 'viewed' else "✅"
        text += f"{status_emoji} `#{s['id']}`: {s['message'][:50]}... ({s['status']})\n"
        if s['admin_reply']:
            text += f"   Відповідь: {s['admin_reply']}\n"
    await message.answer(text)

# ---------- Друзі ----------
@dp.message(Command("friends"))
async def cmd_friends(message: Message):
    await message.answer(
        "👥 **Меню друзів**\n\n"
        "• `/addfriend <id>` – надіслати запит на дружбу\n"
        "• `/myfriends` – список друзів\n"
        "• `/friendrequests` – запити на дружбу",
        parse_mode="Markdown"
    )

@dp.message(Command("addfriend"))
async def cmd_add_friend(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("ℹ Використання: /addfriend <ID_користувача>")
        return
    try:
        friend_id = int(parts[1])
    except:
        await message.answer("❌ ID має бути числом")
        return
    if db.send_friend_request(message.from_user.id, friend_id):
        await message.answer(f"✅ Запит на дружбу надіслано користувачу {friend_id}")
        try:
            await bot.send_message(friend_id, f"👤 Користувач {message.from_user.id} (@{message.from_user.username}) надіслав вам запит на дружбу.\nПрийняти: /acceptfriend {message.from_user.id}")
        except:
            pass
    else:
        await message.answer("❌ Не вдалося надіслати запит (можливо, ви вже друзі або користувач не існує)")

@dp.message(Command("acceptfriend"))
async def cmd_accept_friend(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("ℹ Використання: /acceptfriend <ID_користувача>")
        return
    try:
        friend_id = int(parts[1])
    except:
        await message.answer("❌ ID має бути числом")
        return
    if db.accept_friend_request(message.from_user.id, friend_id):
        await message.answer(f"✅ Ви прийняли запит на дружбу від {friend_id}")
        await bot.send_message(friend_id, f"✅ Користувач {message.from_user.id} прийняв ваш запит на дружбу!")
    else:
        await message.answer("❌ Не вдалося прийняти запит (можливо, його не існує)")

@dp.message(Command("myfriends"))
async def cmd_my_friends(message: Message):
    friends = db.get_friends(message.from_user.id)
    if not friends:
        await message.answer("👥 У вас ще немає друзів. Додайте через /addfriend")
        return
    text = "👥 **Ваші друзі**\n\n"
    for f in friends:
        text += f"• @{f['username'] or f['user_id']} – баланс: {f['balance']}\n"
    await message.answer(text)

# ---------- Приватні турніри ----------
@dp.message(Command("create_tournament"))
async def cmd_create_private_tournament(message: Message):
    parts = message.text.split()
    if len(parts) < 5:
        await message.answer("ℹ Використання: /create_tournament <назва> <внесок> <макс учасників> <тривалість (год)>\nНаприклад: /create_tournament МояБитва 100 8 24")
        return
    name = parts[1]
    try:
        fee = int(parts[2])
        max_part = int(parts[3])
        duration = int(parts[4])
    except:
        await message.answer("❌ Внесок, кількість учасників і тривалість мають бути числами")
        return
    if fee < 0:
        await message.answer("❌ Внесок не може бути від'ємним")
        return
    if max_part < 2:
        await message.answer("❌ Мінімум 2 учасники")
        return
    balance = db.get_user_balance(message.from_user.id)
    if balance < fee:
        await message.answer(f"❌ Недостатньо коштів. Потрібно {fee} монет")
        return
    db.update_balance(message.from_user.id, -fee)
    tournament_id = db.create_private_tournament(message.from_user.id, name, fee, max_part, duration)
    db.join_private_tournament(tournament_id, message.from_user.id)
    await message.answer(f"✅ Турнір «{name}» створено! ID: {tournament_id}\nВнесок: {fee} монет, макс. учасників: {max_part}, тривалість: {duration} год.\nЗапрошуйте друзів командою /join_tournament {tournament_id}")

@dp.message(Command("join_tournament"))
async def cmd_join_private_tournament(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("ℹ Використання: /join_tournament <ID турніру>")
        return
    try:
        t_id = int(parts[1])
    except:
        await message.answer("❌ ID має бути числом")
        return
    if db.join_private_tournament(t_id, message.from_user.id):
        await message.answer(f"✅ Ви долучилися до турніру #{t_id}!")
    else:
        await message.answer("❌ Не вдалося долучитися (турнір не знайдено, повний або недостатньо коштів)")

# ============= ТОП ЗАНОСІВ =============
@dp.message(F.text == "🏆 Топ заносів")
@dp.message(Command("top_wins"))
async def cmd_top_wins(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав.")
        return
    top = db.get_top_big_wins(10)
    if not top:
        await message.answer("📭 Поки що немає заносів.")
        return
    text = "🏆 **ТОП-10 НАЙБІЛЬШИХ ВИГРАШІВ** 🏆\n\n"
    for i, w in enumerate(top, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "▫️"
        username = w['username'] or f"ID {w['user_id']}"
        text += f"{medal} {i}. @{username} — {w['win_amount']} монет ({w['game_type']})\n"
        text += f"   📅 {w['created_at'][:16]}\n"
    await message.answer(text, parse_mode="Markdown")

# ============= НАЛАШТУВАННЯ СПОВІЩЕНЬ =============
@dp.message(F.text == "⚙️ Налаштування")
async def settings_menu(message: Message):
    user_id = message.from_user.id
    settings = db.get_notification_settings(user_id)
    await message.answer(
        "🔔 **Налаштування сповіщень**\n\nОберіть, які сповіщення ви хочете отримувати:",
        reply_markup=get_settings_keyboard(settings['bonus'], settings['market']),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "toggle_bonus")
async def toggle_bonus_notification(callback: CallbackQuery):
    user_id = callback.from_user.id
    db.toggle_notification(user_id, 'bonus')
    settings = db.get_notification_settings(user_id)
    await callback.message.edit_reply_markup(reply_markup=get_settings_keyboard(settings['bonus'], settings['market']))
    await callback.answer("Налаштування збережено")

@dp.callback_query(F.data == "toggle_market")
async def toggle_market_notification(callback: CallbackQuery):
    user_id = callback.from_user.id
    db.toggle_notification(user_id, 'market')
    settings = db.get_notification_settings(user_id)
    await callback.message.edit_reply_markup(reply_markup=get_settings_keyboard(settings['bonus'], settings['market']))
    await callback.answer("Налаштування збережено")

# ============= ПОВЕРНЕННЯ =============
@dp.callback_query(F.data == "back_to_main")
async def handle_back_to_main(callback: CallbackQuery):
    await callback.answer()
    user = db.get_or_create_user(callback.from_user.id, callback.from_user.username)
    text = f"🎮 Головне меню\n\n💰 Баланс: {user['balance']} монет"
    if is_admin(callback.from_user.id):
        markup = get_admin_keyboard()
    elif db.is_moderator(callback.from_user.id):
        markup = get_moderator_keyboard()
    else:
        markup = get_main_keyboard()
    await callback.message.answer(text, reply_markup=markup, parse_mode="Markdown")

@dp.callback_query(F.data == "back_to_inventory")
async def handle_back_to_inventory(callback: CallbackQuery):
    inv = db.get_user_inventory(callback.from_user.id)
    if not inv:
        await callback.message.delete()
        await callback.message.answer("🎒 Інвентар порожній")
        await callback.answer()
        return
    text = f"🎒 **ІНВЕНТАР** (всього: {len(inv)})\n\n"
    for item in inv[:5]:
        e = get_rarity_emoji(item['rarity'])
        text += f"• `#{item['id']}` {e} {item['skin_name']}\n"
    try:
        await callback.message.delete()
    except:
        pass
    await callback.message.answer(text, reply_markup=get_inventory_keyboard(inv, 0), parse_mode="Markdown")
    await callback.answer()

# ============= АДМІН-СТАТИСТИКА =============
@dp.message(Command("adminstats"))
async def cmd_admin_stats(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас немає прав.")
        return
    stats = db.get_admin_stats()
    text = (
        f"📊 **Статистика бота**\n\n"
        f"👥 Користувачів: {stats['total_users']}\n"
        f"🎒 Скінів: {stats['total_skins']}\n"
        f"💳 Платежів: {stats['total_payments']} на суму {stats['total_payments_sum']} монет\n"
        f"🎮 Всього ігор: {stats['total_games']}\n"
        f"📈 Активних за 24 год: {stats['active_24h']}\n"
        f"📊 Конверсія платежів: {stats['payment_conversion']:.1f}%\n"
    )
    await message.answer(text)

@dp.message(Command("check_rare_drops"))
async def cmd_check_rare_drops(message: Message):
    if not is_admin(message.from_user.id):
        return
    drops = db.get_unnotified_rare_drops()
    if not drops:
        await message.answer("📭 Немає нових рідкісних випадінь.")
        return
    for drop in drops:
        user = db.get_or_create_user(drop['user_id'], None)
        await bot.send_message(message.chat.id, f"🔥 **Рідкісне випадіння!**\n\nГравець @{user['username']} вибив {drop['rarity']} скін:\n**{drop['skin_name']}** з кейсу {drop['case_name']}!")
        db.mark_rare_drop_notified(drop['id'])
    await message.answer("✅ Сповіщення надіслано.")

# ============= ЗАПУСК =============
async def on_startup():
    try:
        await bot.delete_webhook()
        await bot.set_chat_menu_button(menu_button=MenuButtonDefault())
        scheduler.add_job(check_bonus_reminders, 'interval', hours=1)
        scheduler.start()
        logger.info("Шедулер запущено")
    except Exception as e:
        logger.error(f"Помилка при налаштуванні: {e}")

async def on_shutdown():
    logger.info("Бот зупиняється")
    scheduler.shutdown()
    await bot.session.close()
    db.close()

if __name__ == "__main__":
    import asyncio
    print("=" * 50)
    print("🤖 ЗАПУСК GGSTANDOFF БОТА")
    print("=" * 50)
    try:
        logger.info("Запуск бота...")
        db.check_tournaments()
        users_count = db.get_total_users_count()
        logger.info(f"✅ База даних: {users_count} користувачів")
        print("\n✅ Бот запущено!")
        print("📝 Логи в bot.log")
        print("=" * 50)
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)
        asyncio.run(dp.start_polling(bot))
    except KeyboardInterrupt:
        print("\n" + "=" * 50)
        print("❌ Бот вимкнено")
        print("=" * 50)
    except Exception as e:
        logger.error(f"❌ Помилка: {e}")
        print(f"\n❌ Помилка: {e}")
    finally:
        print("\n✅ Робота завершена")