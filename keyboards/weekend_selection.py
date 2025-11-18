from datetime import datetime
from calendar import monthrange
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

class WeekendSelectionKeyboard:
    MONTHS_RU = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]
    
    DAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    
    @staticmethod
    def create_calendar(year: int, month: int, selected_dates: set) -> InlineKeyboardMarkup:
        """Создает календарь для выбора выходных с уже выбранными датами"""
        builder = InlineKeyboardBuilder()
        today = datetime.now().date()
        
        # Добавляем заголовок с месяцем и годом
        header = f"{WeekendSelectionKeyboard.MONTHS_RU[month-1]} {year}"
        builder.row(InlineKeyboardButton(text=header, callback_data="ignore"))
        
        # Добавляем дни недели
        for day_name in WeekendSelectionKeyboard.DAYS_RU:
            builder.add(InlineKeyboardButton(text=day_name, callback_data="ignore"))
        builder.adjust(7)
        
        # Получаем первый день месяца и количество дней
        first_day = datetime(year, month, 1)
        days_in_month = monthrange(year, month)[1]
        
        # Определяем день недели первого дня (0-понедельник, 6-воскресенье)
        first_weekday = first_day.weekday()
        
        # Добавляем пустые кнопки для дней до первого дня месяца
        for _ in range(first_weekday):
            builder.add(InlineKeyboardButton(text=" ", callback_data="ignore"))
        
        # Добавляем кнопки с днями месяца
        for day in range(1, days_in_month + 1):
            current_date = datetime(year, month, day).date()
            date_str = current_date.isoformat()
            
            if current_date < today:
                # Прошедшие даты - неактивные
                builder.add(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                # Проверяем, выбрана ли дата
                if date_str in selected_dates:
                    # Выбранная дата - с галочкой
                    builder.add(InlineKeyboardButton(
                        text="✅", 
                        callback_data=f"weekend_select_{year}_{month}_{day}"
                    ))
                else:
                    # Невыбранная дата - число
                    builder.add(InlineKeyboardButton(
                        text=str(day), 
                        callback_data=f"weekend_select_{year}_{month}_{day}"
                    ))
        
        # Добавляем пустые кнопки в конце, чтобы календарь был прямоугольным
        total_cells = first_weekday + days_in_month
        remaining_cells = (7 - (total_cells % 7)) % 7
        
        for _ in range(remaining_cells):
            builder.add(InlineKeyboardButton(text=" ", callback_data="ignore"))
        
        # Настраиваем layout
        layout = [1, 7] + [7] * ((total_cells + remaining_cells) // 7)
        builder.adjust(*layout)
        
        # Добавляем навигацию (только между текущим и следующим месяцем)
        nav_buttons = []
        
        today = datetime.now()
        current_year = today.year
        current_month = today.month
        
        # Если показываем текущий месяц - добавляем только кнопку вперед
        if year == current_year and month == current_month:
            next_year, next_month = WeekendSelectionKeyboard._get_next_month(year, month)
            nav_buttons.append(InlineKeyboardButton(
                text="▶️", 
                callback_data=f"weekend_nav_{next_year}_{next_month}"
            ))
        
        # Если показываем следующий месяц - добавляем только кнопку назад
        else:
            prev_year, prev_month = WeekendSelectionKeyboard._get_previous_month(year, month)
            nav_buttons.append(InlineKeyboardButton(
                text="◀️", 
                callback_data=f"weekend_nav_{prev_year}_{prev_month}"
            ))
        
        builder.row(*nav_buttons)
        
        # Добавляем кнопку подтверждения
        builder.row(InlineKeyboardButton(text="Подтвердить ✅", callback_data="weekend_confirm"))
        
        # Добавляем кнопку "На главную"
        builder.row(InlineKeyboardButton(text="🏠 На главную", callback_data="exit"))
        
        return builder.as_markup()
    
    @staticmethod
    def _get_previous_month(year: int, month: int) -> tuple[int, int]:
        """Возвращает предыдущий месяц"""
        if month == 1:
            return year - 1, 12
        else:
            return year, month - 1
    
    @staticmethod
    def _get_next_month(year: int, month: int) -> tuple[int, int]:
        """Возвращает следующий месяц"""
        if month == 12:
            return year + 1, 1
        else:
            return year, month + 1