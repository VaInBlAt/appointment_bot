from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from keyboards.basic import MainMenu as basic
from JSONfunctions import load_json_data, save_json_data
from handlers.states import States
from user_utils import is_user_registered, get_user_data

router = Router()

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

@router.message(States.registration_fio)
async def process_fio(message: types.Message, state: FSMContext):
    await state.update_data(registration_fio=message.text)
    
    # После ФИО сразу запрашиваем дату рождения
    await state.set_state(States.registration_birth_date)
    await message.answer(
        "📅 Введите вашу дату рождения в формате ДД.ММ.ГГГГ:\n\nНапример: 15.05.1990",
        reply_markup=basic.skip_step()
    )

@router.message(States.registration_birth_date)
async def process_birth_date(message: types.Message, state: FSMContext):
    """Обрабатывает ввод даты рождения при регистрации"""
    if message.text == 'Пропустить':
        await state.update_data(registration_birth_date="Не указано")
    else:
        birth_date = message.text.strip()
        
        if not validate_birth_date(birth_date):
            await message.answer("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ (например: 15.05.1990):")
            return
        
        await state.update_data(registration_birth_date=birth_date)
    
    # После даты рождения запрашиваем телефон
    await state.set_state(States.registration_phone)
    await message.answer(
        "📞 Введите ваш номер телефона:\n\nНапример: +79123456789 или 89123456789",
        reply_markup=basic.skip_step()
    )

@router.message(States.registration_phone)
async def process_phone(message: types.Message, state: FSMContext):
    """Обрабатывает ввод телефона при регистрации"""
    if message.text == 'Пропустить':
        await state.update_data(registration_phone="Не указано")
    else:
        phone = message.text.strip()
        
        if not validate_phone(phone):
            await message.answer("❌ Неверный формат номера. Используйте +79123456789 или 89123456789:")
            return
        
        await state.update_data(registration_phone=phone)
    
    # Продолжаем процесс регистрации в зависимости от роли
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

# Обновляем обработку пропуска для новых состояний
async def handle_skip(callback: types.CallbackQuery, state: FSMContext):
    """Обработка кнопки Пропустить"""
    current_state = await state.get_state()
    data = await state.get_data()
    role = data.get('registration_role')
    
    if current_state == States.registration_fio:
        await state.update_data(registration_fio="Не указано")
        await state.set_state(States.registration_birth_date)
        await callback.message.edit_text(
            "📅 Введите вашу дату рождения в формате ДД.ММ.ГГГГ:\n\nНапример: 15.05.1990",
            reply_markup=basic.skip_step()
        )
    
    elif current_state == States.registration_birth_date:
        await state.update_data(registration_birth_date="Не указано")
        await state.set_state(States.registration_phone)
        await callback.message.edit_text(
            "📞 Введите ваш номер телефона:\n\nНапример: +79123456789 или 89123456789",
            reply_markup=basic.skip_step()
        )
    
    elif current_state == States.registration_phone:
        await state.update_data(registration_phone="Не указано")
        
        # Продолжаем процесс регистрации в зависимости от роли
        if role == 'doctor':
            await state.set_state(States.registration_office_address)
            await callback.message.edit_text(
                "🏢 Введите адрес кабинета:",
                reply_markup=basic.skip_step()
            )
        else:
            # Для пациента пропускаем остальные поля и переходим к фото
            await state.update_data(registration_office_address="Не требуется")
            await state.update_data(registration_specialty="Не требуется")
            await state.update_data(registration_website_link="Не требуется")
            await state.set_state(States.registration_photo)
            await callback.message.edit_text(
                "📷 Загрузите фото профиля:",
                reply_markup=basic.skip_step()
            )
    
    # Остальные случаи пропуска остаются без изменений
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
    birth_date = data.get('registration_birth_date', 'Не указано')
    phone = data.get('registration_phone', 'Не указано')
    office = data.get('registration_office_address', 'Не указано')
    specialty = data.get('registration_specialty', 'Не указано')
    website = data.get('registration_website_link', 'Не указано')
    photo = "✅ Загружено" if data.get('registration_photo') else "❌ Не загружено"
    
    summary_text = f"""
📋 Сводка регистрации:

👤 Роль: {role_text}
📝 ФИО: {fio}
📅 Дата рождения: {birth_date}
📞 Телефон: {phone}
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
            "birth_date": data.get('registration_birth_date'),  # Новое поле
            "phone": data.get('registration_phone'),            # Новое поле
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


def validate_birth_date(date_str: str) -> bool:
    """Проверяет корректность формата даты рождения ДД.ММ.ГГГГ"""
    import re
    pattern = r'^(0[1-9]|[12][0-9]|3[01])\.(0[1-9]|1[0-2])\.(19|20)\d{2}$'
    if not re.match(pattern, date_str):
        return False
    
    # Проверяем что дата не в будущем
    try:
        from datetime import datetime
        day, month, year = map(int, date_str.split('.'))
        birth_date = datetime(year, month, day)
        return birth_date <= datetime.now()
    except ValueError:
        return False

def validate_phone(phone: str) -> bool:
    """Проверяет корректность формата номера телефона"""
    import re
    # Российские номера: +7XXXXXXXXXX или 8XXXXXXXXXX
    pattern = r'^(\+7|8)\d{10}$'
    phone_clean = re.sub(r'[\s\-\(\)]', '', phone)
    return bool(re.match(pattern, phone_clean))