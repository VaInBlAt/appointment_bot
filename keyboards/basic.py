from base import KeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

class MainMenu:
    @staticmethod
    def start() -> InlineKeyboardMarkup:
        return KeyboardBuilder.inline(
            buttons={
                'Регистрация': 'registration_step1_-'
            },
            row_widths=[1])
    
    @staticmethod
    def step1() -> InlineKeyboardMarkup:
        return KeyboardBuilder.inline(
            buttons={
                'Я - врач': 'registration_step2_doctor',
                'Я - Пациент': 'registration_step2_patient'
            },
            row_widths=[1])
    
    @staticmethod
    def skip_step() -> InlineKeyboardMarkup:
        return KeyboardBuilder.inline(
            buttons={
                'Пропустить': 'registration_skip_-'
            },
            row_widths=[1])
    
    @staticmethod
    def confirm_registration() -> InlineKeyboardMarkup:
        return KeyboardBuilder.inline(
            buttons={
                '✅ Подтвердить': 'registration_confirm_-',
                '🔄 Заполнить заново': 'registration_restart_-'
            },
            row_widths=[1])

    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        return KeyboardBuilder.inline(
            buttons={
                '📊 Личный кабинет': 'profile',
                '📅 Расписание': 'appointment_calendar',
                '🔎 Найти врача': 'finddoctor',
                '📋 Мои записи': 'my_appointments'
            },
            row_widths=[1])
    
    @staticmethod
    def exit() -> InlineKeyboardMarkup:
        return KeyboardBuilder.inline(
            buttons={
                '🏠 На главную': 'exit'
            },
            row_widths=[1])
