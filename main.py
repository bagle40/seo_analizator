from urllib.parse import unquote
from fastapi.responses import RedirectResponse
import requests
import re
import time
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from bs4.element import Tag
from fastapi import FastAPI, HTTPException, Query, Request


app = FastAPI()



def fetch_page(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response
    except requests.RequestException as e:
        print(f"Не удалось загрузить URL: {e}")
        return None

def check_title(soup, keyword):
    results = {
        'title_exists': '❌ Тег Title отсутствует.',
        'exact_keyword_in_title': '❌ Ключевая фраза не найдена в теге Title.',
        'title_length': '❌ Тег Title отсутствует.',
    }

    title_tag = soup.title
    if title_tag and title_tag.string:
        title = title_tag.string.strip()
        results['title_exists'] = '✅ Тег Title заполнен.'
        results['exact_keyword_in_title'] = '✅ Ключевая фраза в заголовоке страницы найдена!' if keyword.lower() in title.lower() else '❌ Ключевая фраза в заголовоке страницы не найдена.'
        results['title_length'] = f'✅ Длина тега Title составляет {len(title)} символов, что соответствует требованиям.' if len(title) <= 60 else f'❌ Длина тега Title составляет {len(title)} символов, что меньше требуемого минимального значения.'

    return results

def check_keywords(soup, keyword):
    results = {
        'keywords_exists': '❌ Отсутствуют ключевые слова!',
        'exact_keyword_in_keywords': '❌ Нет точного вхождения ключевой фразы',
        'keywords_fragment_count': 0,
        'keywords_length': 0
    }

    keywords_tag = soup.find('meta', attrs={'name': 'keywords'})
    if keywords_tag and keywords_tag.get('content'):
        keywords_content = keywords_tag['content'].strip()
        results['keywords_exists'] = '✅ Ключевые слова найдены!'
        results['exact_keyword_in_keywords'] = '✅ Точная ключевая фраза найдена в теге keywords .' if keyword.lower() in keywords_content.lower() else '❌ Нет точного вхождения ключевой фразы'
        results['keywords_fragment_count'] = f"🔢 Всего ключевых слов: {len(keywords_content.split(','))}"
        results['keywords_length'] = f"📏 Длина ключевых слов сотставляет: {len(keywords_content)}"

    return results

def check_description(soup, keyword):
    results = {
        'description_exists': '❌ Тег Description на странице отсутствует.',
        'exact_keyword_in_description': '⚠️ Точная ключевая фраза не найдена в теге Description.',
        'description_length': 0
    }

    description_tag = soup.find('meta', attrs={'name': 'description'})
    if description_tag and description_tag.get('content'):
        description_content = description_tag['content'].strip()
        results['description_exists'] = '🎉 Тег Description на странице присутствует.'
        results['exact_keyword_in_description'] = '✅ Точная ключевая фраза найдена в теге Description.' if  keyword.lower() in description_content.lower() else '⚠️ Точная ключевая фраза не найдена в теге Description.'
        results['description_length'] = f"✨ Общая длина тега Description: {len(description_content)}"

    return results

def check_language(soup):
    results = {
        'lang_set': '❌ Язык страницы не установлен.',
        'lang_value': '❌ Язык страницы не установлен.'
    }

    html_tag = soup.find('html')
    if html_tag and html_tag.has_attr('lang'):
        results['lang_set'] = '🌐 Язык страницы установлен.'
        results['lang_value'] = f"'🌐 Язык страницы: {html_tag['lang']}"

    return results

def check_charset(response):
    results = {
        'charset_set': '❌ Кодировка utf-8 не установлена.',
        'charset_value': '❌ Кодировка utf-8 не установлена.'
    }

    content_type = response.headers.get('Content-Type', '')
    if 'charset=utf-8' in content_type.lower():
        results['charset_set'] = '🎉 Кодировка utf-8 установлена.'
        results['charset_value'] = '🎉 Кодировка utf-8 установлена.'

    return results

def check_h1(soup, keyword, title):
    results = {
        'h1_exists': '❌ Тег H1 на странице отсутствует.',
        'exact_keyword_in_h1': '⚠️ Точная ключевая фраза не найдена в H1.',
        'matches_title': '🔍 Тег H1 не совпадает с Title.'
    }

    h1_tags = soup.find_all('h1')
    if h1_tags:
        results['h1_exists'] = '🎉 Тег H1 на странице присутствует.'
        for h1_tag in h1_tags:
            h1_text = h1_tag.get_text().strip()
            if keyword.lower() in h1_text.lower():
                results['exact_keyword_in_h1'] = '✅ Точная ключевая фраза найдена в H1.'
            if h1_text.lower() == title.lower():
                results['matches_title'] = '🔄 Тег H1 точно совпадает с Title.'

    return results

def check_article_tag(soup):
    results = {
        'article_tag_exists': "❌ Тег article отсутствует на странице.",
        'content_in_article': '✅ Всё содержимое контента находится внутри этого тега.'  # По умолчанию считаем, что если тега <article> нет, то условие выполнено
    }

    article_tag = soup.find('article')
    if article_tag:
        results['article_tag_exists'] = '🎉 Тег article присутствует на странице.'
        # Проверяем, что все содержимое контента находится внутри тега <article>
        for child in article_tag.children:
            if child.name not in ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'section']:
                results['content_in_article'] = '⚠️ Не всё содержимое контента находится внутри тега article'
                break

    return results

