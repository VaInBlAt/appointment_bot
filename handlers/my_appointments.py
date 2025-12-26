from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from keyboards.basic import MainMenu as basic
from user_utils import is_user_registered, get_user_data, get_month_name, get_doctor_weekends
from JSONfunctions import load_json_data, save_json_data
from datetime import datetime, timedelta
from aiogram.utils.keyboard import InlineKeyboardBuilder
import json

router = Router()

# Глобальный словарь для хранения данных пагинации (временное решение)
doctor_appointments_data = {}

@router.callback_query(F.data == 'my_appointments')
async def show_my_appointments(callback: types.CallbackQuery, state: FSMContext):
    """Показывает записи пользователя (для пациента) или врача"""
    user_id = callback.from_user.id
    
    if not is_user_registered(user_id):
        await callback.answer("❌ Вы еще не зарегистрированы!", show_alert=True)
        return
    
    user_data = get_user_data(user_id)
    role = user_data["registration_data"]["role"]
    
    if role == "patient":
        await show_patient_appointments(callback, user_id)
    else:
        await show_doctor_appointments(callback, user_id, state)

async def show_patient_appointments(callback: types.CallbackQuery, patient_id: int):
    """Показывает все записи пациента с возможностью удаления"""
    appointments_data = load_json_data('appointments')
    
    # Находим все записи пациента
    patient_appointments = []
    for appointment_id, appointment in appointments_data.get("appointments", {}).items():
        if appointment["patient_id"] == str(patient_id):
            patient_appointments.append(appointment)
    
    if not patient_appointments:
        await callback.message.edit_text(
            "📋 У вас пока нет записей на прием.",
            reply_markup=basic.main_menu()
        )
        await callback.answer()
        return
    
    # Сортируем записи по дате (сначала ближайшие)
    patient_appointments.sort(key=lambda x: x['date'])
    
    # Отправляем каждую запись отдельным сообщением с кнопкой удаления
    for appointment in patient_appointments:
        appointment_text = format_appointment_text(appointment)
        
        # Создаем клавиатуру с кнопкой удаления
        builder = InlineKeyboardBuilder()
        builder.add(types.InlineKeyboardButton(
            text="❌ Удалить запись",
            callback_data=f"delete_appointment_{appointment['appointment_id']}"
        ))
        builder.adjust(1)
        
        await callback.message.answer(appointment_text, reply_markup=builder.as_markup())
    
    await callback.answer(f"📋 Найдено записей: {len(patient_appointments)}")

async def show_doctor_appointments(callback: types.CallbackQuery, doctor_id: int, state: FSMContext):
    """Показывает все записи врача с пагинацией по дням"""
    # Получаем расписание врача
    schedules_data = load_json_data('schedules')
    schedule = schedules_data.get("doctors", {}).get(str(doctor_id), {})
    
    if not schedule:
        await callback.message.edit_text(
            "❌ У вас не настроено расписание. Пожалуйста, настройте расписание через раздел '📅 Расписание'.",
            reply_markup=basic.main_menu()
        )
        await callback.answer()
        return
    
    # Начинаем с сегодняшнего дня
    current_date = datetime.now().date()
    
    # Сохраняем данные в состоянии для пагинации
    await state.update_data(
        doctor_id=doctor_id,
        current_date=current_date.isoformat(),
        schedule=schedule
    )
    
    # Показываем первую страницу (сегодня)
    await show_doctor_appointments_page(callback, state)

