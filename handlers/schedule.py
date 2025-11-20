from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from keyboards.basic import MainMenu as basic
from handlers.states import States
from user_utils import is_user_registered, get_user_data, save_doctor_schedule, has_doctor_schedule
from JSONfunctions import load_json_data, save_json_data
import re

router = Router()

@router.callback_query(F.data == 'appointment_calendar')
async def handle_appointment_calendar(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает нажатие на кнопку 'Записаться на прием'"""
    user_id = callback.from_user.id
    
    if not is_user_registered(user_id):
        await callback.answer("❌ Вы еще не зарегистрированы!", show_alert=True)
        return
    
    user_data = get_user_data(user_id)
    
    # Если пользователь - врач и у него нет настроенного расписания
    if user_data["registration_data"]["role"] == "doctor" and not has_doctor_schedule(user_id):
        # Начинаем настройку расписания
        await start_schedule_setup(callback, state)
    else:
        # Показываем обычный календарь
        await show_regular_calendar(callback)

async def start_schedule_setup(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс настройки расписания врача"""
    await state.set_state(States.schedule_patient_time)
    
    text = """📅 Настройка расписания

Для работы с календарем необходимо настроить расписание.

Укажите, сколько минут длится прием одного пациента:"""
    
    await callback.message.edit_text(
        text,
        reply_markup=basic.exit()
    )
    await callback.answer()

async def show_regular_calendar(callback: types.CallbackQuery):
    """Показывает обычный календарь (перенаправляет в calendar.py)"""
    from handlers.calendar import show_calendar
    await show_calendar(callback)

# Остальные функции остаются без изменений
@router.message(States.schedule_patient_time)
async def process_patient_time(message: types.Message, state: FSMContext):
    """Обрабатывает ввод времени приема одного пациента"""
    time_str = message.text.strip()
    
    if not time_str.isdigit() or not 5 <= int(time_str) <= 180:
        await message.answer("❌ Пожалуйста, введите число от 5 до 180 (минут):")
        return
    
    await state.update_data(schedule_patient_time=int(time_str))
    await state.set_state(States.schedule_primary_start)
    
    await message.answer(
        "⏰ Теперь укажите время начала первичного приема в формате ЧЧ:ММ\n\nНапример: 09:00",
        reply_markup=basic.exit()
    )

@router.message(States.schedule_primary_start)
async def process_primary_start(message: types.Message, state: FSMContext):
    """Обрабатывает ввод времени начала первичного приема"""
    time_str = message.text.strip()
    
    if not validate_time_format(time_str):
        await message.answer("❌ Неверный формат времени. Используйте ЧЧ:ММ (например: 09:00):")
        return
    
    await state.update_data(schedule_primary_start=time_str)
    await state.set_state(States.schedule_primary_end)
    
    await message.answer(
        "⏰ Теперь укажите время окончания первичного приема в формате ЧЧ:ММ\n\nНапример: 13:00",
        reply_markup=basic.exit()
    )

@router.message(States.schedule_primary_end)
async def process_primary_end(message: types.Message, state: FSMContext):
    """Обрабатывает ввод времени окончания первичного приема"""
    time_str = message.text.strip()
    
    if not validate_time_format(time_str):
        await message.answer("❌ Неверный формат времени. Используйте ЧЧ:ММ (например: 13:00):")
        return
    
    # Проверяем, что окончание позже начала
    data = await state.get_data()
    start_time = data.get('schedule_primary_start')
    
    if not is_end_time_after_start(start_time, time_str):
        await message.answer("❌ Время окончания должно быть позже времени начала. Попробуйте снова:")
        return
    
    await state.update_data(schedule_primary_end=time_str)
    await state.set_state(States.schedule_repeat_start)
    
    await message.answer(
        "⏰ Теперь укажите время начала повторного приема в формате ЧЧ:ММ\n\nНапример: 14:00",
        reply_markup=basic.exit()
    )

@router.message(States.schedule_repeat_start)
async def process_repeat_start(message: types.Message, state: FSMContext):
    """Обрабатывает ввод времени начала повторного приема"""
    time_str = message.text.strip()
    
    if not validate_time_format(time_str):
        await message.answer("❌ Неверный формат времени. Используйте ЧЧ:ММ (например: 14:00):")
        return
    
    await state.update_data(schedule_repeat_start=time_str)
    await state.set_state(States.schedule_repeat_end)
    
    await message.answer(
        "⏰ Теперь укажите время окончания повторного приема в формате ЧЧ:ММ\n\nНапример: 18:00",
        reply_markup=basic.exit()
    )

@router.message(States.schedule_repeat_end)
async def process_repeat_end(message: types.Message, state: FSMContext):
    """Обрабатывает ввод времени окончания повторного приема и сохраняет расписание"""
    time_str = message.text.strip()
    
    if not validate_time_format(time_str):
        await message.answer("❌ Неверный формат времени. Используйте ЧЧ:ММ (например: 18:00):")
        return
    
    # Проверяем, что окончание позже начала
    data = await state.get_data()
    start_time = data.get('schedule_repeat_start')
    
    if not is_end_time_after_start(start_time, time_str):
        await message.answer("❌ Время окончания должно быть позже времени начала. Попробуйте снова:")
        return
    
    await state.update_data(schedule_repeat_end=time_str)
    
    # Сохраняем все данные расписания
    await save_schedule_data(message, state)

async def save_schedule_data(message: types.Message, state: FSMContext):
    """Сохраняет данные расписания в JSON"""
    data = await state.get_data()
    user_id = str(message.from_user.id)
    
    schedule_data = {
        "patient_time": data.get('schedule_patient_time'),
        "primary_start": data.get('schedule_primary_start'),
        "primary_end": data.get('schedule_primary_end'),
        "repeat_start": data.get('schedule_repeat_start'),
        "repeat_end": data.get('schedule_repeat_end')
    }
    
    # Сохраняем в JSON
    save_doctor_schedule(user_id, schedule_data)
    
    # Формируем текст подтверждения
    confirmation_text = f"""✅ Расписание настроено!

📋 Ваше расписание:
• Время приема одного пациента: {schedule_data['patient_time']} мин.
• Первичный прием: {schedule_data['primary_start']} - {schedule_data['primary_end']}
• Повторный прием: {schedule_data['repeat_start']} - {schedule_data['repeat_end']}

Теперь вы можете работать с календарем записей."""

    await message.answer(
        confirmation_text,
        reply_markup=basic.main_menu()
    )
    await state.clear()

def validate_time_format(time_str: str) -> bool:
    """Проверяет корректность формата времени ЧЧ:ММ"""
    pattern = r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$'
    return bool(re.match(pattern, time_str))

def is_end_time_after_start(start_time: str, end_time: str) -> bool:
    """Проверяет, что время окончания позже времени начала"""
    start_h, start_m = map(int, start_time.split(':'))
    end_h, end_m = map(int, end_time.split(':'))
    
    start_total = start_h * 60 + start_m
    end_total = end_h * 60 + end_m
    
    return end_total > start_total