def check_h2(soup, keyword):
    results = {
        'h2_count': '⚠️ Ключевая фраза отсутствует в подзаголовках.',
        'keyword_in_h2': '⚠️ Ключевая фраза отсутствует в подзаголовках.'
    }

    h2_tags = soup.find_all('h2')
    results['h2_count'] = len(h2_tags)

    if results['h2_count'] >= 2:
        results['h2_count'] = '🎉 На странице есть как минимум два подзаголовка H2.'
        for h2_tag in h2_tags:
            h2_text = h2_tag.get_text().strip()
            if keyword.lower() in h2_text.lower():
                results['keyword_in_h2'] = '✅ Ключевая фраза присутствует в одном из подзаголовков.'
                break

    return results

def check_toc(soup):
    results = {
        'toc_exists': '❌ TOC отсутствует на странице.',
        'toc_correct': '⚠️  TOC некорректно отображается на странице.'
    }

    # Находим все теги <h2>
    h2_tags = soup.find_all('h2')
    if h2_tags:
        # Проверяем, что есть список (маркированный или не маркированный) перед первым <h2>
        first_h2 = h2_tags[0]
        previous_sibling = first_h2.find_previous_sibling()
        if previous_sibling and (previous_sibling.name == 'ul' or previous_sibling.name == 'ol'):
            # Проверяем, что все <h2> имеют уникальные ID
            h2_ids = []
            for h2_tag in h2_tags:
                h2_id = h2_tag.get('id')
                if h2_id:
                    h2_ids.append(h2_id)
            if len(h2_ids) == len(set(h2_ids)):
                results['toc_correct'] = '✅ TOC корректно отображается на странице.'

        results['toc_exists'] = '✅ TOC присутствует на странице.'

    return results

def check_open_graph(soup):
    og_tags = {
        'og:title': "❌ Не заполнено",
        'og:description': "❌ Не заполнено",
        'og:url': "❌ Не заполнено",
        'og:type': "❌ Не заполнено",
        'og:image': "❌ Не заполнено",
        'og:site_name': "❌ Не заполнено",
        'og:action': "❌ Не заполнено",
        'og:property': "❌ Не заполнено",
        'og:event': "❌ Не заполнено"
    }

    for tag in og_tags.keys():
        og_tag = soup.find('meta', property=tag)
        if og_tag and og_tag.get('content'):
            og_tags[tag] = '✅ Заполнено'

    return og_tags


