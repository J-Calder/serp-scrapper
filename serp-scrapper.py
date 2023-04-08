import requests
import csv
from bs4 import BeautifulSoup
import nltk
from nltk.collocations import BigramAssocMeasures, BigramCollocationFinder
from nltk.corpus import stopwords
from collections import defaultdict
from langdetect import detect
from pymongo import MongoClient

nltk.download('punkt')
nltk.download('stopwords')

client = MongoClient('mongodb://localhost:27017/')
db = client['scraped_data']
scraped_data_collection = db['scraped_data']
new_data_collection = db['new_data']

def detect_language(text):
    try:
        return detect(text)
    except:
        return 'unknown'

def scrape_search_results(query, num_results=10):
    titles = []
    subheaders = []
    headings = []

    for start in range(0, num_results, 10):
        url = f'https://www.google.com/search?q={query}&start={start}'
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        }
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')

        search_results = soup.select('.tF2Cxc')

        for result in search_results:
            title = result.select_one('.LC20lb.DKV0Md').get_text(strip=True)
            titles.append(title)

            subheader = result.select_one('.VwiC3b.yXK7lf.MUxGbd.yDYNvb.lyLwlc')
            if subheader:
                subheaders.append(subheader.get_text(strip=True))
            else:
                subheaders.append(None)

            page_url = result.select_one('a')['href']
            try:
                page_response = requests.get(page_url, headers=headers)
                page_soup = BeautifulSoup(page_response.text, 'html.parser')
                h1_tags = [tag.get_text(strip=True) for tag in page_soup.find_all('h1')]
                h2_tags = [tag.get_text(strip=True) for tag in page_soup.find_all('h2')]
                h3_tags = [tag.get_text(strip=True) for tag in page_soup.find_all('h3')]
                keywords_meta = page_soup.find('meta', attrs={'name': 'keywords'})
                if keywords_meta:
                    page_keywords = keywords_meta['content'].split(', ')
                else:
                    page_keywords = []
                headings.append({'url': page_url, 'h1': h1_tags, 'h2': h2_tags, 'h3': h3_tags, 'keywords': page_keywords})
            except:
                headings.append({'url': page_url, 'error': 'Unable to scrape'})

    return titles, subheaders, headings

def generate_new_titles_subheaders(titles, subheaders, headings):
    new_titles = []
    new_subheaders = []
    new_headings = []

    all_texts = titles + subheaders
    words = [word.lower() for word in nltk.word_tokenize(' '.join(all_texts)) if word.isalpha()]
    bigram_finder = BigramCollocationFinder.from_words(words)
    bigram_measures = BigramAssocMeasures()

    bigrams = bigram_finder.nbest(bigram_measures.raw_freq, 100)

    for bigram in bigrams:
        new_title = ' '.join(bigram).title()
        new_titles.append(new_title)

        new_subheader = f'Learn about {new_title} and its benefits'
        new_subheaders.append(new_subheader)

        new_h1 = f'{new_title} Overview'
        new_h2 = f'What is {new_title}?'
        new_h3 = f'{new_title} Benefits'
        new_keywords = f'{new_title}, benefits, overview'

        new_headings.append({'h1': [new_h1], 'h2': [new_h2], 'h3': [new_h3], 'keywords': new_keywords.split(', ')})

    return new_titles, new_subheaders, new_headings

def store_in_mongodb(collection, titles, subheaders, headings=None):
    for i in range(len(titles)):
        row = {
            'title': titles[i],
            'subheader': subheaders[i]
        }
        if headings:
            row.update({
                'url': headings[i].get('url', ''),
                'h1': ', '.join(headings[i].get('h1', [])),
                'h2': ', '.join(headings[i].get('h2', [])),
                'h3': ', '.join(headings[i].get('h3', [])),
                'keywords': ', '.join(headings[i].get('keywords', []))
            })
        else:
            row.update({
                'url': '',
                'h1': '',
                'h2': '',
                'h3': '',
                'keywords': ''
            })
        collection.insert_one(row)

query = 'cbd france'
titles, subheaders, headings = scrape_search_results(query, num_results=100)

store_in_mongodb(scraped_data_collection, titles, subheaders, headings)

new_titles, new_subheaders, new_headings = generate_new_titles_subheaders(titles, subheaders, headings)

store_in_mongodb(new_data_collection, new_titles, new_subheaders, new_headings)

def export_to_csv(filename, titles, subheaders, headings=None):
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['title', 'subheader', 'url', 'h1', 'h2', 'h3', 'keywords']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for i in range(len(titles)):
            row = {
                'title': titles[i],
                'subheader': subheaders[i]
            }
            if headings:
                row.update({
                    'url': headings[i].get('url', ''),
                    'h1': ', '.join(headings[i].get('h1', [])),
                    'h2': ', '.join(headings[i].get('h2', [])),
                    'h3': ', '.join(headings[i].get('h3', [])),
                    'keywords': ', '.join(headings[i].get('keywords', []))
                })
            else:
                row.update({
                    'url': '',
                    'h1': '',
                    'h2': '',
                    'h3': '',
                    'keywords': ''
                })
            writer.writerow(row)

# Store scraped data to a CSV file
export_to_csv('scraped_data.csv', titles, subheaders, headings)

# Store generated titles, subheaders, and headings to a separate CSV file
export_to_csv('new_titles_and_subheaders.csv', new_titles, new_subheaders, new_headings)
