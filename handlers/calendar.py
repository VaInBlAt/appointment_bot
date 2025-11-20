from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from keyboards.basic import MainMenu as basic
from keyboards.calendar import CalendarKeyboard
from keyboards.weekend_selection import WeekendSelectionKeyboard
from handlers.states import States
from user_utils import *
from datetime import datetime
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()
temp_weekends_storage = {}

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
    """Обрабатывает навигацию по календарю (текущий пользователь)"""
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

@router.callback_query(F.data.startswith('calendar_nav_'))
async def navigate_calendar(callback: types.CallbackQuery):
    """Обрабатывает навигацию по личному календарю"""
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
    """Обрабатывает выбор даты и показывает выбор типа приема"""
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

    # Определяем doctor_id (для личного календаря - текущий пользователь)
    user_id = callback.from_user.id
    doctor_id = user_id
    
    # Получаем данные врача
    doctor_data = get_user_data(doctor_id)
    if not doctor_data or doctor_data["registration_data"]["role"] != "doctor":
        await callback.answer("❌ Функция записи доступна только врачам!", show_alert=True)
        return
    
    reg_data = doctor_data["registration_data"]
    doctor_name = reg_data['fio']
    month_name = CalendarKeyboard.MONTHS_RU[month-1]
    
    # Формируем текст
    text = f"Запись на {day} {month_name} {year}.\nПервичный прием к врачу {doctor_name}"
    
    # Создаем клавиатуру с выбором типа приема
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="Первичная запись", 
        callback_data=f"appointment_primary_{doctor_id}_{year}_{month}_{day}"
    ))
    builder.add(InlineKeyboardButton(
        text="Вторичная запись", 
        callback_data=f"appointment_repeat_{doctor_id}_{year}_{month}_{day}"
    ))
    builder.add(InlineKeyboardButton(
        text="🏠 На главную", 
        callback_data="exit"
    ))
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith('appointment_primary_'))
async def choose_primary_time(callback: types.CallbackQuery):
    """Показывает доступные временные интервалы для первичного приема"""
    await show_time_slots(callback, "primary")

@router.callback_query(F.data.startswith('appointment_repeat_'))
async def choose_repeat_time(callback: types.CallbackQuery):
    """Показывает доступные временные интервалы для вторичного приема"""
    await show_time_slots(callback, "repeat")

async def show_time_slots(callback: types.CallbackQuery, appointment_type: str):
    """Показывает доступные временные интервалы"""
    data = callback.data
    parts = data.split('_')
    
    if len(parts) != 6:
        await callback.answer("Ошибка выбора типа приема")
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
    
    # Получаем расписание врача
    schedule = get_doctor_schedule(doctor_id)
    if not schedule:
        await callback.answer("❌ У врача не настроено расписание!", show_alert=True)
        return
    
    # Определяем временной диапазон в зависимости от типа приема
    if appointment_type == "primary":
        start_time = schedule.get("primary_start")
        end_time = schedule.get("primary_end")
        type_text = "Первичный"
    else:
        start_time = schedule.get("repeat_start")
        end_time = schedule.get("repeat_end")
        type_text = "Вторичный"
    
    if not start_time or not end_time:
        await callback.answer("❌ В расписании врача не указано время для данного типа приема!", show_alert=True)
        return
    
    # Генерируем временные интервалы
    time_slots = generate_time_slots(start_time, end_time, schedule["patient_time"])
    
    if not time_slots:
        await callback.answer("❌ Нет доступных временных интервалов!", show_alert=True)
        return
    
    reg_data = doctor_data["registration_data"]
    doctor_name = reg_data['fio']
    month_name = CalendarKeyboard.MONTHS_RU[month-1]
    
    text = f"Запись на {day} {month_name} {year}.\n{type_text} прием к врачу {doctor_name}"
    
    # Создаем клавиатуру с временными интервалами
    builder = InlineKeyboardBuilder()
    for slot in time_slots:
        builder.add(InlineKeyboardButton(
            text=slot,
            callback_data=f"appointment_time_{doctor_id}_{year}_{month}_{day}_{slot}_{appointment_type}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="🏠 На главную", 
        callback_data="exit"
    ))
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

'''@router.callback_query(F.data.startswith('appointment_time_'))
async def select_appointment_time(callback: types.CallbackQuery):
    """Обрабатывает выбор временного интервала"""
    data = callback.data
    parts = data.split('_')
    
    if len(parts) != 8:
        await callback.answer("Ошибка выбора времени")
        return
    
    doctor_id = int(parts[2])
    year = int(parts[3])
    month = int(parts[4])
    day = int(parts[5])
    time_slot = parts[6]
    appointment_type = parts[7]
    
    # Получаем данные врача
    doctor_data = get_user_data(doctor_id)
    if not doctor_data:
        await callback.answer("❌ Врач не найден!", show_alert=True)
        return
    
    reg_data = doctor_data["registration_data"]
    doctor_name = reg_data['fio']
    
    type_text = "Первичный" if appointment_type == "primary" else "Вторичный"
    month_name = CalendarKeyboard.MONTHS_RU[month-1]
    
    await callback.answer(
        f"✅ Запись на {type_text} прием к врачу {doctor_name} на {day} {month_name} {year} {time_slot}",
        show_alert=True
    )'''

def generate_time_slots(start_time: str, end_time: str, patient_time: int) -> list:
    """Генерирует список временных интервалов в формате ЧЧ:00-ЧЧ:30"""
    slots = []
    start_h, start_m = map(int, start_time.split(':'))
    end_h, end_m = map(int, end_time.split(':'))
    
    start_total = start_h * 60 + start_m
    end_total = end_h * 60 + end_m
    
    current = start_total
    while current + patient_time <= end_total:
        # Форматируем начало и конец интервала
        start_slot = f"{current//60:02d}:{(current%60):02d}"
        end_slot = f"{(current+patient_time)//60:02d}:{((current+patient_time)%60):02d}"
        slots.append(f"{start_slot}-{end_slot}")
        current += patient_time
    
    return slots