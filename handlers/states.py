from typing import Optional
from aiogram.fsm.state import StatesGroup, State


class States(StatesGroup):
    registration_role: Optional[str] = State()
    registration_fio: Optional[str] = State()
    registration_office_address: Optional[str] = State()
    registration_specialty: Optional[str] = State()
    registration_website_link: Optional[str] = State()
    registration_photo: Optional[str] = State()
    find_doctor_query: Optional[str] = State()
    schedule_patient_time: Optional[str] = State()
    schedule_primary_start: Optional[str] = State()
    schedule_primary_end: Optional[str] = State()
    schedule_repeat_start: Optional[str] = State()
    schedule_repeat_end: Optional[str] = State()