async def show_doctor_appointments_page(callback: types.CallbackQuery, state: FSMContext):
    """Показывает записи врача за один день"""
    data = await state.get_data()
    doctor_id = data.get("doctor_id")
    current_date_str = data.get("current_date")
    schedule = data.get("schedule")
    
    if not all([doctor_id, current_date_str, schedule]):
        await callback.message.edit_text(
            "❌ Ошибка загрузки данных.",
            reply_markup=basic.main_menu()
        )
        return
    
    # Преобразуем дату
    current_date = datetime.fromisoformat(current_date_str).date()
    
    # Проверяем, является ли день выходным
    weekends = get_doctor_weekends(int(doctor_id))
    weekday = current_date.weekday()  # 0-понедельник, 6-воскресенье
    
    if weekday in weekends:
        # Если сегодня выходной, переходим к следующему рабочему дню
        next_date = find_next_working_day(current_date, weekends)
        if next_date:
            await state.update_data(current_date=next_date.isoformat())
            current_date = next_date
            current_date_str = next_date.isoformat()
        else:
            await callback.message.edit_text(
                "❌ Нет доступных рабочих дней.",
                reply_markup=basic.main_menu()
            )
            await callback.answer()
            return
    
    # Получаем все записи врача на эту дату
    appointments_data = load_json_data('appointments')
    day_appointments = []
    
    for appointment in appointments_data.get("appointments", {}).values():
        if (appointment["doctor_id"] == str(doctor_id) and 
            appointment["date"] == current_date_str):
            day_appointments.append(appointment)
    
    # Генерируем интервалы расписания
    time_slots = generate_time_slots(schedule, current_date_str)
    
    # Формируем текст для отображения
    day_name = get_month_name(current_date.month)
    page_text = f"{current_date.day} {day_name}:\n\n"
    
    # Сопоставляем записи с интервалами
    for slot in time_slots:
        # Ищем запись на этот интервал
        appointment = find_appointment_for_slot(day_appointments, slot["start"], slot["end"])
        
        if appointment:
            # Получаем данные пациента
            patient_id = appointment["patient_id"]
            patient_data = get_user_data(int(patient_id))
            
            # Получаем name пациента
            name = patient_data.get("first_name", "") + ' ' + patient_data.get("last_name", "") if patient_data else ""
            
            # Форматируем телефон (убираем лишние символы, оставляем только цифры)
            phone = appointment.get("patient_phone", "")
            phone_clean = ''.join(filter(str.isdigit, phone))
            
            # Формируем строку с временем и данными пациента
            page_text += f"{slot['start']}-{slot['end']} +{phone_clean} {name}\n"
        else:
            # Пустой интервал
            page_text += f"{slot['start']}-{slot['end']} ----------------\n"
    
    # Формируем навигацию
    prev_date = find_prev_working_day(current_date, weekends)
    next_date = find_next_working_day(current_date, weekends)
    
    # Создаем клавиатуру с пагинацией
    builder = InlineKeyboardBuilder()
    
    nav_buttons = []
    
    if prev_date:
        nav_buttons.append(types.InlineKeyboardButton(
            text="◀️ Назад", 
            callback_data="appointments_prev"
        ))
    
    if next_date:
        nav_buttons.append(types.InlineKeyboardButton(
            text="Вперед ▶️", 
            callback_data="appointments_next"
        ))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.row(types.InlineKeyboardButton(
        text="🏠 На главную", 
        callback_data="exit"
    ))
    
    await callback.message.edit_text(page_text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data == 'appointments_prev')
async def appointments_prev_page(callback: types.CallbackQuery, state: FSMContext):
    """Переход на предыдущий рабочий день"""
    data = await state.get_data()
    current_date_str = data.get("current_date")
    doctor_id = data.get("doctor_id")
    
    if not all([current_date_str, doctor_id]):
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return
    
    current_date = datetime.fromisoformat(current_date_str).date()
    weekends = get_doctor_weekends(int(doctor_id))
    
    prev_date = find_prev_working_day(current_date, weekends)
    
    if prev_date:
        await state.update_data(current_date=prev_date.isoformat())
        await show_doctor_appointments_page(callback, state)
    else:
        await callback.answer("❌ Нет предыдущих рабочих дней", show_alert=True)

@router.callback_query(F.data == 'appointments_next')
async def appointments_next_page(callback: types.CallbackQuery, state: FSMContext):
    """Переход на следующий рабочий день"""
    data = await state.get_data()
    current_date_str = data.get("current_date")
    doctor_id = data.get("doctor_id")
    
    if not all([current_date_str, doctor_id]):
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return
    
    current_date = datetime.fromisoformat(current_date_str).date()
    weekends = get_doctor_weekends(int(doctor_id))
    
    next_date = find_next_working_day(current_date, weekends)
    
    if next_date:
        await state.update_data(current_date=next_date.isoformat())
        await show_doctor_appointments_page(callback, state)
    else:
        await callback.answer("❌ Нет следующих рабочих дней", show_alert=True)

def find_next_working_day(current_date, weekends, max_days=365):
    """Находит следующий рабочий день, пропуская выходные"""
    for i in range(1, max_days + 1):
        next_date = current_date + timedelta(days=i)
        if next_date.weekday() not in weekends:
            return next_date
    return None

def find_prev_working_day(current_date, weekends, max_days=365):
    """Находит предыдущий рабочий день, пропуская выходные"""
    for i in range(1, max_days + 1):
        prev_date = current_date - timedelta(days=i)
        if prev_date.weekday() not in weekends:
            return prev_date
    return None

