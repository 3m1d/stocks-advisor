import re

import click
import nltk
import pandas as pd
from natasha import Doc, MorphVocab, NewsEmbedding, NewsMorphTagger, NewsNERTagger, NewsSyntaxParser, Segmenter
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from tqdm import tqdm
from transformers import pipeline

tqdm.pandas()
nltk.download('stopwords')

# Словарь ключевых слов для тикеров голубых фишек
TICKER_KEYWORDS = {
    'SBER': ['сбербанк', 'сбер', 'пао сбербанк'],
    'GAZP': ['газпром', 'пао газпром', 'газовая компания'],
    'LKOH': ['лукойл', 'пао лукойл', 'нк лукойл'],
    'ROSN': ['роснефть', 'пао роснефть', 'нк роснефть'],
    'YDEX': ['яндекс', 'yandex', 'яндекс.такси', 'яндекс.недвижимость'],
    'VTBR': ['втб', 'банк втб', 'пао втб'],
    'TATN': ['татнефть', 'пао татнефть', 'татнефть-нк'],
    'GMKN': ['норильский никель', 'пао гмк норильский никель', 'gmk norilsk nickel'],
}

# Ключевые слова по индексам
INDEX_KEYWORDS = {
    'MOEXOG': [  # Нефть и газ
        'нефть',
        'газ',
        'добыча',
        'бурение',
        'скважина',
        'топливо',
        'трубопровод',
        'нефтепереработка',
        'нефтехимия',
        'сланец',
        'бензин',
        'дизель',
        'нефтяная компания',
    ],
    'MOEXFN': [  # Финансовый сектор
        'банк',
        'кредит',
        'ставка',
        'ипотека',
        'вклад',
        'депозит',
        'облигация',
        'акция',
        'финансы',
        'страхование',
        'инвестиции',
        'ЦБ',
        'биржа',
        'дивиденды',
        'брокер',
    ],
    'MOEXMM': [  # Металлургия и добыча
        'металл',
        'сталь',
        'рудник',
        'шахта',
        'добыча',
        'уголь',
        'железная руда',
        'никель',
        'медь',
        'алюминий',
        'золото',
        'серебро',
        'горнодобыча',
        'плавка',
    ],
    'MOEXCN': [  # Потребительский сектор
        'потребитель',
        'ритейл',
        'магазин',
        'торговля',
        'продукты',
        'еда',
        'напитки',
        'одежда',
        'FMCG',
        'бытовая техника',
        'супермаркет',
        'розничная торговля',
        'товары',
    ],
    'MOEXTN': [  # Транспорт
        'транспорт',
        'логистика',
        'авиакомпания',
        'железная дорога',
        'порт',
        'флот',
        'аэропорт',
        'автоперевозки',
        'грузоперевозки',
        'контейнер',
        'трамвай',
        'метро',
    ],
    'MOEXEU': [  # Электроэнергетика
        'электроэнергия',
        'энергетика',
        'генерация',
        'электростанция',
        'теплоэнергия',
        'ГЭС',
        'ТЭЦ',
        'АЭС',
        'мощность',
        'энергосбыт',
        'электричество',
        'энергокомпания',
    ],
    'MOEXTL': [  # Телекоммуникации
        'телеком',
        'связь',
        'интернет',
        'мобильный оператор',
        'сотовая связь',
        'телефон',
        'передача данных',
        'оптоволокно',
        'трафик',
        'сетевые технологии',
    ],
    'MOEXCH': [  # Химия и нефтехимия
        'химия',
        'нефтехимия',
        'пластик',
        'полимер',
        'удобрения',
        'реактивы',
        'синтез',
        'нефтепродукты',
        'катализатор',
        'химическое производство',
        'серная кислота',
    ],
    'MOEXIT': [  # Информационные технологии
        'it',
        'айти',
        'технологии',
        'программное обеспечение',
        'разработка',
        'интернет-сервис',
        'стартап',
        'искусственный интеллект',
        'кибербезопасность',
        'софт',
        'облачные технологии',
        'приложение',
        'данные',
        'автоматизация',
        'цифровизация',
    ],
    'MOEXRE': [  # Строительные компании
        'стройка',
        'строительство',
        'девелопмент',
        'недвижимость',
        'жилой комплекс',
        'инфраструктура',
        'ремонт',
        'архитектура',
        'подрядчик',
        'застройщик',
        'объект',
        'капитальное строительство',
    ],
}


def normalize_text(text: str) -> str:
    """Лемматизация и очистка текста от чисел и символов."""
    doc = Doc(text)
    doc.segment(segmenter)
    doc.tag_morph(morph_tagger)
    if not doc.tokens:
        return ''
    lemmas = []
    for token in doc.tokens:
        token.lemmatize(morph_vocab)
        if re.match(r'^[а-яА-Яa-zA-Z]+$', token.text):  # исключаем числа и знаки
            lemmas.append(token.lemma.lower())

    return ' '.join(lemmas)


# Инициализация модели для определения тональности
sentiment_model = pipeline(task='text-classification', model='mxlcw/rubert-tiny2-russian-economic-sentiment')


