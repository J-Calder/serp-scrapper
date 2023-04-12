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
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import StaleElementReferenceException

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
            keywords = response_data['choices'][0]['text'].strip()
            return keywords.split(", ")

    except Exception as e:
        print(f"Error analyzing text: {e}")
        return []

async def scrape_search_results(session, query, num_results):
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run Chrome in headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Initialize the WebDriver
    driver = webdriver.Chrome(options=chrome_options)

    data = []

    for start in range(0, num_results, 10):
        url = f'https://www.google.com/search?q={query}&start={start}'

        try:
            driver.get(url)

            # Wait for the search results to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.tF2Cxc'))
            )

            search_results = driver.find_elements(By.CSS_SELECTOR, '.tF2Cxc')

            for result in search_results:
              title = result.find_element(By.CSS_SELECTOR, 'h3').text
            try:
                    subheader_element = result.find_element(By.CSS_SELECTOR, '.VwiC3b.yXK7lf.MUxGbd.yDYNvb.lyLwlc')
                    subheader = subheader_element.text
            except NoSuchElementException:
                    subheader = None
                    page_url = result.find_element(By.CSS_SELECTOR, 'a').get_attribute('href')
                    print(f"Scraping URL: {page_url}")
                    # Scrape the content of the page
                    driver.get(page_url)

                    h1_tags = [tag.text for tag in driver.find_elements(By.TAG_NAME, 'h1')]
                    h2_tags = [tag.text for tag in driver.find_elements(By.TAG_NAME, 'h2')]
                    h3_tags = [tag.text for tag in driver.find_elements(By.TAG_NAME, 'h3')]
                    headings = h1_tags + h2_tags + h3_tags

                    paragraph_keywords = []

                    for heading_tag in ['h1', 'h2', 'h3']:
                       heading_elements = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.XPATH, f"//{heading_tag}")))

                    for heading_element in heading_elements:
                        if heading_element:
                            heading_text = heading_element.text
                            try:
                                paragraph = heading_element.find_element(By.XPATH, './following-sibling::p')
                            except NoSuchElementException:
                                paragraph = None

                            if paragraph:
                                paragraph_text = paragraph.text
                                if len(paragraph_text) >= 50:
                                    keywords = await analyze_text_with_chatgpt(session, paragraph_text)
                                    paragraph_keywords.extend(keywords)

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

        except Exception as e:
            print(f"Error while processing result: {e}")
            continue

    driver.quit()  # Close the browser and quit the WebDriver

    return data

async def main():
    query = "cbd"
    num_results = 1

    async with aiohttp.ClientSession() as session:
        data = await scrape_search_results(session, query, num_results)

    scraped_data_cursor = scraped_data_collection.find({}, {"_id": 0})
    scraped_data_df = pd.DataFrame(list(scraped_data_cursor))
    scraped_data_df.to_csv("scraped_data.csv", index=False)

    chatgpt_data_cursor = chatgpt_data_collection.find({}, {"_id": 0})
    chatgpt_data_df = pd.DataFrame(list(chatgpt_data_cursor))
    chatgpt_data_df.to_csv("chatgpt_data.csv", index=False)

# Run the main function
if __name__ == "__main__":
    asyncio.run(main())

