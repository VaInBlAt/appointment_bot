from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from keyboards.basic import MainMenu as basic
from keyboards.calendar import CalendarKeyboard
from keyboards.weekend_selection import WeekendSelectionKeyboard
from handlers.states import States
from user_utils import *
from datetime import datetime
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from JSONfunctions import load_json_data
from config import settings

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
    """Добавляет/убирает день из выбранных выходных с уведомлениями"""
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
    
    # Проверяем, добавляем или убираем выходной
    was_weekend = date_str in weekends
    
    if was_weekend:
        # Убираем выходной
        weekends.remove(date_str)
        action = "removed"
    else:
        # Добавляем выходной - проверяем есть ли записи на этот день
        appointments_on_date = get_appointments_on_date(user_id, year, month, day)
        if appointments_on_date:
            # Есть записи - отправляем уведомления и удаляем записи
            await notify_patients_about_cancellation(appointments_on_date, selected_date, settings.BOT_TOKEN)
            delete_appointments_on_date(appointments_on_date)
        
        weekends.add(date_str)
        action = "added"
    
    # Обновляем временное хранилище
    temp_weekends_storage[user_id] = weekends
    
    # Обновляем календарь
    markup = WeekendSelectionKeyboard.create_calendar(year, month, weekends)
  
    await callback.message.edit_text(
        "📅 Выбор выходных дней\nНажимайте на даты, чтобы отметить их как выходные\nЗатем нажмите 'Подтвердить ✅'",
        reply_markup=markup
    )

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
    """Обрабатывает выбор даты в личном календаре врача"""
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

    user_id = callback.from_user.id
    
    # Проверяем, является ли пользователь врачом
    if is_user_registered(user_id):
        user_data = get_user_data(user_id)
        if user_data["registration_data"]["role"] == "doctor":
            # Показываем записи на выбранный день
            await show_doctor_day_appointments(callback, user_id, year, month, day)
            return
    
    # Для пациентов или если что-то пошло не так - обычный выбор типа приема
    await show_appointment_type_selection(callback, user_id, year, month, day)

async def show_doctor_day_appointments(callback: types.CallbackQuery, doctor_id: int, year: int, month: int, day: int):
    """Показывает записи врача на конкретный день"""
    appointments_data = load_json_data('appointments')
    
    # Форматируем дату для поиска
    target_date = f"{year}-{month:02d}-{day:02d}"
    
    # Находим записи врача на эту дату
    day_appointments = []
    for appointment_id, appointment in appointments_data.get("appointments", {}).items():
        if (appointment["doctor_id"] == str(doctor_id) and 
            appointment["date"] == target_date):
            day_appointments.append(appointment)
    
    # Сортируем записи по времени
    day_appointments.sort(key=lambda x: x['time_slot'])
    
    month_name = CalendarKeyboard.MONTHS_RU[month-1]
    
    # Формируем текст
    text = f"📅 Записи на {day} {month_name} {year}\n\n"
    
    if not day_appointments:
        text += "На этот день записей нет."
    else:
        text += f"Всего записей: {len(day_appointments)}\n\n"
        
        for appointment in day_appointments:
            time_slot = appointment["time_slot"]
            patient_fio = appointment["patient_fio"]
            appointment_type = "Первичный" if appointment["appointment_type"] == "primary" else "Вторичный"
            status = get_appointment_status_text(appointment["status"])
            
            text += f"⏰ {time_slot} - {patient_fio}\n"
            text += f"   🎯 {appointment_type} | {status}\n\n"
    
    # Создаем клавиатуру
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🏠 На главную", callback_data="exit"))
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

async def show_appointment_type_selection(callback: types.CallbackQuery, user_id: int, year: int, month: int, day: int):
    """Показывает выбор типа приема (старая логика для пациентов)"""
    # Определяем doctor_id (для личного календаря - текущий пользователь)
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

