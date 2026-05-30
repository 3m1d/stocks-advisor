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
GPU_SENTIMENT_BATCH_SIZE = 16
CPU_SENTIMENT_BATCH_SIZE = 32
SECTOR_SIMILARITY_THRESHOLD = 0.1


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

    def __init__(
        self,
        *,
        use_gpu: bool = False,
        sentiment_batch_size: int | None = None,
    ):
        sentiment_device = self._resolve_sentiment_device(use_gpu)
        if sentiment_batch_size is None:
            sentiment_batch_size = GPU_SENTIMENT_BATCH_SIZE if sentiment_device >= 0 else CPU_SENTIMENT_BATCH_SIZE
        self.sentiment_device = sentiment_device
        self.sentiment_batch_size = sentiment_batch_size

        self._org_to_ticker = {
            keyword.lower(): ticker for ticker, keywords in self.TICKER_KEYWORDS.items() for keyword in keywords
        }

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
        model_config = self.sentiment_model.model.config
        model_max_length = getattr(model_config, 'max_position_embeddings', SENTIMENT_MAX_LENGTH)
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

    @staticmethod
    def _lemmatize_doc(doc: Doc, morph_vocab: MorphVocab) -> str:
        if not doc.tokens:
            return ''
        lemmas = []
        for token in doc.tokens:
            token.lemmatize(morph_vocab)
            if re.match(r'^[а-яА-Яa-zA-Z]+$', token.text):
                lemmas.append(token.lemma.lower())
        return ' '.join(lemmas)

    def normalize_text(self, text: str) -> str:
        """Лемматизация и очистка текста от чисел и символов."""
        doc = Doc(text)
        doc.segment(self.segmenter)
        doc.tag_morph(self.morph_tagger)
        return self._lemmatize_doc(doc, self.morph_vocab)

    def enrich_text(self, text: str) -> tuple[list[str], str]:
        """Извлекает тикеры и нормализованный текст за один проход модели Natasha."""
        doc = Doc(text)
        doc.segment(self.segmenter)
        doc.tag_morph(self.morph_tagger)
        text_norm = self._lemmatize_doc(doc, self.morph_vocab)

        doc.parse_syntax(self.syntax_parser)
        doc.tag_ner(self.ner_tagger)
        orgs: list[str] = []
        if doc.spans:
            for span in doc.spans:
                if span.type == 'ORG':
                    span.normalize(self.morph_vocab)
                    orgs.append(span.normal.lower())

        return self.extract_tickers(orgs), text_norm

    def enrich_texts(self, texts: list[str]) -> tuple[list[list[str]], list[str]]:
        results = [self.enrich_text(text) for text in tqdm(texts, desc='Enrichment')]
        tickers, text_norms = zip(*results)
        return list(tickers), list(text_norms)

    def detect_sectors_batch(self, text_norms: list[str]) -> list[str | None]:
        if not text_norms:
            return []
        text_vectors = self.vectorizer.transform(text_norms)
        sims = cosine_similarity(text_vectors, self.sector_matrix)
        sectors: list[str | None] = []
        for row in sims:
            if row.max() < SECTOR_SIMILARITY_THRESHOLD:
                sectors.append(None)
            else:
                sectors.append(self.sector_names[row.argmax()])
        return sectors

    def get_text_sentiment(self, news_texts: list[str]) -> list[str | None]:
        """
        Принимает на вход список текстов, применяет модель для определения тональности.
        Выделяет только класс новости (без уверенности) и возврашает список меток той же размерности

        Args:
            news_texts (list[str]): Список новостей

        Returns:
            _type_: Список меток(label) тональностей для новостей
        """
        if self.sentiment_device >= 0:
            torch.cuda.empty_cache()

        results = self.sentiment_model(
            news_texts,
            truncation=True,
            max_length=self.sentiment_max_length,
            batch_size=self.sentiment_batch_size,
        )
        return [sentiment.get('label') for sentiment in results]

    def extract_tickers(self, orgs: list[str]) -> list[str]:
        """Определяет тикеры по извлечённым названиям компаний."""
        tickers = set()
        for org in orgs:
            ticker = self._org_to_ticker.get(org)
            if ticker:
                tickers.add(ticker)
        return list(tickers)

    def detect_sector_tfidf(self, text: str) -> str | None:
        """
        Определяет сектор новости по косинусному сходству с TF-IDF.
        Если нет явного сходства - возвращает None
        """
        return self.detect_sectors_batch([self.normalize_text(text)])[0]

    def get_tickers(self, text: str) -> list[str]:
        """Верхнеуровневая функция для поиска тикеров."""
        return self.enrich_text(text)[0]

    def process_news(
        self,
        df: pd.DataFrame,
    ):
        texts = df['text'].tolist()

        print('Извлекаем тикеры и готовим тексты для секторов...')
        tickers, text_norms = self.enrich_texts(texts)
        df['tickers'] = tickers
        print('DONE!\n')

        print('Определяем сектор влияния новостей...')
        df['sector'] = self.detect_sectors_batch(text_norms)
        print('DONE!\n')

        print('Определяем тональность новостей...')
        df['text_sentiment'] = self.get_text_sentiment(texts)
        print('DONE!\n')

        print('Обработка завершена')
        return df
