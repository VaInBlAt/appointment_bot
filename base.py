from typing import List, Dict, Union
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

class KeyboardBuilder:
    """Универсальный строитель клавиатур со строгой типизацией"""

    @staticmethod
    def inline(
        buttons: Dict[str, str],
        row_widths: List[int]
    ) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        
        for text, callback_data in buttons.items():
            builder.button(text=text, callback_data=callback_data)

        builder.adjust(*row_widths)
        
        return builder.as_markup()