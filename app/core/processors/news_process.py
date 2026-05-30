import logging
import re

import nltk
import pandas as pd
import torch
from natasha import Doc, MorphVocab, NewsEmbedding, NewsMorphTagger, NewsNERTagger, NewsSyntaxParser, Segmenter
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from tqdm import tqdm
from transformers import pipeline

logger = logging.getLogger(__name__)

SENTIMENT_MODEL_NAME = 'mxlcw/rubert-tiny2-russian-financial-sentiment'
SENTIMENT_MAX_LENGTH = 512
GPU_SENTIMENT_BATCH_SIZE = 4
CPU_SENTIMENT_BATCH_SIZE = 32


class NewsProcessor:
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

    def __init__(self, *, use_gpu: bool = False, sentiment_batch_size: int | None = None):
        sentiment_device = self._resolve_sentiment_device(use_gpu)
        if sentiment_batch_size is None:
            sentiment_batch_size = GPU_SENTIMENT_BATCH_SIZE if sentiment_device >= 0 else CPU_SENTIMENT_BATCH_SIZE
        self.sentiment_device = sentiment_device
        self.sentiment_batch_size = sentiment_batch_size

        tqdm.pandas()
        nltk.download('stopwords')

        # Инициализация моделей Natasha
        self.segmenter = Segmenter()
        self.morph_vocab = MorphVocab()
        self.emb = NewsEmbedding()
        self.morph_tagger = NewsMorphTagger(self.emb)
        self.syntax_parser = NewsSyntaxParser(self.emb)
        self.ner_tagger = NewsNERTagger(self.emb)

        # Подготовка для векторизации
        self.russian_stopwords = stopwords.words('russian')

        self.sector_names = list(self.INDEX_KEYWORDS.keys())  # список индексов секторов
        self.sector_docs = [' '.join(words) for words in self.INDEX_KEYWORDS.values()]  # вектор ключевых слов
        self.sector_docs_norm = [self.normalize_text(doc) for doc in self.sector_docs]  # нормализация вектора

        self.vectorizer = TfidfVectorizer(stop_words=self.russian_stopwords)
        self.sector_matrix = self.vectorizer.fit_transform(self.sector_docs_norm)

        self.sentiment_model = pipeline(
            task='text-classification',
            model=SENTIMENT_MODEL_NAME,
            device=sentiment_device,
        )
        model_max_length = getattr(self.sentiment_model.model.config, 'max_position_embeddings', SENTIMENT_MAX_LENGTH)
        self.sentiment_max_length = min(model_max_length, SENTIMENT_MAX_LENGTH)
        device_name = 'GPU' if sentiment_device >= 0 else 'CPU'
        logger.info(
            'Sentiment model loaded on %s (use_gpu=%s, batch_size=%s, max_length=%s)',
            device_name,
            use_gpu,
            self.sentiment_batch_size,
            self.sentiment_max_length,
        )

    @staticmethod
    def _resolve_sentiment_device(use_gpu: bool) -> int:
        if not use_gpu:
            return -1
        if torch.cuda.is_available():
            return 0
        logger.warning('GPU requested but CUDA is not available, falling back to CPU')
        return -1

    def normalize_text(self, text: str) -> str:
        """Лемматизация и очистка текста от чисел и символов."""
        doc = Doc(text)
        doc.segment(self.segmenter)
        doc.tag_morph(self.morph_tagger)
        if not doc.tokens:
            return ''
        lemmas = []
        for token in doc.tokens:
            token.lemmatize(self.morph_vocab)
            if re.match(r'^[а-яА-Яa-zA-Z]+$', token.text):  # исключаем числа и знаки
                lemmas.append(token.lemma.lower())

        return ' '.join(lemmas)

    def get_text_sentiment(self, news_texts: list[str]) -> list[str | None]:
        """
        Принимает на вход список текстов, применяет модель для определения тональности.
        Выделяет только класс новости (без уверенности) и возврашает список меток той же размерности

        Args:
            news_texts (list[str]): Список новостей

        Returns:
            _type_: Список меток(label) тональностей для новостей
        """
        max_length = self.sentiment_max_length
        if self.sentiment_device >= 0:
            torch.cuda.empty_cache()

        labels: list[str | None] = []
        for offset in tqdm(range(0, len(news_texts), self.sentiment_batch_size), desc='Sentiment'):
            batch = news_texts[offset : offset + self.sentiment_batch_size]
            results = self.sentiment_model(
                batch,
                truncation=True,
                max_length=max_length,
                batch_size=len(batch),
            )
            labels.extend(sentiment.get('label') for sentiment in results)
        return labels

    def extract_organizations(self, text: str) -> list[str]:
        """Извлекает организации из текста с помощью Natasha NER."""
        doc = Doc(text)
        doc.segment(self.segmenter)
        doc.parse_syntax(self.syntax_parser)
        doc.tag_morph(self.morph_tagger)
        doc.tag_ner(self.ner_tagger)
        found_spans = []
        if not doc.spans:
            return []
        for span in doc.spans:
            if span.type == 'ORG':
                span.normalize(self.morph_vocab)
                found_spans.append(span.normal.lower())
        return found_spans

    def extract_tickers(self, orgs: list[str]) -> list[str]:
        """Определяет тикеры по извлечённым названиям компаний."""
        tickers = set()
        for org in orgs:
            for ticker, keywords in self.TICKER_KEYWORDS.items():
                if any(org == kw.lower() for kw in keywords):
                    tickers.add(ticker)
        return list(tickers)

    def detect_sector_tfidf(self, text: str) -> str | None:
        """
        Определяет сектор новости по косинусному сходству с TF-IDF.
        Если нет явного сходства - возвращает None
        """
        text_norm = self.normalize_text(text)
        text_vector = self.vectorizer.transform([text_norm])
        sims = cosine_similarity(text_vector, self.sector_matrix)[0]
        if sims.max() < 0.1:
            return None
        return self.sector_names[sims.argmax()]

    def get_tickers(self, text: str) -> list[str]:
        """Верхнеуровневая функция для поиска тикеров

        Args:
            text (str): текст новости

        Returns:
            list[str]: список найденных тикеров
        """
        orgs = self.extract_organizations(text)
        return self.extract_tickers(orgs)

    def process_news(
        self,
        df: pd.DataFrame,
    ):
        print('Ищем тикеры в новостях...')
        df['tickers'] = df['text'].progress_apply(self.get_tickers)
        print('DONE!\n')

        print('Определяем сектор влияния новостей...')
        df['sector'] = df['text'].progress_apply(self.detect_sector_tfidf)
        print('DONE!\n')

        print('Определяем тональность новостей...')
        df['text_sentiment'] = self.get_text_sentiment(df.text.to_list())
        print('DONE!\n')

        print('Обработка завершена')
        return df
