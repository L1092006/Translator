import configparser
from openai import OpenAI
import argparse
import requests


#Load api_key and model from connect.config
connect = configparser.ConfigParser()
connect.read("connect.config")
api_key = connect["info"]["api_key"]
model = connect["info"]["model"]



client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key= api_key
)


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


    #Get the HTML form novelURL
    html = requests.get(novelUrl).text


    #Create the promt
    prompt = f"""
    You’re given the full HTML source of a chapter on a web‑novel site. Your job is to:


    1. **Extract** the original novel title.  
    2. **Extract** the full URL of the “next chapter.”  
    3. **Translate** the novel title into {lang}.  
    4. **Translate** the *current* chapter’s body text into {lang}.  
    - **Highest priority**: high-quality translation (produce a fluent, natural, error‑free).  
    - After your first pass, **reread and refine** for accuracy, consistency, and style.


    **Output format** :


    <Translated Novel Title>
    ---
    <Next Chapter FULL URL>
    ---
    <Translated Chapter Text> (just plain text for reading)


    - **Do not** output anything else (no HTML tag, no commentary, no extra labels, just the content of the chapter).
    - "Only two" separators for three parts are in the response. Do not use this symbol anywhere else


    Here is the HTML to process:
    {html}


    """
   
    reponse = client.chat.completions.create(
        model="deepseek/deepseek-chat-v3-0324:free",
        messages=[
            {
            "role": "user",
            "content": prompt
            }
        ]
    )


    nextChap, title, currChapTrans = reponse.choices[0].message.content.split("---")
   
    """
    with open("chapter_output.txt", "w", encoding="utf-8") as file:
        file.write(f"Next chap at {nextChap}")
        file.write(currChapTrans)
    """


    print(nextChap)
    print(currChapTrans)


if __name__ == '__main__':
    main()

