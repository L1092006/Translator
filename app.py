import configparser
from openai import OpenAI, RateLimitError
import argparse
from ftfy import fix_text
from bs4 import BeautifulSoup
from playwright.sync_api import Error
import test as wh
from pathlib import Path
import sys
import time
import tiktoken





#Get the path to Info
info = Path(__file__).resolve().parent / "Info"

#Load api_key and model from connect.config
connect = configparser.ConfigParser()
connect.read(str(info / "connect.config"))
myModel = connect["info"]["model"]

#Get the path to keys
keysFile = info / "keys.txt"
with keysFile.open( "r", encoding="utf-8") as k:
    keys = [line.strip() for line in k]
    api_key = keys[int(connect["info"]["api_key"])]
    
#Context limit from the model
context = int(connect["info"]["context"])
limit = int(context / 4)
enc = tiktoken.get_encoding("cl100k_base")





#Connect to AI
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key= api_key
)




#Load command-line arguements
parser = argparse.ArgumentParser()
parser.add_argument("name", help="Enter the name of the novel")
parser.add_argument("currChap", help="Enter the current chapter")
parser.add_argument("lang", help="Enter the language to translate to")
args = parser.parse_args()

#Load command-line arguments into global variables
name = args.name
currChap = int(args.currChap)
lang = args.lang



#Create novels/novelName directory if needed
novel = info.parent / "novels" / name
novel.mkdir(parents=True, exist_ok=True)

#Create novelSpecific.txt if needed
try:
    with (novel / "novelSpecific.txt").open("x", encoding="utf-8") as ns:
        with (info / "template.txt").open("r", encoding="utf-8") as file:
            template = ""
            for line in file:
                template += line
        ns.write(template)
except FileExistsError:
    pass



def main():
   
    allAtOnce()




#Return the soup
def getSoup(url, page):
    page.goto(url, wait_until="networkidle")
    return BeautifulSoup(page.content(), "html.parser")




#Get all chapter link at once
def allAtOnce():
    global currChap


    #Launch chrome and login if needed
    wh.launch_chrome()
    input("Please login if needed, then navigate to the current chapter, press Enter when you're done")


    #Contain all chapter soups
    soups = []




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
        finally:
            #Close webs component
            wh.close_all(webs)
            time.sleep(3)

    # All texts spliting from the combined text to ensure token limit
    oriTexts = []
    originalText = ""
    oriChap = currChap
    #For safety, just use 1/4 of the context
    


    #Collect all the chapters text
    for i in range(len(soups)):
        #Get the soup
        soup = soups[i]
        text = soup.get_text(separator="\n", strip=True)
        text = fix_text(text)


        #Add current chapter to originalText
        originalText += f"\nChap{currChap}\n{text}"

        #Only append NEXTCHAPTER if it's not the end of the input
        if i != len(soups) - 1:
            originalText += "\n" + "NEXTCHAPTER"

        #Check if the limit is exceeded
        l = len(enc.encode(originalText))
        if l > limit:
            #Append up to the last newline of the first limit words to oriTexts and assign the remaining to originalText
            split_idx = originalText[:limit].rfind("\n")
            if split_idx == -1: 
                split_idx = limit
            oriTexts.append(originalText[:split_idx])
            originalText = originalText[split_idx:]

        
        currChap += 1

    #Append the remaining of originalText to oriTexts
    l = len(enc.encode(originalText))
    while l > 0:
        if l > limit:
            #Append up to the last newline of the first limit words to oriTexts and assign the remaining to originalText
            split_idx = originalText[:limit].rfind("\n")
            if split_idx == -1: 
                split_idx = limit
            oriTexts.append(originalText[:split_idx])
            originalText = originalText[split_idx:]
        else:
            oriTexts.append(originalText)
            originalText = ""
        l = len(enc.encode(originalText))

    #For debug, save the whole text to a file
    with open("novels/oriText.txt", "w", encoding="utf-8") as f:
        f.write("".join(oriTexts))
   


    #Translate the text
    print("Translating all chapters")
    translated = ""

    for i in range(len(oriTexts)):
        print(f"Processing batch {i}")
        translated += translate(oriTexts[i])

    #For debug, save the whole translated text to a file
    with open("novels/transText.txt", "w", encoding="utf-8") as f:
        f.write(translated)


    currChap -= 1
   
    #save it into a file
    with (novel / f"chapter{oriChap}-{currChap}.txt").open("w", encoding="utf-8") as file:
        file.write(translated)
    currChap += 1


       
