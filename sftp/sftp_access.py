import boto3

role = 'arn:aws:iam::00000000000:role/SFTPS3AccessRole'; # The user will be authenticated if and only if the Role field is not blank
ddb_cli=boto3.client('dynamodb','region')
region = "region"
tablename = 'tablename'


def lambda_handler(event, context):
    print(event)
    message={}
    username=event["username"]
    serverid=event['serverId']
    password=event['password']

    if serverid!="":
        response = ddb_cli.get_item(
        TableName=tablename,
        Key={ 'username':{'S':username}
        })
        if response['Item']:
            if response['Item']['role']['S']!="":
                if response['Item']['password']['S']== password:
                    role=response['Item']['role']['S']
                    home=response['Item']['home']['S']
                    message={
                        'Role':role,
                        'HomeDirectory':home
                    }
                else:
                    message={}
            else:
                message={}
        else:
            message={}
    else:
        message={}

    return {
            "Role": message['Role'],
            "HomeDirectory": message['HomeDirectory']
            }

