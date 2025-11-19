from JSONfunctions import load_json_data, save_json_data
from typing import Dict, Any, Optional

temp_weekends_storage = {}

def is_user_registered(user_id: int) -> bool:
    """Проверяет, зарегистрирован ли пользователь"""
    users_data = load_json_data('users')
    return str(user_id) in users_data["users"]

def get_user_data(user_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает данные пользователя"""
    users_data = load_json_data('users')
    return users_data["users"].get(str(user_id))

def get_doctor_weekends(user_id: int) -> set:
    """Получает сохраненные выходные дни врача из JSON"""
    users_data = load_json_data('users')
    user_data = users_data["users"].get(str(user_id), {})
    weekends = user_data.get("weekends", [])
    return set(weekends)

def save_doctor_weekends(user_id: int, weekends: set):
    """Сохраняет выходные дни врача в JSON"""
    users_data = load_json_data('users')
    if str(user_id) in users_data["users"]:
        users_data["users"][str(user_id)]["weekends"] = list(weekends)
        save_json_data(users_data, 'users')

def find_doctors_by_query(query: str) -> list:
    """Ищет врачей по ФИО, адресу или специальности"""
    users_data = load_json_data('users')
    found_doctors = []
    
    for user_id, user_data in users_data["users"].items():
        reg_data = user_data.get("registration_data", {})
        
        # Проверяем, что это врач
        if reg_data.get("role") != "doctor":
            continue
        
        # Проверяем совпадение по всем полям
        search_fields = [
            reg_data.get("fio", "").lower(),
            reg_data.get("office_address", "").lower(),
            reg_data.get("specialty", "").lower()
        ]
        
        # Ищем совпадение в любом из полей
        for field in search_fields:
            if field and field != "не указано" and query in field:
                found_doctors.append(user_data)
                break
    
    return found_doctors

def get_short_name(full_name: str) -> str:
    """Сокращает ФИО до формата 'Фамилия И.О.'"""
    parts = full_name.split()
    if len(parts) >= 3:
        return f"{parts[0]} {parts[1][0]}.{parts[2][0]}."
    elif len(parts) == 2:
        return f"{parts[0]} {parts[1][0]}."
    else:
        return full_name
    
def save_doctor_schedule(user_id: str, schedule_data: dict):
    """Сохраняет расписание врача в JSON"""
    schedules_data = load_json_data('schedules')
    
    if "doctors" not in schedules_data:
        schedules_data["doctors"] = {}
    
    schedules_data["doctors"][user_id] = schedule_data
    save_json_data(schedules_data, 'schedules')

def get_doctor_schedule(user_id: str) -> dict:
    """Получает расписание врача из JSON"""
    schedules_data = load_json_data('schedules')
    return schedules_data.get("doctors", {}).get(str(user_id), {})

def has_doctor_schedule(user_id: str) -> bool:
    """Проверяет, есть ли у врача настроенное расписание"""
    schedules_data = load_json_data('schedules')
    return str(user_id) in schedules_data.get("doctors", {})