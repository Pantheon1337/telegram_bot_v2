import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv
from database import (
    init_db, add_user, get_categories, get_products, is_admin,
    add_product, get_product_by_id, add_to_cart_db, get_cart_items,
    clear_cart, create_order, get_order_details, export_products,
    delete_product, update_product, session_scope, Product, Category,
    User, Order, CartItem, OrderItem, update_admin_status, get_admin_ids,
    get_all_users
)
import logging
import shutil
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.sql import func
import time
import glob

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', mode='w'),  # Перезаписываем файл при каждом запуске
        logging.StreamHandler()  # Вывод в консоль
    ]
)
logger = logging.getLogger(__name__)

# Создаем директорию для логов, если её нет
os.makedirs('logs', exist_ok=True)

# Функция для ротации логов
def setup_logging():
    # Создаем имя файла с текущей датой и временем
    log_filename = f'logs/bot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    
    # Настраиваем логирование
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, mode='w'),
            logging.StreamHandler()
        ]
    )
    
    logger.info("Логирование настроено")
    logger.info(f"Логи сохраняются в файл: {log_filename}")

# Вызываем настройку логирования при запуске
setup_logging()

# Определение состояний
class ProductStates(StatesGroup):
    waiting_product_info = State()

# Добавляем состояния для добавления товара
class AddProduct(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_category = State()
    waiting_for_image = State()

# Добавляем состояния для редактирования товара
class EditProduct(StatesGroup):
    waiting_for_field = State()
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_category = State()
    waiting_for_image = State()

# Добавляем состояние для массовой рассылки
class BroadcastStates(StatesGroup):
    waiting_for_message = State()

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(id) for id in os.getenv('ADMIN_IDS', '').split(',') if id]

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Инициализация базы данных
init_db()

# Создание необходимых директорий
os.makedirs("products", exist_ok=True)
os.makedirs("images", exist_ok=True)

# Путь к стандартной картинке
DEFAULT_IMAGE = "images/default_product.jpg"

# Создание клавиатуры главного меню
def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍 Каталог")],
            [KeyboardButton(text="🛒 Корзина"), KeyboardButton(text="💳 Оплата")],
            [KeyboardButton(text="ℹ️ О нас"), KeyboardButton(text="📞 Контакты")]
        ],
        resize_keyboard=True
    )
    return keyboard

