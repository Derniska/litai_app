import os
import requests
from bs4 import BeautifulSoup
import json
import time
import random
from urllib import request
from urllib import parse
import xml.etree.ElementTree as et
from tqdm import tqdm
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ArXiv parser
def load_arxiv_articles(max_results, keywords):
    row_data = []
    temp = 'economics'
    
    keywords_with_field = [f'all:"{kw}"' for kw in keywords]
    string = '(' + ' OR '.join(keywords_with_field) + ')'
    query = f'all:{temp} AND {string}'
    
    params = {
        'search_query': query,
        'start': 0,
        'max_results': max_results
    }
    query_string = parse.urlencode(params)
    
    url =  f'http://export.arxiv.org/api/query?{query_string}'
    with request.urlopen(url) as response:
        raw_data = response.read().decode('utf-8')
    return raw_data

def parse_arxiv_articles(raw_data):
    articles = []
    root = et.fromstring(raw_data)
    namespace = '{http://www.w3.org/2005/Atom}'
    for entree in root.findall(f'{namespace}entry'):
        title = entree.find(f'{namespace}title').text
        summary = entree.find(f'{namespace}summary').text
        published = entree.find(f'{namespace}published').text

        arxiv_id = ''
        id_elem = entree.find(f'{namespace}id')
        if id_elem is not None and id_elem.text:
            arxiv_id = id_elem.text
        
        pdf_url = arxiv_id.replace('abs', 'pdf') + '.pdf'
    
        authors = []
        for author_elem in entree.findall(f'{namespace}author'):
            name_elem = author_elem.find(f'{namespace}name')
            if name_elem is not None and name_elem.text:
                authors.append(name_elem.text.strip())
        categories = []
        for category_elem in entree.findall(f'{namespace}category'):
            term = category_elem.get('term')
            if term:
                categories.append(term)
        
        article = {
        'url' : arxiv_id,
        'title' : title,
        'full_abstract' : summary,
        'publication_date' : published,
        'authors' : authors,
        'categories' : categories,
        'pdf_url' : pdf_url,
        'source' : 'arXiv'
        }
        articles.append(article)
    return articles

# NBER parser
def nber_full_summary(nber_url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }
    resp = requests.get(nber_url, headers = headers)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content)
    summary = soup.find('div', class_ = 'page-header__intro-inner').find('p').text
    summary = summary.replace('\n', '')
    return summary

def load_nber_articles(keywords, max_articles, load_full_abstract = False):
    url = 'https://www.nber.org/api/v1/search'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    all_articles = []
    
    words = []
    for k in keywords:
        words.extend(k.split())
    query = '+'.join(words)
    
    page = 1
    while len(all_articles) < max_articles:
        params = {
        'q': query,
        'page': page,
        'perPage': 100,
        'sort': 'relevance'
        }
    
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        results = data.get('results', [])
        total_results = int(data.get('totalResults'))
        if page == 1:
                total_results = data.get('totalResults', 0)
                print(f"Всего найдено статей: {total_results}")
        if not results:
            print(f'All available articles on {keywords} are parsed')
            break
    
        for res in tqdm(results, desc = f"Page: {page}"):
            if len(all_articles) >= max_articles:
                        break
            if res.get('type') == 'working_paper':
                try:
                    authors = []
                    authors_html = res.get('authors')
                    for aut in authors_html:
                        soup = BeautifulSoup(aut)
                        author = soup.find('a').text
                        authors.append(author)
                    nid = res.get('url', '').split('/')[-1]
                    article = {
                        'title': res.get('title', ''),
                        'authors': authors,
                        'type': res.get('type', ''),
                        'id': nid,
                        'abstract': res.get('abstract', ''),
                        'publication_date': res.get('displaydate', ''),
                        'url': f"https://www.nber.org{res.get('url', '')}",
                        'pdf_url' : f"https://www.nber.org/system/files/working_papers/{nid}/{nid}.pdf",
                        'source' : 'nber'
                     }
                    if load_full_abstract:
                        abstract = nber_full_summary(article['url'])
                        article['full_abstract'] = abstract
                        time.sleep(random.uniform(1,3))
                    all_articles.append(article)
            
                        
                except Exception as e:
                    pass
    
        
        progress = len(all_articles) / min(total_results, max_articles) * 100
        print(f'{round(len(all_articles)/  min(total_results, max_articles) *100,2 )}% are loaded')
    
        page += 1
        time.sleep(random.uniform(0.2, 0.5))
    return all_articles

