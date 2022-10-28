import json
import os
import boto3
import jmespath




def lambda_handler(event, context):
    access_key=event['queryStringParameters']['access_key']
    secret_key=event['queryStringParameters']['secret_key'].replace(" ","+")
    
        # event['queryStringParameters']['token'] != "":
    try: 
        access_token=event['queryStringParameters']['session_token'].replace(" ","+")
        session = boto3.session.Session(aws_access_key_id=access_key, aws_secret_access_key=secret_key, aws_session_token=access_token)
        
    except Exception as e:
        session = boto3.session.Session(aws_access_key_id=access_key, aws_secret_access_key=secret_key)
        # session = boto3.session.Session(aws_access_key_id=access_key, aws_secret_access_key=secret_key)
        print (e)
        
        # else: 
        #     session = boto3.session.Session(aws_access_key_id=access_key, aws_secret_access_key=secret_key)
        # session = boto3.session.Session(aws_session_token=access_token)
    s3_cli = session.client('s3')
    list_resources = []
    bucket_name = event["pathParameters"]["resource"] 
    amgid_value = event["queryStringParameters"]["amgid"]
    s3_paginator = s3_cli.get_paginator('list_objects')
    s3_response_iterator = s3_paginator.paginate(Bucket=bucket_name, Prefix=amgid_value)
    for page in s3_response_iterator:
        mydata = jmespath.search("Contents[].[Key]", page)
        try:
            for i in range(0,len(mydata)):
                    if mydata[i][0].split("/")[0] == amgid_value:
                        print(mydata[i][0].split("/")[1])
                        list_resources.append((mydata[i][0].split("/")[1]).replace("#","/"))
                        
                    
                    else:
                        list_resources = ["This amgid does not exist"]
                        
                    #     pass
            
            # status_code = 200
                      
        except Exception as e:
            print(e)
            list_resources = ["This amgid does not exist"]
            pass
    
    # print(list_resources)    
            
    return {
       
            'statusCode': 200,
            'body': json.dumps(list_resources)
           }    
    
        
         
           
   
                
 

        
                  
