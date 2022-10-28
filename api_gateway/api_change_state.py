import json
import boto3
import time


def elasticache_create_cluster(cluster_id,ec_cli):
    response=ec_cli.create_cache_cluster(
    CacheClusterId=cluster_id,
    SnapshotName=cluster_id)

def elasticache_delete_cluster(cluster_id,ec_cli):
    try:
        response = ec_cli.delete_cache_cluster(
            CacheClusterId=cluster_id,
            FinalSnapshotIdentifier=cluster_id)
    except Exception as e:
        if "SnapshotAlreadyExistsFault" in str(e):
            #message="snapshot existed with name: "+cluster_id+". Existing one is deleted and new one is being created"
            response = ec_cli.delete_snapshot(
            SnapshotName=cluster_id
            )
            time.sleep(20)
            elasticache_create_cluster(cluster_id,ec_cli)
        else:
            message=str(e)
            

def lambda_handler(event, context):
    access_key=event['queryStringParameters']['access_key']
    secret_key=event['queryStringParameters']['secret_key'].replace(" ","+")
    resource_arn = event['queryStringParameters']['arn']
    resource_state = event['queryStringParameters']['action']
    resource_name = event["pathParameters"]["resource"]
        # event['queryStringParameters']['token'] != "":
    try: 
        access_token=event['queryStringParameters']['session_token'].replace(" ","+")
        session = boto3.session.Session(aws_access_key_id=access_key, aws_secret_access_key=secret_key, aws_session_token=access_token)
        
    except Exception as e:
        session = boto3.session.Session(aws_access_key_id=access_key, aws_secret_access_key=secret_key)
        # session = boto3.session.Session(aws_access_key_id=access_key, aws_secret_access_key=secret_key)
        print (e)
    region=resource_arn.split(":")[3]
    
    if resource_name=="medialive" and "channel" in resource_arn:
        channel_id=resource_arn.split(":")[-1]
        medialive=session.client('medialive',region)
        try:
            ml_response=medialive.describe_channel(ChannelId=channel_id)
            state=ml_response['State']
            if state=="IDLE" and resource_state=="start":
                response=medialive.start_channel(ChannelId=channel_id)
                message="Starting channel"
            elif state=='RUNNING' and resource_state=="stop":
                response=medialive.stop_channel(ChannelId=channel_id)
                message="Stopping channel"
            else:
                message="Channel already in desired state"
        except Exception as e:
            message=str(e)
    
    if resource_name == "ec2": 
        ec2_cli = session.client('ec2', region)
        instance_id = resource_arn.split("/")[1]
        try:
            ec2_response = ec2_cli.describe_instances(InstanceIds=[instance_id])
            state= ec2_response['Reservations'][0]['Instances'][0]['State']['Name'] 
            if state == "running" and resource_state == "stop":
                ec2_response_state = ec2_cli.stop_instances(InstanceIds=[instance_id])
                message="Instance stopping"
            elif state == "stopped" and resource_state == "start":
                ec2_response_state = ec2_cli.start_instances(InstanceIds=[instance_id])
                message="Instance started"
            else:
                message="Instance is in desired state"
        except Exception as e:
            message=str(e)


    if resource_name == "mediaconnect":
        mediaconnect_cli = session.client('mediaconnect', region)
        try:
            mediaconnect_response = mediaconnect_cli.describe_flow(FlowArn = resource_arn)
            if mediaconnect_response['Flow']['Status'] == "STANDBY" and resource_state == "start":
                mediaconnect_state= mediaconnect_cli.start_flow(FlowArn= resource_arn)
                message = resource_arn + " is active"
            elif mediaconnect_response['Flow']['Status'] == "ACTIVE" and resource_state == "stop": 
                mediaconnect_state= mediaconnect_cli.stop_flow(FlowArn= resource_arn)
                message = resource_arn + "is stopped"
            else:
                message = resource_arn + "is in desired state"  
        except Exception as e:
            message = str(e)      

    if resource_name=="cloudfront":
        distribution_id = resource_arn.split("/")[1]
        cf_cli=session.client("cloudfront")
        try:
            response = cf_cli.get_distribution_config(Id=distribution_id)
            Etag=response['ETag']
            modified_config=response['DistributionConfig']
            if resource_state=='enable' and modified_config['Enabled']==False:
                modified_config['Enabled']=True
                cf_cli.update_distribution(DistributionConfig=modified_config, Id=distribution_id,IfMatch=Etag)
                message="Enabling Distribution:"+ distribution_id
            elif resource_state=='disable' and modified_config['Enabled']==True:
                modified_config['Enabled']=False
                cf_cli.update_distribution(DistributionConfig=modified_config, Id=distribution_id,IfMatch=Etag)
                message="Disabling Dstribution:"+ distribution_id
            else:
                message="Cloudfront distribution is in desired state"
        except Exception as e:
            message=str(e)

            
    if resource_name=='rds':
        cluster_id=resource_arn.split(":")[-1]
        try:
            rds_cli=session.client("rds",region)
            response = rds_cli.describe_db_clusters(Filters=[{'Name': 'db-cluster-id','Values': [cluster_id]}])
            status=response['DBClusters'][0]['Status']
            if resource_state=='start' and status=='stopped':
                response = rds_cli.start_db_cluster(DBClusterIdentifier=cluster_id)
                message="Starting Cluster:"+ cluster_id 
            elif resource_state=='stop' and status=='available':
                response = rds_cli.stop_db_cluster(DBClusterIdentifier=cluster_id)
                message="Stopping Cluster:"+ cluster_id +"(Note:You can stop a database for up to seven (7) days. If you do not manually start your database after seven (7) days, it will be automatically started)"
            else:
                message="Cluster:"+ resource_arn + " is in desired state"
        except Exception as e:
            message=str(e)
    
    

    if resource_name=='elasticache':
        ec_cli=session.client("elasticache",region)
        cluster_id=resource_arn.split(":")[-1] 
        try:
            response = ec_cli.describe_cache_clusters(CacheClusterId=cluster_id)
            cluster_present=True
        except:
            cluster_present=False
        if resource_state=='enable' and cluster_present==False:
            try:
                elasticache_create_cluster(cluster_id,ec_cli)
                message="cluster "+ cluster_id + " enabled.(by restoring cluster from snapshot with BackupName provided: "+cluster_id+")"
            except Exception as e:
                message=str(e)
        elif resource_state=='disable' and cluster_present==True:
            elasticache_delete_cluster(cluster_id,ec_cli)
            message="cluster "+ cluster_id + " disabled. (deleted cluster and snapshot is taken with BackupName: " + cluster_id +")"
        else:
            message="cluster " + cluster_id + " is in desired state"


                
    return {
        # if statusCode == 200:
    
            'statusCode': 200,
            'body': json.dumps(str(message))
            }

