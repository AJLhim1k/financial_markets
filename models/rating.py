from typing import List, Dict, Tuple
import numpy as np
from scipy import stats


EXCLUSION_THRESHOLD = -15  # Порог исключения из расчета


def calculate_grades(students_data: List[Tuple[int, float]]) -> Dict[int, Dict]:
    """
    Рассчитывает оценки для студентов по формуле нормального распределения.
    
    Оценка за семинары рассчитывается по формуле:
    Norm.dist(x; µ; σ; true) * 10
    
    где:
    - x - балл студента за семинары
    - µ - среднее арифметическое по студентам с баллами > -15
    - σ - стандартное отклонение по студентам с баллами > -15
    
    Студенты с баллами <= -15 получают оценку 0.
    
    Args:
        students_data: Список кортежей (user_id, score)
        
    Returns:
        Словарь {user_id: {'grade': оценка, 'excluded': bool, 'cdf_value': float, 'mu': float, 'sigma': float}}
    """
    if not students_data:
        return {}

    # Разделяем студентов на включенных и исключенных
    included_students = [(uid, score) for uid, score in students_data if score > EXCLUSION_THRESHOLD]
    excluded_students = [(uid, score) for uid, score in students_data if score <= EXCLUSION_THRESHOLD]

    result = {}

    # Студентам с баллами <= -15 ставим оценку 0
    for user_id, score in excluded_students:
        result[user_id] = {
            'grade': 0.0,
            'excluded': True,
            'cdf_value': 0.0
        }

    if not included_students:
        return result

    # Вычисляем параметры нормального распределения только для включенных студентов
    included_scores = np.array([score for _, score in included_students])
    mu = np.mean(included_scores)  # Среднее арифметическое
    sigma = np.std(included_scores, ddof=0)  # Стандартное отклонение (как в Excel)

    # Если стандартное отклонение равно 0, все баллы одинаковые
    if sigma == 0:
        # Если все баллы одинаковые, всем ставим одинаковую оценку
        # Используем среднее значение для оценки
        for user_id, score in included_students:
            result[user_id] = {
                'grade': 5.0,  # Средняя оценка в 10-балльной системе
                'excluded': False,
                'cdf_value': 0.5,
                'mu': float(mu),
                'sigma': 0.0
            }
        return result

    # Рассчитываем оценки для включенных студентов
    # Norm.dist(x; µ; σ; true) * 10
    for user_id, score in included_students:
        # Вычисляем кумулятивную функцию распределения (CDF)
        cdf_value = stats.norm.cdf(score, loc=mu, scale=sigma)
        # Умножаем на 10 для перевода в 10-балльную систему
        grade = cdf_value * 10

        result[user_id] = {
            'grade': float(grade),
            'excluded': False,
            'cdf_value': float(cdf_value),
            'mu': float(mu),
            'sigma': float(sigma)
        }

    return result


def format_rating_message(rating: List[Dict], title: str = "Рейтинг") -> str:
    """
    Форматирует рейтинг в текстовое сообщение для Telegram
    
    Args:
        rating: Список записей рейтинга
        title: Заголовок рейтинга
        
    Returns:
        Отформатированное текстовое сообщение
    """
    if not rating:
        return f"{title}\n\nРейтинг пуст."

    message = f"📊 {title}\n\n"
    
    for entry in rating:  # Ограничиваем до 20 записей
        medal = ""
        if entry['rank'] == 1:
            medal = "🥇"
        elif entry['rank'] == 2:
            medal = "🥈"
        elif entry['rank'] == 3:
            medal = "🥉"
        
        group_info = f" | {entry['group_name']}" if entry.get('group_name') else ""
        excluded_mark = " ⚠️" if entry.get('excluded', False) else ""
        message += f"{medal} {entry['rank']}. {entry['username']}{group_info}{excluded_mark}\n"
        message += f"   Баллы: {entry['score']} | Оценка: {entry['grade']:.2f}\n\n"

    if len(rating) > 20:
        message += f"... и еще {len(rating) - 20} студентов"

    return message

