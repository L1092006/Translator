import configparser
from openai import OpenAI
import argparse
import requests
from ftfy import fix_text
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright






#Load api_key and model from connect.config
connect = configparser.ConfigParser()
connect.read("connect.config")
api_key = connect["info"]["api_key"]
myModel = connect["info"]["model"]












client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key= api_key
)




def getHTMLbytes(url):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        html = page.content()
        browser.close()
        return html


def main():
    #Load command-line arguements
    parser = argparse.ArgumentParser()
    parser.add_argument("novelUrl", help="Enter the url of the novel web")
    parser.add_argument("currChap", help="Enter the current chapter")
    parser.add_argument("numChap", help="Enter the number of chapter you want to translate")
    parser.add_argument("lang", help="Enter the language to translate to")
    args = parser.parse_args()

    #Load command-line arguments into variables
    novelUrl = args.novelUrl
    currChap = int(args.currChap)
    numChap = int(args.numChap)
    lang = args.lang
    i = 0

    while i < numChap:
        #Get the text form novelURL
        html_bytes = getHTMLbytes(novelUrl)
        soup = BeautifulSoup(html_bytes, "html.parser", from_encoding="utf-8")
        text = soup.get_text(separator="\n", strip=True)
        text = fix_text(text)


        #Get all the links from the HTML
        links = ""
        for a in soup.find_all("a", href=True):
            links += a["href"] + "|||"


        print(links)


        #Create the promt to translate text
        prompt = f"""
        You’re given the text extracted from the HTML of a chapter on a web‑novel site. Your job is to:
        **Translate** the *current* chapter’s body text into {lang}.  
            - **Highest priority**: high-quality translation (produce a fluent, natural, error‑free).  
            - After your first pass, **reread and refine** for accuracy, consistency, and style.
            - Omit any irrelevant words only if you're sure that it's not part of the chapter content because the text extracted from HTML may contain the text which isn't in the chapter content
        **Output format** :
        <Translated Chapter Text> (just plain text for reading)
        - **Do not** output anything else (no HTML tag, no commentary, no extra labels, just the content of the chapter).
        Here is the text to process:
        {text}
        """
        # Get the reposnse from AI
        reponse = client.chat.completions.create(
            model=myModel,
            messages=[
                {
                "role": "user",
                "content": prompt
                }
            ]
        )
       
        #Load the url of the next chapterand the translation
        currChapTrans = reponse.choices[0].message.content

        prompt = f"""
        You’re given all URLs extracted from the HTML of a chapter on a web‑novel site and the URL of the website. Your job is to:
        Return to me the whole URL to the next chapter which I can use to paste directly in the browser.  
            - All the links given may not be their full versions except for the URL of the website of the current chapter. If that's the case, combine the former and the later to give me the whole URL to the next chapter.
        **Output format** :
        The whole URL to the next chapter (Only one URL)
        - **Do not** output anything else.
        Here are the URLs to process, each URL is seperated from the other by symbol `|||`:
        {links}
        Here is the URL of the website of the current chapter:
        {novelUrl}
        """


        # Get the reposnse from AI
        reponse = client.chat.completions.create(
            model=myModel,
            messages=[
                {
                "role": "user",
                "content": prompt
                }
            ]
        )
       
        #Load the url of the next chapterand the translation
        novelUrl = reponse.choices[0].message.content


        #save it into a file
        with open(f"novels/chapter{currChap}.txt", "w", encoding="utf-8") as file:
            file.write(currChapTrans)
        i += 1
        currChap += 1
        print(currChapTrans)








if __name__ == '__main__':
    main()















