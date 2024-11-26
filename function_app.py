import logging
import azure.functions as func
from dotenv import load_dotenv
import os
import pyodbc
import requests
import json
import datetime
from sumy.parsers.plaintext import PlaintextParser
from sumy.summarizers.lsa import LsaSummarizer
from sumy.nlp.tokenizers import Tokenizer
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer

nltk.download('punkt_tab')

app = func.FunctionApp()

load_dotenv()
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
CONNECTION_STRING = os.getenv("AZURE_SQL_CONNECTION_STRING")

@app.timer_trigger(schedule="0 0 */12 * * *", arg_name="myTimer", run_on_startup=False,
              use_monitor=False) 
def fetch_news(myTimer: func.TimerRequest) -> None:
    response = requests.get(f"https://newsapi.org/v2/top-headlines?apiKey={NEWS_API_KEY}&country=us")
    articles = response.json().get("articles", [])

    # connect to azure sql database
    
    conn = pyodbc.connect(CONNECTION_STRING)

    cursor = conn.cursor()

    for article in articles:
        cursor.execute(
            "INSERT INTO Articles (Title, Description, URL, PublishedDate) VALUES (?,?,?,?)",
            article["title"], article["description"], article["url"], datetime.datetime.now()
        )
    conn.commit()
    conn.close()

    if myTimer.past_due:
        logging.info('The timer is past due!')

    logging.info('Python timer trigger function executed.')


@app.sql_trigger(arg_name="summarise", table_name="Articles", connection_string_setting="ConnectionStringSetting")
def description_trigger(summarise) -> None:

    conn = pyodbc.connect(CONNECTION_STRING)

    cursor = conn.cursor()

    cursor.execute("SELECT ArticleID, Description FROM Articles WHERE Processed = 0")
    rows = cursor.fetchall()

    for row in rows:
        article_id = row.ArticleID
        description = row.Description

        parser = PlaintextParser.from_string(description, Tokenizer("english"))

        summariser = LsaSummarizer()
        summary = summariser(parser.document, 3)

        summary_text =  " ".join([str(sentence) for sentence in summary])

        # update article with summary
        cursor.execute(
            "UPDATE Articles SET Summary = ?, Processed = 1 WHERE ArticleID = ?",
            summary_text, article_id
        )

    if rows:
        conn.commit()

    conn.close()

    logging.info('Processed all new articles and added summaries')

@app.sql_trigger(arg_name="sentiment", table_name="Articles", connection_string_setting="ConnectionStringSetting")
def sql_sentiment_trigger(sentiment) -> None:
    conn = pyodbc.connect(CONNECTION_STRING)
    
    cursor = conn.cursor()

    cursor.execute("SELECT ArticleID, Summary, Sentiment FROM Articles WHERE Sentiment IS NULL AND Summary IS NOT NULL")
    rows = cursor.fetchall()

    for row in rows:
        article_id = row.ArticleID
        summary = row.Summary
        senti = row.Sentiment

        if summary and not senti:
            sid = SentimentIntensityAnalyzer()
            sentiment_result = sid.polarity_scores(summary)
            sentiment = "POSITIVE" if sentiment_result['compound'] > 0 else "NEGATIVE"

            cursor.execute(
                "UPDATE Articles SET Sentiment = ? WHERE ArticleID = ?",
                sentiment, article_id
            )

            conn.commit()

    conn.close()

@app.route(route="top-headlines", methods=[func.HttpMethod.GET], auth_level=func.AuthLevel.ANONYMOUS)
def get_top_headlines(req: func.HttpRequest) -> func.HttpResponse:
    try: 
        conn = pyodbc.connect(CONNECTION_STRING)
        cursor = conn.cursor()

        today = datetime.datetime.now().date()

        cursor.execute(
            """
            SELECT Title, Summary, Sentiment, PublishedDate
            FROM Articles
            WHERE CAST(PublishedDate AS DATE) = ? AND Summary IS NOT NULL AND Sentiment IS NOT NULL
            """,
            today
        )

        articles = cursor.fetchall()

        html_content = """
        <html>
        <head>
            <title>Today's Top Headlines</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    margin: 20px;
                }
                .article {
                    border: 1px solid #ddd;
                    padding: 15px;
                    margin-bottom: 20px;
                    border-radius: 8px;
                    box-shadow: 2px 2px 8px rgba(0,0,0,0.1);
                }
                .title {
                    font-size: 20px;
                    font-weight: bold;
                }
                .summary {
                    margin: 10px 0;
                }
                .sentiment {
                    font-size: 14px;
                    color: #555;
                }
                .positive {
                    color: green;
                }
                .negative {
                    color: red;
                }
            </style>
        </head>
        <body>
            <h1>Today's Top Headlines</h1>
        """
        for article in articles:
            title = article.Title
            summary = article.Summary
            sentiment = article.Sentiment
            published_date = article.PublishedDate.strftime("%Y-%m-%d %H:%M:%S")

            sentiment_class = "positive" if sentiment == "POSITIVE" else "negative"

            html_content += f"""
            <div class="article">
                <div class="title">{title}</div>
                <div class="summary">{summary}</div>
                <div class="sentiment {sentiment_class}">Sentiment: {sentiment}</div>
                <div class="date">Published on: {published_date}</div>
            </div>
            """

        # Close the HTML content
        html_content += """
        </body>
        </html>
        """

        conn.close()

        return func.HttpResponse(
            html_content,
            status_code = 200,
            mimetype = "text/html"
        )
    except Exception as e:
        logging.error(f"Error fetching headlines: {str(e)}")
        return func.HttpResponse(
            "An error occurred while fetching headlines.",
            status_code=500
        )
