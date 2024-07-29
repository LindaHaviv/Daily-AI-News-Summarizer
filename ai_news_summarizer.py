import os
import boto3
import feedparser
from bs4 import BeautifulSoup
import requests
import json

# Initialize AWS clients
bedrock_client = boto3.client('bedrock-runtime')
ses_client = boto3.client('ses')
ssm_client = boto3.client('ssm')

# Retrieve parameters from Parameter Store
def get_parameter(name):
    response = ssm_client.get_parameter(Name=name, WithDecryption=True)
    return response['Parameter']['Value']

# Retrieve parameters
BEDROCK_MODEL_ID = get_parameter('/BEDROCK_MODEL_ID')
SENDER_EMAIL = get_parameter('/SENDER_EMAIL')
RECIPIENT_EMAIL = get_parameter('/RECIPIENT_EMAIL')

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
    request_body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1000,
        "messages": [
            {
                "role": "user",
                "content": content
            }
        ]
    })

    response = bedrock_client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=request_body,
        contentType='application/json',
        accept='application/json'
    )
    response_body = json.loads(response['body'].read())
    print(f"DEBUG: Bedrock API response: {response_body}")  # Debug statement
    summary = response_body['content'][0]['text'].strip()
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
                'Text': {
                    'Data': body
                }
            }
        }
    )
    return response

# Main function to process RSS feeds and send summaries
def main(event=None, context=None):
    summaries = []

    for feed_url in rss_feeds:
        feed = fetch_rss_feed(feed_url)
        for entry in feed.entries[:5]:  # Limiting to the top 5 entries per feed
            article_content = extract_article_content(entry.link)
            summary = summarize_article(article_content)
            summaries.append(f"{entry.title}: {summary}")

    combined_summary = "\n\n".join(summaries)

    # Send email with the combined summary
    send_email('Daily AI News Summary', combined_summary)

if __name__ == '__main__':
    main()
