import json
import os
import shutil

def load_json_data(filename):
    try:
        with open('data/'+filename+'.json', 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        return {"users": {}}

def save_json_data(data, filename):
    with open('data/'+filename+'.json', 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        


async def send_leaderboard(filename):
    try:
        data = load_json_data(filename)
    except FileNotFoundError:
        return "Рейтинг пока пуст"
    
    sorted_users = sorted(
        data["users"].values(),
        key=lambda x: x["score"],
        reverse=True
    )[:10]
    
    leaderboard_text = ""
    for i, user in enumerate(sorted_users, 1):
        leaderboard_text += f"{i}. {user['username']}: {user['score']} очков\n"
    
    return leaderboard_text

def get_next_counter():
    """Получить следующий номер для генерации PDF"""
    data = load_json_data('counters')
    
    # Инициализируем счетчик если его нет
    if 'pdf_counter' not in data:
        data['pdf_counter'] = 0
    
    # Увеличиваем счетчик
    data['pdf_counter'] += 1
    
    # Сохраняем изменения
    save_json_data(data, 'counters')
    
    return data['pdf_counter']

def save_variant_to_files(user_id: int, var: int, pages: list, answers: list) -> dict:
    """Сохраняет вариант во временные файлы и возвращает метаданные"""
    user_dir = f"/tmp/bot_user_{user_id}"
    os.makedirs(user_dir, exist_ok=True)
    
    # Сохраняем изображения
    image_paths = []
    for i, page in enumerate(pages):
        filename = f"var_{var}_page_{i}.png"
        file_path = os.path.join(user_dir, filename)
        with open(file_path, "wb") as f:
            f.write(page.data)
        image_paths.append(file_path)
    
    # Сохраняем ответы в JSON
    answers_file = os.path.join(user_dir, f"var_{var}_answers.json")
    with open(answers_file, 'w', encoding='utf-8') as f:
        json.dump(answers, f, ensure_ascii=False)
    
    return {
        "image_paths": image_paths,
        "answers_file": answers_file,
        "var": var
    }

def load_variant_from_files(metadata: dict) -> tuple[list, list]:
    """Загружает вариант из временных файлов"""
    from aiogram.types import BufferedInputFile
    
    pages = []
    for file_path in metadata["image_paths"]:
        with open(file_path, "rb") as f:
            file_data = f.read()
        filename = os.path.basename(file_path)
        pages.append(BufferedInputFile(file_data, filename=filename))
    
    with open(metadata["answers_file"], 'r', encoding='utf-8') as f:
        answers = json.load(f)
    
    return pages, answers

def cleanup_user_files(user_id: int):
    """Очищает все временные файлы пользователя"""
    user_dir = f"/tmp/bot_user_{user_id}"
    if os.path.exists(user_dir):
        shutil.rmtree(user_dir, ignore_errors=True)

def get_user_variants_count(user_id: int) -> int:
    """Возвращает количество сохраненных вариантов пользователя"""
    user_dir = f"/tmp/bot_user_{user_id}"
    if not os.path.exists(user_dir):
        return 0
    
    # Считаем файлы с ответами
    answer_files = [f for f in os.listdir(user_dir) if f.endswith('_answers.json')]
    return len(answer_files)