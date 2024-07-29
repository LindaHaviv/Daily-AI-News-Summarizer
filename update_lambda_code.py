import json
import boto3
import os

def lambda_handler(event, context):
    # Initialize AWS clients
    lambda_client = boto3.client('lambda')
    
    # Extract the bucket name and object key from the S3 event
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    object_key = event['Records'][0]['s3']['object']['key']
    
    # Update the Lambda function code
    response = lambda_client.update_function_code(
        FunctionName=os.environ['LAMBDA_FUNCTION_NAME'],  # Use environment variable for the function name
        S3Bucket=bucket_name,
        S3Key=object_key,
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps('Lambda function code updated successfully!')
    }