def check_p_tags(soup, keyword):
    results = {
        'exact_keyword_in_first_p': '❌ Ключевая фраза не встречается в начале или середине первого предложения первого элемента P.',
        'exact_keyword_density': 0,
        'partial_keyword_density': 0,
        'p_length_limit_exceeded': '🚫 Длина одного или более элементов P превышает установленное значение.',
        'consecutive_p_count': '🚧 Количество подряд идущих элементов P без разделения превышает допустимое.',
        'total_p_length': 0,
        'keyword_distribution_uniformity': False
    }

    p_tags = soup.find_all('p')
    keyword_lower = keyword.lower()
    total_text = ""
    total_exact_count = 0
    total_partial_count = 0
    max_p_length = 1000  # Максимальная длина элемента p
    consecutive_p_limit = 3  # Максимальное количество идущих подряд p
    max_consecutive_p_count = 0
    current_consecutive_p_count = 0
    keyword_positions = []

    for i, p in enumerate(p_tags):
        p_text = p.get_text().strip()
        total_text += p_text + " "

        if i == 0:
            first_sentence = p_text.split('.')[0]
            if keyword_lower in first_sentence.lower():
                results['exact_keyword_in_first_p'] = '🎯 Ключевая фраза точно встречается в начале или середине первого предложения первого элемента P.'

        exact_count = p_text.lower().count(keyword_lower)
        total_exact_count += exact_count

        partial_count = sum([1 for word in p_text.lower().split() if keyword_lower in word])
        total_partial_count += partial_count

        if len(p_text) > max_p_length:
            results['p_length_limit_exceeded'] = '📏 Длина каждого элемента P в пределах нормы.'

        if p_text:
            current_consecutive_p_count += 1
        else:
            current_consecutive_p_count = 0

        max_consecutive_p_count = max(max_consecutive_p_count, current_consecutive_p_count)

        keyword_positions.extend([m.start() for m in re.finditer(keyword_lower, p_text.lower())])

    if max_consecutive_p_count > consecutive_p_limit:
        results['consecutive_p_count'] = '🧩 Количество подряд идущих элементов P без разделения допустимо.'

    total_length = len(total_text)
    results['total_p_length'] = f'📜 Общая длина всех элементов P: {total_length}' 
    results['exact_keyword_density'] = '🔍 Точное вхождение ключевой фразы встречается не менее одного раза на 1,000 символов.' if total_exact_count / (total_length / 1000) >= 1 else '⚠️ Точное вхождение ключевой фразы реже одного раза на 1,000 символов.'
    results['partial_keyword_density'] = total_partial_count / (total_length / 1000)

    if len(keyword_positions) > 1:
        intervals = [keyword_positions[i + 1] - keyword_positions[i] for i in range(len(keyword_positions) - 1)]
        avg_interval = sum(intervals) / len(intervals)
        uniformity_threshold = avg_interval * 0.5

    return results

def check_lists(soup):
    results = {
        'lists_between_p': '❌ Списки (UL, OL) отсутствуют между тегами P',
        'lists_in_article': False
    }

    # Проверка наличия списков между элементами <p>
    p_tags = soup.find_all('p')
    ul_tags = soup.find_all('ul')
    ol_tags = soup.find_all('ol')

    for i in range(len(p_tags) - 1):
        p1 = p_tags[i]
        p2 = p_tags[i + 1]
        lists_between = p1.find_next_siblings(['ul', 'ol'], limit=1)
        if lists_between and lists_between[0] != p2:
            results['lists_between_p'] = '📋 Списки (UL, OL) присутствуют между тегами P'
            break

    # Проверка наличия списков внутри <article>
    article_tag = soup.find('article')
    if article_tag:
        if article_tag.find_all(['ul', 'ol']):
            results['lists_in_article'] = True

    return results

def check_tables(soup):
    results = {
        'tables_between_p': '❌ Таблицы отсутствуют между тегами',
        'tables_in_article': False
    }

    # Проверка наличия таблиц между элементами <p>
    p_tags = soup.find_all('p')
    table_tags = soup.find_all('table')

    for i in range(len(p_tags) - 1):
        p1 = p_tags[i]
        p2 = p_tags[i + 1]
        tables_between = p1.find_next_siblings('table', limit=1)
        if tables_between and tables_between[0] != p2:
            results['tables_between_p'] = '📝 Таблицы обнаружены между тегами P'
            break

    # Проверка наличия таблиц внутри <article>
    article_tag = soup.find('article')
    if article_tag:
        if article_tag.find_all('table'):
            results['tables_in_article'] = True

    return results

def is_image_visible(img_tag):
    # Проверяем видимость изображения на странице
    styles = img_tag.get('style', '')
    if 'display: none' in styles:
        return False
    parent_tags = img_tag.find_parents()
    for parent in parent_tags:
        parent_style = parent.get('style', '')
        if 'display: none' in parent_style:
            return False
    noscript_parent = img_tag.find_parent('noscript')
    if noscript_parent:
        return False
    return True