# Создание клавиатуры администратора
def get_admin_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить товар"), KeyboardButton(text="📝 Редактировать товар")],
            [KeyboardButton(text="🗑 Удалить товар"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="📢 Рассылка")],
            [KeyboardButton(text="🔙 В главное меню")]
        ],
        resize_keyboard=True
    )
    return keyboard

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    try:
        is_user_admin = message.from_user.id in ADMIN_IDS
        add_user(message.from_user.id, is_user_admin, message.from_user.username)
        
        # Формируем текст приветствия
        welcome_text = (
            "🌟 Добро пожаловать в наш магазин!\n\n"
            "🛍 Здесь вы найдете лучшие товары для вейпинга\n"
            "🚚 Быстрая доставка\n"
            "💯 Гарантия качества\n"
            "👨‍💼 Профессиональная консультация\n\n"
            "Выберите нужный раздел в меню ниже 👇"
        )
        
        # Отправляем логотип с текстом, если он существует
        if os.path.exists("logo.jpg"):
            try:
                photo = FSInputFile("logo.jpg")
                await message.answer_photo(
                    photo,
                    caption=welcome_text,
                    reply_markup=get_main_keyboard()
                )
            except Exception as e:
                logger.error(f"Error sending logo: {e}")
                # Если не удалось отправить фото, отправляем только текст
                await message.answer(welcome_text, reply_markup=get_main_keyboard())
        else:
            logger.warning("Logo file not found: logo.jpg")
            # Если логотип не найден, отправляем только текст
            await message.answer(welcome_text, reply_markup=get_main_keyboard())
            
    except Exception as e:
        logger.error(f"Error in cmd_start: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик кнопки "Каталог"
@dp.message(lambda message: message.text == "🛍 Каталог")
async def show_catalog(message: types.Message):
    try:
        categories = get_categories()
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=cat, callback_data=f"cat_{cat}")] for cat in categories
            ]
        )
        await message.answer(
            "🛍 Выберите категорию:",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Error in show_catalog: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик выбора категории
@dp.callback_query(lambda c: c.data.startswith('cat_'))
async def show_category_products(callback: types.CallbackQuery):
    try:
        category = callback.data[4:]  # Убираем префикс 'cat_'
        products = get_products(category)
        if not products:
            await callback.message.answer("В этой категории пока нет товаров.")
            return
        
        # Разбиваем товары на страницы по 5 штук
        products_per_page = 5
        pages = [products[i:i + products_per_page] for i in range(0, len(products), products_per_page)]
        
        # Создаем клавиатуру для первой страницы
        keyboard_buttons = []
        for product in pages[0]:
            keyboard_buttons.append([InlineKeyboardButton(
                text=f"{product['name']} - {product['price']} ₽",
                callback_data=f"product_{product['id']}"
            )])
        
        # Добавляем кнопки навигации, если есть больше одной страницы
        if len(pages) > 1:
            keyboard_buttons.append([
                InlineKeyboardButton(text="➡️", callback_data=f"page_{category}_1")
            ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await callback.message.answer(
            f"🛍 Товары в категории {category}:\n\n"
            f"Страница 1 из {len(pages)}",
            reply_markup=keyboard
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in show_category_products: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик пагинации
@dp.callback_query(lambda c: c.data.startswith('page_'))
async def handle_pagination(callback: types.CallbackQuery):
    try:
        _, category, page = callback.data.split('_')
        page = int(page)
        products = get_products(category)
        products_per_page = 5
        pages = [products[i:i + products_per_page] for i in range(0, len(products), products_per_page)]
        
        if page < 0 or page >= len(pages):
            await callback.answer("Это последняя страница")
            return
        
        keyboard = InlineKeyboardMarkup(row_width=2)
        for product in pages[page]:
            keyboard.add(InlineKeyboardButton(
                text=f"{product['name']} - {product['price']} ₽",
                callback_data=f"product_{product['id']}"
            ))
        
        # Добавляем кнопки навигации
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"page_{category}_{page-1}"))
        if page < len(pages) - 1:
            nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"page_{category}_{page+1}"))
        if nav_buttons:
            keyboard.add(*nav_buttons)
        
        await callback.message.edit_text(
            f"🛍 Товары в категории {category}:\n\n"
            f"Страница {page + 1} из {len(pages)}",
            reply_markup=keyboard
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in handle_pagination: {e}")
        await callback.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик кнопки "Назад в категории"
@dp.callback_query(F.data.startswith("back_to_cat_"))
async def handle_back_to_category(callback_query: types.CallbackQuery):
    """Обработчик кнопки 'Назад в категории'"""
    try:
        # Получаем список категорий
        categories = get_categories()
        if not categories:
            await callback_query.message.answer("❌ Нет доступных категорий")
            return
        
        # Создаем клавиатуру с категориями
        keyboard_buttons = []
        for category in categories:
            keyboard_buttons.append([types.InlineKeyboardButton(
                text=category,
                callback_data=f"cat_{category}"
            )])
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        # Проверяем, есть ли текст в сообщении
        if callback_query.message.text:
            await callback_query.message.edit_text(
                "🛍 Выберите категорию:",
                reply_markup=keyboard
            )
        else:
            # Если сообщение не содержит текста, отправляем новое
            await callback_query.message.answer(
                "🛍 Выберите категорию:",
                reply_markup=keyboard
            )
        
    except Exception as e:
        logger.error(f"Error in handle_back_to_category: {e}", exc_info=True)
        await callback_query.answer("❌ Произошла ошибка при возврате к категориям")

# Обработчик просмотра товара
@dp.callback_query(lambda c: c.data.startswith('product_'))
async def show_product(callback: types.CallbackQuery):
    try:
        product_id = int(callback.data[8:])
        product = get_product_by_id(product_id)
        if not product:
            await callback.answer("Товар не найден")
            return
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🛒 Добавить в корзину", callback_data=f"add_{product['id']}")],
                [InlineKeyboardButton(text="⬅️ Назад в категорию", callback_data=f"back_to_cat_{product['category']}")]
            ]
        )
        
        if product['image_path'] and os.path.exists(product['image_path']):
            try:
                photo = FSInputFile(product['image_path'])
                await callback.message.answer_photo(
                    photo,
                    caption=f"*{product['name']}*\n\n{product['description']}\n\nЦена: {product['price']} ₽",
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Error sending photo: {e}")
                await callback.message.answer(
                    f"*{product['name']}*\n\n{product['description']}\n\nЦена: {product['price']} ₽",
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
        else:
            await callback.message.answer(
                f"*{product['name']}*\n\n{product['description']}\n\nЦена: {product['price']} ₽",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in show_product: {e}")
        await callback.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик кнопки "Корзина"
@dp.message(lambda message: message.text == "🛒 Корзина")
async def show_cart(message: types.Message):
    try:
        cart_items = get_cart_items(message.from_user.id)
        if not cart_items:
            await message.answer("Ваша корзина пуста")
            return
        
        total = sum(item['price'] * item['quantity'] for item in cart_items)
        cart_text = "🛒 Ваша корзина:\n\n"
        for item in cart_items:
            cart_text += f"{item['name']} x{item['quantity']} - {item['price'] * item['quantity']} ₽\n"
        cart_text += f"\nИтого: {total} ₽"
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout")],
                [InlineKeyboardButton(text="🗑 Очистить корзину", callback_data="clear_cart")]
            ]
        )
        
        await message.answer(cart_text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Error in show_cart: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик оформления заказа
@dp.callback_query(F.data == "checkout")
async def handle_checkout(callback: types.CallbackQuery):
    """Обработчик оформления заказа"""
    try:
        # Создаем заказ
        order_id = create_order(callback.from_user.id)
        if not order_id:
            await callback.message.answer("❌ Произошла ошибка при создании заказа")
            return
        
        # Получаем детали заказа
        order_details = get_order_details(order_id)
        if not order_details:
            await callback.message.answer("❌ Произошла ошибка при получении деталей заказа")
            return
        
        # Формируем сообщение о заказе
        order_message = (
            "🛒 Новый заказ!\n\n"
            f"👤 Пользователь: {order_details['username']}\n"
            f"🆔 ID: {order_details['user_id']}\n\n"
            "📦 Товары:\n"
        )
        
        for item in order_details['items']:
            order_message += f"• {item['name']} x{item['quantity']} - {item['price']}₽\n"
        
        order_message += f"\n💰 Итого: {order_details['total']}₽"
        
        # Получаем список ID администраторов
        admin_ids = get_admin_ids()
        logger.info(f"Sending order notification to admins: {admin_ids}")
        
        # Отправляем сообщение всем администраторам
        for admin_id in admin_ids:
            try:
                await bot.send_message(admin_id, order_message)
                logger.info(f"Order notification sent to admin {admin_id}")
            except Exception as e:
                logger.error(f"Error sending order notification to admin {admin_id}: {e}")
        
        # Отправляем сообщение пользователю
        await callback.message.answer(
            "✅ Заказ успешно оформлен!\n"
            "Администратор свяжется с вами в ближайшее время."
        )
        
        # Очищаем корзину
        clear_cart(callback.from_user.id)
        
    except Exception as e:
        logger.error(f"Error in handle_checkout: {e}", exc_info=True)
        await callback.message.answer("❌ Произошла ошибка при оформлении заказа")

# Обработчик очистки корзины
@dp.callback_query(lambda c: c.data == "clear_cart")
async def handle_clear_cart(callback: types.CallbackQuery):
    try:
        if clear_cart(callback.from_user.id):
            await callback.message.answer("Корзина очищена")
        else:
            await callback.message.answer("Ваша корзина уже пуста")
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in handle_clear_cart: {e}")
        await callback.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик кнопки "Оплата"
@dp.message(F.text == "💳 Оплата")
async def show_payment(message: types.Message):
    try:
        await message.answer(
            "💳 Способы оплаты\n\n"
            "1️⃣ По QR-коду\n"
            "2️⃣ Банковским переводом\n"
            "3️⃣ Наличными при встрече с менеджером\n\n"
            "📸 После оплаты отправьте скриншот чека менеджеру @Jmih_maneger\n\n"
            "⏳ Обработка заказа происходит в течение 15 минут",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in show_payment: {e}")
        await message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик кнопки "О нас"
@dp.message(lambda message: message.text == "ℹ️ О нас")
async def show_about(message: types.Message):
    try:
        await message.answer(
            "🌟 *О ЖМЫХ Vape Shop*\n\n"
            "🛍 *Наш магазин предлагает:*\n"
            "• Качественные товары для вейпинга\n"
            "• Широкий ассортимент\n"
            "• Доступные цены\n\n"
            "🚚 *Преимущества:*\n"
            "• Быстрая доставка\n"
            "• Гарантия качества\n"
            "• Профессиональная консультация\n\n"
            "💯 *Мы работаем для вас!*",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in show_about: {e}")
        await message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик кнопки "Контакты"
@dp.message(lambda message: message.text == "📞 Контакты")
async def show_contacts(message: types.Message):
    try:
        await message.answer(
            "📱 *Наши контакты*\n\n"
            "📢 *Официальный канал:*\n"
            "[ЖМЫХ Vape Shop](https://t.me/spot_pp)\n\n"
            "👨‍💼 *Менеджер:*\n"
            "[@Jmih_maneger](https://t.me/Jmih_maneger)\n\n"
            "💬 *По всем вопросам обращайтесь к менеджеру*\n"
            "⏰ *Работаем круглосуточно*",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in show_contacts: {e}")
        await message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик кнопки "Назад"
@dp.message(lambda message: message.text == "🔙 В главное меню")
async def back_to_main(message: types.Message):
    try:
        await message.answer("Главное меню", reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Error in back_to_main: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик команды /admin
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    try:
        if is_admin(message.from_user.id):
            await message.answer(
                "👨‍💼 Панель администратора\n\n"
                "Выберите действие:",
                reply_markup=get_admin_keyboard()
            )
        else:
            await message.answer("У вас нет доступа к этой команде.")
    except Exception as e:
        logger.error(f"Error in cmd_admin: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик кнопки "Добавить товар"
@dp.message(F.text == "➕ Добавить товар")
async def add_product_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде")
        return
    
    await message.answer("Введите название товара:")
    await state.set_state(AddProduct.waiting_for_name)

# Обработчик ввода названия товара
@dp.message(AddProduct.waiting_for_name)
async def process_product_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите описание товара:")
    await state.set_state(AddProduct.waiting_for_description)

# Обработчик ввода описания товара
@dp.message(AddProduct.waiting_for_description)
async def process_product_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Введите цену товара (только число):")
    await state.set_state(AddProduct.waiting_for_price)

# Обработчик ввода цены товара
@dp.message(AddProduct.waiting_for_price)
async def process_product_price(message: types.Message, state: FSMContext):
    try:
        # Удаляем все пробелы и заменяем запятую на точку
        price_text = message.text.strip().replace(',', '.')
        logger.info(f"Attempting to parse price: {price_text}")
        
        # Проверяем, что строка содержит только цифры и одну точку
        if not price_text.replace('.', '').isdigit():
            logger.error(f"Invalid price format: {price_text}")
            await message.answer(
                "❌ Пожалуйста, введите корректную цену.\n"
                "Используйте только цифры и точку или запятую.\n"
                "Например: 1000 или 1000.50"
            )
            return
            
        # Преобразуем в число
        price = float(price_text)
        logger.info(f"Successfully parsed price: {price}")
        
        # Проверяем, что цена положительная
        if price <= 0:
            logger.error(f"Price is not positive: {price}")
            await message.answer("❌ Цена должна быть больше нуля")
            return
            
        await state.update_data(price=price)
        
        # Получаем список категорий
        categories = get_categories()
        if not categories:
            logger.error("No categories found")
            await message.answer("❌ Нет доступных категорий. Пожалуйста, добавьте категории через админ-панель.")
            await state.clear()
            return
            
        # Создаем кнопки для каждой категории
        keyboard_buttons = []
        for category in categories:
            keyboard_buttons.append([InlineKeyboardButton(
                text=category,
                callback_data=f"select_category_{category}"
            )])
        
        # Создаем клавиатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await message.answer("Выберите категорию товара:", reply_markup=keyboard)
        await state.set_state(AddProduct.waiting_for_category)
        
    except ValueError as e:
        logger.error(f"ValueError in price parsing: {e}")
        await message.answer(
            "❌ Пожалуйста, введите корректную цену.\n"
            "Используйте только цифры и точку или запятую.\n"
            "Например: 1000 или 1000.50"
        )
    except Exception as e:
        logger.error(f"Unexpected error in price processing: {e}")
        await message.answer("❌ Произошла ошибка при обработке цены. Пожалуйста, попробуйте еще раз.")

# Обработчик выбора категории
@dp.callback_query(F.data.startswith('select_category_'))
async def process_category_selection(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора категории товара"""
    try:
        category = callback_query.data.replace('select_category_', '')
        await state.update_data(category=category)
        
        # Создаем клавиатуру с кнопками
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="📷 Добавить фото", callback_data="add_photo")],
            [types.InlineKeyboardButton(text="⏩ Пропустить", callback_data="skip_photo")]
        ])
        
        await callback_query.message.edit_text(
            "Отправьте фото товара или нажмите 'Пропустить':",
            reply_markup=keyboard
        )
        await state.set_state(AddProduct.waiting_for_image)
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Error in process_category_selection: {e}", exc_info=True)
        await callback_query.message.edit_text("❌ Произошла ошибка при выборе категории")
        await state.clear()

@dp.callback_query(F.data == 'add_photo')
async def add_photo(callback_query: types.CallbackQuery):
    """Обработчик добавления фото товара"""
    try:
        await callback_query.message.answer("Пожалуйста, отправьте фото товара")
        await AddProduct.image.set()
    except Exception as e:
        logger.error(f"Error in add_photo handler: {e}")
        await callback_query.message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")

@dp.callback_query(F.data == 'skip_photo')
async def skip_photo(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик пропуска добавления фото"""
    try:
        # Получаем данные о товаре из состояния
        data = await state.get_data()
        
        # Проверяем существование стандартной фотографии
        if not os.path.exists(DEFAULT_IMAGE):
            # Создаем директорию для изображений, если её нет
            os.makedirs('images', exist_ok=True)
            # Создаем пустой файл для стандартной фотографии
            with open(DEFAULT_IMAGE, 'wb') as f:
                f.write(b'')
        
        # Добавляем товар со стандартной фотографией
        success = add_product(
            name=data['name'],
            description=data['description'],
            price=data['price'],
            category_name=data['category'],
            image_path=DEFAULT_IMAGE
        )
        
        if success:
            await callback_query.message.answer("✅ Товар успешно добавлен!")
        else:
            await callback_query.message.answer("❌ Не удалось добавить товар. Пожалуйста, попробуйте позже.")
            
        await state.clear()
    except Exception as e:
        logger.error(f"Error in skip_photo handler: {e}")
        await callback_query.message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")

@dp.message(F.photo, AddProduct.waiting_for_image)
async def process_product_image(message: types.Message, state: FSMContext):
    """Обработчик получения фото товара"""
    try:
        # Создаем директорию для изображений, если её нет
        if not os.path.exists('images'):
            os.makedirs('images')
            
        # Получаем файл фото
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        
        # Генерируем уникальное имя файла
        file_extension = file_info.file_path.split('.')[-1]
        file_name = f"product_{int(time.time())}.{file_extension}"
        file_path = f"images/{file_name}"
        
        # Сохраняем фото
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file.getvalue())
            
        # Получаем данные о товаре из состояния
        data = await state.get_data()
        
        # Добавляем товар с фото
        success = add_product(
            name=data['name'],
            description=data['description'],
            price=data['price'],
            category_name=data['category'],
            image_path=file_path
        )
        
        if success:
            await message.answer("✅ Товар успешно добавлен!")
        else:
            await message.answer("❌ Не удалось добавить товар. Пожалуйста, попробуйте позже.")
            
        await state.clear()
    except Exception as e:
        logger.error(f"Error in process_product_image handler: {e}")
        await message.answer("❌ Произошла ошибка при сохранении фото. Пожалуйста, попробуйте позже.")
        await state.clear()

# Обработчик отмены добавления товара
@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    
    await state.clear()
    await message.answer("❌ Добавление товара отменено")

# Обработчик добавления товара в корзину
@dp.callback_query(lambda c: c.data.startswith('add_'))
async def add_to_cart(callback: types.CallbackQuery):
    try:
        product_id = int(callback.data[4:])  # Убираем префикс 'add_'
        logger.info(f"Attempting to add product {product_id} to cart for user {callback.from_user.id}")
        
        product = get_product_by_id(product_id)
        if not product:
            logger.error(f"Product {product_id} not found")
            await callback.answer("❌ Товар не найден", show_alert=True)
            return
            
        user_id = callback.from_user.id
        logger.info(f"Adding product {product_id} to cart for user {user_id}")
        
        try:
            add_to_cart_db(user_id, product_id)
            logger.info(f"Successfully added product {product_id} to cart")
            await callback.answer("✅ Товар добавлен в корзину")
        except ValueError as e:
            logger.error(f"Error adding to cart: {str(e)}")
            await callback.answer(str(e), show_alert=True)
        except Exception as e:
            logger.error(f"Unexpected error in add_to_cart_db: {str(e)}", exc_info=True)
            await callback.answer("❌ Произошла ошибка при добавлении товара в корзину", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error in add_to_cart: {str(e)}", exc_info=True)
        await callback.answer("❌ Произошла ошибка. Пожалуйста, попробуйте позже.", show_alert=True)

# Обработчик команды /backup
@dp.message(Command("backup"))
async def cmd_backup(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде")
        return
    
    try:
        # Создаем директорию для бэкапов, если её нет
        os.makedirs("backups", exist_ok=True)
        
        # Используем фиксированное имя файла
        backup_file = "backups/products_backup.json"
        
        # Экспортируем товары
        if export_products(backup_file):
            await message.answer(f"✅ Резервная копия успешно создана: {backup_file}")
        else:
            await message.answer("❌ Не удалось создать резервную копию")
            
    except Exception as e:
        logger.error(f"Error in cmd_backup: {e}")
        await message.answer("❌ Произошла ошибка при создании резервной копии")

# Обработчик кнопки "Статистика"
@dp.message(F.text == "📊 Статистика")
async def show_statistics(message: types.Message):
    """Обработчик кнопки статистики"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде")
        return
    
    try:
        # Получаем статистику из базы данных
        with session_scope() as session:
            # Количество товаров
            total_products = session.query(Product).count()
            
            # Количество категорий
            total_categories = session.query(Category).count()
            
            # Количество пользователей
            total_users = session.query(User).count()
            
            # Количество заказов
            total_orders = session.query(Order).count()
            
            # Популярные категории
            popular_categories = session.query(
                Category.name,
                func.count(Product.id).label('product_count')
            ).join(Product).group_by(Category.name).order_by(func.count(Product.id).desc()).limit(5).all()
            
            # Формируем сообщение
            stats_message = (
                "📊 Статистика магазина:\n\n"
                f"📦 Всего товаров: {total_products}\n"
                f"📁 Категорий: {total_categories}\n"
                f"👥 Пользователей: {total_users}\n"
                f"🛒 Заказов: {total_orders}\n\n"
                "🔥 Популярные категории:\n"
            )
            
            for category, count in popular_categories:
                stats_message += f"• {category}: {count} товаров\n"
            
            await message.answer(stats_message)
            
    except Exception as e:
        logger.error(f"Error in show_statistics: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при получении статистики")

# Обработчик кнопки "Редактировать товар"
@dp.message(F.text == "📝 Редактировать товар")
async def edit_product_start(message: types.Message):
    """Обработчик кнопки редактирования товара"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде")
        return
    
    try:
        # Получаем список всех товаров
        products = get_products()
        if not products:
            await message.answer("❌ В базе нет товаров для редактирования")
            return
        
        # Создаем клавиатуру с товарами
        keyboard_buttons = []
        for product in products:
            keyboard_buttons.append([InlineKeyboardButton(
                text=f"{product['name']} - {product['price']} руб.",
                callback_data=f"edit_{product['id']}"
            )])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        await message.answer("Выберите товар для редактирования:", reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in edit_product_start: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при получении списка товаров")

@dp.callback_query(F.data.startswith("edit_"))
async def edit_product(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик редактирования товара"""
    try:
        # Получаем ID товара и тип редактирования из callback_data
        data = callback_query.data.replace('edit_', '')
        if '_' in data:
            product_id = int(data.split('_')[1])
            edit_type = data.split('_')[0]
        else:
            product_id = int(data)
            edit_type = None
            
        # Получаем информацию о товаре
        product = get_product_by_id(product_id)
        if not product:
            await callback_query.answer("❌ Товар не найден")
            return
            
        # Сохраняем ID товара в состоянии
        await state.update_data(product_id=product_id)
        
        if edit_type == 'name':
            await state.set_state(EditProduct.waiting_for_name)
            await callback_query.message.edit_text(
                f"✏️ Текущее название: {product['name']}\n"
                "Введите новое название товара:"
            )
        elif edit_type == 'desc':
            await state.set_state(EditProduct.waiting_for_description)
            await callback_query.message.edit_text(
                f"✏️ Текущее описание: {product['description']}\n"
                "Введите новое описание товара:"
            )
        elif edit_type == 'price':
            await state.set_state(EditProduct.waiting_for_price)
            await callback_query.message.edit_text(
                f"✏️ Текущая цена: {product['price']}\n"
                "Введите новую цену товара:"
            )
        elif edit_type == 'image':
            await state.set_state(EditProduct.waiting_for_image)
            await callback_query.message.edit_text(
                "📷 Отправьте новое изображение товара:"
            )
        else:
            # Если тип редактирования не указан, показываем меню выбора
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                [
                    types.InlineKeyboardButton(text="✏️ Название", callback_data=f"edit_name_{product_id}"),
                    types.InlineKeyboardButton(text="📝 Описание", callback_data=f"edit_desc_{product_id}")
                ],
                [
                    types.InlineKeyboardButton(text="💰 Цена", callback_data=f"edit_price_{product_id}"),
                    types.InlineKeyboardButton(text="📷 Изображение", callback_data=f"edit_image_{product_id}")
                ],
                [types.InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_products")]
            ])
            await callback_query.message.edit_text(
                f"✏️ Редактирование товара: {product['name']}\n"
                "Выберите, что хотите изменить:",
                reply_markup=keyboard
            )
            
    except Exception as e:
        logger.error(f"Error in edit_product: {e}", exc_info=True)
        await callback_query.answer("❌ Произошла ошибка при редактировании товара")

@dp.callback_query(F.data.startswith('edit_name_'))
async def edit_product_name(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик редактирования названия товара"""
    try:
        product_id = int(callback_query.data.replace('edit_name_', ''))
        await state.set_state(EditProduct.waiting_for_name)
        await state.update_data(product_id=product_id)
        
        await callback_query.message.edit_text(
            "✏️ Введите новое название товара:"
        )
        
    except Exception as e:
        logger.error(f"Error in edit_product_name: {e}", exc_info=True)
        await callback_query.answer("❌ Произошла ошибка при редактировании")

@dp.callback_query(F.data.startswith('edit_desc_'))
async def edit_product_description(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик редактирования описания товара"""
    try:
        product_id = int(callback_query.data.replace('edit_desc_', ''))
        await state.set_state(EditProduct.waiting_for_description)
        await state.update_data(product_id=product_id)
        
        await callback_query.message.edit_text(
            "📝 Введите новое описание товара:"
        )
        
    except Exception as e:
        logger.error(f"Error in edit_product_description: {e}", exc_info=True)
        await callback_query.answer("❌ Произошла ошибка при редактировании")

@dp.callback_query(F.data.startswith('edit_price_'))
async def edit_product_price(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик редактирования цены товара"""
    try:
        product_id = int(callback_query.data.replace('edit_price_', ''))
        await state.set_state(EditProduct.waiting_for_price)
        await state.update_data(product_id=product_id)
        
        await callback_query.message.edit_text(
            "💰 Введите новую цену товара (только число):"
        )
        
    except Exception as e:
        logger.error(f"Error in edit_product_price: {e}", exc_info=True)
        await callback_query.answer("❌ Произошла ошибка при редактировании")

@dp.callback_query(F.data.startswith('edit_image_'))
async def edit_product_image(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик редактирования изображения товара"""
    try:
        product_id = int(callback_query.data.replace('edit_image_', ''))
        await state.set_state(EditProduct.waiting_for_image)
        await state.update_data(product_id=product_id)
        
        await callback_query.message.edit_text(
            "📷 Отправьте новое изображение товара:"
        )
        
    except Exception as e:
        logger.error(f"Error in edit_product_image: {e}", exc_info=True)
        await callback_query.answer("❌ Произошла ошибка при редактировании")

@dp.message(EditProduct.waiting_for_name)
async def process_edit_name(message: types.Message, state: FSMContext):
    """Обработчик ввода нового названия товара"""
    try:
        data = await state.get_data()
        product_id = data['product_id']
        
        if update_product(product_id, name=message.text):
            await message.answer("✅ Название товара успешно обновлено")
        else:
            await message.answer("❌ Не удалось обновить название товара")
            
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error in process_edit_name: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при обновлении названия")
        await state.clear()

@dp.message(EditProduct.waiting_for_description)
async def process_edit_description(message: types.Message, state: FSMContext):
    """Обработчик ввода нового описания товара"""
    try:
        data = await state.get_data()
        product_id = data['product_id']
        
        if update_product(product_id, description=message.text):
            await message.answer("✅ Описание товара успешно обновлено")
        else:
            await message.answer("❌ Не удалось обновить описание товара")
            
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error in process_edit_description: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при обновлении описания")
        await state.clear()

@dp.message(EditProduct.waiting_for_price)
async def process_edit_price(message: types.Message, state: FSMContext):
    """Обработчик ввода новой цены товара"""
    try:
        data = await state.get_data()
        product_id = data['product_id']
        
        # Проверяем, что введено число
        try:
            price = float(message.text)
        except ValueError:
            await message.answer("❌ Пожалуйста, введите число")
            return
            
        if update_product(product_id, price=price):
            await message.answer("✅ Цена товара успешно обновлена")
        else:
            await message.answer("❌ Не удалось обновить цену товара")
            
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error in process_edit_price: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при обновлении цены")
        await state.clear()

@dp.message(EditProduct.waiting_for_image, F.photo)
async def process_edit_image(message: types.Message, state: FSMContext):
    """Обработчик загрузки нового изображения товара"""
    try:
        data = await state.get_data()
        product_id = data['product_id']
        
        # Создаем директорию для изображений, если её нет
        os.makedirs('product_images', exist_ok=True)
        
        # Получаем файл изображения
        photo = message.photo[-1]
        file_id = photo.file_id
        file = await message.bot.get_file(file_id)
        file_path = file.file_path
        
        # Скачиваем изображение
        downloaded_file = await message.bot.download_file(file_path)
        
        # Генерируем уникальное имя файла
        filename = f"product_{product_id}_{int(time.time())}.jpg"
        filepath = os.path.join('product_images', filename)
        
        # Сохраняем изображение
        with open(filepath, 'wb') as new_file:
            new_file.write(downloaded_file.getvalue())
            
        # Обновляем путь к изображению в базе данных
        if update_product(product_id, image_path=filepath):
            await message.answer("✅ Изображение товара успешно обновлено")
        else:
            await message.answer("❌ Не удалось обновить изображение товара")
            
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error in process_edit_image: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при обновлении изображения")
        await state.clear()

async def delete_product_from_db(product_id: int) -> bool:
    """Удаление товара из базы данных"""
    try:
        with session_scope() as session:
            # Получаем товар
            product = session.query(Product).filter_by(id=product_id).first()
            if not product:
                logger.error(f"Product {product_id} not found")
                return False
                
            # Удаляем связанные записи в корзинах
            session.query(CartItem).filter_by(product_id=product_id).delete()
            
            # Удаляем связанные записи в заказах
            session.query(OrderItem).filter_by(product_id=product_id).delete()
            
            # Удаляем изображение товара, если оно существует
            if product.image_path and os.path.exists(product.image_path):
                try:
                    os.remove(product.image_path)
                    logger.info(f"Deleted image file: {product.image_path}")
                except Exception as e:
                    logger.error(f"Error deleting image file: {e}")
            
            # Удаляем товар из базы данных
            session.delete(product)
            logger.info(f"Product {product_id} deleted successfully")
            return True
            
    except Exception as e:
        logger.error(f"Error deleting product: {e}", exc_info=True)
        return False

@dp.callback_query(F.data.startswith('delete_'))
async def handle_delete_product(callback_query: types.CallbackQuery):
    """Обработчик кнопки удаления товара"""
    try:
        product_id = int(callback_query.data.replace('delete_', ''))
        
        # Создаем клавиатуру с подтверждением удаления
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{product_id}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete")]
        ])
        
        await callback_query.message.edit_text(
            "⚠️ Вы уверены, что хотите удалить этот товар?",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error in handle_delete_product: {e}", exc_info=True)
        await callback_query.answer("❌ Произошла ошибка при удалении")

@dp.callback_query(F.data.startswith('confirm_delete_'))
async def confirm_delete(callback_query: types.CallbackQuery):
    """Обработчик подтверждения удаления товара"""
    try:
        product_id = int(callback_query.data.replace('confirm_delete_', ''))
        
        # Удаляем товар из базы данных
        success = await delete_product_from_db(product_id)
        if success:
            await callback_query.message.edit_text("✅ Товар успешно удален")
        else:
            await callback_query.message.edit_text("❌ Не удалось удалить товар")
            
    except Exception as e:
        logger.error(f"Error in confirm_delete: {e}", exc_info=True)
        await callback_query.answer("❌ Произошла ошибка при удалении")

@dp.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback_query: types.CallbackQuery):
    """Обработчик отмены удаления товара"""
    try:
        await callback_query.message.edit_text("❌ Удаление товара отменено")
    except Exception as e:
        logger.error(f"Error in cancel_delete: {e}", exc_info=True)
        await callback_query.answer("❌ Произошла ошибка при отмене удаления")

@dp.message(AddProduct.waiting_for_category)
async def process_product_category(message: types.Message, state: FSMContext):
    """Обработчик выбора категории товара"""
    try:
        category = message.text
        await state.update_data(category=category)
        
        # Создаем клавиатуру с кнопками
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="📷 Добавить фото", callback_data="add_photo")],
            [types.InlineKeyboardButton(text="⏩ Пропустить", callback_data="skip_photo")]
        ])
        
        await message.answer(
            "Отправьте фото товара или нажмите 'Пропустить':",
            reply_markup=keyboard
        )
        await state.set_state(AddProduct.waiting_for_image)
        
    except Exception as e:
        logger.error(f"Error in process_product_category: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при выборе категории")
        await state.clear()

# Обработчик кнопки удаления товара
@dp.message(F.text == "🗑 Удалить товар")
async def delete_product_start(message: types.Message):
    """Обработчик кнопки удаления товара"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде")
        return
    
    try:
        # Получаем список всех товаров
        products = get_products()
        if not products:
            await message.answer("❌ В базе нет товаров для удаления")
            return
        
        # Создаем клавиатуру с товарами
        keyboard_buttons = []
        for product in products:
            keyboard_buttons.append([InlineKeyboardButton(
                text=f"{product['name']} - {product['price']} руб.",
                callback_data=f"delete_{product['id']}"
            )])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        await message.answer("Выберите товар для удаления:", reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in delete_product_start: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при получении списка товаров")

# Обработчик команды /update_admin
@dp.message(Command("update_admin"))
async def cmd_update_admin(message: types.Message):
    """Обновление статуса администратора"""
    try:
        if update_admin_status(message.from_user.id):
            await message.answer("✅ Статус администратора обновлен")
        else:
            await message.answer("❌ Пользователь не найден в базе данных")
    except Exception as e:
        logger.error(f"Error in update_admin command: {e}")
        await message.answer("❌ Произошла ошибка при обновлении статуса")

@dp.callback_query(F.data == "confirm_order")
async def confirm_order(callback: types.CallbackQuery):
    """Подтверждение заказа"""
    try:
        # Создаем заказ
        order_id = create_order(callback.from_user.id)
        if not order_id:
            await callback.message.answer("❌ Произошла ошибка при создании заказа")
            return
        
        # Получаем детали заказа
        order_details = get_order_details(order_id)
        if not order_details:
            await callback.message.answer("❌ Произошла ошибка при получении деталей заказа")
            return
        
        # Формируем сообщение о заказе
        order_message = (
            "🛒 Новый заказ!\n\n"
            f"👤 Пользователь: {order_details['username']}\n"
            f"🆔 ID: {order_details['user_id']}\n\n"
            "📦 Товары:\n"
        )
        
        for item in order_details['items']:
            order_message += f"• {item['name']} x{item['quantity']} - {item['price']}₽\n"
        
        order_message += f"\n💰 Итого: {order_details['total']}₽"
        
        # Получаем список ID администраторов
        admin_ids = get_admin_ids()
        logger.info(f"Sending order notification to admins: {admin_ids}")
        
        # Отправляем сообщение всем администраторам
        for admin_id in admin_ids:
            try:
                await bot.send_message(admin_id, order_message)
                logger.info(f"Order notification sent to admin {admin_id}")
            except Exception as e:
                logger.error(f"Error sending order notification to admin {admin_id}: {e}")
        
        # Отправляем сообщение пользователю
        await callback.message.answer(
            "✅ Заказ успешно оформлен!\n"
            "Администратор свяжется с вами в ближайшее время."
        )
        
        # Очищаем корзину
        clear_cart(callback.from_user.id)
        
    except Exception as e:
        logger.error(f"Error in confirm_order: {e}", exc_info=True)
        await callback.message.answer("❌ Произошла ошибка при оформлении заказа")

async def notify_admins(message: str, bot: Bot):
    """Отправка уведомления всем администраторам"""
    try:
        admin_ids = get_admin_ids()
        for admin_id in admin_ids:
            try:
                await bot.send_message(admin_id, message)
                logger.info(f"Notification sent to admin {admin_id}")
            except Exception as e:
                logger.error(f"Error sending notification to admin {admin_id}: {e}")
    except Exception as e:
        logger.error(f"Error in notify_admins: {e}")

async def backup_database():
    """Создание резервной копии базы данных"""
    try:
        # Создаем директорию для бэкапов, если её нет
        os.makedirs("backups", exist_ok=True)
        
        # Создаем имя файла с текущей датой и временем
        backup_filename = f"backups/shop_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        
        # Копируем файл базы данных
        shutil.copy2("shop.db", backup_filename)
        
        # Удаляем старые бэкапы (оставляем только последние 5)
        backup_files = sorted(glob.glob("backups/shop_*.db"))
        if len(backup_files) > 5:
            for old_backup in backup_files[:-5]:
                os.remove(old_backup)
        
        logger.info(f"Database backup created: {backup_filename}")
        return True
    except Exception as e:
        logger.error(f"Error creating database backup: {e}")
        return False

# Обработчик кнопки "📢 Рассылка"
@dp.message(F.text == "📢 Рассылка")
async def broadcast_start(message: types.Message, state: FSMContext):
    """Начало процесса массовой рассылки"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде")
        return
    
    await message.answer(
        "📢 Отправьте сообщение для рассылки всем пользователям.\n\n"
        "⚠️ Поддерживаются все типы сообщений (текст, фото, видео и т.д.)\n"
        "❌ Для отмены используйте команду /cancel"
    )
    await state.set_state(BroadcastStates.waiting_for_message)

# Обработчик сообщения для рассылки
@dp.message(BroadcastStates.waiting_for_message)
async def process_broadcast_message(message: types.Message, state: FSMContext):
    """Обработка сообщения для массовой рассылки"""
    try:
        # Получаем список всех пользователей
        user_ids = get_all_users()
        total_users = len(user_ids)
        successful_sends = 0
        failed_sends = 0
        
        # Отправляем сообщение о начале рассылки
        await message.answer(f"📢 Начинаю рассылку для {total_users} пользователей...")
        
        # Отправляем сообщение каждому пользователю
        for user_id in user_ids:
            try:
                # Копируем сообщение с сохранением всех атрибутов
                if message.photo:
                    await bot.send_photo(
                        user_id,
                        message.photo[-1].file_id,
                        caption=message.caption if message.caption else None
                    )
                elif message.video:
                    await bot.send_video(
                        user_id,
                        message.video.file_id,
                        caption=message.caption if message.caption else None
                    )
                elif message.document:
                    await bot.send_document(
                        user_id,
                        message.document.file_id,
                        caption=message.caption if message.caption else None
                    )
                else:
                    await bot.send_message(
                        user_id,
                        message.text
                    )
                successful_sends += 1
            except Exception as e:
                logger.error(f"Error sending broadcast to user {user_id}: {e}")
                failed_sends += 1
        
        # Отправляем отчет о результатах рассылки
        report_message = (
            "📊 Отчет о рассылке:\n\n"
            f"👥 Всего пользователей: {total_users}\n"
            f"✅ Успешно отправлено: {successful_sends}\n"
            f"❌ Не удалось отправить: {failed_sends}"
        )
        await message.answer(report_message)
        
    except Exception as e:
        logger.error(f"Error in broadcast process: {e}")
        await message.answer("❌ Произошла ошибка при рассылке")
    
    finally:
        await state.clear()

# Запуск бота
async def main():
    # Создаем резервную копию базы данных
    if await backup_database():
        logger.info("Database backup created successfully")
    else:
        logger.error("Failed to create database backup")
    
    # Отправляем уведомление администраторам о запуске бота
    await notify_admins("🤖 Бот запущен и готов к работе!", bot)
    
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 