from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from keyboards.basic import MainMenu as basic
from handlers.states import States
from user_utils import is_user_registered, get_user_data
from datetime import datetime

router = Router()

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