#Translate the text and update the prompt (novelSpecific.txt) as needed
def translate(text):

    #Get the general requirements
    with (info / "generalPrompt.txt").open("r", encoding="utf-8") as file:
        genRe = ""
        for line in file:
            genRe += line
    
    #Get novel-specific requirements
    with (novel / "novelSpecific.txt").open("r", encoding="utf-8") as file:
        noRe = ""
        for line in file:
            noRe += line

    
    

    #Create the promt to translate text
    prompt = f"""
    **Role**: Professional Literary Translator  
    **Task**: Translate web-novel chapters into {lang} and **update** this novel’s specific requirements for future use.

    === INPUT SPECIFICATIONS ===
    - Multiple chapters separated by the exact string `NEXTCHAPTER`.  
    - Each chapter begins with its English chapter number (if present).  
    - HTML artifacts (navigation bars, ads, stray tags) may appear.

    === TRANSLATION REQUIREMENTS ===
    1. **Quality Assurance**  
    {genRe.strip()}

    2. **Novel-Specific Requirements**  
    **Warning**: The list below may be incomplete and contain templates (`<…>`) you must fill in based on the chapters’ content.  
    - If you spot a `<template>`, ignore this Novel-Specific Requirements
    Begin of Novel-Specific Requirements
    {noRe.strip()}
    End of Novel-Specific Requirements

    3. **Content Handling**  
    - **Retain**: all story elements (dialogue, descriptions, sound effects).  
    - **Remove**: non-story elements (page numbers, “next chapter” prompts, HTML tags, stray characters).

    === OUTPUT FORMAT ===  
    1. Chapters **only**, in the same order as input.  
    2. Between each chapter, insert **exactly one** `NEXTCHAPTER` (case-sensitive).  
    3. **Do not** emit any extra text, labels, HTML/XML tags, or explanation.  
    4. Ensure neither `NEXTCHAPTER` nor `CHAPTERSENDED` appears **inside** any chapter’s text.

    **Strict Validation** (self-check before returning):  
    - Separator count and placement are correct.  
    - Chapter count matches the input.  
    - Output is a single continuous string (no leading/trailing separators).

    === SOURCE TEXT ===  
    {text}
    """
    translated = response(prompt)

    prompt = f"""
    **ROLE**: You are a translation meta-analyst specializing translating to {lang} literary translation. Your task is to update the translator's note by learning from provided translations of several chapters of a novel.

    **INPUT PROCESSING**:
    - Analyze translation choices against all sections of the current note
    - Identify patterns to update: glossary terms, style observations, audience adjustments, etc.
    - Update ALL applicable sections while preserving original structure
    - WARNING!!!: The original adn translated texts may have irrelavant words, symbols, HTML tags,... Ignore them during your analysis

    **UPDATE RULES FOR EACH SECTION**:
    1. **ROLE & TONE**  
    - Add observed style patterns as bullet points under existing guidelines
    - Example: `- Observed frequent use of alliteration → maintained in translation`

    2. **AUDIENCE & REGISTER**  
    - Note any vocabulary level adjustments made for target audience
    - Example: `- Simplified archaic terms for YA audience`

    3. **STRUCTURE & FORMATTING**  
    - Record any consistent formatting decisions
    - Example: `- Preserved em-dash usage for interrupted dialogue`

    4. **IDIOMS & CULTURAL REFERENCES**  
    - Add recurring translation patterns as new bullet points
    - Example: `- 'Kick the bucket' → 'Bite the dust' (humorous equivalent)`

    5. **QUALITY CONTROL**  
    - Add observed proofreading patterns
    - Example: `- Consistently converted passive→active voice`

    6. **GLOSSARY & CONSISTENCY**  
    - Append new terms at bottom of list
    - Maintain exact `• <Original> → <Translation>` format

    7. **NOVEL SUMMARY**  
    - Append a concise summary of the chapters to existing text
    - May remove the content you're certain that it will NOT BE NEEDED FOR FUUTURE TRANSLATION
    OUTPUT RULES:
        Return ONLY the complete updated note in EXACT original format
        Preserve all original headers and section numbering

    **CRITICAL INSTRUCTIONS**
    For section updates:
    - Add new bullets UNDER existing guidelines
    - Preserve original wording of core instructions
    - Never remove existing content except for the summary

    **Here are the inputs**

    *Original Text*
    {text}

    *Translated Text*
    {translated}

    *Current Note*
    {noRe}
    """
    noRe = response(prompt)
    with (novel / "novelSpecific.txt").open("w", encoding="utf-8") as file:
        file.write(noRe)

    
    
    
    return translated

def response(prompt):
    global client
     #Try to get the respons, switch model if rate-limit is exceeded
    #Number of tries, max is the number of keys in keys.text
    i = 0
    while i < len(keys):
        try:
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
            print(reponse.choices[0].message.content)
            return reponse.choices[0].message.content

        #Handle the rate-limit exceeced error
        except RateLimitError:
            print("Rate limit exceeded")


            #Check if tried all the keys
            i += 1
            if i >= len(keys):
                break


            #Update the new key
            newKey = (int(connect["info"]["api_key"]) + 1) % len(keys)
            connect["info"]["api_key"] = str(newKey)
            with (info / "connect.config").open( "w", encoding="utf-8") as c:
                connect.write(c)
            api_key = keys[newKey]
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key= api_key
            )
            print(f"Changed to key {newKey}. Retrying {i}")

    if i == len(keys):
        sys.exit("All keys exhausted, please add new key or wait a day")
    return reponse.choices[0].message.content

#Navigate from chapter to chapter
def chapToChap(page):
    global currChap
    currUrl = "novelUrl"
    #Replace 1 by toChap
    while currChap < 1:
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


if __name__ == '__main__':
    main()







































































