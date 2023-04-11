import os
import asyncio
import aiohttp
import json
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pymongo import MongoClient
import pandas as pd
import openai
import sys

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()
os.environ["OPENAI_API_KEY"] = "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"

client = MongoClient('mongodb://localhost:27017/')
db = client['scraped_data']
db = client['chatgpt_data']
scraped_data_collection = db['scraped_data']
chatgpt_data_collection = db['chatgpt_data']

async def analyze_text_with_chatgpt(session, text):
    print("Analyzing text with ChatGPT...")
    prompt = f"Extract keywords from the following paragraph:\n\n{text}\n\nKeywords:"

    try:
        async with session.post(
            "https://api.openai.com/v1/engines/text-davinci-003/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            },
            json={
                "prompt": prompt,
                "max_tokens": 100,
                "n": 1,
                "stop": None,
                "temperature": 0.7,
            },
        ) as response:
            response_data = await response.json()
            if 'choices' not in response_data:
                print(f"Unexpected API response: {response_data}")
                return []
            keywords = response_data["choices"][0]["text"].strip()
            return keywords.split(", ")

    except Exception as e:
        print(f"Error analyzing text: {e}")
        return []

async def fetch(session, url, headers):
    async with session.get(url, headers=headers, ssl=False) as response:
        return await response.text()

async def scrape_search_results(query, num_results):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }

    data = []

    async with aiohttp.ClientSession() as session:
        for start in range(0, num_results, 10):
            url = f'https://www.google.com/search?q={query}&start={start}'

            try:
                response_text = await fetch(session, url, headers)
            except Exception as e:
                print(f"Error while making request: {e}")
                continue

            soup = BeautifulSoup(response_text, 'html.parser')
            search_results = soup.select('.tF2Cxc')

            for result in search_results:
                title = result.select_one('.LC20lb.DKV0Md').get_text(strip=True)

                subheader = result.select_one('.VwiC3b.yXK7lf.MUxGbd.yDYNvb.lyLwlc')
                
                if subheader:
                    subheader = subheader.get_text(strip=True)    

                page_url = result.select_one('a')['href']
                print(f"Scraping URL: {page_url}")

                try:
                    page_response_text = await fetch(session, page_url, headers)
                    page_soup = BeautifulSoup(page_response_text, 'html.parser')

                    
                    h1_tags = [tag.get_text(strip=True) for tag in page_soup.find_all('h1')]
                    h2_tags = [tag.get_text(strip=True) for tag in page_soup.find_all('h2')]
                    h3_tags = [tag.get_text(strip=True) for tag in page_soup.find_all('h3')]
                    headings = h1_tags + h2_tags + h3_tags

                    paragraphs = page_soup.find_all('p')

                    # Process paragraphs
                    paragraph_keywords = []
                    for paragraph in paragraphs[:num_paragraphs]:
                        paragraph_text = paragraph.get_text(strip=True)
                        if len(paragraph_text) < 50:
                            continue

                        keywords = await analyze_text_with_chatgpt(session, paragraph_text)
                        paragraph_keywords.extend(keywords)

                except Exception as e:
                    print(f"Error while processing result: {e}")
                    continue

                scraped_data = {
                    "url": page_url,
                    "metadata": {
                        "title": title,
                        "subheader": subheader,
                    },
                    "content": {
                        "headings": headings,
                    },
                }

                chatgpt_data = {
                    "url": page_url,
                    "analysis": {
                        "keywords": paragraph_keywords,
                    },
                }

                data.append(scraped_data)
                scraped_data_collection.insert_one(scraped_data)
                chatgpt_data_collection.insert_one({"url": page_url, "keywords": paragraph_keywords})

    return data

if __name__ == "__main__":
    query = "cbd"
    num_results = 1
    num_paragraphs = 3

    asyncio.run(scrape_search_results(query, num_results))

    scraped_data_cursor = scraped_data_collection.find()
    scraped_data_df = pd.DataFrame(list(scraped_data_cursor))

    print(scraped_data_df.columns)
    # Multi-level columns for scraped_data_df
    scraped_data_df = scraped_data_df.drop(columns=['_id'])
    scraped_data_df.columns = pd.MultiIndex.from_tuples(
        [("metadata", "title"), ("metadata", "subheader"), ("url", ""), ("content", "headings"), ("metadata_unused", ""), ("content_unused", "")]
    )

    chatgpt_data_cursor = chatgpt_data_collection.find()
    chatgpt_data_df = pd.DataFrame(list(chatgpt_data_cursor))

    # Adding the requested code
    scraped_data_cursor = scraped_data_collection.find({}, {"_id": 0})
    scraped_data_df = pd.DataFrame(list(scraped_data_cursor))
    scraped_data_df.to_csv("scraped_data.csv", index=False)

    chatgpt_data_cursor = chatgpt_data_collection.find()
    chatgpt_data_df = pd.DataFrame(list(chatgpt_data_cursor))
    
	# Adding the code to export chatgpt_data to a CSV file
    chatgpt_data_cursor = chatgpt_data_collection.find({}, {"_id": 0})
    chatgpt_data_df = pd.DataFrame(list(chatgpt_data_cursor))
    chatgpt_data_df.to_csv("chatgpt_data.csv", index=False)