def get_appointment_status_text(status: str) -> str:
    """Возвращает текстовое представление статуса записи"""
    status_map = {
        "pending": "⏳ Ожидает",
        "confirmed": "✅ Подтверждена",
        "cancelled": "❌ Отменена"
    }
    return status_map.get(status, "❓ Неизвестно")

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
    
    # Получаем занятые временные слоты на эту дату
    booked_slots = get_booked_time_slots(doctor_id, year, month, day)
    
    # Генерируем временные интервалы и фильтруем занятые
    time_slots = generate_time_slots(start_time, end_time, schedule["patient_time"])
    available_slots = [slot for slot in time_slots if slot not in booked_slots]
    
    if not available_slots:
        await callback.answer("❌ На этот день нет свободных временных слотов!", show_alert=True)
        return
    
    reg_data = doctor_data["registration_data"]
    doctor_name = reg_data['fio']
    month_name = CalendarKeyboard.MONTHS_RU[month-1]
    
    text = f"Запись на {day} {month_name} {year}.\n{type_text} прием к врачу {doctor_name}"
    
    if booked_slots:
        text += f"\n\n✅ Свободные слоты ({len(available_slots)} из {len(time_slots)})"
    else:
        text += f"\n\n✅ Доступные слоты: {len(available_slots)}"
    
    # Создаем клавиатуру с временными интервалами
    builder = InlineKeyboardBuilder()
    for slot in available_slots:
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

def get_booked_time_slots(doctor_id: int, year: int, month: int, day: int) -> list:
    """Возвращает список занятых временных слотов на указанную дату"""
    appointments_data = load_json_data('appointments')
    
    # Форматируем дату для поиска
    target_date = f"{year}-{month:02d}-{day:02d}"
    
    booked_slots = []
    
    # Ищем все записи врача на эту дату
    for appointment_id, appointment in appointments_data.get("appointments", {}).items():
        if (appointment["doctor_id"] == str(doctor_id) and 
            appointment["date"] == target_date and
            appointment["status"] != "cancelled"):  # Не учитываем отмененные записи
            booked_slots.append(appointment["time_slot"])
    
    return booked_slots

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

def get_appointments_on_date(doctor_id: int, year: int, month: int, day: int) -> list:
    """Возвращает все записи врача на указанную дату"""
    appointments_data = load_json_data('appointments')
    
    target_date = f"{year}-{month:02d}-{day:02d}"
    appointments_on_date = []
    
    for appointment_id, appointment in appointments_data.get("appointments", {}).items():
        if (appointment["doctor_id"] == str(doctor_id) and 
            appointment["date"] == target_date and
            appointment["status"] != "cancelled"):
            appointments_on_date.append(appointment)
    
    return appointments_on_date

async def notify_patients_about_cancellation(appointments: list, date: datetime.date, bot_token: str):
    """Отправляет уведомления пациентам об отмене записей"""
    from aiogram import Bot
    
    # Создаем экземпляр бота с токеном
    bot = Bot(token=bot_token)
    
    month_name = CalendarKeyboard.MONTHS_RU[date.month - 1]
    date_text = f"{date.day} {month_name} {date.year}"
    
    for appointment in appointments:
        try:
            patient_id = int(appointment["patient_id"])
            message_text = f"❌ Ваша запись на {date_text} была отменена, пожалуйста, запишитесь на другое время"
            
            await bot.send_message(
                chat_id=patient_id,
                text=message_text
            )
            print(f"✅ Уведомление отправлено пациенту {appointment['patient_id']}")
        except Exception as e:
            print(f"❌ Ошибка отправки уведомления пациенту {appointment['patient_id']}: {e}")
    
    # Закрываем сессию бота
    await bot.session.close()

def delete_appointments_on_date(appointments: list):
    """Удаляет записи на указанную дату"""
    appointments_data = load_json_data('appointments')
    
    for appointment in appointments:
        appointment_id = appointment["appointment_id"]
        doctor_id = appointment["doctor_id"]
        
        # Удаляем запись из общего списка
        if appointment_id in appointments_data.get("appointments", {}):
            del appointments_data["appointments"][appointment_id]
        
        # Удаляем запись из списка врача
        if (doctor_id in appointments_data.get("doctors", {}) and 
            "appointments" in appointments_data["doctors"][doctor_id]):
            appointments_data["doctors"][doctor_id]["appointments"] = [
                app_id for app_id in appointments_data["doctors"][doctor_id]["appointments"]
                if app_id != appointment_id
            ]
    
    # Сохраняем изменения
    save_json_data(appointments_data, 'appointments')