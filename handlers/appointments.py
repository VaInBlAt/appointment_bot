from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from keyboards.basic import MainMenu as basic
from handlers.states import States
from user_utils import is_user_registered, get_user_data
from JSONfunctions import load_json_data, save_json_data
from datetime import datetime
from handlers.calendar import get_booked_time_slots
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
    
    # Проверяем, заполнены ли дата рождения и телефон
    reg_data = patient_data["registration_data"]
    birth_date = reg_data.get("birth_date")
    phone = reg_data.get("phone")
    
    # Если данные не заполнены, просим заполнить
    if birth_date == "Не указано" or phone == "Не указано":
        await state.update_data(
            appointment_doctor_id=doctor_id,
            appointment_year=year,
            appointment_month=month,
            appointment_day=day,
            appointment_time_slot=time_slot,
            appointment_type=appointment_type,
            appointment_patient_fio=reg_data["fio"]
        )
        
        text = f"""📅 Запись на прием

Для завершения записи необходимо заполнить недостающие данные:"""
        
        if birth_date == "Не указано":
            text += "\n📅 Дата рождения: НЕ ЗАПОЛНЕНО"
        else:
            text += f"\n📅 Дата рождения: {birth_date}"
            
        if phone == "Не указано":
            text += "\n📞 Телефон: НЕ ЗАПОЛНЕНО"
        else:
            text += f"\n📞 Телефон: {phone}"
        
        text += "\n\nПожалуйста, заполните недостающие данные в личном кабинете."
        
        await callback.message.edit_text(text, reply_markup=basic.main_menu())
        await callback.answer()
        return
    
    # Если все данные заполнены - сразу сохраняем запись
    await save_appointment_data_direct(
        doctor_id=doctor_id,
        year=year,
        month=month,
        day=day,
        time_slot=time_slot,
        appointment_type=appointment_type,
        patient_id=patient_id,
        patient_data=patient_data,
        callback=callback
    )

async def save_appointment_data_direct(doctor_id: int, year: int, month: int, day: int, 
                                     time_slot: str, appointment_type: str, 
                                     patient_id: int, patient_data: dict, callback: types.CallbackQuery):
    """Сразу сохраняет запись если все данные пациента заполнены"""
    # Проверяем, не занят ли уже этот слот
    booked_slots = get_booked_time_slots(doctor_id, year, month, day)
    if time_slot in booked_slots:
        await callback.answer("❌ Это время уже занято. Пожалуйста, выберите другое время.", show_alert=True)
        return
    
    reg_data = patient_data["registration_data"]
    
    # Сохраняем запись в JSON
    appointment_data = {
        "appointment_id": generate_appointment_id(),
        "patient_id": str(patient_id),
        "patient_fio": reg_data["fio"],
        "patient_birth_date": reg_data["birth_date"],
        "patient_phone": reg_data["phone"],
        "doctor_id": str(doctor_id),
        "date": f"{year}-{month:02d}-{day:02d}",
        "time_slot": time_slot,
        "appointment_type": appointment_type,
        "status": "pending",
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
    
    # Формируем текст подтверждения
    doctor_data = get_user_data(doctor_id)
    doctor_name = doctor_data["registration_data"]["fio"] if doctor_data else "Неизвестный врач"
    month_name = get_month_name(month)
    type_text = "Первичный" if appointment_type == "primary" else "Вторичный"
    
    confirmation_text = f"""✅ Запись успешно создана!

📋 Детали записи:
👨‍⚕️ Врач: {doctor_name}
📅 Дата: {day} {month_name} {year}
⏰ Время: {time_slot}
🎯 Тип приема: {type_text}
👤 Пациент: {reg_data['fio']}
📅 Дата рождения: {reg_data['birth_date']}
📞 Телефон: {reg_data['phone']}

Запись ожидает подтверждения врачом."""
    
    await callback.message.edit_text(confirmation_text, reply_markup=basic.main_menu())
    await callback.answer()
    
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