# SSRN parser
def create_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=3,  
        backoff_factor=2,  
        status_forcelist=[429, 500, 502, 503, 504, 400],  
        allowed_methods=["GET"]  
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session
def ssrn_article_abstract(article_id, session=None):
    
    if session is None:
        session = create_session()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    time.sleep(random.uniform(2,6))
    try:
        resp = session.get(
            f'https://papers.ssrn.com/sol3/papers.cfm?abstract_id={article_id}',
            headers=headers,
            timeout=30
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content)
        abstract = soup.find('div', class_ = 'abstract-text').find('p').text
        
        keywords = []
        for k in soup.find_all('p'):
            if 'keywords' in k.text.lower():
                kw_text = k.text
                if 'Keywords:' in kw_text:
                    kw_text = kw_text.split('Keywords:', 1)[1]
                keywords = [kw.strip() for kw in kw_text.split(',')]
                break
        metadata = {
            'full_abstract' : abstract,
            'keywords' : keywords        
        }
        return metadata
    
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            print(f"Ошибка 429 для статьи {article_id}. Ждем 30 секунд...")
            time.sleep(30)
            return None
        raise e

def load_ssrn_articles(keywords, max_articles, load_full_abstract = False):
    url = "https://api.ssrn.com/papers/v1/papers/search/advanced"
    all_articles = []

    words = []
    for k in keywords:
        words.extend(k.split())
    query = '+'.join(words)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://www.ssrn.com/',
        'Origin': 'https://www.ssrn.com',
    }
    page = 1
    while len(all_articles) < max_articles: 
        params = {
        'text': query,
        'text_fields': 'title-abstract-keywords',
        'search_mode': 'fuzzy',
        'sort_by': '',
        'page': page,
        'authors': '',
        'date': 'all_time'
        }
        response = requests.get(url, params=params, headers=headers)
        time.sleep(1)
        response.raise_for_status()
        data = response.json()
        results = data['papers']
        if not results:
            print("Больше нет результатов (пустая страница)")
            break
        
        for res in tqdm(results):
            if len(all_articles) >= max_articles:
                break
            snippets_list = res.get('snippets', [])  
            snippets = ' '.join(snippets_list) if snippets_list else ''
            authors = res.get('authors')
            clean_authors = []
            for a in authors:
                clean_authors.append(a['full_name'])
            article = {
                'title' : res.get('title', '').replace('<em>', '').replace('</em>', ''),
                'id' : res.get('id'),
                'authors' : clean_authors,
                'abstract' : snippets.replace('<em>', '').replace('</em>', ''),
                'publication_date' : res.get('approved_date', ''),
                'soucre' : 'ssrn'
            }
            if load_full_abstract:
                meta_data = ssrn_article_abstract(article['id'])
                article['full_abstract'] = meta_data['full_abstract']
                article['keywords'] = meta_data['keywords']
            
            all_articles.append(article)
        
        print(f'Pages loaded {page}')
        print(f'Articles loaded {len(all_articles)}')
        page += 1
        time.sleep(1)
        
    return all_articles

# All articles
def parse_all_articles(keywords, max_articles, saving_path, load_full_abstract = False, save = False):

    nber_articles = int(max_articles * 0.5)
    nber_papers = load_nber_articles(keywords, max_articles = nber_articles, 
                                     load_full_abstract = load_full_abstract)
    print('==' * 40)
    print(f'{len(nber_papers)} NBER articles are parsed')

    arxiv_articles = int(max_articles * 0.1)
    arxiv_papers = parse_arxiv_articles(load_arxiv_articles(max_results = arxiv_articles, keywords = keywords))
    print('\n', '==' * 20)
    print(f'{len(arxiv_papers)} arXiv articles are parsed')

    ssrn_articles = int(max_articles * 0.4)
    ssrn_papers = load_ssrn_articles(keywords, ssrn_articles, load_full_abstract = load_full_abstract)
    print('\n', '==' * 20)
    print(f'{len(ssrn_papers)} SSRN articles are parsed')
    
    all_articles = []
    all_articles.extend(nber_papers)
    all_articles.extend(arxiv_papers) 
    all_articles.extend(ssrn_papers)
    download_path = os.path.join(saving_path,'articles.json')
    if save:
        with open(download_path, 'w', encoding='utf-8') as file:
            json.dump(all_articles, file, indent=2)
        
    return all_articles