import boto3
import json
import sys
import random
import string

message={}
account_id = sys.argv[1]
bucket_name = sys.argv[3]
acess_to_full_bucket = sys.argv[4]

aws_mng_con=boto3.session.Session(profile_name=account_id)
iam_client = aws_mng_con.client('iam')
ddb_cli=aws_mng_con.client("dynamodb","us-east-1")

if acess_to_full_bucket=="YES":
    bucket_path = "/"+bucket_name+"/"
    tablename=sys.argv[5]
else:
    folder_path = sys.argv[5]
    bucket_path = "/"+bucket_name+"/"+folder_path
    tablename=sys.argv[6]


def main():
    user_name = sys.argv[2]
    role_name = "{}_sftp_role".format(user_name)
    return_policy_arn = create_policy(user_name, bucket_name)
    return_role_name, role_arn= create_role(role_name)
    attach_iam_policy= attach_policy(return_role_name, return_policy_arn)
    password=generate_random_password()
    query_stmt='insert into "'+ tablename + '"'+" value {'username':'" + user_name +"','password':'" + password +"','home':'"+ bucket_path +"','role':'"+ role_arn +"'}"
    try:
        response = ddb_cli.execute_statement(
        Statement=query_stmt
        )
        message={
            "username":user_name,
            "password":password,
            "home":bucket_path,
            "role":role_arn
        }
        
    except ddb_cli.exceptions.DuplicateItemException as e:
        message={
                "Error":e
            }
        print(message)
        exit()
    print(message)
    

def create_policy(user_name, bucket_name):
    rfile = open("/var/lib/jenkins/scripts/Sftp-role-policy-creation/construct_policy.json", 'r')
    data= json.load(rfile)
    rfile.close()
    acess_to_full_bucket = sys.argv[4]
    if acess_to_full_bucket == "NO":
        folder_path = sys.argv[5]
        data['Statement'][0]['Resource'] = "arn:aws:s3:::{}/{}/*".format(bucket_name,folder_path)
        data['Statement'][1]['Resource'] = "arn:aws:s3:::{}".format(bucket_name)
        data['Statement'][1]['Condition']['StringLike']['s3:prefix']= "{}/*".format(folder_path)
        
    elif acess_to_full_bucket == "YES": 
        data['Statement'][0]['Resource'] = "arn:aws:s3:::{}/*".format(bucket_name)
        data['Statement'][1]['Resource'] = "arn:aws:s3:::{}".format(bucket_name)
        data['Statement'][1]['Condition']['StringLike']['s3:prefix']="*"


    wfile = open("iam_policy.json", 'w+')
    wfile.write(json.dumps(data))
    wfile.close()

    r1file = open("iam_policy.json", 'r')
    policy_data= json.load(r1file)
    rfile.close()

    policy_name = "{}_sftp_policy".format(user_name)
    try:
        iam_create_policy_response = iam_client.create_policy(
            PolicyName= policy_name,
            PolicyDocument= json.dumps(policy_data)    
        )
        policy_arn = iam_create_policy_response['Policy']['Arn']
        return (policy_arn)
    except Exception as e:
        message={
            "Error":e
        }
        print(message)
        exit()
    
def create_role(role_name):
    
    ro_file = open("/var/lib/jenkins/scripts/Sftp-role-policy-creation/assumed_role.json", 'r')
    data1= json.load(ro_file)
    ro_file.close()
    try:
        iam_create_role_response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(data1)
        )
        role_arn = iam_create_role_response['Role']['Arn']
        response_role_name =iam_create_role_response['Role']['RoleName']
        return(response_role_name, role_arn)
    except Exception as e:
        message={
            "Error":e
        }
        print(message)
        exit()

def attach_policy(role_name, policy_arn):    
    iam_attach_policy = iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn=policy_arn
        )
    return (iam_attach_policy)


def generate_random_password():
    characters = list(string.ascii_letters + string.digits + "!@#$%^&*()")
    random.shuffle(characters)
    password=[]
    for i in range(10):
        password.append(random.choice(characters))
    random.shuffle(characters)
    return "".join(password)


if __name__=='__main__':
    main()