def get_text_sentiment(news_texts: list[str]) -> list[str | None]:
    """
    Принимает на вход список текстов, применяет модель для определения тональности.
    Выделяет только класс новости (без уверенности) и возврашает список меток той же размерности

    Args:
        news_texts (list[str]): Список новостей

    Returns:
        _type_: Список меток(label) тональностей для новостей
    """
    return [sentiment.get('label') for sentiment in tqdm(sentiment_model(news_texts))]


# Инициализация моделей Natasha
segmenter = Segmenter()
morph_vocab = MorphVocab()
emb = NewsEmbedding()
morph_tagger = NewsMorphTagger(emb)
syntax_parser = NewsSyntaxParser(emb)
ner_tagger = NewsNERTagger(emb)


# Подготовка для векторизации
russian_stopwords = stopwords.words('russian')


sector_names = list(INDEX_KEYWORDS.keys())  # список индексов секторов
sector_docs = [' '.join(words) for words in INDEX_KEYWORDS.values()]  # вектор ключевых слов
sector_docs_norm = [normalize_text(doc) for doc in sector_docs]  # нормализация вектора

vectorizer = TfidfVectorizer(stop_words=russian_stopwords)
sector_matrix = vectorizer.fit_transform(sector_docs_norm)


def extract_organizations(text: str) -> list[str]:
    """Извлекает организации из текста с помощью Natasha NER."""
    doc = Doc(text)
    doc.segment(segmenter)
    doc.parse_syntax(syntax_parser)
    doc.tag_morph(morph_tagger)
    doc.tag_ner(ner_tagger)
    found_spans = []
    if not doc.spans:
        return []
    for span in doc.spans:
        if span.type == 'ORG':
            span.normalize(morph_vocab)
            found_spans.append(span.normal.lower())
    return found_spans


def extract_tickers(orgs: list[str]) -> list[str]:
    """Определяет тикеры по извлечённым названиям компаний."""
    tickers = set()
    for org in orgs:
        for ticker, keywords in TICKER_KEYWORDS.items():
            if any(org == kw.lower() for kw in keywords):
                tickers.add(ticker)
    return list(tickers)


def detect_sector_tfidf(text: str) -> str | None:
    """
    Определяет сектор новости по косинусному сходству с TF-IDF.
    Если нет явного сходства - возвращает None
    """
    text_norm = normalize_text(text)
    text_vector = vectorizer.transform([text_norm])
    sims = cosine_similarity(text_vector, sector_matrix)[0]
    if sims.max() < 0.1:
        return None
    return sector_names[sims.argmax()]


def concatenate_datasets(input_files: list[str], out_file: str) -> pd.DataFrame:
    """Собираем датасеты в один

    Args:
        input_files (list[str]): список файлов, которые надо
        out_file (str): _description_

    Returns:
        pd.DataFrame: итоговый датасет
    """
    print('Соединяем датасеты...')
    dataframes = [pd.read_csv(file) for file in input_files]
    final_df = pd.concat(dataframes, ignore_index=True)

    final_df.date = pd.to_datetime(final_df.date, errors='coerce')
    final_df = final_df.sort_values(by='date').reset_index(drop=True)

    final_df.to_csv(out_file, na_rep='NULL', index=False)

    print('DONE!\n')
    # слияние дубликатов finance и financies
    final_df.topic = final_df.topic.apply(lambda topic: 'finance' if topic == 'financies' else topic)

    return final_df


def get_tickers(text: str) -> list[str]:
    """Верхнеуровневая функция для поиска тикеров

    Args:
        text (str): текст новости

    Returns:
        list[str]: список найденных тикеров
    """
    orgs = extract_organizations(text)
    return extract_tickers(orgs)


def run_news_pipeline(df: pd.DataFrame, out_file: str):
    print('Ищем тикеры в новостях...')
    df['tickers'] = df['text'].progress_apply(get_tickers)
    print('DONE!\n')

    print('Определяем сектор влияния новостей...')
    df['sector'] = df['text'].progress_apply(detect_sector_tfidf)
    print('DONE!\n')

    print('Определяем тональность новостей...')
    df['text_sentiment'] = get_text_sentiment(df.text.to_list())
    print('DONE!\n')

    # сохраняем итоговый файл
    print('Cохраняем итоговый файл...')
    df.to_csv(out_file, index=False, na_rep='NULL')
    print('DONE!')


@click.command()
@click.argument('input_files', nargs=-1, type=click.Path(exists=True))
@click.option('--out_raw', help='Выходной необработанный csv файл')
@click.option('--out', help='Выходной обработанный csv файл')
@click.option('--test', '-t', default=0, help='Размер тестовой выборки (если 0 - обработка целиком)')
def main(input_files: str, out_raw: str, out: str, test: int):
    input_file_list = list(input_files)
    df = concatenate_datasets(input_file_list, out_raw)
    if test:
        df = df.sample(test)

    run_news_pipeline(df, out)


if __name__ == '__main__':
    main()
