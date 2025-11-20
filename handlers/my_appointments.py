from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from keyboards.basic import MainMenu as basic
from user_utils import is_user_registered, get_user_data, get_month_name
from JSONfunctions import load_json_data
from datetime import datetime
from aiogram.utils.keyboard import InlineKeyboardBuilder

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
    """Показывает все записи пациента"""
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
    
    # Отправляем каждую запись отдельным сообщением
    for appointment in patient_appointments:
        appointment_text = format_appointment_text(appointment)
        await callback.message.answer(appointment_text)
    
    await callback.answer(f"📋 Найдено записей: {len(patient_appointments)}")

async def show_doctor_appointments(callback: types.CallbackQuery, doctor_id: int, state: FSMContext):
    """Показывает все записи врача с пагинацией"""
    appointments_data = load_json_data('appointments')
    
    # Находим все записи врача
    doctor_appointments = []
    for appointment_id, appointment in appointments_data.get("appointments", {}).items():
        if appointment["doctor_id"] == str(doctor_id):
            doctor_appointments.append(appointment)
    
    if not doctor_appointments:
        await callback.message.edit_text(
            "📋 У вас пока нет записей от пациентов.",
            reply_markup=basic.main_menu()
        )
        await callback.answer()
        return
    
    # Сортируем записи по дате (сначала ближайшие)
    doctor_appointments.sort(key=lambda x: x['date'])
    
    # Сохраняем данные в состоянии для пагинации
    await state.update_data(
        doctor_appointments=doctor_appointments,
        current_page=0
    )
    
    # Показываем первую страницу
    await show_doctor_appointments_page(callback, state)

async def show_doctor_appointments_page(callback: types.CallbackQuery, state: FSMContext):
    """Показывает одну страницу с записями врача"""
    data = await state.get_data()
    appointments = data.get("doctor_appointments", [])
    current_page = data.get("current_page", 0)
    
    if not appointments:
        await callback.message.edit_text(
            "📋 У вас пока нет записей от пациентов.",
            reply_markup=basic.main_menu()
        )
        return
    
    # Настройки пагинации
    APPOINTMENTS_PER_PAGE = 5
    total_pages = (len(appointments) + APPOINTMENTS_PER_PAGE - 1) // APPOINTMENTS_PER_PAGE
    
    # Получаем записи для текущей страницы
    start_index = current_page * APPOINTMENTS_PER_PAGE
    end_index = start_index + APPOINTMENTS_PER_PAGE
    page_appointments = appointments[start_index:end_index]
    
    # Формируем текст страницы
    page_text = f"📋 Записи пациентов\n\n"
    page_text += f"Страница {current_page + 1} из {total_pages}\n"
    page_text += f"Всего записей: {len(appointments)}\n\n"
    
    for i, appointment in enumerate(page_appointments, start_index + 1):
        page_text += f"📌 Запись #{i}\n"
        page_text += format_appointment_short(appointment)
        page_text += "\n" + "─" * 30 + "\n\n"
    
    # Создаем клавиатуру с пагинацией
    builder = InlineKeyboardBuilder()
    
    # Кнопки навигации
    nav_buttons = []
    
    if current_page > 0:
        nav_buttons.append(types.InlineKeyboardButton(
            text="◀️ Назад", 
            callback_data="appointments_prev"
        ))
    
    if current_page < total_pages - 1:
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
    
    if callback.message.text != page_text:
        await callback.message.edit_text(page_text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data == 'appointments_prev')
async def appointments_prev_page(callback: types.CallbackQuery, state: FSMContext):
    """Переход на предыдущую страницу записей врача"""
    data = await state.get_data()
    current_page = data.get("current_page", 0)
    
    if current_page > 0:
        await state.update_data(current_page=current_page - 1)
        await show_doctor_appointments_page(callback, state)
    
    await callback.answer()

@router.callback_query(F.data == 'appointments_next')
async def appointments_next_page(callback: types.CallbackQuery, state: FSMContext):
    """Переход на следующую страницу записей врача"""
    data = await state.get_data()
    appointments = data.get("doctor_appointments", [])
    current_page = data.get("current_page", 0)
    
    APPOINTMENTS_PER_PAGE = 5
    total_pages = (len(appointments) + APPOINTMENTS_PER_PAGE - 1) // APPOINTMENTS_PER_PAGE
    
    if current_page < total_pages - 1:
        await state.update_data(current_page=current_page + 1)
        await show_doctor_appointments_page(callback, state)
    
    await callback.answer()

def format_appointment_text(appointment: dict) -> str:
    """Форматирует полный текст записи"""
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

def format_appointment_short(appointment: dict) -> str:
    """Форматирует короткий текст записи для списка врача"""
    # Парсим дату
    date_obj = datetime.strptime(appointment["date"], "%Y-%m-%d")
    day = date_obj.day
    month = get_month_name(date_obj.month)
    
    type_text = "Первичный" if appointment["appointment_type"] == "primary" else "Вторичный"
    status_text = get_status_text(appointment["status"])
    
    return f"""👤 {appointment["patient_fio"]}
📅 {day} {month} | {appointment["time_slot"]}
🎯 {type_text}
📞 {appointment["patient_phone"]}
📊 {status_text}"""

def get_status_text(status: str) -> str:
    """Возвращает текстовое представление статуса"""
    status_map = {
        "pending": "⏳ Ожидает подтверждения",
        "confirmed": "✅ Подтверждена",
        "cancelled": "❌ Отменена"
    }
    return status_map.get(status, "❓ Неизвестно")

