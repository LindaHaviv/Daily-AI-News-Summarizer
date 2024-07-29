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
def get_parameter(name):
    response = ssm_client.get_parameter(Name=name, WithDecryption=True)
    return response['Parameter']['Value']

BEDROCK_MODEL_ID = get_parameter('BEDROCK_MODEL_ID')
SENDER_EMAIL = get_parameter('SENDER_EMAIL')
RECIPIENT_EMAIL = get_parameter('RECIPIENT_EMAIL')

# RSS feeds of AI news sources
rss_feeds = [
    'https://www.technologyreview.com/feed/',
    'https://venturebeat.com/category/ai/feed/',
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
def summarize_article(content):
    prompt = f"Please summarize the following article in 3 sentences:\n\n{content}"
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
            "max_tokens": 100,
            "anthropic_version": "bedrock-2023-05-31"
        })
    )
    response_body = json.loads(response['body'].read().decode('utf-8'))
    print(f"DEBUG: Bedrock API response: {response_body}")  # Added logging for debugging
    summary = response_body['messages'][0]['content'].strip()  # Adjusted to match the response structure
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
        summary = summarize_article(article['content'])
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
            'content': extract_article_content(entry.link)
        } for entry in feed.entries[:10]]
        
        # Log the feed object to inspect its structure
        print(f"DEBUG: Feed object for {feed_url}: {feed.feed}")

        top_summaries = summarize_and_select_top_articles(articles)
        feed_title = feed.feed.get('title', 'Unknown Source')  # Handle missing title gracefully
        combined_summaries.append(f"<h2>Top Articles from {feed_title}</h2>")
        for summary in top_summaries[:3]:
            combined_summaries.append(f"<h3>{summary['title']}</h3><p>{summary['summary']}</p><p><a href='{summary['link']}'>Read more</a></p>")

    email_body = "<html><body>" + "".join(combined_summaries) + "</body></html>"
    send_email('Daily AI News Summary', email_body)

if __name__ == '__main__':
    main()
