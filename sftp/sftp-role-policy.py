from urllib import response
import boto3
import json
import sys

account_id = sys.argv[1]
aws_mng_con=boto3.session.Session(profile_name=account_id)
iam_client = aws_mng_con.client('iam')

def main():
    user_name = sys.argv[2]
    # account_id = sys.argv[3]
    bucket_name = sys.argv[3]
    # filename = user_name+'.json'
    role_name = "{}_sftp_role".format(user_name)
    return_policy_arn = create_policy(user_name, bucket_name)
    return_role_name, role_arn= create_role(role_name)
    # policy_arn="arn:aws:iam::{}:policy/{}".format(account_id, return_policy_name)
    attach_iam_policy= attach_policy(return_role_name, return_policy_arn)
    print (role_arn)
    return(role_arn)

def create_policy(user_name, bucket_name):
    rfile = open("/var/lib/jenkins/scripts/Sftp-role-policy-creation/construct_policy.json", 'r')
    data= json.load(rfile)
    rfile.close()
    path_value = sys.argv[4]
    if path_value == "true":
        path_name = sys.argv[5]
        data['Statement'][0]['Resource'] = "arn:aws:s3:::{}/{}/*".format(bucket_name,path_name)
        data['Statement'][1]['Resource'] = "arn:aws:s3:::{}".format(bucket_name)
        data['Statement'][1]['Condition']['StringLike']['s3:prefix']= "{}/*".format(path_name)
        
    elif path_value == "false": 
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
    iam_create_policy_response = iam_client.create_policy(
        PolicyName= policy_name,
        PolicyDocument= json.dumps(policy_data)    
    )
    policy_arn = iam_create_policy_response['Policy']['Arn']
    return (policy_arn)
    
def create_role(role_name):
    
    ro_file = open("/var/lib/jenkins/scripts/Sftp-role-policy-creation/assumed_role.json", 'r')
    data1= json.load(ro_file)
    ro_file.close()
    iam_create_role_response = iam_client.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps(data1)
    )
    role_arn = iam_create_role_response['Role']['Arn']
    response_role_name =iam_create_role_response['Role']['RoleName']
    return(response_role_name, role_arn)

def attach_policy(role_name, policy_arn):    
    iam_attach_policy = iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn=policy_arn
        )
    return (iam_attach_policy)

if __name__=='__main__':
    main()
