import os
import boto3
import feedparser
from bs4 import BeautifulSoup
import requests
import json

# Initialize AWS clients
bedrock_runtime_client = boto3.client('bedrock-runtime')
ses_client = boto3.client('ses')
ssm_client = boto3.client('ssm')

# Retrieve parameters from Parameter Store
parameter_response = ssm_client.get_parameter(
    Name='BEDROCK_MODEL_ID',
    WithDecryption=True  # Set to True if the parameter is encrypted
)
BEDROCK_MODEL_ID = parameter_response['Parameter']['Value']

parameter_response = ssm_client.get_parameter(
    Name='SENDER_EMAIL',
    WithDecryption=True  # Set to True if the parameter is encrypted
)
SENDER_EMAIL = parameter_response['Parameter']['Value']

parameter_response = ssm_client.get_parameter(
    Name='RECIPIENT_EMAIL',
    WithDecryption=True  # Set to True if the parameter is encrypted
)
RECIPIENT_EMAIL = parameter_response['Parameter']['Value']

# RSS feeds of AI news sources
rss_feeds = [
    'https://www.technologyreview.com/feed/',
    'https://rss.app/feeds/dj8tuoyGtKUe0Ts7.xml',
    'https://www.forbes.com/ai/feed/',
]

# Function to fetch and parse RSS feeds
def fetch_rss_feed(feed_url):
    return feedparser.parse(feed_url)

# Function to extract and clean article content
def extract_article_content(link):
    response = requests.get(link)
    soup = BeautifulSoup(response.content, 'html.parser')
    paragraphs = soup.find_all('p')
    article_content = ' '.join([p.get_text() for p in paragraphs])
    return article_content

# Function to summarize articles using Amazon Bedrock
def summarize_article(title, content, source, pub_date):
    prompt = f"Article Title: {title}\nSource: {source}\nPublication Date: {pub_date}\n\nArticle Content:\n{content}\n\nPlease provide a concise summary of the key points and main ideas of this article in approximately 150 words."
    response = bedrock_runtime_client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        contentType='application/json',
        accept='application/json',
        body=json.dumps({
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 300,
            "anthropic_version": "bedrock-2023-05-31"
        })
    )
    response_body = json.loads(response['body'].read().decode('utf-8'))
    print(f"DEBUG: Bedrock API response: {response_body}")

    if 'content' in response_body and len(response_body['content']) > 0:
        summary = response_body['content'][0]['text'].strip()  # Adjusted to match the response structure
    else:
        summary = "Summary not available."

    return summary

# Function to send summaries via Amazon SES
def send_email(subject, body):
    response = ses_client.send_email(
        Source=SENDER_EMAIL,
        Destination={
            'ToAddresses': [RECIPIENT_EMAIL],
        },
        Message={
            'Subject': {
                'Data': subject
            },
            'Body': {
                'Html': {
                    'Data': body
                }
            }
        }
    )
    return response

# Function to summarize and select top articles
def summarize_and_select_top_articles(articles):
    summaries = []
    for article in articles:
        summary = summarize_article(article['title'], article['content'], article['source'], article['pub_date'])
        summaries.append({
            'title': article['title'],
            'summary': summary,
            'link': article['link']
        })
    return summaries

# Main function to process RSS feeds and send summaries
def main(event=None, context=None):
    combined_summaries = []

    for feed_url in rss_feeds:
        feed = fetch_rss_feed(feed_url)
        articles = [{
            'title': entry.title,
            'link': entry.link,
            'content': extract_article_content(entry.link),
            'source': feed.feed.get('title', 'Unknown Source'),
            'pub_date': entry.published
        } for entry in feed.entries[:10]]

        top_summaries = summarize_and_select_top_articles(articles)
        feed_title = feed.feed.get('title', 'Unknown Source')
        combined_summaries.append(f"<h2>Top Articles from {feed_title}</h2>")
        for summary in top_summaries[:3]:
            combined_summaries.append(f"<h3>{summary['title']}</h3><p>{summary['summary']}</p><p><a href='{summary['link']}'>Read more</a></p>")

    email_body = "<html><body>" + "".join(combined_summaries) + "</body></html>"
    send_email('Daily AI News Summary', email_body)

if __name__ == '__main__':
    main()
