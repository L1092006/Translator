import configparser
from openai import OpenAI
import argparse
from ftfy import fix_text
from bs4 import BeautifulSoup
from playwright.sync_api import Error
import test as wh






#Load api_key and model from connect.config
connect = configparser.ConfigParser()
connect.read("connect.config")
api_key = connect["info"]["api_key"]
myModel = connect["info"]["model"]


#Connect to AI
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key= api_key
)


#Load command-line arguements
parser = argparse.ArgumentParser()
parser.add_argument("novelUrl", help="Enter the url of the novel web")
parser.add_argument("currChap", help="Enter the current chapter")
parser.add_argument("toChap", help="Enter the chapter you want to translate to")
parser.add_argument("lang", help="Enter the language to translate to")
args = parser.parse_args()


#Load command-line arguments into global variables
novelUrl = args.novelUrl
currChap = int(args.currChap)
toChap = int(args.toChap)
lang = args.lang




def main():
    
    allAtOnce()


#Return the soup
def getSoup(url, page):
    page.goto(url, wait_until="networkidle")
    return BeautifulSoup(page.content(), "html.parser")


#Get all chapter link at once
def allAtOnce():
    global currChap
    currUrl= novelUrl

    #Launch chrome and login if needed
    wh.launch_chrome()
    input("Please login if needed, then navigate to the current chapter, press Enter when you're done")

    #Contain all chapter soups
    soups = []

    #User input

    #Get the soups for all chapters
    while True:
        #Get new webs component and the page to operate on
        webs, page = wh.getWeb()
        soups.append(BeautifulSoup(page.content(), "html.parser"))

        #Wait for user to go to next chapter, break if the close the page which will raise an error
        try:
            page.wait_for_event("framenavigated")
        except Error as e:
            print(e)
            break 
       
        #Close webs component
        wh.close_all(webs)


    i = 0
    #Translate the chapters
    while currChap <= toChap:
        print(f"Processing chap {currChap}")
        #Get the soup
        soup = soups[i]
        text = soup.get_text(separator="\n", strip=True)
        text = fix_text(text)
       
        #Translate the text
        currChapTrans = translate(text)


        #save it into a file
        with open(f"novels/chapter{currChap}.txt", "w", encoding="utf-8") as file:
            file.write(currChapTrans)


        print(f"Finished chap {currChap}")
        currChap += 1
        i += 1


#Navigate from chapter to chapter
def chapToChap(page):
    global currChap
    currUrl = novelUrl
    while currChap <= toChap:
        print(f"Processing chap {currChap}")
        #Get the soup from currUrl
        soup = getSoup(currUrl, page)
        text = soup.get_text(separator="\n", strip=True)
        text = fix_text(text)




        #Get all the links from the HTML
        links = ""
        for a in soup.find_all("a", href=True):
            links += a["href"] + "|||"




        #Translate the text
        currChapTrans = translate(text)


        #save it into a file
        with open(f"novels/chapter{currChap}.txt", "w", encoding="utf-8") as file:
            file.write(currChapTrans)


        print(f"Finished chap {currChap}")


       
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
        {currUrl}
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
        currUrl = reponse.choices[0].message.content
        currChap += 1






       








def translate(text):
    #Create the promt to translate text
    prompt = f"""
    You’re given the text extracted from the HTML of a chapter on a web‑novel site. Your job is to:
    **Translate** the *current* chapter’s body text into {lang}.  
        - **Highest priority**: high-quality translation (produce a fluent, natural, error‑free).  
        - After your first pass, **reread and refine** for accuracy, consistency, and style. ENSURE THE TRANSLATION QUALITY IS HIGH AND PROFESSIONAL
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
    return reponse.choices[0].message.content


if __name__ == '__main__':
    main()

































