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






#Get the path to Info
info = Path(__file__).resolve().parent / "Info"






#Load api_key and model from connect.config
connect = configparser.ConfigParser()
connect.read(str(info / "connect.config"))
myModel = connect["info"]["model"]
#Context limit from the model
context = int(connect["info"]["context"])
#Get the path to keys
keysFile = info / "keys.txt"
with keysFile.open( "r", encoding="utf-8") as k:
    keys = [line.strip() for line in k]
    api_key = keys[int(connect["info"]["api_key"])]






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
currChap = float(args.currChap)
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
    limit = int(context / 4)


    #Collect all the chapters text
    for i in range(len(soups)):
        #Get the soup
        soup = soups[i]
        text = soup.get_text(separator="\n", strip=True)
        text = fix_text(text)


        #Add current chapter to originalText
        originalText += f"\nChap{currChap:.0f}\n{text}"

        #Only append NEXTCHAPTER if it's not the end of the input
        if i != len(soups) - 1:
            originalText += "\n" + "NEXTCHAPTER"

        #Check if the limit is exceeded
        l = len(originalText)
        if l > limit:
            #Append up to the last newline of the first limit words to oriTexts and assign the remaining to originalText
            split_idx = originalText[:limit].rfind("\n")
            if split_idx == -1: 
                split_idx = limit
            oriTexts.append(originalText[:split_idx])
            originalText = originalText[split_idx:]

        
        currChap += 1

    #Append the remaining of originalText to oriTexts
    l = len(originalText)
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
        l = len(originalText)

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


    #Create novels/novelName directory if needed
    novel = info.parent / "novels" / name
    novel.mkdir(parents=True, exist_ok=True)

    currChap -= 1
   
    #save it into a file
    with (novel / f"chapter{oriChap:0f}-{currChap:.0f}.txt").open("w", encoding="utf-8") as file:
        file.write(translated)
    currChap += 1


       




def translate(text):
    global client
    #Create the promt to translate text
    prompt = f"""
    **Role**: Professional Literary Translator
    **Task**: Translate web novel chapters into {lang}


    ### Input Specifications
    - Input contains multiple chapters separated by EXACTLY: `NEXTCHAPTER`. Each chapter have its own chapter number in English at the beginning
    - Chapter order: the same order of the input
    - HTML artifacts may be present (navigation, ads, etc.)


    ### Translation Requirements
    1. **Quality Assurance**:
    - Perform **dual-pass translation**:
        First pass: Complete translation
        Second pass: Refine for fluency, consistency, and style
    - Preserve:
        - Narrative voice and tone
        - Cultural context (adapt appropriately)
        - Dialogue rhythms and speech patterns


    2. **Content Handling**:
    - RETAIN all story elements (dialogue, descriptions, sound effects)
    - REMOVE non-story elements (page numbers, "next chapter" prompts, remaining HTML elements, unrelated or nonsense characters,...)


    ### Output Formatting Rules
    **STRICTLY FOLLOW THESE FORMAT INSTRUCTIONS:**
    1. Output ONLY chapter number and its translated chapter content separated by:
    `NEXTCHAPTER` (exactly this string, case-sensitive)
    2. Format per chapter:
    [Translated Chapter Content]NEXTCHAPTER[Next Chapter Content]
    3. ABSOLUTELY NO:
    - Other unnecessary words (Here is the translated content with all non-story elements removed and chapters separated by NEXTCHAPTER as instructed,...)
    - HTML/XML tags
    - Additional labels or formatting
    4. Ensure `NEXTCHAPTER` appears EXACTLY ONCE between chapters
    5. Never use `NEXTCHAPTER` within chapter content
    6. In the input, if there is no chapter number at the beginning of a chapter, don't include the chapter number of that chapter in the translated output


    ### Critical Validation
    Before outputting, verify:
    ✅ Separators are EXACTLY `NEXTCHAPTER` (11 characters)
    ✅ No separator appears inside chapter text
    ✅ Chapter count matches input
    ✅ Output begins/ends with chapter content (no separators at start/end)
    ✅ Entire output is a SINGLE string with embedded separators


    *** INPUT TEXT ***
    {text}
    """

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
            break
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


    print(reponse.choices[0].message.content)
    #Load the url of the next chapter and the translation
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







































































