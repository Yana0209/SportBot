from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import aiohttp
import atexit
import logging
import sqlite3

logging.basicConfig(level=logging.INFO)

OPENWEATHERMAP_API_KEY = "54251196aae71c0a50fab2af69547bf7"

advice_requests = {}
router = Router()

# Ініціалізація бази даних SQLite
DATABASE_NAME = 'sport_bot.db'
conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS carts (
    user_id INTEGER,
    item_name TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS advice (
    user_id INTEGER,
    question TEXT
)
''')

conn.commit()

user_carts = {}

async def get_weather(city, api_key):
    base_url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": api_key,
        "units": "metric",
        "lang": "ua"
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    logging.error(f"Помилка API OpenWeatherMap: Статус {response.status}")
                    return None
        except aiohttp.ClientError as e:
            logging.error(f"Помилка клієнта aiohttp: {e}")
            return None

async def send_weather_info(message: types.Message, city: str):
    weather_data = await get_weather(city, OPENWEATHERMAP_API_KEY)
    if weather_data:
        try:
            description = weather_data['weather'][0]['description']
            temp = weather_data['main']['temp']
            feels_like = weather_data['main']['feels_like']
            humidity = weather_data['main']['humidity']
            wind_speed = weather_data['wind']['speed']
            await message.answer(
                f"Погода в місті {city}:\n"
                f"Опис: {description}\n"
                f"Температура: {temp}°C (відчувається як {feels_like}°C)\n"
                f"Вологість: {humidity}%\n"
                f"Швидкість вітру: {wind_speed} м/с"
            )
        except KeyError:
            await message.answer("Отримано некоректні дані про погоду від API.")
    else:
        await message.answer(f"Не вдалося отримати погоду для міста {city}.")

@router.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name

    # Перевіряємо, чи є користувач вже в базі даних
    cursor.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    existing_user = cursor.fetchone()

    if not existing_user:
        # Додаємо нового користувача в базу даних
        cursor.execute("INSERT INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)",
                       (user_id, username, first_name, last_name))
        conn.commit()
        logging.info(f"Додано нового користувача: {user_id}, {username}, {first_name} {last_name}")

    user_name = first_name
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🏊 Плавання", callback_data="sport_плавання")
    keyboard.button(text="⚽ Футбол", callback_data="sport_футбол")
    keyboard.button(text="🏐 Волейбол", callback_data="sport_волейбол")
    await message.answer(
        f"Привіт, {user_name}! 👋\nЯ бот для підбору спортивного інвентаря.\nБудь ласка, оберіть вид спорту:",
        reply_markup=keyboard.adjust(2).as_markup()
    )

    reply_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Підібраний інвентар"),
            ],
            [
                KeyboardButton(text="Запитати пораду"),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    await message.answer("Або скористайтеся кнопками нижче:", reply_markup=reply_keyboard)

    # Одразу запитуємо та надсилаємо погоду для Києва
    await send_weather_info(message, "Kyiv")

@router.message(lambda message: message.text and message.text.lower().startswith("погода в"))
async def handle_weather_request(message: types.Message):
    city = message.text[len("погода в"):].strip()
    if city:
        await send_weather_info(message, city)
    else:
        await message.answer("Будь ласка, вкажіть назву міста після 'погода в'.")

@router.callback_query(lambda c: c.data.startswith("sport_"))
async def sport_chosen_handler(callback: types.CallbackQuery):
    chosen_sport = callback.data.split("_")[1]
    await callback.message.answer(f"Ви обрали вид спорту: {chosen_sport}.\nТепер оберіть, який саме інвентар вас цікавить для {chosen_sport}:")

    inventory_keyboard = InlineKeyboardBuilder()
    if chosen_sport == "плавання":
        inventory_keyboard.button(text="Окуляри для плавання", callback_data="item_окуляри")
        inventory_keyboard.button(text="Шапочка для плавання", callback_data="item_шапочка")
        inventory_keyboard.button(text="Плавки/купальник", callback_data="item_купальний_костюм")
    elif chosen_sport == "футбол":
        inventory_keyboard.button(text="Футбольний м'яч", callback_data="item_м'яч")
        inventory_keyboard.button(text="Футбольні бутси", callback_data="item_бутси")
        inventory_keyboard.button(text="Форма футбольна", callback_data="item_форма")
    elif chosen_sport == "волейбол":
        inventory_keyboard.button(text="Волейбольний м'яч", callback_data="item_м'яч")
        inventory_keyboard.button(text="Наколінники", callback_data="item_наколінники")
        inventory_keyboard.button(text="Спортивна форма", callback_data="item_форма")

    await callback.message.answer(
        text="Оберіть інвентар:",
        reply_markup=inventory_keyboard.adjust(1).as_markup()
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("item_"))
async def item_chosen_handler(callback: types.CallbackQuery):
    chosen_item = callback.data.split("_")[1]

    if chosen_item == "окуляри":
        builder = InlineKeyboardBuilder()
        builder.button(text="Додати", callback_data="add_to_cart_окуляри_speedo")
        await callback.message.answer(
            f"Пропозиція 1: - <a href=\"https://sportano.ua/p/202107/okuljari-dlja-plavannja-speedo-biofuse-2-0-black-white-smoke-8-00233214501?utm_source=google&utm_medium=cpc&utm_campaign=21796485290&utm_content=&utm_term=&gad_source=1&gclid=CjwKCAjwzMi_BhACEiwAX4YZUEeSMSJaLOswSDri9Ji9s0V6gcDLj7SqeBOHaYtmdzbaDRZkRiMIjhoCByEQAvD_BwE\">Окуляри для плавання Speedo Futura Biofuse Flexiseal</a>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=builder.as_markup()
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="Додати", callback_data="add_to_cart_окуляри_arena")
        await callback.message.answer(
            f"Пропозиція 2: - <a href=\"https://www.googleadservices.com/pagead/aclk?sa=L&ai=DChcSEwjd2I6mwsOMAxXOTpEFHYceAkMYABABGgJscg&co=1&gclid=CjwKCAjwzMi_BhACEiwAX4YZUGa0gYIWURGF1VcJlhz_1wgWgdrWS8FIJ1mRvLYye6EdO1DmsCkXtBoCxbkQAvD_BwE&ohost=www.google.com&cid=CAESVuD2Y0jt-9oYyTwoRpX79PHD1pdDTyAB6R8M8PSXzN6n2wYC8BSnaeBbzD7DuDWXJrpgKjnSQFG70WUYBB7y1j5F3yYVuI25J_D7aYD1Ham4rukS-oPK&sig=AOD64_20SJowG430KwQxN6j-qP6P4uhOmA&ctype=5&q=&ved=2ahUKEwiR7YimwsOMAxVqIhAIHZ7mK1IQ9aACKAB6BAgEEA8&adurl=\">Окуляри для плавання Arena Cobra Core Mirror</a>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=builder.as_markup()
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="Додати", callback_data="add_to_cart_окуляри_tyr")
        await callback.message.answer(
            f"Пропозиція 3: - <a href=\"https://sportano.ua/p/175381/okuljari-dlja-plavannja-tyr-socket-rockets-2-0-smoke-lgl2-041?utm_source=google&utm_medium=cpc&utm_campaign=21796485290&utm_content=&utm_term=&gad_source=1&gclid=CjwKCAjwzMi_BhACEiwAX4YZULxtjapHw5uC-BY2orPWRpaksBaB4Yk1o2LfsNp1o0o4xwpJPojXzhoCaTEQAvD_BwE\">Окуляри для плавання TYR Socket Rockets 2.0 </a>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=builder.as_markup()
        )
    elif chosen_item == "шапочка":
        builder = InlineKeyboardBuilder()
        builder.button(text="Додати", callback_data="add_to_cart_шапочка_arena")
        await callback.message.answer(
            f"Пропозиція 1: - <a href=\"https://sportano.ua/p/211255/shapochka-dlja-plavannja-arena-moulded-pro-ii-white?utm_source=google&utm_medium=cpc&utm_campaign=21796485290&utm_content=&utm_term=&gad_source=1&gclid=CjwKCAjwzMi_BhACEiwAX4YZUCale_cN7USomPnOYIDWLzXxmx_akdJLQM2BC8rSKvX3bUUcuB4fexoCnd0QAvD_BwE\">Шапочка для плавання Arena Moulded Race Cap</a>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=builder.as_markup()
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="Додати", callback_data="add_to_cart_шапочка_speedo")
        await callback.message.answer(
            f"Пропозиція 2: - <a href=\"https://sportano.ua/p/135112/shapochka-dlja-plavannja-speedo-ultra-pace-chorna-8-017310001?utm_source=google&utm_medium=cpc&utm_campaign=21796485290&utm_content=&utm_term=&gad_source=1&gclid=CjwKCAjwzMi_BhACEiwAX4YZUJVytunmnkKJ6dBG4HnzYdUiqX2i0xthUiLaDkNe4OJPiOX-ARweQRoCcRIQAvD_BwE\">Шапочка для плавання Speedo Pace Cap AU</a>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=builder.as_markup()
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="Додати", callback_data="add_to_cart_шапочка_madwave")
        await callback.message.answer(
            f"Пропозиція 3: - <a href=\"https://sportano.ua/p/346297/shapochka-dlja-plavannja-aqua-speed-ob-emna-shapochka-dlja-vuh-chorna?utm_source=google&utm_medium=cpc&utm_campaign=21796485290&utm_content=&utm_term=&gad_source=1&gclid=CjwKCAjwzMi_BhACEiwAX4YZUD6nnwl-HQ78mvBb8P2aq4PUQlWFK_tslkiLUiUEEh1vfObRRX4cThoCUjIQAvD_BwE\">Шапочка для плавання Mad Wave Race Silicone</a>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=builder.as_markup()
        )
    elif chosen_item == "купальний_костюм":
        builder = InlineKeyboardBuilder()
        builder.button(text="Додати", callback_data="add_to_cart_купальник_speedo_жіночий")
        await callback.message.answer(
            f"Пропозиція 1: - <a href=\"https://rozetka.com.ua/ua/speedo_5053744154992/p306724153/\">Жіночий купальник Speedo LZR Racer X Openback Kneeskin</a>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=builder.as_markup()
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="Додати", callback_data="add_to_cart_купальник_arena_чоловічий")
        await callback.message.answer(
            f"Пропозиція 2: - <a href=\"https://meryl.com.ua/kombinezon-d-plav-arena-carbon-air2-jammer-001130-853?gclid=CjwKCAjwzMi_BhACEiwAX4YZUHcxlzykJnqCiP2Mj0ZGXo2PE8P07PuKP4ttlo1DQtn0UukbmhPr5BoCvmEQAvD_BwE\">Чоловічі плавки Arena Carbon Race Jammer</a>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=builder.as_markup()
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="Додати", callback_data="add_to_cart_купальник_funkita_дитячий")
        await callback.message.answer(
            f"Пропозиція 3: - <a href=\"https://sportano.ua/p/538104/kupal-nik-sucil-nij-ditjachij-funkita-strapped-in-one-piece-rockie-high?utm_source=google&utm_medium=cpc&utm_campaign=20416458475&utm_content=667551714643&utm_term=&gad_source=1&gclid=CjwKCAjwzMi_BhACEiwAX4YZUDWGy_gcLzI3twdWCpLshaVhykw8Ysan4ZQ7TByYX5RhkB5KZe5HeRoCglIQAvD_BwE\">Дитячий купальник Funkita Single Strap</a>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=builder.as_markup()
        )
    elif chosen_item == "м'яч": # Для футболу та волейболу
        builder = InlineKeyboardBuilder()
        builder.button(text="Додати", callback_data="add_to_cart_м'яч_adidas")
        await callback.message.answer(
            f"Пропозиція 1: - <a href=\"https://rozetka.com.ua/ua/363948705/p363948705/?gad_source=1&gclid=CjwKCAjwzMi_BhACEiwAX4YZUBGzj-aFkqtavg8RN1i8p00SKVWmrUpq84cQLCXz-kDu_BjIBEWCdBoC1yMQAvD_BwE\">Футбольний м'яч Adidas Al Rihla Pro</a>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=builder.as_markup()
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="Додати", callback_data="add_to_cart_м'яч_mikasa")
        await callback.message.answer(
            f"Пропозиція 2: - <a href=\"https://sport-liga.com.ua/p750495043-volejbolnyj-myach-mikasa.html?source=merchant_center&utm_source=google&utm_medium=cpc&utm_campaign=volejbolnye-myachi&gad_source=1&gclid=CjwKCAjwzMi_BhACEiwAX4YZUF8E7EMXs9VsDN58DO_XhqjYW77tmfGcuCFt2OBij8PoEpW6J7zq2xoCouUQAvD_BwE\">Волейбольний м'яч Mikasa V200W-CE</a>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=builder.as_markup()
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="Додати", callback_data="add_to_cart_м'яч_select")
        await callback.message.answer(
            f"Пропозиція 3: - <a href=\"https://a-sport.in.ua/product/select-numero-10-v23/?gad_source=1&gclid=CjwKCAjwzMi_BhACEiwAX4YZUDXR2Xkt50nwxhi9ocFOb8cJ30SSiA_JkfK61y28XmXlTkLzLvi_vRoC894QAvD_BwE\">Універсальний м'яч Select Numero 10</a>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=builder.as_markup()
        )
    elif chosen_item == "бутси":
        builder = InlineKeyboardBuilder()
        builder.button(text="Додати", callback_data="add_to_cart_бутси_nike")
        await callback.message.answer(
            f"Пропозиція 1: - <a href=\"https://sportano.ua/p/562958/krosivki-futbol-ni-nike-mercurial-superfly-10-academy-mg-volt-black?utm_source=google&utm_medium=cpc&utm_campaign=20416458475&utm_content=667551714643&utm_term=&gad_source=1&gclid=CjwKCAjwzMi_BhACEiwAX4YZUMIcJn3EEceDxCUZyOxAzVBS5wzpXAiKirblfSk8s79xYC-G1eLSjBoCQ8oQAvD_BwE\">Футбольні бутси Nike Mercurial Vapor 15 Elite FG</a>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=builder.as_markup()
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="Додати", callback_data="add_to_cart_бутси_adidas")
        await callback.message.answer(
            f"Пропозиція 2: - <a href=\"https://sportano.ua/p/433735/krosivki-futbol-ni-cholovichi-adidas-predator-pro-fg-core-black-carbon?utm_source=google&utm_medium=cpc&utm_campaign=20416458475&utm_content=667551714643&utm_term=&gad_source=1&gclid=CjwKCAjwzMi_BhACEiwAX4YZUBwWSNz4ZVeoaquxo07d47dRFUZ4NtzuCUo7Esa1x8h-uhAP7iPhtxoCrJAQAvD_BwE\">Футбольні бутси Adidas Predator Accuracy.1 FG</a>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=builder.as_markup()
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="Додати", callback_data="add_to_cart_бутси_puma")
        await callback.message.answer(
            f"Пропозиція 3: - <a href=\"https://sportano.ua/p/229914/futbol-ni-butsi-cholovichi-puma-ultra-ultimate-fg-ag-blakitni-107163-03?utm_source=google&utm_medium=cpc&utm_campaign=20416458475&utm_content=667551714643&utm_term=&gad_source=1&gclid=CjwKCAjwzMi_BhACEiwAX4YZUK25cW9ps4q92rD353YGaVWYZ2QIVIGkQzyfzZugaSF16a0wS0ZvthoCvL0QAvD_BwE\">Футбольні бутси Puma Ultra Ultimate FG/AG</a>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=builder.as_markup()
        )
    elif chosen_item == "форма":  # Для футболу та волейболу
        builder = InlineKeyboardBuilder()
        builder.button(text="Додати", callback_data="add_to_cart_форма_joma_футбол")
        await callback.message.answer(
            f"Пропозиція 1: - <a href=\"https://soccer-shop.com.ua/ua/p93980-futbolnaya_forma_ukraina_s_gerbom_2023-2024_igrovaya-povsednevnaya_11229503_tsvet_zheltiy?gad_source=1&gclid=CjwKCAjwzMi_BhACEiwAX4YZUMo2XKv_E4v1Fvg54AHXbhDo1Oonh9M-nZZbGPKuqnZjF5YDtjURRhoCJ0cQAvD_BwE\">Футбольна форма збірної України Joma</a>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=builder.as_markup()
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="Додати", callback_data="add_to_cart_форма_errea_волейбол")
        await callback.message.answer(
            f"Пропозиція 2: - <a href=\"https://www.store.volleyball.ua/katalog-tovarov/errea/sportyvnyi-kostium-cholovichyi-errea-mick-milo-30-chornyi-bilyi\">Волейбольна форма чоловіча Erreà комплект</a>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=builder.as_markup()
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="Додати", callback_data="add_to_cart_форма_kelme_дитяча")
        await callback.message.answer(
            f"Пропозиція 3: - <a href=\"https://sport-liga.com.ua/p2048608001-futbolnaya-forma-ukraine.html?source=merchant_center&utm_source=google&utm_medium=cpc&utm_campaign=futbolnaya-forma&gad_source=1&gclid=CjwKCAjwzMi_BhACEiwAX4YZUDwVPalfJSoHnY6gkUts7Tg2O8ruQQYPVRAWdEeDKMIl4hFnXGBdeRoC3sEQAvD_BwE\">Дитяча спортивна форма Kelme комплект</a>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=builder.as_markup()
        )
    elif chosen_item == "наколінники":
        builder = InlineKeyboardBuilder()
        builder.button(text="Додати", callback_data="add_to_cart_наколінники_asics")
        await callback.message.answer(
            f"Пропозиція 1: - <a href=\"https://rozetka.com.ua/ua/426649488/p426649488/\">Наколінники волейбольні Asics Gel-Kayano</a>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=builder.as_markup()
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="Додати", callback_data="add_to_cart_наколінники_mizuno")
        await callback.message.answer(
            f"Пропозиція 2: - <a href=\"https://sportano.ua/p/64567/nakolinniki-volejbol-ni-mizuno-vs1-kneepad-chorni-z59ss89109?utm_source=google&utm_medium=cpc&utm_campaign=22226974291&utm_content=732570459298&utm_term=&gad_source=1&gclid=CjwKCAjwzMi_BhACEiwAX4YZUD7g_HOfaeYBFCCf6TZrWErGy5oEJj6E28HQwRC-DyaIdEs_KSHBKRoCC0YQAvD_BwE\">Наколінники волейбольні Mizuno VS1 Knee Pads</a>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=builder.as_markup()
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="Додати", callback_data="add_to_cart_наколінники_mikasa")
        await callback.message.answer(
            f"Пропозиція 3: - <a href=\"https://rozetka.com.ua/ua/331321444/p331321444/\">Дитячі наколінники Mikasa MT7 Junior</a>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=builder.as_markup()
        )

    await callback.answer()

    @router.callback_query(lambda c: c.data.startswith("add_to_cart_"))
    async def add_to_cart_handler(callback: types.CallbackQuery):
        user_id = callback.from_user.id
        item_data = callback.data[len("add_to_cart_"):]  # Отримуємо ідентифікатор товару
        item_name = item_data.replace("_", " ").title()  # Формуємо назву товару

        # Зберігаємо товар у базі даних
        cursor.execute("INSERT INTO carts (user_id, item_name) VALUES (?, ?)", (user_id, item_name))
        conn.commit()
        await callback.answer(f"Інвентар '{item_name}' додано!", show_alert=False)

        if user_id not in user_carts:
            user_carts[user_id] = []
        user_carts[user_id].append(item_name)

    @router.message(F.text == "Підібраний інвентар")
    async def show_cart_handler(message: types.Message):
        user_id = message.from_user.id
        cursor.execute("SELECT item_name FROM carts WHERE user_id=?", (user_id,))
        cart_items_db = cursor.fetchall()

        if cart_items_db:
            cart_items = "\n".join([f"- {item[0]}" for item in cart_items_db])
            builder = InlineKeyboardBuilder()
            builder.button(text="🗑️ Очистити", callback_data="clear_cart")
            await message.answer(
                f"Ваш підібраний інвентар:\n{cart_items}",
                reply_markup=builder.as_markup()
            )
        else:
            await message.answer("Тут порожньо.")

    @router.callback_query(F.data == "clear_cart")
    async def clear_cart_handler(callback: types.CallbackQuery):
        user_id = callback.from_user.id
        cursor.execute("DELETE FROM carts WHERE user_id=?", (user_id,))
        conn.commit()
        await callback.message.edit_text("Очищено.")
        await callback.answer()

    # Обробник кнопки "Запитати пораду"
    @router.message(F.text == "Запитати пораду")
    async def ask_advice_handler(message: types.Message):
        await message.answer(
            "Будь ласка, введіть ваше питання, і ми зв'яжемося з вами для надання детальних рекомендацій.")

    # Обробник отриманого питання для поради
    @router.message()
    async def handle_advice_question(message: types.Message):
        user_id = message.from_user.id
        question = message.text
        if message.text not in ["Підібраний інвентар", "Запитати пораду"] and not message.text.lower().startswith(
                "погода в"):
            # Зберігаємо питання в базі даних
            cursor.execute("INSERT INTO advice (user_id, question) VALUES (?, ?)", (user_id, question))
            conn.commit()
            await message.answer(
                "Дякуємо за ваше питання! Ми зв'яжемося з вами найближчим часом для надання рекомендацій.")
            logging.info(f"Отримано запитання на пораду від user_id {user_id}: {question}")

    # Обробник команди /help
    @router.message(Command("help"))
    async def command_help_handler(message: types.Message) -> None:
        help_text = (
            "Я можу допомогти вам підібрати спортивний інвентар.\n\n"
            "Натисніть /start, щоб обрати вид спорту або дізнатися погоду.\n"
            "Потім ви зможете обрати потрібний інвентар та додати його до кошика.\n"
            "Переглянути кошик можна за допомогою кнопки 'Підібраний інвентар'.\n"
            "Якщо вам потрібна порада, натисніть кнопку 'Запитати пораду' та введіть своє питання."
            "\n\nТакож доступні команди:\n"
            "/start - Почати спілкування з ботом\n"
            "/info - Інформація про бота\n"
            "/weather [місто] - Дізнатися погоду вказаного міста"
        )
        await message.answer(help_text)

    # Обробник команди /info
    @router.message(Command("info"))
    async def command_info_handler(message: types.Message) -> None:
        info_text = ("Цей бот розроблений для демонстрації можливостей Aiogram 3.0 у підборі спортивного інвентаря."
                     "\nТакож реалізована функція отримання погоди та кошик для обраних товарів.")
        await message.answer(info_text)

    # Обробник фото
    @router.message(F.photo)
    async def photo_handler(message: types.Message):
        file_id = message.photo[-1].file_id
        await message.answer(f"Дякую за фото! ID файлу: `{file_id}`")

    # Обробник відео
    @router.message(F.video)
    async def video_handler(message: types.Message):
        file_id = message.video.file_id
        await message.answer(f"Дякую за відео! ID файлу: `{file_id}`")

    # Обробник будь-якого текстового повідомлення, який не є командою або запитом на погоду
    @router.message()
    async def handle_message(message: types.Message) -> None:
        user_query = message.text
        await message.answer(
            f"Ви запитали: '{user_query}'.\nБудь ласка, скористайтеся кнопками для вибору виду спорту "
            f"або введіть 'погода в [місто]' для дізнання погоди.")

    def close_db_connection():
        conn.close()
        logging.info("З'єднання з базою даних закрито.")

    atexit.register(close_db_connection)