def check_images(soup, keyword):
    results = {
        'image_count_per_3000_chars': 0,
        'all_images_have_alt': '✅ Все теги ALT заполнены.',
        'keyword_in_alt': '🔎 Ключевая фраза отсутствует в ALT.',
        'image_formats': '📷 Форматы изображений соответствуют требованиям.',
        'image_size_within_limit': '⚖️ Вес изображений в пределах нормы.'
    }

    # Получаем текст страницы для вычисления символов
    text = soup.get_text()
    char_count = len(text)

    # Находим все теги <img>
    img_tags = soup.find_all('img')
    visible_img_tags = [img for img in img_tags if is_image_visible(img)]

    total_images = len(visible_img_tags)
    if char_count > 0:
        results['image_count_per_3000_chars'] = '🖼️ На странице достаточно изображений.' if total_images / (char_count / 3000) >=1 else '❌ Недостаточно изображений на странице.'

    # Проверяем alt атрибуты и остальные условия
    for img in visible_img_tags:
        alt = img.get('alt', '').strip()
        if not alt:
            results['all_images_have_alt'] = '⚠️ Не все теги ALT заполнены.'
        if keyword.lower() in alt.lower():
            results['keyword_in_alt'] = '🔍 Ключевая фраза найдена в одном из ALT.'

        # Проверяем формат и размер изображения
        src = img.get('src', '')
        try:
            response = requests.get(src)
            if response.status_code == 200:
                image_data = BytesIO(response.content)
                img = Image.open(image_data)
                width, height = img.size
                file_format = img.format.lower()
                if file_format not in ['webp', 'jpeg', 'jpg', 'png']:
                    results['image_formats'] = '🖼️ Форматы изображений не соответствуют требованиям.'
                if width * height > 100 * 100 and len(response.content) > 100 * 100:
                    results['image_size_within_limit'] = '📏 Вес изображений превышает допустимый.'
        except Exception as e:
            print(f"Error checking image {src}: {e}")

    return results

# def check_formatting_tags(soup, keyword):
#     results = {
#         'tags_present':'❌ Теги оформления текста отсутствуют.',
#         'exact_keyword_in_tags': '⚠️ Точные ключевые слова не найдены внутри тегов оформления.',
#         'partial_keyword_in_tags': '🚫 Не точные ключевые слова отсутствуют внутри тегов оформления.'
#     }

#     # Поиск тегов оформления текста
#     tags_to_check = ['b', 'strong', 's', 'i', 'u', 'span']
#     for tag_name in tags_to_check:
#         tag_elements = soup.find_all(tag_name)
#         if tag_elements:
#             results['tags_present'][tag_name] = '🎨 Теги оформления текста присутствуют.'
#             for tag in tag_elements:
#                 text = tag.get_text().lower()
#                 if keyword.lower() in text:
#                     results['exact_keyword_in_tags'][tag_name] = '🏷️ Точные ключевые слова найдены внутри тегов оформления.'
#                 if keyword.lower()[:-1] in text or keyword.lower()[1:] in text:
#                     results['partial_keyword_in_tags'][tag_name] = '🔍 Не точные ключевые слова также присутствуют внутри тегов оформления.'

#     return results

def check_formatting_tags_and_keywords(soup, keyword):
    tags_to_check = ['b', 'strong', 's', 'i', 'u', 'span']
    formatting_tags_present = '❌ Теги оформления текста отсутствуют.'
    exact_keyword_found = '⚠️ Точные ключевые слова не найдены внутри тегов оформления.'
    partial_keyword_found = '🚫 Не точные ключевые слова отсутствуют внутри тегов оформления.'

    for tag_name in tags_to_check:
        tag_elements = soup.find_all(tag_name)
        if tag_elements:
            formatting_tags_present = '🎨 Теги оформления текста присутствуют.'
            for tag in tag_elements:
                text = tag.get_text().lower()
                if keyword.lower() in text:
                    exact_keyword_found = '🏷️ Точные ключевые слова найдены внутри тегов оформления.'
                if keyword.lower()[:-1] in text or keyword.lower()[1:] in text:
                    partial_keyword_found = '🔍 Не точные ключевые слова также присутствуют внутри тегов оформления.'
            # Если найдены все нужные результаты, выходим из цикла
            if formatting_tags_present and exact_keyword_found and partial_keyword_found:
                break

    return {
        'formatting_tags_present': formatting_tags_present,
        'exact_keyword_in_formatting_tags': exact_keyword_found,
        'partial_keyword_in_formatting_tags': partial_keyword_found
    }

