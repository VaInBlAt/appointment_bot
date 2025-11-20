from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from keyboards.basic import MainMenu as basic
from handlers.states import States
from user_utils import is_user_registered, get_user_data
from JSONfunctions import load_json_data, save_json_data
from datetime import datetime
import re

router = Router()

@router.callback_query(F.data.startswith('appointment_time_'))
async def start_appointment_process(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс записи на прием после выбора времени"""
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
    
    # Получаем данные пациента (текущего пользователя)
    patient_id = callback.from_user.id
    patient_data = get_user_data(patient_id)
    
    if not patient_data:
        await callback.answer("❌ Вы не зарегистрированы!", show_alert=True)
        return
    
    # Сохраняем данные записи в состоянии
    await state.update_data(
        appointment_doctor_id=doctor_id,
        appointment_year=year,
        appointment_month=month,
        appointment_day=day,
        appointment_time_slot=time_slot,
        appointment_type=appointment_type,
        appointment_patient_fio=patient_data["registration_data"]["fio"]
    )
    
    reg_data = doctor_data["registration_data"]
    doctor_name = reg_data['fio']
    month_name = get_month_name(month)
    
    type_text = "Первичный" if appointment_type == "primary" else "Вторичный"
    
    text = f"""📅 Запись на прием

👨‍⚕️ Врач: {doctor_name}
📅 Дата: {day} {month_name} {year}
⏰ Время: {time_slot}
🎯 Тип: {type_text} прием
👤 Пациент: {patient_data['registration_data']['fio']}

Для завершения записи введите вашу дату рождения в формате ДД.ММ.ГГГГ:

Например: 15.05.1990"""
    
    await state.set_state(States.appointment_birth_date)
    await callback.message.edit_text(text, reply_markup=basic.exit())
    await callback.answer()

@router.message(States.appointment_birth_date)
async def process_birth_date(message: types.Message, state: FSMContext):
    """Обрабатывает ввод даты рождения"""
    birth_date = message.text.strip()
    
    if not validate_birth_date(birth_date):
        await message.answer("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ (например: 15.05.1990):")
        return
    
    await state.update_data(appointment_birth_date=birth_date)
    await state.set_state(States.appointment_phone)
    
    await message.answer(
        "📞 Теперь введите ваш номер телефона:\n\nНапример: +79123456789 или 89123456789",
        reply_markup=basic.exit()
    )

@router.message(States.appointment_phone)
async def process_phone(message: types.Message, state: FSMContext):
    """Обрабатывает ввод номера телефона и сохраняет запись"""
    phone = message.text.strip()
    
    if not validate_phone(phone):
        await message.answer("❌ Неверный формат номера. Используйте +79123456789 или 89123456789:")
        return
    
    # Получаем все данные из состояния
    data = await state.get_data()
    
    # Сохраняем запись в JSON
    await save_appointment_data(data, phone, message.from_user.id)
    
    # Формируем текст подтверждения
    confirmation_text = await format_confirmation_text(data, phone)
    
    await message.answer(confirmation_text, reply_markup=basic.main_menu())
    await state.clear()

async def save_appointment_data(data: dict, phone: str, patient_id: int):
    """Сохраняет данные записи в JSON"""
    doctor_id = data['appointment_doctor_id']
    
    # Формируем данные записи
    appointment_data = {
        "appointment_id": generate_appointment_id(),
        "patient_id": str(patient_id),
        "patient_fio": data['appointment_patient_fio'],
        "patient_birth_date": data['appointment_birth_date'],
        "patient_phone": phone,
        "doctor_id": str(doctor_id),
        "date": f"{data['appointment_year']}-{data['appointment_month']:02d}-{data['appointment_day']:02d}",
        "time_slot": data['appointment_time_slot'],
        "appointment_type": data['appointment_type'],
        "status": "pending",  # pending, confirmed, cancelled
        "created_at": datetime.now().isoformat()
    }
    
    # Загружаем существующие записи
    appointments_data = load_json_data('appointments')
    
    # Инициализируем структуру если ее нет
    if "appointments" not in appointments_data:
        appointments_data["appointments"] = {}
    
    if "doctors" not in appointments_data:
        appointments_data["doctors"] = {}
    
    # Сохраняем запись в общий список
    appointments_data["appointments"][appointment_data["appointment_id"]] = appointment_data
    
    # Сохраняем запись в список врача
    if str(doctor_id) not in appointments_data["doctors"]:
        appointments_data["doctors"][str(doctor_id)] = {}
    
    if "appointments" not in appointments_data["doctors"][str(doctor_id)]:
        appointments_data["doctors"][str(doctor_id)]["appointments"] = []
    
    appointments_data["doctors"][str(doctor_id)]["appointments"].append(appointment_data["appointment_id"])
    
    # Сохраняем в JSON
    save_json_data(appointments_data, 'appointments')

async def format_confirmation_text(data: dict, phone: str) -> str:
    """Формирует текст подтверждения записи"""
    doctor_id = data['appointment_doctor_id']
    doctor_data = get_user_data(doctor_id)
    doctor_name = doctor_data["registration_data"]["fio"]
    
    month_name = get_month_name(data['appointment_month'])
    type_text = "Первичный" if data['appointment_type'] == "primary" else "Вторичный"
    
    return f"""✅ Запись успешно создана!

📋 Детали записи:
👨‍⚕️ Врач: {doctor_name}
📅 Дата: {data['appointment_day']} {month_name} {data['appointment_year']}
⏰ Время: {data['appointment_time_slot']}
🎯 Тип приема: {type_text}
👤 Пациент: {data['appointment_patient_fio']}
📅 Дата рождения: {data['appointment_birth_date']}
📞 Телефон: {phone}
"""

def validate_birth_date(date_str: str) -> bool:
    """Проверяет корректность формата даты рождения ДД.ММ.ГГГГ"""
    pattern = r'^(0[1-9]|[12][0-9]|3[01])\.(0[1-9]|1[0-2])\.(19|20)\d{2}$'
    if not re.match(pattern, date_str):
        return False
    
    # Проверяем что дата не в будущем
    try:
        day, month, year = map(int, date_str.split('.'))
        birth_date = datetime(year, month, day)
        return birth_date <= datetime.now()
    except ValueError:
        return False

def validate_phone(phone: str) -> bool:
    """Проверяет корректность формата номера телефона"""
    # Российские номера: +7XXXXXXXXXX или 8XXXXXXXXXX
    pattern = r'^(\+7|8)\d{10}$'
    phone_clean = re.sub(r'[\s\-\(\)]', '', phone)
    return bool(re.match(pattern, phone_clean))

def generate_appointment_id() -> str:
    """Генерирует уникальный ID для записи"""
    import time
    import random
    return f"app_{int(time.time())}_{random.randint(1000, 9999)}"

def get_month_name(month: int) -> str:
    """Возвращает название месяца на русском"""
    months = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]
    return months[month-1] if 1 <= month <= 12 else ""