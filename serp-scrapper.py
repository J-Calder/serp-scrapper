import requests
from bs4 import BeautifulSoup
import nltk
from nltk.probability import FreqDist
from nltk.corpus import stopwords
nltk.download('punkt')
nltk.download('stopwords')

# Define a function to scrape search results
def scrape_search_results(query, num_results=50):
    titles = []
    subheaders = []

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

    return titles, subheaders

def extract_keywords(texts):
    words = []
    for text in texts:
        tokens = nltk.word_tokenize(text)
        words.extend(tokens)

    words = [word.lower() for word in words if word.isalpha() and word.lower() not in stopwords.words('english')]

    fdist = FreqDist(words)

    return fdist

query = 'cbd france'
titles, subheaders = scrape_search_results(query, num_results=100)

texts = titles + [subheader for subheader in subheaders if subheader]

print("Search Results for: ", query)
print("-" * 50)

print("\nTitles:")
for i, title in enumerate(titles, start=1):
    print(f"{i}. {title}")

print("\nSubheaders:")
for i, subheader in enumerate(subheaders, start=1):
    if subheader:
        print(f"{i}. {subheader}")

print("\nTop 20 Keywords:")
for i, (keyword, count) in enumerate(extract_keywords(texts).most_common(20), start=1):
    print(f"{i}. {keyword} ({count} occurrences)")
