from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from typing import Optional
from keyboards.basic import MainMenu as basic
from keyboards.calendar import CalendarKeyboard
from keyboards.weekend_selection import WeekendSelectionKeyboard
from JSONfunctions import load_json_data, save_json_data
from datetime import datetime

router = Router()

class States(StatesGroup):
    registration_role: Optional[str] = State()
    registration_fio: Optional[str] = State()
    registration_office_address: Optional[str] = State()
    registration_specialty: Optional[str] = State()
    registration_website_link: Optional[str] = State()
    registration_photo: Optional[str] = State()
# Глобальный словарь для временного хранения выбранных выходных (user_id -> set of dates)
temp_weekends_storage = {}

def get_doctor_weekends(user_id: int) -> set:
    """Получает сохраненные выходные дни врача из JSON"""
    users_data = load_json_data('users')
    user_data = users_data["users"].get(str(user_id), {})
    weekends = user_data.get("weekends", [])
    return set(weekends)

def save_doctor_weekends(user_id: int, weekends: set):
    """Сохраняет выходные дни врача в JSON"""
    users_data = load_json_data('users')
    if str(user_id) in users_data["users"]:
        users_data["users"][str(user_id)]["weekends"] = list(weekends)
        save_json_data(users_data, 'users')

@router.message(Command("start"))
@router.callback_query(F.data == 'exit')
async def start_handler(update: types.Message | types.CallbackQuery, state: FSMContext):
    await state.clear()
    
    user_id = update.from_user.id
    is_callback = isinstance(update, types.CallbackQuery)
    message = update if not is_callback else update.message
    
    if is_user_registered(user_id):
        user_data = get_user_data(user_id)
        role_text = "врач" if user_data["registration_data"]["role"] == "doctor" else "пациент"
        text = f"👋 С возвращением, {user_data['registration_data']['fio']}!\nВы зарегистрированы как {role_text}."
        markup = basic.main_menu()
    else:
        text = "👋 Добро пожаловать!\nЕсли вы здесь впервые, пожалуйста, зарегистрируйтесь"
        markup = basic.start()
    
    if is_callback:
        await message.edit_text(text, reply_markup=markup)
        await update.answer()
    else:
        await message.answer(text, reply_markup=markup)

