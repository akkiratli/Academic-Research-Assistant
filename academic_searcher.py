"""
ACADEMIC SEARCHER PRO - Akademik Makalelerin Google'ı
Gelişmiş Arama + Not Modülü + Özet Çıkarma
"""

import threading
import webbrowser
import requests
from bs4 import BeautifulSoup
import json
import time
import re
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
import sqlite3
import os
import nltk
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from sumy.summarizers.text_rank import TextRankSummarizer

# Ttkbootstrap teması (opsiyonel)
try:
    import ttkbootstrap as tb
    THEME_AVAILABLE = True
except ImportError:
    THEME_AVAILABLE = False

# NLTK verilerini indir
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

class DatabaseManager:
    """Veritabanı yönetim sınıfı"""
    
    def __init__(self, db_path="academic_notes.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Veritabanını başlat"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_title TEXT,
                    source_url TEXT,
                    source_authors TEXT,
                    source_year TEXT,
                    page_reference TEXT,
                    tags TEXT,
                    created_date TEXT,
                    modified_date TEXT
                )
            ''')
            conn.commit()
    
    def add_note(self, note_data):
        """Yeni not ekle"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO notes 
                (title, content, source_title, source_url, source_authors, source_year, 
                 page_reference, tags, created_date, modified_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                note_data['title'],
                note_data['content'],
                note_data.get('source_title', ''),
                note_data.get('source_url', ''),
                note_data.get('source_authors', ''),
                note_data.get('source_year', ''),
                note_data.get('page_reference', ''),
                note_data.get('tags', ''),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
            return cursor.lastrowid
    
    def get_all_notes(self):
        """Tüm notları getir"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM notes ORDER BY modified_date DESC')
            return [self._row_to_dict(row) for row in cursor.fetchall()]
    
    def search_notes(self, query):
        """Notlarda arama yap"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM notes 
                WHERE title LIKE ? OR content LIKE ? OR tags LIKE ? 
                OR source_title LIKE ? OR source_authors LIKE ?
                ORDER BY modified_date DESC
            ''', (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%'))
            return [self._row_to_dict(row) for row in cursor.fetchall()]
    
    def update_note(self, note_id, note_data):
        """Notu güncelle"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE notes 
                SET title=?, content=?, source_title=?, source_url=?, source_authors=?, 
                    source_year=?, page_reference=?, tags=?, modified_date=?
                WHERE id=?
            ''', (
                note_data['title'],
                note_data['content'],
                note_data.get('source_title', ''),
                note_data.get('source_url', ''),
                note_data.get('source_authors', ''),
                note_data.get('source_year', ''),
                note_data.get('page_reference', ''),
                note_data.get('tags', ''),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                note_id
            ))
    
    def delete_note(self, note_id):
        """Notu sil"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM notes WHERE id=?', (note_id,))
    
    def _row_to_dict(self, row):
        """SQL satırını dictionary'e çevir"""
        return {
            'id': row[0], 'title': row[1], 'content': row[2], 'source_title': row[3],
            'source_url': row[4], 'source_authors': row[5], 'source_year': row[6],
            'page_reference': row[7], 'tags': row[8], 'created_date': row[9],
            'modified_date': row[10]
        }


class SearchEngine:
    """Arama motoru sınıfı"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'AcademicSearcher/2.0',
            'Accept': 'application/json'
        }
    
    def search(self, source, query, max_results):
        """Kaynağa göre arama yap"""
        search_methods = {
            'DOAJ': self._search_doaj,
            'ArXiv': self._search_arxiv,
            'Crossref': self._search_crossref,
            'PubMed': self._search_pubmed,
            'IEEE': self._search_ieee,
            'MIT': self._search_mit,
            'DergiPark': self._search_dergipark,
            'TÜBİTAK': self._search_tubitak,
            'ODTÜ': self._search_metu,
            'İTÜ': self._search_itu,
            'Boğaziçi': self._search_boun,
            'Ankara Üniv.': self._search_ankara,
            # YENİ KAYNAKLAR
            'ScienceDirect': self._search_sciencedirect,
            'Springer': self._search_springer,
            'YÖK Tez': self._search_yok_tez,
            'Milli Kütüphane': self._search_milli_kutuphane
        }
        
        if source in search_methods:
            return search_methods[source](query, max_results)
        return []
    
    def _search_doaj(self, query, max_results):
        """DOAJ arama"""
        try:
            url = f'https://doaj.org/api/search/articles/{requests.utils.quote(query)}?pageSize={max_results}'
            response = requests.get(url, headers=self.headers, timeout=15)
            if response.status_code != 200:
                return []
            
            data = response.json()
            results = []
            for item in data.get('results', []):
                bib = item.get('bibjson', {})
                title = bib.get('title', '')
                if isinstance(title, list):
                    title = title[0] if title else 'No title'
                
                authors = ', '.join([a.get('name', '') for a in bib.get('author', [])])
                year = bib.get('year', '') or bib.get('publication_year', '')
                
                # Link bul
                link = ''
                for l in bib.get('link', []):
                    if l.get('url'): 
                        link = l.get('url')
                        break
                if not link:
                    link = bib.get('url', '') or item.get('id', '')
                
                results.append({
                    'title': title, 'authors': authors, 'year': str(year),
                    'source': 'DOAJ', 'link': link
                })
            return results
        except Exception:
            return []
    
    def _search_arxiv(self, query, max_results):
        """ArXiv arama"""
        try:
            url = f'http://export.arxiv.org/api/query?search_query=all:{requests.utils.quote(query)}&max_results={max_results}'
            response = requests.get(url, headers=self.headers, timeout=15)
            if response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.content, 'xml')
            results = []
            for entry in soup.find_all('entry'):
                title = entry.find('title')
                title = title.text.strip() if title else 'No title'
                
                authors = []
                for author in entry.find_all('author'):
                    name = author.find('name')
                    if name:
                        authors.append(name.text.strip())
                
                published = entry.find('published')
                year = published.text[:4] if published else ''
                
                link_elem = entry.find('link', {'title': 'pdf'})
                link = link_elem['href'] if link_elem else entry.find('id').text if entry.find('id') else ''
                
                results.append({
                    'title': title, 'authors': ', '.join(authors), 'year': year,
                    'source': 'ArXiv', 'link': link
                })
            return results
        except Exception:
            return []
    
    def _search_crossref(self, query, max_results):
        """Crossref arama"""
        try:
            url = f'https://api.crossref.org/works?query={requests.utils.quote(query)}&rows={max_results}'
            response = requests.get(url, headers=self.headers, timeout=15)
            if response.status_code != 200:
                return []
            
            data = response.json()
            results = []
            for item in data.get('message', {}).get('items', []):
                title = item.get('title', [''])[0] if item.get('title') else 'No title'
                
                authors = []
                for author in item.get('author', []):
                    given = author.get('given', '')
                    family = author.get('family', '')
                    if given or family:
                        authors.append(f"{given} {family}".strip())
                
                # Yıl bul
                year = ''
                date_parts = (item.get('published-print') or item.get('published-online') or 
                            item.get('created', {})).get('date-parts', [[None]])[0]
                if date_parts and date_parts[0]:
                    year = str(date_parts[0])
                
                link = item.get('URL', '')
                
                results.append({
                    'title': title, 'authors': ', '.join(authors), 'year': year,
                    'source': 'Crossref', 'link': link
                })
            return results
        except Exception:
            return []
    
    def _search_pubmed(self, query, max_results):
        """PubMed arama"""
        try:
            # Basitleştirilmiş PubMed arama
            return [{
                'title': f'PubMed: {query}',
                'authors': 'NCBI',
                'year': datetime.now().year,
                'source': 'PubMed',
                'link': f'https://pubmed.ncbi.nlm.nih.gov/?term={requests.utils.quote(query)}'
            }]
        except Exception:
            return []
    
    def _search_ieee(self, query, max_results):
        """IEEE arama"""
        return [{
            'title': f'IEEE Xplore: {query}',
            'authors': 'IEEE',
            'year': datetime.now().year,
            'source': 'IEEE',
            'link': f'https://ieeexplore.ieee.org/search/searchresult.jsp?newsearch=true&queryText={requests.utils.quote(query)}'
        }]
    
    def _search_mit(self, query, max_results):
        """MIT Libraries Search"""
        try:
            # MIT Libraries genel arama
            return [{
                'title': f'MIT Libraries: {query}',
                'authors': 'MIT Libraries',
                'year': str(datetime.now().year),
                'source': 'MIT',
                'link': f'https://libraries.mit.edu/search/?q={requests.utils.quote(query)}'
            }]
        except Exception:
            return []
    
    def _search_dergipark(self, query, max_results):
        """DergiPark arama"""
        try:
            url = f'https://dergipark.org.tr/tr/search/{requests.utils.quote(query)}'
            headers = {'User-Agent': 'AcademicSearcher/2.0'}
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            results = []
            
            # Basitleştirilmiş arama
            return [{
                'title': f'DergiPark: {query}',
                'authors': 'Türk Akademik',
                'year': datetime.now().year,
                'source': 'DergiPark',
                'link': url
            }]
        except Exception:
            return []
    
    def _search_tubitak(self, query, max_results):
        """TÜBİTAK arama"""
        return [{
            'title': f'TÜBİTAK: {query}',
            'authors': 'ULAKBİM',
            'year': datetime.now().year,
            'source': 'TÜBİTAK',
            'link': f'https://uvt.ulakbim.gov.tr/uvt/index.php?cwid=2&vtadi=TPRJ&query={requests.utils.quote(query)}'
        }]
    
    def _search_metu(self, query, max_results):
        """ODTÜ arama"""
        return [{
            'title': f'ODTÜ: {query}',
            'authors': 'ODTÜ Akademik',
            'year': datetime.now().year,
            'source': 'ODTÜ',
            'link': f'https://dspace.metu.edu.tr/handle/11511?query={requests.utils.quote(query)}'
        }]
    
    def _search_itu(self, query, max_results):
        """İTÜ arama"""
        return [{
            'title': f'İTÜ: {query}',
            'authors': 'İTÜ Akademik',
            'year': datetime.now().year,
            'source': 'İTÜ',
            'link': f'https://acikarsiv.itu.edu.tr/handle?query={requests.utils.quote(query)}'
        }]
    
    def _search_boun(self, query, max_results):
        """Boğaziçi arama"""
        return [{
            'title': f'Boğaziçi: {query}',
            'authors': 'Boğaziçi Üniversitesi',
            'year': datetime.now().year,
            'source': 'Boğaziçi',
            'link': f'https://openaccess.boun.edu.tr/handle?query={requests.utils.quote(query)}'
        }]
    
    def _search_ankara(self, query, max_results):
        """Ankara Üniversitesi arama"""
        try:
            # Ankara Üniversitesi akademik portalı
            return [{
                'title': f'Ankara Üniversitesi Araştırma: {query}',
                'authors': 'Ankara Üniversitesi Akademik',
                'year': str(datetime.now().year),  # String olarak döndür
                'source': 'Ankara Üniv.',
                'link': f'https://acikarsiv.ankara.edu.tr/handle?query={requests.utils.quote(query)}'
            }]
        except Exception:
            return []

    def _search_sciencedirect(self, query, max_results):
        """ScienceDirect (Elsevier) arama"""
        try:
            # ScienceDirect genel arama linki - API key gerektirmeden
            return [{
                'title': f'ScienceDirect: {query}',
                'authors': 'Elsevier',
                'year': str(datetime.now().year),
                'source': 'ScienceDirect', 
                'link': f'https://www.sciencedirect.com/search?qs={requests.utils.quote(query)}'
            }]
        except Exception:
            return []
            
    def _search_springer(self, query, max_results):
        """Springer Link arama"""
        try:
            # Springer Link genel arama
            return [{
                'title': f'Springer: {query}',
                'authors': 'Springer Nature',
                'year': str(datetime.now().year),
                'source': 'Springer',
                'link': f'https://link.springer.com/search?query={requests.utils.quote(query)}'
            }]
        except Exception:
            return []
            
    def _search_yok_tez(self, query, max_results):
        """YÖK Tez Merkezi arama"""
        try:
            # YÖK Tez için genel bilgilendirme linki
            # JavaScript tabanlı arayüz olduğu için direkt arama yapılamıyor
            return [{
                'title': f'YÖK Tez Ara: {query}',
                'authors': 'Yükseköğretim Kurulu',
                'year': str(datetime.now().year),
                'source': 'YÖK Tez',
                'link': 'https://tez.yok.gov.tr/UlusalTezMerkezi/',
                'note': 'Siteye gidip manuel arama yapmanız gerekiyor'
            }]
        except Exception:
            return []
            
    def _search_milli_kutuphane(self, query, max_results):
        """Milli Kütüphane arama"""
        try:
            # Milli Kütüphane katalog tarama
            return [{
                'title': f'Milli Kütüphane: {query}',
                'authors': 'T.C. Kültür Bakanlığı',
                'year': str(datetime.now().year),
                'source': 'Milli Kütüphane',
                'link': f'https://www.mkutup.gov.tr/arama?q={requests.utils.quote(query)}'
            }]
        except Exception:
            return []

class SummaryEngine:
    """Özet çıkarma motoru"""
    
    def __init__(self):
        self.supported_languages = ['english', 'turkish']
    
    def summarize(self, text, algorithm='lsa', sentences_count=5):
        """Metni özetle"""
        try:
            language = 'turkish' if self._is_turkish(text) else 'english'
            
            if algorithm == 'key_sentences':
                return self._extract_key_sentences(text, sentences_count)
            else:
                return self._algorithmic_summary(text, sentences_count, algorithm, language)
        except Exception as e:
            return f"Özetleme hatası: {str(e)}"
    
    def _algorithmic_summary(self, text, sentences_count, algorithm, language):
        """Algoritmik özet"""
        parser = PlaintextParser.from_string(text, Tokenizer(language))
        
        if algorithm == 'lsa':
            summarizer = LsaSummarizer()
        else:  # textrank
            summarizer = TextRankSummarizer()
        
        summary_sentences = summarizer(parser.document, sentences_count)
        return "\n".join([str(sentence) for sentence in summary_sentences])
    
    def _extract_key_sentences(self, text, sentences_count):
        """Anahtar cümleleri çıkar"""
        sentences = nltk.sent_tokenize(text)
        if not sentences:
            return "Özet çıkarılamadı"
        
        selected = []
        if sentences:
            selected.append(sentences[0])  # İlk cümle
        
        if len(sentences) > 1:
            selected.append(sentences[-1])  # Son cümle
        
        # En uzun cümleler
        remaining = sentences_count - len(selected)
        if remaining > 0:
            long_sentences = sorted(sentences[1:-1], key=len, reverse=True)[:remaining]
            selected.extend(long_sentences)
        
        return "\n".join(selected[:sentences_count])
    
    def extract_theses(self, text):
        """Temel tezleri çıkar"""
        sentences = nltk.sent_tokenize(text)
        thesis_indicators = [
            'bu çalışmada', 'amacımız', 'hipotezimiz', 'tezimiz', 'sonuç olarak',
            'bulgularımız', 'kanıtlamaktadır', 'göstermektedir', 'öneriyoruz',
            'this study', 'we propose', 'our hypothesis', 'we demonstrate',
            'results show', 'we conclude', 'contributes to'
        ]
        
        thesis_sentences = []
        for sentence in sentences:
            lower_sentence = sentence.lower()
            if any(indicator in lower_sentence for indicator in thesis_indicators) and len(sentence) > 20:
                thesis_sentences.append(sentence)
        
        if len(thesis_sentences) < 3:
            thesis_sentences = sentences[:5]
        
        return "\n".join([f"• {thesis}" for thesis in thesis_sentences[:7]])
    
    def _is_turkish(self, text):
        """Metnin Türkçe olup olmadığını kontrol et"""
        turkish_chars = set('çğıöşüÇĞİÖŞÜ')
        sample = text[:1000] if len(text) > 1000 else text
        return any(char in turkish_chars for char in sample)


class AcademicSearcherPro:
    """Ana uygulama sınıfı"""
    
    def __init__(self, root):
        self.root = root
        self.db = DatabaseManager()
        self.search_engine = SearchEngine()
        self.summary_engine = SummaryEngine()
        
        # GUI teması
        if THEME_AVAILABLE:
            self.style = tb.Style(theme='flatly')
            self.root = self.style.master
        
        self.root.title("Academic Searcher Pro - Akademik Makalelerin Google'ı")
        self.root.geometry('1400x900')
        
        # Değişkenler
        self.search_history = []
        self.current_results = []
        
        self.setup_gui()
        self.load_notes()
    
    def setup_gui(self):
        """GUI'yi kur"""
        # Ana notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Sekmeleri oluştur
        self.setup_search_tab()
        self.setup_notes_tab()
        self.setup_summary_tab()
    
    def setup_search_tab(self):
        """Arama sekmesi"""
        self.search_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.search_frame, text='🔍 Akademik Arama')
        
        # Arama kontrolleri
        self.setup_search_controls()
        
        # Sonuç tablosu
        self.setup_results_table()
        
        # Durum çubuğu
        self.setup_status_bar()
    
    def setup_search_controls(self):
        """Arama kontrolleri"""
        # Başlık
        title_frame = ttk.Frame(self.search_frame)
        title_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(title_frame, text="🔬 AcademicSearch Engine", 
                 font=('Arial', 14, 'bold')).pack()
        
        # Arama girişi
        search_frame = ttk.Frame(self.search_frame)
        search_frame.pack(fill='x', padx=10, pady=8)
        
        ttk.Label(search_frame, text='Arama:').pack(side='left')
        self.query_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.query_var, width=60)
        search_entry.pack(side='left', fill='x', expand=True, padx=5)
        search_entry.bind('<Return>', lambda e: self.start_search())
        
        ttk.Button(search_frame, text='🔍 Ara', command=self.start_search).pack(side='left')
        
        # Kaynak seçimi
        self.setup_source_selection()
        
        # Filtreler
        self.setup_filters()
    
    def setup_source_selection(self):
        """Kaynak seçimi"""
        sources_frame = ttk.LabelFrame(self.search_frame, text="🌍 Akademik Kaynaklar")
        sources_frame.pack(fill='x', padx=10, pady=8)
        
        # Kaynak değişkenleri
        self.sources = {
            'DOAJ': tk.BooleanVar(value=True),
            'ArXiv': tk.BooleanVar(value=True),
            'Crossref': tk.BooleanVar(value=True),
            'PubMed': tk.BooleanVar(value=False),
            'IEEE': tk.BooleanVar(value=False),
            'MIT': tk.BooleanVar(value=False),
            'DergiPark': tk.BooleanVar(value=False),
            'TÜBİTAK': tk.BooleanVar(value=False),
            'ODTÜ': tk.BooleanVar(value=False),
            'İTÜ': tk.BooleanVar(value=False),
            'Boğaziçi': tk.BooleanVar(value=False),
            'Ankara Üniv.': tk.BooleanVar(value=False),
            # YENİ KAYNAKLAR
            'ScienceDirect': tk.BooleanVar(value=False),
            'Springer': tk.BooleanVar(value=False),
            'YÖK Tez': tk.BooleanVar(value=False),
            'Milli Kütüphane': tk.BooleanVar(value=False)
        }
        
        # Kaynakları 3 sütuna yerleştir
        sources_list = list(self.sources.keys())
        third = len(sources_list) // 3
        
        sources_row = ttk.Frame(sources_frame)
        sources_row.pack(fill='x', pady=5)
        
        left_frame = ttk.Frame(sources_row)
        left_frame.pack(side='left', fill='x', expand=True)
        
        center_frame = ttk.Frame(sources_row)
        center_frame.pack(side='left', fill='x', expand=True)
        
        right_frame = ttk.Frame(sources_row)
        right_frame.pack(side='left', fill='x', expand=True)
        
        for i, source in enumerate(sources_list):
            if i < third:
                frame = left_frame
            elif i < third * 2:
                frame = center_frame
            else:
                frame = right_frame
            ttk.Checkbutton(frame, text=source, variable=self.sources[source]).pack(anchor='w')
        
        # Hızlı seçim butonları
        quick_frame = ttk.Frame(sources_frame)
        quick_frame.pack(fill='x', pady=5)
        
        ttk.Button(quick_frame, text='🎯 Tümünü Seç', command=self.select_all_sources).pack(side='left', padx=2)
        ttk.Button(quick_frame, text='🇹🇷 Sadece TR', command=self.select_tr_sources).pack(side='left', padx=2)
        ttk.Button(quick_frame, text='🌍 Sadece Uluslararası', command=self.select_intl_sources).pack(side='left', padx=2)
        ttk.Button(quick_frame, text='❌ Hiçbiri', command=self.deselect_all_sources).pack(side='left', padx=2)
    
    def setup_filters(self):
        """Filtre kontrolleri"""
        filter_frame = ttk.Frame(self.search_frame)
        filter_frame.pack(fill='x', padx=10, pady=5)
        
        # Yıl filtresi
        ttk.Label(filter_frame, text='Yıl:').pack(side='left')
        self.year_from = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.year_from, width=6).pack(side='left', padx=2)
        ttk.Label(filter_frame, text='-').pack(side='left')
        self.year_to = tk.StringVar(value=str(datetime.now().year))
        ttk.Entry(filter_frame, textvariable=self.year_to, width=6).pack(side='left', padx=2)
        
        # Sıralama
        ttk.Label(filter_frame, text='Sırala:').pack(side='left', padx=(20,5))
        self.sort_by = tk.StringVar(value='year')
        ttk.Combobox(filter_frame, textvariable=self.sort_by, 
                    values=['year', 'title', 'source'], width=10).pack(side='left')
        
        self.sort_order = tk.StringVar(value='desc')
        ttk.Combobox(filter_frame, textvariable=self.sort_order, 
                    values=['desc', 'asc'], width=8).pack(side='left', padx=2)
        
        # Sonuç sayısı
        ttk.Label(filter_frame, text='Sonuç:').pack(side='left', padx=(20,5))
        self.max_results = tk.StringVar(value='50')
        ttk.Combobox(filter_frame, textvariable=self.max_results, 
                    values=['20', '50', '100', '200'], width=8).pack(side='left')
    
    def setup_results_table(self):
        """Sonuç tablosu"""
        table_frame = ttk.Frame(self.search_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Treeview
        columns = ('title', 'authors', 'year', 'source', 'link')
        self.results_tree = ttk.Treeview(table_frame, columns=columns, show='headings')
        
        # Kolonlar
        self.results_tree.heading('title', text='Başlık')
        self.results_tree.heading('authors', text='Yazarlar')
        self.results_tree.heading('year', text='Yıl')
        self.results_tree.heading('source', text='Kaynak')
        self.results_tree.heading('link', text='Link')
        
        self.results_tree.column('title', width=400)
        self.results_tree.column('authors', width=200)
        self.results_tree.column('year', width=80)
        self.results_tree.column('source', width=100)
        self.results_tree.column('link', width=150)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient='vertical', command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)
        
        self.results_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Etkileşim
        self.results_tree.bind('<Double-1>', self.open_selected_link)
        
        # Sağ tık menüsü
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Linki Aç", command=self.open_selected_link)
        self.context_menu.add_command(label="Not Ekle", command=self.add_note_from_selection)
        self.context_menu.add_command(label="Özete Aktar", command=self.send_to_summary)
        self.results_tree.bind('<Button-3>', self.show_context_menu)
    
    def setup_status_bar(self):
        """Durum çubuğu"""
        status_frame = ttk.Frame(self.search_frame)
        status_frame.pack(fill='x', padx=10, pady=2)
        
        self.status_var = tk.StringVar(value="Hazır")
        ttk.Label(status_frame, textvariable=self.status_var).pack(side='left')
        
        self.progress = ttk.Progressbar(status_frame, mode='indeterminate')
        self.progress.pack(side='left', fill='x', expand=True, padx=10)
        
        self.results_count = tk.StringVar(value="0 sonuç")
        ttk.Label(status_frame, textvariable=self.results_count).pack(side='right')
    
    def setup_notes_tab(self):
        """Notlar sekmesi"""
        self.notes_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.notes_frame, text='📝 Notlarım')
        
        # Not arama
        search_frame = ttk.Frame(self.notes_frame)
        search_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(search_frame, text='Not Ara:').pack(side='left')
        self.note_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.note_search_var, width=30)
        search_entry.pack(side='left', padx=5)
        search_entry.bind('<Return>', lambda e: self.search_notes())
        
        ttk.Button(search_frame, text='Ara', command=self.search_notes).pack(side='left', padx=2)
        ttk.Button(search_frame, text='Tümünü Göster', command=self.load_notes).pack(side='left', padx=2)
        ttk.Button(search_frame, text='+ Yeni Not', command=self.create_note).pack(side='left', padx=2)
        
        # Not listesi
        list_frame = ttk.Frame(self.notes_frame)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        columns = ('id', 'title', 'source', 'authors', 'date')
        self.notes_tree = ttk.Treeview(list_frame, columns=columns, show='headings')
        
        self.notes_tree.heading('id', text='ID')
        self.notes_tree.heading('title', text='Başlık')
        self.notes_tree.heading('source', text='Kaynak')
        self.notes_tree.heading('authors', text='Yazarlar')
        self.notes_tree.heading('date', text='Tarih')
        
        self.notes_tree.column('id', width=50)
        self.notes_tree.column('title', width=250)
        self.notes_tree.column('source', width=200)
        self.notes_tree.column('authors', width=150)
        self.notes_tree.column('date', width=120)
        
        self.notes_tree.pack(fill='both', expand=True)
        self.notes_tree.bind('<Double-1>', self.open_note_editor)
        
        # Not işlem butonları
        button_frame = ttk.Frame(self.notes_frame)
        button_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(button_frame, text='📖 Aç', command=self.open_note_editor).pack(side='left', padx=2)
        ttk.Button(button_frame, text='✏️ Düzenle', command=self.open_note_editor).pack(side='left', padx=2)
        ttk.Button(button_frame, text='🗑️ Sil', command=self.delete_note).pack(side='left', padx=2)
        ttk.Button(button_frame, text='📋 Kaynağı Aç', command=self.open_note_source).pack(side='left', padx=2)
        ttk.Button(button_frame, text='📄 Özete Aktar', command=self.send_note_to_summary).pack(side='left', padx=2)
    
    def setup_summary_tab(self):
        """Özet sekmesi"""
        self.summary_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.summary_frame, text='📄 Özet Çıkar')
        
        # Giriş bölümü
        input_frame = ttk.LabelFrame(self.summary_frame, text="📝 Metin Girişi")
        input_frame.pack(fill='x', padx=10, pady=5)
        
        self.summary_input = scrolledtext.ScrolledText(input_frame, height=10)
        self.summary_input.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Kontroller
        control_frame = ttk.Frame(self.summary_frame)
        control_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(control_frame, text='Algoritma:').pack(side='left')
        self.summary_algo = tk.StringVar(value='lsa')
        ttk.Combobox(control_frame, textvariable=self.summary_algo,
                    values=['lsa', 'textrank', 'key_sentences'], width=12).pack(side='left', padx=2)
        
        ttk.Label(control_frame, text='Cümle:').pack(side='left', padx=(10,0))
        self.summary_length = tk.StringVar(value='5')
        ttk.Combobox(control_frame, textvariable=self.summary_length,
                    values=['3', '5', '7', '10'], width=8).pack(side='left', padx=2)
        
        ttk.Button(control_frame, text='🔍 Özet Çıkar', command=self.generate_summary).pack(side='left', padx=5)
        ttk.Button(control_frame, text='🎯 Tezleri Çıkar', command=self.extract_theses).pack(side='left', padx=2)
        ttk.Button(control_frame, text='💾 Kaydet', command=self.save_summary).pack(side='left', padx=2)
        
        # Çıktı bölümü
        output_frame = ttk.LabelFrame(self.summary_frame, text="📄 Özet Çıktısı")
        output_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.summary_output = scrolledtext.ScrolledText(output_frame, height=15)
        self.summary_output.pack(fill='both', expand=True, padx=5, pady=5)
    
    # ARAMA FONKSİYONLARI
    def start_search(self):
        """Arama başlat"""
        query = self.query_var.get().strip()
        if not query:
            messagebox.showwarning("Uyarı", "Lütfen arama terimi girin")
            return
        
        # Geçmişe ekle
        if query not in self.search_history:
            self.search_history.insert(0, query)
            if len(self.search_history) > 10:
                self.search_history.pop()
        
        # Temizle ve başlat
        self.results_tree.delete(*self.results_tree.get_children())
        self.status_var.set("Aranıyor...")
        self.progress.start()
        
        thread = threading.Thread(target=self.perform_search, args=(query,))
        thread.daemon = True
        thread.start()
    
    def perform_search(self, query):
        """Arama yap (thread)"""
        try:
            max_results = int(self.max_results.get())
            selected_sources = [source for source, var in self.sources.items() if var.get()]
            
            if not selected_sources:
                self.root.after(0, self.show_no_sources_warning)
                self.progress.stop()
                return
            
            all_results = []
            results_per_source = max(3, max_results // len(selected_sources))
            
            for source in selected_sources:
                self.root.after(0, lambda s=source: self.status_var.set(f"{s} aranıyor..."))
                results = self.search_engine.search(source, query, results_per_source)
                all_results.extend(results)
                time.sleep(0.2)  # Rate limiting
            
            # Filtrele ve sırala
            filtered = self.filter_results(all_results)
            sorted_results = self.sort_results(filtered)
            self.current_results = sorted_results
            
            # GUI'yi güncelle
            self.root.after(0, self.update_results_display, sorted_results)
            
        except Exception as e:
            self.root.after(0, lambda error=e: self.show_search_error(error))
        finally:
            self.root.after(0, self.progress.stop)
    
    def show_no_sources_warning(self):
        """Kaynak seçilmedi uyarısı"""
        messagebox.showwarning("Uyarı", "Lütfen en az bir kaynak seçin")
    
    def show_search_error(self, error):
        """Arama hatası göster"""
        messagebox.showerror("Hata", f"Arama hatası: {str(error)}")
    
    def filter_results(self, results):
        """Sonuçları filtrele"""
        year_from = self.year_from.get().strip()
        year_to = self.year_to.get().strip()
        
        if not year_from and not year_to:
            return results
        
        filtered = []
        for item in results:
            year = item.get('year', '')
            # Year değerinin string olduğundan ve digit kontrolü yapmadan önce boş olmadığından emin ol
            if year and isinstance(year, str) and year.isdigit():
                year_int = int(year)
                if year_from and year_from.isdigit() and year_int < int(year_from):
                    continue
                if year_to and year_to.isdigit() and year_int > int(year_to):
                    continue
            filtered.append(item)
        
        return filtered

    def sort_results(self, results):
        """Sonuçları sırala"""
        sort_by = self.sort_by.get()
        reverse = self.sort_order.get() == 'desc'
        
        if sort_by == 'year':
            return sorted(results, 
                         key=lambda x: int(x.get('year', 0)) if x.get('year') and str(x.get('year')).isdigit() else 0, 
                         reverse=reverse)
        elif sort_by == 'title':
            return sorted(results, key=lambda x: x.get('title', '').lower(), reverse=reverse)
        elif sort_by == 'source':
            return sorted(results, key=lambda x: x.get('source', ''), reverse=reverse)
        return results
    
    def update_results_display(self, results):
        """Sonuçları göster"""
        for item in results:
            self.results_tree.insert('', 'end', values=(
                item.get('title', ''),
                item.get('authors', ''),
                item.get('year', ''),
                item.get('source', ''),
                item.get('link', '')
            ))
        
        self.results_count.set(f"{len(results)} sonuç")
        self.status_var.set("Arama tamamlandı")
    
    def open_selected_link(self, event=None):
        """Seçili linki aç"""
        selection = self.results_tree.selection()
        if not selection:
            return
        
        item = self.results_tree.item(selection[0])
        link = item['values'][4]
        if link.startswith(('http://', 'https://')):
            webbrowser.open(link)
    
    def show_context_menu(self, event):
        """Sağ tık menüsü göster"""
        item = self.results_tree.identify_row(event.y)
        if item:
            self.results_tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
    
    # NOT FONKSİYONLARI
    def load_notes(self):
        """Notları yükle"""
        notes = self.db.get_all_notes()
        self.display_notes(notes)
    
    def display_notes(self, notes):
        """Notları göster"""
        self.notes_tree.delete(*self.notes_tree.get_children())
        
        for note in notes:
            self.notes_tree.insert('', 'end', values=(
                note['id'],
                note['title'],
                note['source_title'][:50] + '...' if len(note['source_title']) > 50 else note['source_title'],
                note['source_authors'][:30] + '...' if len(note['source_authors']) > 30 else note['source_authors'],
                note['modified_date'][:16]
            ))
    
    def search_notes(self):
        """Notlarda arama"""
        query = self.note_search_var.get().strip()
        if query:
            notes = self.db.search_notes(query)
            self.display_notes(notes)
        else:
            self.load_notes()
    
    def create_note(self):
        """Yeni not oluştur"""
        self.open_note_editor()
    
    def open_note_editor(self, event=None):
        """Not düzenleyiciyi aç"""
        selection = self.notes_tree.selection()
        if not selection:
            # Yeni not
            note_data = {}
        else:
            # Mevcut not
            note_id = self.notes_tree.item(selection[0])['values'][0]
            notes = self.db.get_all_notes()
            note_data = next((n for n in notes if n['id'] == note_id), {})
        
        self.show_note_editor(note_data)
    
    def show_note_editor(self, note_data):
        """Not düzenleyici penceresi"""
        editor = tk.Toplevel(self.root)
        editor.title("Not Düzenleyici" if note_data else "Yeni Not")
        editor.geometry("800x600")
        
        # Form alanları
        form_frame = ttk.Frame(editor)
        form_frame.pack(fill='x', padx=10, pady=10)
        
        fields = [
            ('Not Başlığı:', 'title', ''),
            ('Kaynak Makale:', 'source_title', ''),
            ('Yazarlar:', 'source_authors', ''),
            ('Yıl:', 'source_year', ''),
            ('Sayfa:', 'page_reference', ''),
            ('Etiketler:', 'tags', ''),
            ('URL:', 'source_url', '')
        ]
        
        entries = {}
        for i, (label, field, default) in enumerate(fields):
            ttk.Label(form_frame, text=label).grid(row=i, column=0, sticky='w', pady=2)
            entry = ttk.Entry(form_frame, width=80)
            entry.grid(row=i, column=1, sticky='ew', pady=2)
            entry.insert(0, note_data.get(field, default))
            entries[field] = entry
        
        form_frame.columnconfigure(1, weight=1)
        
        # İçerik
        ttk.Label(editor, text="Not İçeriği:").pack(anchor='w', padx=10, pady=(10,0))
        content_text = scrolledtext.ScrolledText(editor, wrap=tk.WORD, height=15)
        content_text.pack(fill='both', expand=True, padx=10, pady=5)
        content_text.insert('1.0', note_data.get('content', ''))
        
        def save_note():
            data = {field: entries[field].get() for field in entries}
            data['content'] = content_text.get('1.0', tk.END).strip()
            
            if not data['title']:
                messagebox.showwarning("Uyarı", "Lütfen başlık girin")
                return
            
            if note_data:  # Güncelle
                self.db.update_note(note_data['id'], data)
            else:  # Yeni
                self.db.add_note(data)
            
            messagebox.showinfo("Başarılı", "Not kaydedildi!")
            editor.destroy()
            self.load_notes()
        
        def delete_note():
            if note_data and messagebox.askyesno("Onay", "Bu notu silmek istediğinizden emin misiniz?"):
                self.db.delete_note(note_data['id'])
                messagebox.showinfo("Başarılı", "Not silindi!")
                editor.destroy()
                self.load_notes()
        
        # Butonlar
        button_frame = ttk.Frame(editor)
        button_frame.pack(fill='x', padx=10, pady=10)
        
        if note_data:
            ttk.Button(button_frame, text='🗑️ Sil', command=delete_note).pack(side='left')
        
        ttk.Button(button_frame, text='İptal', command=editor.destroy).pack(side='right', padx=5)
        ttk.Button(button_frame, text='💾 Kaydet', command=save_note).pack(side='right')
    
    def delete_note(self):
        """Notu sil"""
        selection = self.notes_tree.selection()
        if not selection:
            messagebox.showwarning("Uyarı", "Lütfen not seçin")
            return
        
        note_id = self.notes_tree.item(selection[0])['values'][0]
        if messagebox.askyesno("Onay", "Bu notu silmek istediğinizden emin misiniz?"):
            self.db.delete_note(note_id)
            self.load_notes()
    
    def open_note_source(self):
        """Not kaynağını aç"""
        selection = self.notes_tree.selection()
        if not selection:
            return
        
        note_id = self.notes_tree.item(selection[0])['values'][0]
        notes = self.db.get_all_notes()
        note = next((n for n in notes if n['id'] == note_id), None)
        
        if note and note['source_url']:
            webbrowser.open(note['source_url'])
    
    def add_note_from_selection(self):
        """Seçili makaleden not ekle"""
        selection = self.results_tree.selection()
        if not selection:
            messagebox.showwarning("Uyarı", "Lütfen makale seçin")
            return
        
        item = self.results_tree.item(selection[0])
        values = item['values']
        
        note_data = {
            'source_title': values[0],
            'source_authors': values[1],
            'source_year': values[2],
            'source_url': values[4]
        }
        
        self.show_note_editor(note_data)
    
    # ÖZET FONKSİYONLARI
    def send_to_summary(self):
        """Seçili makaleyi özete aktar"""
        selection = self.results_tree.selection()
        if not selection:
            messagebox.showwarning("Uyarı", "Lütfen makale seçin")
            return
        
        item = self.results_tree.item(selection[0])
        title = item['values'][0]
        authors = item['values'][1]
        year = item['values'][2]
        
        self.summary_input.delete('1.0', tk.END)
        self.summary_input.insert('1.0', f"Makale: {title}\nYazarlar: {authors}\nYıl: {year}\n\n")
        self.notebook.select(2)  # Özet sekmesine geç
    
    def send_note_to_summary(self):
        """Notu özete aktar"""
        selection = self.notes_tree.selection()
        if not selection:
            messagebox.showwarning("Uyarı", "Lütfen not seçin")
            return
        
        note_id = self.notes_tree.item(selection[0])['values'][0]
        notes = self.db.get_all_notes()
        note = next((n for n in notes if n['id'] == note_id), None)
        
        if note:
            self.summary_input.delete('1.0', tk.END)
            self.summary_input.insert('1.0', note['content'])
            self.notebook.select(2)
    
    def generate_summary(self):
        """Özet oluştur"""
        text = self.summary_input.get('1.0', tk.END).strip()
        if len(text) < 100:
            messagebox.showwarning("Uyarı", "Lütfen daha uzun metin girin")
            return
        
        algorithm = self.summary_algo.get()
        sentences = int(self.summary_length.get())
        
        try:
            summary = self.summary_engine.summarize(text, algorithm, sentences)
            self.display_summary(summary, "ÖZET")
        except Exception as e:
            messagebox.showerror("Hata", f"Özetleme hatası: {str(e)}")
    
    def extract_theses(self):
        """Tezleri çıkar"""
        text = self.summary_input.get('1.0', tk.END).strip()
        if len(text) < 100:
            messagebox.showwarning("Uyarı", "Lütfen daha uzun metin girin")
            return
        
        try:
            theses = self.summary_engine.extract_theses(text)
            self.display_summary(theses, "TEMEL TEZLER")
        except Exception as e:
            messagebox.showerror("Hata", f"Tez çıkarma hatası: {str(e)}")
    
    def display_summary(self, content, title):
        """Özeti göster"""
        self.summary_output.delete('1.0', tk.END)
        self.summary_output.insert('1.0', f"=== {title} ===\n\n{content}")
    
    def save_summary(self):
        """Özeti kaydet"""
        summary = self.summary_output.get('1.0', tk.END).strip()
        if not summary:
            messagebox.showwarning("Uyarı", "Kaydedilecek özet yok")
            return
        
        note_data = {
            'title': f"Özet: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            'content': summary,
            'tags': 'özet,akademik'
        }
        
        self.db.add_note(note_data)
        messagebox.showinfo("Başarılı", "Özet not olarak kaydedildi!")
    
    # KAYNAK SEÇİM FONKSİYONLARI
    def select_all_sources(self):
        """Tüm kaynakları seç"""
        for var in self.sources.values():
            var.set(True)
    
    def select_tr_sources(self):
        """Sadece Türkiye kaynaklarını seç"""
        tr_sources = ['DergiPark', 'TÜBİTAK', 'ODTÜ', 'İTÜ', 'Boğaziçi', 'Ankara Üniv.', 'YÖK Tez', 'Milli Kütüphane']
        for source, var in self.sources.items():
            var.set(source in tr_sources)
    
    def select_intl_sources(self):
        """Sadece uluslararası kaynakları seç"""
        intl_sources = ['DOAJ', 'ArXiv', 'Crossref', 'PubMed', 'IEEE', 'MIT', 'ScienceDirect', 'Springer']
        for source, var in self.sources.items():
            var.set(source in intl_sources)
    
    def deselect_all_sources(self):
        """Tüm kaynakların seçimini kaldır"""
        for var in self.sources.values():
            var.set(False)


def main():
    """Ana fonksiyon"""
    root = tk.Tk()
    app = AcademicSearcherPro(root)
    root.mainloop()

if __name__ == '__main__':
    main()