def generate_time_slots(schedule, date_str):
    """Генерирует временные интервалы на основе расписания врача"""
    slots = []
    
    # Парсим время из расписания
    patient_time = schedule.get("patient_time", 30)  # по умолчанию 30 минут
    
    # Первичные приемы
    primary_start = schedule.get("primary_start", "09:00")
    primary_end = schedule.get("primary_end", "13:00")
    
    # Повторные приемы
    repeat_start = schedule.get("repeat_start", "14:00")
    repeat_end = schedule.get("repeat_end", "18:00")
    
    # Генерируем интервалы для первичных приемов
    if primary_start and primary_end:
        slots.extend(generate_slots_for_period(primary_start, primary_end, patient_time))
    
    # Генерируем интервалы для повторных приемов
    if repeat_start and repeat_end:
        slots.extend(generate_slots_for_period(repeat_start, repeat_end, patient_time))
    
    return slots

def generate_slots_for_period(start_time_str, end_time_str, slot_duration_minutes):
    """Генерирует временные интервалы для заданного периода"""
    slots = []
    
    # Преобразуем строки времени в минуты
    start_hour, start_minute = map(int, start_time_str.split(':'))
    end_hour, end_minute = map(int, end_time_str.split(':'))
    
    start_total = start_hour * 60 + start_minute
    end_total = end_hour * 60 + end_minute
    
    current_time = start_total
    
    while current_time + slot_duration_minutes <= end_total:
        # Начало интервала
        start_h = current_time // 60
        start_m = current_time % 60
        start_str = f"{start_h:02d}:{start_m:02d}"
        
        # Конец интервала
        end_time = current_time + slot_duration_minutes
        end_h = end_time // 60
        end_m = end_time % 60
        end_str = f"{end_h:02d}:{end_m:02d}"
        
        slots.append({
            "start": start_str,
            "end": end_str,
            "start_total": current_time,
            "end_total": end_time
        })
        
        current_time += slot_duration_minutes
    
    return slots

def find_appointment_for_slot(appointments, slot_start, slot_end):
    """Находит запись на указанный временной интервал"""
    for appointment in appointments:
        if appointment.get("time_slot", "").startswith(f"{slot_start}-"):
            return appointment
    return None

def format_appointment_text(appointment: dict) -> str:
    """Форматирует полный текст записи (для пациента)"""
    doctor_data = get_user_data(int(appointment["doctor_id"]))
    doctor_name = doctor_data["registration_data"]["fio"] if doctor_data else "Неизвестный врач"
    
    # Парсим дату
    date_obj = datetime.strptime(appointment["date"], "%Y-%m-%d")
    day = date_obj.day
    month = get_month_name(date_obj.month)
    year = date_obj.year
    
    type_text = "Первичный" if appointment["appointment_type"] == "primary" else "Вторичный"
    status_text = get_status_text(appointment["status"])
    
    return f"""📋 Запись на прием

👨‍⚕️ Врач: {doctor_name}
📅 Дата: {day} {month} {year}
⏰ Время: {appointment["time_slot"]}
🎯 Тип приема: {type_text}
👤 Пациент: {appointment["patient_fio"]}
📅 Дата рождения: {appointment["patient_birth_date"]}
📞 Телефон: {appointment["patient_phone"]}
📊 Статус: {status_text}"""

def get_status_text(status: str) -> str:
    """Возвращает текстовое представление статуса"""
    status_map = {
        "pending": "⏳ Ожидает подтверждения",
        "confirmed": "✅ Подтверждена",
        "cancelled": "❌ Отменена"
    }
    return status_map.get(status, "❓ Неизвестно")

@router.callback_query(F.data.startswith('delete_appointment_'))
async def delete_appointment(callback: types.CallbackQuery):
    """Удаляет запись пациента"""
    appointment_id = callback.data.split('_')[2]
    
    appointments_data = load_json_data('appointments')
    
    # Проверяем существование записи
    if appointment_id not in appointments_data.get("appointments", {}):
        await callback.answer("❌ Запись не найдена!", show_alert=True)
        return
    
    appointment = appointments_data["appointments"][appointment_id]
    
    # Проверяем, что запись принадлежит текущему пользователю
    if appointment["patient_id"] != str(callback.from_user.id):
        await callback.answer("❌ Вы не можете удалить эту запись!", show_alert=True)
        return
    
    # Удаляем запись
    del appointments_data["appointments"][appointment_id]
    
    # Удаляем запись из списка врача
    doctor_id = appointment["doctor_id"]
    if (doctor_id in appointments_data.get("doctors", {}) and 
        "appointments" in appointments_data["doctors"][doctor_id]):
        appointments_data["doctors"][doctor_id]["appointments"] = [
            app_id for app_id in appointments_data["doctors"][doctor_id]["appointments"]
            if app_id != appointment_id
        ]
    
    # Сохраняем изменения
    save_json_data(appointments_data, 'appointments')
    
    await callback.answer("✅ Запись успешно удалена!", show_alert=True)
    
    # Удаляем сообщение с записью
    await callback.message.delete()