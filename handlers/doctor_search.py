from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from keyboards.basic import MainMenu as basic
from keyboards.calendar import CalendarKeyboard
from handlers.states import States
from user_utils import is_user_registered, get_user_data, get_doctor_weekends, find_doctors_by_query, get_short_name
from datetime import datetime
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()

@router.callback_query(F.data == 'finddoctor')
async def start_find_doctor(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс поиска врача"""
    await state.set_state(States.find_doctor_query)
    
    text = """🔎 Поиск врача
    
Введите фамилию врача, адрес кабинета или специальность для поиска.

Например:
• Иванов
• Терапевт
• Москва
• ул. Ленина"""

    await callback.message.edit_text(
        text,
        reply_markup=basic.exit()
    )
    await callback.answer()

@router.message(States.find_doctor_query)
async def process_find_doctor_query(message: types.Message, state: FSMContext):
    """Обрабатывает поисковый запрос и показывает результаты"""
    search_query = message.text.strip().lower()
    
    if not search_query:
        await message.answer("Пожалуйста, введите поисковый запрос:")
        return
    
    # Ищем врачей по всем полям
    found_doctors = find_doctors_by_query(search_query)
    
    if not found_doctors:
        await message.answer(
            f"❌ По запросу '{message.text}' врачей не найдено.\n\nПопробуйте другой запрос:",
            reply_markup=basic.exit()
        )
        return
    
    # Формируем список найденных врачей
    results_text = f"🔎 Найдено врачей: {len(found_doctors)}\n\n"
    
    for i, doctor_data in enumerate(found_doctors, 1):
        reg_data = doctor_data["registration_data"]
        results_text += f"{i}. 👨‍⚕️ {reg_data['fio']}\n"
        results_text += f"   🏥 {reg_data['specialty']}\n"
        results_text += f"   🏢 {reg_data['office_address']}\n"
        
        if reg_data.get('website_link') and reg_data['website_link'] != "Не указано":
            results_text += f"   🌐 {reg_data['website_link']}\n"
        
        results_text += "\n"
    
    # Создаем клавиатуру с кнопками для каждого врача
    builder = InlineKeyboardBuilder()
    
    for doctor_data in found_doctors:
        reg_data = doctor_data["registration_data"]
        doctor_user_id = doctor_data["user_id"]
        
        # Сокращаем ФИО для кнопки
        short_name = get_short_name(reg_data['fio'])
        
        builder.add(InlineKeyboardButton(
            text=short_name,
            callback_data=f"doctor_calendar_{doctor_user_id}"
        ))
    
    # Добавляем кнопку "На главную"
    builder.add(InlineKeyboardButton(
        text="🏠 На главную", 
        callback_data="exit"
    ))
    
    # Располагаем кнопки по одной в строке
    builder.adjust(1)
    
    await message.answer(results_text, reply_markup=builder.as_markup())
    await state.set_state(States.find_doctor_query)

@router.callback_query(F.data.startswith('doctor_calendar_') & ~F.data.contains('nav'))
async def show_doctor_calendar(callback: types.CallbackQuery):
    """Показывает календарь выбранного врача (только при прямом вызове, не навигация)"""
    data = callback.data
    parts = data.split('_')
    
    if len(parts) != 3:
        await callback.answer("Ошибка открытия календаря")
        return
    
    doctor_user_id = int(parts[2])
    
    # Получаем данные врача
    doctor_data = get_user_data(doctor_user_id)
    if not doctor_data or doctor_data["registration_data"]["role"] != "doctor":
        await callback.answer("❌ Врач не найден!", show_alert=True)
        return
    
    today = datetime.now()
    year = today.year
    month = today.month
    
    # Получаем выходные ВРАЧА
    weekends = get_doctor_weekends(doctor_user_id)
    
    # Создаем календарь врача (is_doctor=False, но передаем doctor_id)
    markup = CalendarKeyboard.create_calendar(
        year=year, 
        month=month, 
        is_doctor=False, 
        weekends=weekends,
        doctor_id=doctor_user_id
    )
    
    reg_data = doctor_data["registration_data"]
    doctor_name = reg_data['fio']
    
    text = f"📅 Запись к врачу\n👨‍⚕️ {doctor_name}\n{CalendarKeyboard.MONTHS_RU[month-1]} {year}\n❌ - выходные дни"
    
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()

@router.callback_query(F.data.startswith('doctor_calendar_nav_'))
async def navigate_doctor_calendar(callback: types.CallbackQuery):
    """Обрабатывает навигацию по календарю врача"""
    data = callback.data
    parts = data.split('_')
    
    if len(parts) != 6:
        await callback.answer("Ошибка навигации")
        return
    
    doctor_id = int(parts[3])
    year = int(parts[4])
    month = int(parts[5])
    
    # Получаем данные врача
    doctor_data = get_user_data(doctor_id)
    if not doctor_data or doctor_data["registration_data"]["role"] != "doctor":
        await callback.answer("❌ Врач не найден!", show_alert=True)
        return
    
    # Получаем выходные врача
    weekends = get_doctor_weekends(doctor_id)
    
    # Создаем календарь врача
    markup = CalendarKeyboard.create_calendar(
        year=year, 
        month=month, 
        is_doctor=False, 
        weekends=weekends,
        doctor_id=doctor_id
    )
    
    reg_data = doctor_data["registration_data"]
    doctor_name = reg_data['fio']
    
    text = f"📅 Запись к врачу\n👨‍⚕️ {doctor_name}\n{CalendarKeyboard.MONTHS_RU[month-1]} {year}\n❌ - выходные дни"
    
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()

@router.callback_query(F.data.startswith('appointment_doctor_'))
async def select_doctor_appointment_date(callback: types.CallbackQuery):
    """Обрабатывает выбор даты для записи к конкретному врачу"""
    data = callback.data
    parts = data.split('_')
    
    if len(parts) != 7:
        await callback.answer("Ошибка выбора даты")
        return
    
    doctor_id = int(parts[2])
    year = int(parts[3])
    month = int(parts[4])
    day = int(parts[5])
    
    # Получаем данные врача
    doctor_data = get_user_data(doctor_id)
    if not doctor_data:
        await callback.answer("❌ Врач не найден!", show_alert=True)
        return
    
    selected_date = datetime(year, month, day).date()
    today = datetime.now().date()
    
    if selected_date < today:
        await callback.answer("Нельзя выбрать прошедшую дату")
        return

    reg_data = doctor_data["registration_data"]
    doctor_name = reg_data['fio']
    month_name = CalendarKeyboard.MONTHS_RU[month-1]
    
    # TODO: Здесь будет логика записи на прием к врачу
    await callback.answer(
        f"✅ Запись к врачу {doctor_name} на {day} {month_name} {year}\nЗапрос отправлен!",
        show_alert=True
    )