import configparser
from openai import OpenAI
import argparse
import requests
from ftfy import fix_text
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
import re



#Load api_key and model from connect.config
connect = configparser.ConfigParser()
connect.read("connect.config")
api_key = connect["info"]["api_key"]
myModel = connect["info"]["model"]






client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key= api_key
)


def find_next_chapter_url(html, current_url):
    """
    Universal next-chapter finder:
      1) Decode bytes if needed
      2) Try to extract `chapterList` from any <script type="application/json"> block
      3) Fallback to <a> text lookup (for static sites like Genesis Studio)
    Raises RuntimeError if no next chapter is found.
    """
    # 1) Decode bytes to str
    if isinstance(html, bytes):
        try:
            html = html.decode('utf-8')
        except UnicodeDecodeError:
            html = html.decode('latin-1')

    soup = BeautifulSoup(html, "html.parser")

    # 2) Search all <script type="application/json"> for chapterList
    for script in soup.find_all("script", {"type": "application/json"}):
        text = script.string
        if not text:
            continue
        try:
            data = json.loads(text)
        except ValueError:
            continue

        # If dict with chapterList
        if isinstance(data, dict) and "chapterList" in data:
            chap_list = data["chapterList"]
        # If list, each entry might have data.chapterList
        elif isinstance(data, list):
            chap_list = None
            for entry in data:
                if isinstance(entry, dict) and "chapterList" in entry:
                    chap_list = entry["chapterList"]
                    break
        else:
            chap_list = None

        if isinstance(chap_list, list):
            ids = [str(ch.get("id")) for ch in chap_list]
            cur = current_url.rstrip("/").split("/")[-1]
            if cur in ids:
                idx = ids.index(cur)
                if idx + 1 < len(ids):
                    next_id = ids[idx + 1]
                    return urljoin(current_url, "/chapters/" + next_id)
                else:
                    raise RuntimeError("Already on the last chapter")

    # 3) Fallback: scan for an <a> whose visible text is “Next” or variants
    next_texts = {'next', 'next chapter', '›', '>', '→'}
    for a in soup.find_all('a', href=True):
        if a.get_text(strip=True).lower() in next_texts:
            return urljoin(current_url, a['href'])

    raise RuntimeError("Next chapter link not found")


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
        resURL = requests.get(novelUrl)
        html_bytes = resURL.content
        soup = BeautifulSoup(html_bytes, "html.parser", from_encoding="utf-8")
        text = soup.get_text(separator="\n", strip=True)
        text = fix_text(text)

        #Get the link to the next chapter
        novelUrl = find_next_chapter_url(html_bytes, novelUrl)
        print(novelUrl)

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

        

        #save it into a file
        with open(f"novels/chapter{currChap}.txt", "w", encoding="utf-8") as file:
            file.write(currChapTrans)
        i += 1
        currChap += 1




    print(currChapTrans)




if __name__ == '__main__':
    main()