@router.callback_query(F.data.startswith('registration'))
async def handle_registration(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split('_')
    
    if len(parts) < 2:
        await callback.answer("Ошибка обработки запроса")
        return
    
    action = parts[1]  # step, confirm, restart, skip
    
    match action:
        case 'step1':
            await callback.message.edit_text(
                'Кем вы являетесь?',
                reply_markup=basic.step1()
            )
        
        case 'step2':
            if len(parts) >= 3:
                role = parts[2]
                await state.update_data(registration_role=role)
                await state.set_state(States.registration_fio)
                await callback.message.edit_text('📝 Введите ваше ФИО:')
                await callback.message.answer(
                    "Нажмите 'Пропустить', если не хотите заполнять этот пункт",
                    reply_markup=basic.skip_step()
                )
            else:
                await callback.answer("Ошибка выбора роли")
        
        case 'skip':
            await handle_skip(callback, state)
        
        case 'confirm':
            await save_registration_data(callback, state)
        
        case 'restart':
            await state.clear()
            await callback.message.edit_text(
                "👋 Добро пожаловать!\nЕсли вы здесь впервые, пожалуйста, зарегистрируйтесь",
                reply_markup=basic.start()
            )
        
        case _:
            await callback.answer("Неизвестное действие")

async def handle_skip(callback: types.CallbackQuery, state: FSMContext):
    """Обработка кнопки Пропустить"""
    current_state = await state.get_state()
    data = await state.get_data()
    role = data.get('registration_role')
    
    if current_state == States.registration_fio:
        await state.update_data(registration_fio="Не указано")
        
        # Для врача запрашиваем адрес кабинета, для пациента сразу специальность
        if role == 'doctor':
            await state.set_state(States.registration_office_address)
            await callback.message.edit_text(
                "🏢 Введите адрес кабинета:",
                reply_markup=basic.skip_step()
            )
        else:
            # Для пациента пропускаем адрес и специальность, переходим к фото
            await state.update_data(registration_office_address="Не требуется")
            await state.update_data(registration_specialty="Не требуется")
            await state.update_data(registration_website_link="Не требуется")
            await state.set_state(States.registration_photo)
            await callback.message.edit_text(
                "📷 Загрузите фото профиля:",
                reply_markup=basic.skip_step()
            )
    
    elif current_state == States.registration_office_address:
        await state.update_data(registration_office_address="Не указано")
        await state.set_state(States.registration_specialty)
        await callback.message.edit_text(
            "🏥 Введите вашу специальность:",
            reply_markup=basic.skip_step()
        )
    
    elif current_state == States.registration_specialty:
        await state.update_data(registration_specialty="Не указано")
        await state.set_state(States.registration_website_link)
        await callback.message.edit_text(
            "🌐 Введите ссылку с сайта 'На поправку':",
            reply_markup=basic.skip_step()
        )
    
    elif current_state == States.registration_website_link:
        await state.update_data(registration_website_link="Не указано")
        await state.set_state(States.registration_photo)
        await callback.message.edit_text(
            "📷 Загрузите фото профиля:",
            reply_markup=basic.skip_step()
        )
    
    elif current_state == States.registration_photo:
        await state.update_data(registration_photo=None)
        await show_summary(callback, state)
    
    else:
        await callback.answer("Нельзя пропустить этот шаг")

@router.message(States.registration_fio)
async def process_fio(message: types.Message, state: FSMContext):
    await state.update_data(registration_fio=message.text)
    data = await state.get_data()
    role = data.get('registration_role')
    
    # Для врача запрашиваем адрес кабинета, для пациента сразу фото
    if role == 'doctor':
        await state.set_state(States.registration_office_address)
        await message.answer(
            "🏢 Введите адрес кабинета:",
            reply_markup=basic.skip_step()
        )
    else:
        # Для пациента пропускаем остальные поля и переходим к фото
        await state.update_data(registration_office_address="Не требуется")
        await state.update_data(registration_specialty="Не требуется")
        await state.update_data(registration_website_link="Не требуется")
        await state.set_state(States.registration_photo)
        await message.answer(
            "📷 Загрузите фото профиля:",
            reply_markup=basic.skip_step()
        )

@router.message(States.registration_office_address)
async def process_office_address(message: types.Message, state: FSMContext):
    await state.update_data(registration_office_address=message.text)
    await state.set_state(States.registration_specialty)
    await message.answer(
        "🏥 Введите вашу специальность:",
        reply_markup=basic.skip_step()
    )

@router.message(States.registration_specialty)
async def process_specialty(message: types.Message, state: FSMContext):
    await state.update_data(registration_specialty=message.text)
    await state.set_state(States.registration_website_link)
    await message.answer(
        "🌐 Введите ссылку с сайта 'На поправку':",
        reply_markup=basic.skip_step()
    )

@router.message(States.registration_website_link)
async def process_website_link(message: types.Message, state: FSMContext):
    await state.update_data(registration_website_link=message.text)
    await state.set_state(States.registration_photo)
    await message.answer(
        "📷 Загрузите фото профиля:",
        reply_markup=basic.skip_step()
    )

@router.message(States.registration_photo)
async def process_photo(message: types.Message, state: FSMContext):
    if message.photo:
        photo_id = message.photo[-1].file_id
        await state.update_data(registration_photo=photo_id)
        await show_summary(message, state)
    else:
        await message.answer("Пожалуйста, загрузите фото:", reply_markup=basic.skip_step())

async def show_summary(message: types.Message | types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    role_text = "Врач" if data.get('registration_role') == 'doctor' else "Пациент"
    fio = data.get('registration_fio', 'Не указано')
    office = data.get('registration_office_address', 'Не указано')
    specialty = data.get('registration_specialty', 'Не указано')
    website = data.get('registration_website_link', 'Не указано')
    photo = "✅ Загружено" if data.get('registration_photo') else "❌ Не загружено"
    
    summary_text = f"""
📋 Сводка регистрации:

👤 Роль: {role_text}
📝 ФИО: {fio}
"""
    
    # Добавляем поля только для врачей
    if data.get('registration_role') == 'doctor':
        summary_text += f"🏢 Адрес кабинета: {office}\n"
        summary_text += f"🏥 Специальность: {specialty}\n"
        summary_text += f"🌐 Ссылка: {website}\n"
    
    summary_text += f"📷 Фото: {photo}\n\nВсё верно?"

    if isinstance(message, types.CallbackQuery):
        await message.message.edit_text(summary_text, reply_markup=basic.confirm_registration())
    else:
        await message.answer(summary_text, reply_markup=basic.confirm_registration())

async def save_registration_data(callback: types.CallbackQuery, state: FSMContext):
    """Сохраняет данные регистрации в JSON"""
    data = await state.get_data()
    user_id = str(callback.from_user.id)
    
    users_data = load_json_data('users')
    
    users_data["users"][user_id] = {
        "user_id": user_id,
        "username": callback.from_user.username or "",
        "first_name": callback.from_user.first_name or "",
        "last_name": callback.from_user.last_name or "",
        "registration_data": {
            "role": data.get('registration_role'),
            "fio": data.get('registration_fio'),
            "office_address": data.get('registration_office_address'),
            "specialty": data.get('registration_specialty'),
            "website_link": data.get('registration_website_link'),
            "photo_file_id": data.get('registration_photo'),
            "registration_date": callback.message.date.isoformat() if callback.message else ""
        }
    }
    
    save_json_data(users_data, 'users')
    
    await callback.message.edit_text(
        "✅ Регистрация завершена! Ваши данные сохранены.",
        reply_markup=basic.main_menu()
    )
    await state.clear()

def is_user_registered(user_id: int) -> bool:
    """Проверяет, зарегистрирован ли пользователь"""
    users_data = load_json_data('users')
    return str(user_id) in users_data["users"]

def get_user_data(user_id: int):
    """Возвращает данные пользователя"""
    users_data = load_json_data('users')
    return users_data["users"].get(str(user_id))

@router.callback_query(F.data == 'profile')
async def show_user_profile(callback: types.CallbackQuery):
    """Показывает информацию о пользователе в личном кабинете"""
    
    # Проверяем, зарегистрирован ли пользователь
    if not is_user_registered(callback.from_user.id):
        await callback.answer("❌ Вы еще не зарегистрированы!", show_alert=True)
        return
    
    # Получаем данные пользователя
    user_data = get_user_data(callback.from_user.id)
    reg_data = user_data["registration_data"]
    
    # Формируем текст профиля
    role_text = "👨‍⚕️ Врач" if reg_data["role"] == "doctor" else "👤 Пациент"
    fio = reg_data.get("fio", "Не указано")
    
    profile_text = f"""
📊 Личный кабинет

{role_text}
📝 ФИО: {fio}
"""
    
    # Добавляем дополнительные поля для врачей
    if reg_data["role"] == "doctor":
        office = reg_data.get("office_address", "Не указано")
        specialty = reg_data.get("specialty", "Не указано")
        website = reg_data.get("website_link", "Не указано")
        
        profile_text += f"🏢 Адрес кабинета: {office}\n"
        profile_text += f"🏥 Специальность: {specialty}\n"
        profile_text += f"🌐 Ссылка на профиль: {website}\n"
    
    # Добавляем информацию о фото
    photo_status = "✅ Загружено" if reg_data.get("photo_file_id") else "❌ Отсутствует"
    profile_text += f"📷 Фото профиля: {photo_status}"
    
    # Добавляем информацию о дате регистрации, если есть
    if reg_data.get("registration_date"):
        from datetime import datetime
        try:
            reg_date = datetime.fromisoformat(reg_data["registration_date"]).strftime("%d.%m.%Y")
            profile_text += f"\n📅 Дата регистрации: {reg_date}"
        except:
            pass
    
    # Отправляем сообщение с профилем
    await callback.message.edit_text(
        profile_text,
        reply_markup=basic.exit()
    )
    await callback.answer()

@router.callback_query(F.data == 'appointment_calendar')
async def show_calendar(callback: types.CallbackQuery):
    """Показывает календарь для записи на прием"""
    today = datetime.now()
    year = today.year
    month = today.month
    
    user_id = callback.from_user.id
    is_doctor = False
    weekends = set()
    
    if is_user_registered(user_id):
        user_data = get_user_data(user_id)
        if user_data["registration_data"]["role"] == "doctor":
            is_doctor = True
            weekends = get_doctor_weekends(user_id)
    
    markup = CalendarKeyboard.create_calendar(year, month, is_doctor=is_doctor, weekends=weekends)
    
    text = f"📅 Запись на прием\n{CalendarKeyboard.MONTHS_RU[month-1]} {year}"
    if is_doctor and weekends:
        text += f"\n✅ - ваши выходные дни ({len(weekends)} дней)"
    
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()

@router.callback_query(F.data.startswith('calendar_prev_') | F.data.startswith('calendar_next_'))
async def navigate_calendar(callback: types.CallbackQuery):
    """Обрабатывает навигацию по календарю (только между текущим и следующим месяцем)"""
    data = callback.data
    parts = data.split('_')
    
    if len(parts) != 4:
        await callback.answer("Ошибка навигации")
        return
    
    year = int(parts[2])
    month = int(parts[3])
    
    user_id = callback.from_user.id
    is_doctor = False
    weekends = set()
    
    if is_user_registered(user_id):
        user_data = get_user_data(user_id)
        if user_data["registration_data"]["role"] == "doctor":
            is_doctor = True
            weekends = get_doctor_weekends(user_id)
    
    markup = CalendarKeyboard.create_calendar(year, month, is_doctor=is_doctor, weekends=weekends)
    
    text = f"📅 Запись на прием\n{CalendarKeyboard.MONTHS_RU[month-1]} {year}"
    if is_doctor and weekends:
        text += f"\n✅ - ваши выходные дни ({len(weekends)} дней)"
    
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()

@router.callback_query(F.data.startswith('appointment_date_'))
async def select_appointment_date(callback: types.CallbackQuery):
    """Обрабатывает выбор даты для записи"""
    data = callback.data
    parts = data.split('_')
    
    if len(parts) != 5:
        await callback.answer("Ошибка выбора даты")
        return
    
    year = int(parts[2])
    month = int(parts[3])
    day = int(parts[4])
    
    selected_date = datetime(year, month, day).date()
    today = datetime.now().date()
    
    if selected_date < today:
        await callback.answer("Нельзя выбрать прошедшую дату")
        return

    month_name = CalendarKeyboard.MONTHS_RU[month-1]
    
    await callback.answer(f"Выбрана дата: {day} {month_name} {year}", show_alert=True)

@router.callback_query(F.data == 'weekend_selection')
async def start_weekend_selection(callback: types.CallbackQuery):
    """Начинает процесс выбора выходных дней"""
    user_id = callback.from_user.id
    
    # Проверяем, что пользователь - врач
    if not is_user_registered(user_id):
        await callback.answer("❌ Вы еще не зарегистрированы!", show_alert=True)
        return
    
    user_data = get_user_data(user_id)
    if user_data["registration_data"]["role"] != "doctor":
        await callback.answer("❌ Эта функция доступна только врачам!", show_alert=True)
        return
    
    today = datetime.now()
    year = today.year
    month = today.month
    
    # Загружаем текущие выходные врача и сохраняем во временное хранилище
    weekends = get_doctor_weekends(user_id)
    temp_weekends_storage[user_id] = weekends.copy()
    
    markup = WeekendSelectionKeyboard.create_calendar(year, month, weekends)
    
    await callback.message.edit_text(
        "📅 Выбор выходных дней\nНажимайте на даты, чтобы отметить их как выходные\nЗатем нажмите 'Подтвердить ✅'",
        reply_markup=markup
    )
    await callback.answer()

@router.callback_query(F.data.startswith('weekend_select_'))
async def select_weekend_day(callback: types.CallbackQuery):
    """Добавляет/убирает день из выбранных выходных"""
    user_id = callback.from_user.id
    
    # Проверяем, что пользователь - врач
    user_data = get_user_data(user_id)
    if user_data["registration_data"]["role"] != "doctor":
        await callback.answer("❌ Эта функция доступна только врачам!", show_alert=True)
        return
    
    data = callback.data
    parts = data.split('_')
    
    if len(parts) != 5:
        await callback.answer("Ошибка выбора даты")
        return
    
    year = int(parts[2])
    month = int(parts[3])
    day = int(parts[4])
    
    selected_date = datetime(year, month, day).date()
    date_str = selected_date.isoformat()
    
    # Получаем текущие выбранные даты из временного хранилища
    if user_id not in temp_weekends_storage:
        temp_weekends_storage[user_id] = set()
    
    weekends = temp_weekends_storage[user_id]
    
    # Переключаем состояние
    if date_str in weekends:
        weekends.remove(date_str)
    else:
        weekends.add(date_str)
    
    # Обновляем временное хранилище
    temp_weekends_storage[user_id] = weekends
    
    # Обновляем календарь
    markup = WeekendSelectionKeyboard.create_calendar(year, month, weekends)
    
    await callback.message.edit_text(
        "📅 Выбор выходных дней\nНажимайте на даты, чтобы отметить их как выходные\nЗатем нажмите 'Подтвердить ✅'",
        reply_markup=markup
    )
    await callback.answer()

@router.callback_query(F.data.startswith('weekend_nav_'))
async def navigate_weekend_calendar(callback: types.CallbackQuery):
    """Обрабатывает навигацию по календарю выходных (только между текущим и следующим месяцем)"""
    user_id = callback.from_user.id
    data = callback.data
    parts = data.split('_')
    
    if len(parts) != 4:
        await callback.answer("Ошибка навигации")
        return
    
    year = int(parts[2])
    month = int(parts[3])
    
    # Получаем текущие выбранные даты из временного хранилища
    if user_id not in temp_weekends_storage:
        temp_weekends_storage[user_id] = set()
    
    weekends = temp_weekends_storage[user_id]
    
    markup = WeekendSelectionKeyboard.create_calendar(year, month, weekends)
    
    await callback.message.edit_text(
        "📅 Выбор выходных дней\nНажимайте на даты, чтобы отметить их как выходные\nЗатем нажмите 'Подтвердить ✅'",
        reply_markup=markup
    )
    await callback.answer()

@router.callback_query(F.data == 'weekend_confirm')
async def confirm_weekends(callback: types.CallbackQuery):
    """Подтверждает выбор выходных дней и сохраняет их в JSON"""
    user_id = callback.from_user.id
    
    # Получаем выбранные даты из временного хранилища
    if user_id not in temp_weekends_storage:
        await callback.answer("❌ Не выбрано ни одного дня!", show_alert=True)
        return
    
    weekends = temp_weekends_storage[user_id]
    
    # Сохраняем в JSON
    save_doctor_weekends(user_id, weekends)
    
    # Очищаем временное хранилище
    if user_id in temp_weekends_storage:
        del temp_weekends_storage[user_id]
    
    await callback.answer(f"✅ Сохранено выходных дней: {len(weekends)}", show_alert=True)
    
    # Возвращаемся к обычному календарю
    today = datetime.now()
    year = today.year
    month = today.month
    
    markup = CalendarKeyboard.create_calendar(year, month, is_doctor=True, weekends=weekends)
    
    await callback.message.edit_text(
        f"📅 Запись на прием\n✅ - выходные дни\n{CalendarKeyboard.MONTHS_RU[month-1]} {year}",
        reply_markup=markup
    )