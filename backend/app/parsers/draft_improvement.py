MORALIZING_MARKERS = (
    'не вправе',
    'неуместно',
    'конструктивно',
    'нельзя писать',
    'пожалуйста, попробуйте',
    'приносим свои извинения за ненормативную лексику',
    'мы понимаем, что вы испытываете',
    'опишите вашу проблему более подробно',
)


def has_moralizing_marker(text: str) -> bool:
    low = text.lower()
    return any(marker in low for marker in MORALIZING_MARKERS)


def is_acceptable_improvement(text: str) -> bool:
    return len(text) > 10 and not has_moralizing_marker(text)