def check_links(soup, keyword):
    external_links_present = '❌ Внешние ссылки не найдены.'
    internal_links_present = '🚫 Внутренние ссылки отсутствуют.'
    exact_keyword_in_anchor = '❗ Ключевое слово не найдено внутри ссылки.'
    # Проверка всех тегов <a> на наличие внешних и внутренних ссылок
    for a_tag in soup.find_all('a', href=True):
        href = a_tag.get('href')
        if href.startswith('http'):
            external_links_present = '🌐 Внешние ссылки найдены.'
        else:
            internal_links_present = '🔗 Внутренние ссылки присутствуют.'

        # Проверка наличия ключевого слова внутри текста ссылки
        anchor_text = a_tag.get_text().lower()
        if keyword.lower() in anchor_text:
            exact_keyword_in_anchor = '🔍 Ключевое слово точно найдено внутри ссылки.'

        # Выходим из цикла, если все нужные результаты найдены
        if external_links_present and internal_links_present and exact_keyword_in_anchor :
            break

    return {
        'external_links_present': external_links_present,
        'internal_links_present': internal_links_present,
        'exact_keyword_in_anchor': exact_keyword_in_anchor,
    }

def check_text_size_ratio(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    text_length = len(soup.get_text())
    html_length = len(str(soup))

    words_count = len(soup.get_text().split())
    characters_count = len(soup.get_text())

    text_code_ratio = '⚖️ Отношение символов контента к символам кода оптимально.' if text_length / html_length >= 0.2 else '📉 Отношение символов контента к символам кода неоптимально.'

    return {
        'words_count': f"📄 Количество слов на странице: {words_count}",
        'characters_count': f"✏️ Количество символов на странице: {characters_count}",
        'text_code_ratio': text_code_ratio
    }

def check_page_speed_and_size(url):
    try:
        start_time = time.time()
        response = requests.get(url)
        end_time = time.time()
        page_load_time = end_time - start_time

        if response.status_code == 200:
            page_size = len(response.content) / 1024  # размер страницы в килобайтах
            return {
                'page_load_time_seconds': '🚀 Скорость загрузки страницы отличная.' if page_load_time <= 2 else '🐢 Скорость загрузки страницы медленная.',
                'page_size_kb': page_size
            }
        else:
            return {
                'page_load_time_seconds': f"Не удалось загрузить URL: {e}",
                'page_size_kb': f"Не удалось загрузить URL: {e}"
            }

    except requests.exceptions.RequestException:
        return {
            'page_load_time_seconds': f"Не удалось загрузить URL: {e}",
            'page_size_kb': f"Не удалось загрузить URL: {e}"
        }
    
def check_iframe(soup):
    iframe_present = '🎉 Тег iframe отсутствует на странице.'
    if soup.find('iframe'):
        iframe_present = '❌ Тег iframe присутствует на странице.'

    return iframe_present

def check_shockwave_flash(soup):
    flash_present = '❌ Shockwave Flash отсутствует на странице.'

    # Проверяем теги object и embed, которые могут быть связаны с Flash
    object_tags = soup.find_all('object', type='application/x-shockwave-flash')
    embed_tags = soup.find_all('embed', type='application/x-shockwave-flash')

    if object_tags or embed_tags:
        flash_present = '✅ Наличие Shockwave Flash на странице подтверждено.'

    return flash_present

def check_favicon(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            favicon_tags = soup.find_all('link', rel='icon') + soup.find_all('link', rel='shortcut icon')

            has_favicon = '✅ Favicon присутствует на странице.' if any(tag.get('href') for tag in favicon_tags) else '❌ Favicon отсутствует на странице.'

            has_svg_favicon = '🖼️ Иконка в формате SVG обнаружена.' if any(tag.get('href').endswith('.svg') for tag in favicon_tags) else '🚫 Отсутствует иконка в формате SVG.'

            return {
                'has_favicon': has_favicon,
                'has_svg_favicon': has_svg_favicon
            }
        else:
            return {
                'has_favicon': '❌ Favicon отсутствует на странице.',
                'has_svg_favicon': '🚫 Отсутствует иконка в формате SVG.'
            }

    except requests.exceptions.RequestException:
        return {
            'has_favicon': f"Не удалось загрузить URL: {e}",
            'has_svg_favicon': f"Не удалось загрузить URL: {e}"
        }


def check_scripts_at_bottom(soup):
    body_tag = soup.body
    if not body_tag:
        return '❌ Скрипт не расположен внизу страницы.  # Если тег <body> отсутствует, то считаем, что скрипты не расположены внизу'

    script_tags = soup.find_all('script')

    for script_tag in script_tags:
        if script_tag.parent != body_tag:
            return '❌ Скрипт не расположен внизу страницы.' # Если скрипт не находится внутри тега <body>, то считаем, что скрипты не расположены внизу
        if script_tag.find_next_sibling():  # Если есть следующий соседний элемент, то скрипт не находится внизу
            return '❌ Скрипт не расположен внизу страницы.'

    return '🎉 Скрипт расположен внизу страницы.'

def check_analytics(soup):
    analytics = {
        'yandex_metrika': '🚫 Яндекс Метрика отсутствует.',
        'google_analytics': '📉 Google Analytics не работает.',
        'vk_pixel': '📵 Отсутствует VK pixel.'
    }

    # Проверяем наличие кода Яндекс Метрика
    yandex_metrika_scripts = soup.find_all('script', src=lambda x: x and 'mc.yandex.ru/metrika' in x)
    yandex_metrika_noscripts = soup.find_all('noscript', div=lambda x: x and 'mc.yandex.ru/metrika' in x)

    if yandex_metrika_scripts or yandex_metrika_noscripts:
        analytics['yandex_metrika'] = '🔍 Яндекс Метрика подключена.'

    # Проверяем наличие кода Google Analytics
    google_analytics_scripts = soup.find_all('script', src=lambda x: x and 'google-analytics.com/analytics' in x)

    if google_analytics_scripts:
        analytics['google_analytics'] = '📈 Google Analytics работает.'

    # Проверяем наличие VK pixel
    vk_pixel_scripts = soup.find_all('script', src=lambda x: x and 'vk.com/js/api/openapi.js' in x)

    if vk_pixel_scripts:
        analytics['vk_pixel'] = '📱 VK pixel установлен.'

    return analytics

def check_crm(soup):
    crm = {
        'bitrix24': '🚫 Битрикс24 не подключен',
        'amo': '🚫 Амо не подключен'
    }

    # Проверяем наличие кода Битрикс24
    bitrix24_scripts = soup.find_all('script', src=lambda x: x and 'bitrix24' in x)

    if bitrix24_scripts:
        crm['bitrix24'] = '📈 Битрикс24 подключен.'

    # Проверяем наличие кода AMO
    amo_scripts = soup.find_all('script', src=lambda x: x and 'amocrm' in x)

    if amo_scripts:
        crm['amo'] = '📈 Амо подключен'

    return crm


def check_cms(soup):
    cms = {
        'wordpress': '❌ Сайт не работает на WordPress.',
        'tilda': '❌ Сайт не работает на Tilda.',
        '1c_bitrix': '❌ Сайт не работает на 1C-Bitrix.'
    }

    # Проверяем наличие кода WordPress
    wordpress_meta_generator = soup.find('meta', {'name': 'generator', 'content': 'WordPress'})

    if wordpress_meta_generator:
        cms['wordpress'] = '✅ Сайт работает на WordPress'

    # Проверяем наличие кода Tilda
    tilda_scripts = soup.find_all('script', src=lambda x: x and 'tilda.cc' in x)

    if tilda_scripts:
        cms['tilda'] = '✅ Сайт работает на Tilda.'

    # Проверяем наличие кода 1C-Bitrix
    bitrix1c_scripts = soup.find_all('script', src=lambda x: x and 'bitrix' in x)

    if bitrix1c_scripts:
        cms['1c_bitrix'] = '✅ Сайт работает на 1C-Bitrix.'

    return cms




def seo_analysis(url, keyword):
    response = fetch_page(url)
    if response is None:
        return {'error': 'Unable to fetch the page.'}

    content_type = response.headers.get('Content-Type', '').lower()
    if 'text/html' not in content_type:
        return {'error': 'The URL does not point to an HTML page.'}

    content = response.content
    soup = BeautifulSoup(content, 'html.parser')

    title_results = check_title(soup, keyword)
    keywords_results = check_keywords(soup, keyword)
    description_results = check_description(soup, keyword)
    language_results = check_language(soup)
    charset_results = check_charset(response)
    h1_results = check_h1(soup, keyword, title_results.get('title', ''))
    article_results = check_article_tag(soup)
    h2_results = check_h2(soup, keyword)
    toc_results = check_toc(soup)
    open_graph_results = check_open_graph(soup)
    p_tag_results = check_p_tags(soup, keyword)
    list_results = check_lists(soup)
    table_results = check_tables(soup)
    image_results = check_images(soup, keyword)
    formatting_tags_keywords = check_formatting_tags_and_keywords(soup, keyword)
    links_results = check_links(soup, keyword)
    text_size_ratio_results = check_text_size_ratio(response.content)
    text_size_ratio_results = check_text_size_ratio(response.content)
    page_speed_and_size_results = check_page_speed_and_size(url) 
    iframe_results = check_iframe(soup)
    shockwave_flash_results = check_shockwave_flash(soup)
    favicon_results = check_favicon(url)
    scripts_at_bottom_results = check_scripts_at_bottom(soup)
    analytics_results = check_analytics(soup)
    crm_results = check_crm(soup)
    cms_results = check_cms(soup)

    return  {
        'title': title_results,
        'keywords': keywords_results,
        'description': description_results,
        'language': language_results,
        'charset': charset_results,
        'h1': h1_results,
        'article': article_results,
        'h2': h2_results,
        'toc': toc_results,
        'open_graph': open_graph_results,
        'p_tags': p_tag_results,
        'lists': list_results,
        'tables': table_results,
        'images': image_results,
        'formatting_tags_keywords': formatting_tags_keywords,
        'links': links_results,
        'text_size_ratio': text_size_ratio_results,
        'text_size_ratio': text_size_ratio_results,
        'page_speed_and_size': page_speed_and_size_results,
        'iframe': iframe_results,
        'shockwave_flash': shockwave_flash_results,
        'favicon': favicon_results,
        'scripts_at_bottom': scripts_at_bottom_results,
        'analytics': analytics_results,
        'crm': crm_results,
        'cms': cms_results,
        
    }




@app.get("/seo-analysis/")
async def seo_analysis(url: str = Query(..., description="URL страницы для анализа"),
                        keyword: str = Query(..., description="Ключевая фраза для анализа")):
    try:
        response = fetch_page(url)
    
        if response is None:
            return {'error': 'Unable to fetch the page.'}

        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' not in content_type:
            return {'error': 'The URL does not point to an HTML page.'}

        content = response.content
        soup = BeautifulSoup(content, 'html.parser')

        title_results = check_title(soup, keyword)
        keywords_results = check_keywords(soup, keyword)
        description_results = check_description(soup, keyword)
        language_results = check_language(soup)
        charset_results = check_charset(response)
        h1_results = check_h1(soup, keyword, title_results.get('title', ''))
        article_results = check_article_tag(soup)
        h2_results = check_h2(soup, keyword)
        toc_results = check_toc(soup)
        open_graph_results = check_open_graph(soup)
        p_tag_results = check_p_tags(soup, keyword)
        list_results = check_lists(soup)
        table_results = check_tables(soup)
        image_results = check_images(soup, keyword)
        formatting_tags_keywords = check_formatting_tags_and_keywords(soup, keyword)
        links_results = check_links(soup, keyword)
        text_size_ratio_results = check_text_size_ratio(response.content)
        text_size_ratio_results = check_text_size_ratio(response.content)
        page_speed_and_size_results = check_page_speed_and_size(url) 
        iframe_results = check_iframe(soup)
        shockwave_flash_results = check_shockwave_flash(soup)
        favicon_results = check_favicon(url)
        scripts_at_bottom_results = check_scripts_at_bottom(soup)
        analytics_results = check_analytics(soup)
        crm_results = check_crm(soup)
        cms_results = check_cms(soup)
        check_keywords_result = check_keywords(soup, keyword)
            

        return {
            'title': title_results,
        'keywords': keywords_results,
        'description': description_results,
        'language': language_results,
        'charset': charset_results,
        'h1': h1_results,
        'article': article_results,
        'h2': h2_results,
        'toc': toc_results,
        'open_graph': open_graph_results,
        'p_tags': p_tag_results,
        'lists': list_results,
        'tables': table_results,
        'images': image_results,
        'formatting_tags_keywords': formatting_tags_keywords,
        'links': links_results,
        'text_size_ratio': text_size_ratio_results,
        'text_size_ratio': text_size_ratio_results,
        'page_speed_and_size': page_speed_and_size_results,
        'iframe': iframe_results,
        'shockwave_flash': shockwave_flash_results,
        'favicon': favicon_results,
        'scripts_at_bottom': scripts_at_bottom_results,
        'analytics': analytics_results,
        'crm': crm_results,
        'cms': cms_results,
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)