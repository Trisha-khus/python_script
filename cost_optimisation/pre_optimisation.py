import boto3
import csv
import sys
import datetime as DT
import botocore
import pytz

Today = DT.date.today()
three_days_ago = Today - DT.timedelta(days=3)
seven_days_ago= Today -DT.timedelta(days=7)
ninty_days_ago=Today-DT.timedelta(days=90)

region_names=[]
spot=[]
idle_resources=[]
eip_allocations={'ids':{}}
all_elb={'ids':{}}
s3=[]
azs=" "
resource_arn=" "
ins_type=" "
table_rcu=0
table_wcu=0

aws_mag_con=boto3.session.Session(profile_name=sys.argv[1])
account_id=aws_mag_con.client('sts').get_caller_identity()['Account']

def main():
    #fetch Idle load balancers and unassociated elastic ip addresses
    get_EIP_ELB()
    #fetch available EBS
    get_available_ebs()
    #fetch cloudwatch logs with retention>7 days
    get_cwLogs()
    #fetch s3 buckets whose lifecycle does not include deleting Incomplete multipartuploads in lifecycle applied for whole bucket
    get_s3_IncompleteUpload_delete_disabled()
    #fetch s3 buckets with versioning enabled and does not include deleting previous versions in lifecycle applied for whole bucket
    get_s3_DeletePreviousVersions_disabled()
    #fetch On-demand ASG
    get_ASG_on_demand()
    #fetch non-t series RDS instances
    get_RDS_instance_type()
    #fetch non-t series Elasticache instances
    get_EC_instance_type()
    #fetch non-t series DocumentDB instances
    get_DocDB_instance_type()
    #fetch non-t series MemoryDB instances
    get_MemDB_instance_type()
    #fetch RDS with replica's
    get_RDS_replica()
    #fetch Elasticache with replica's
    get_EC_replica()
    #fetch DocumentDB with replica's
    get_DocDB_replica()
    #fetch MemoryDB with replica's
    get_MemDB_replica()
    #fetch idle medialive inputs
    get_medialive_inputs()
    #fetch idle medialive channels
    get_medialive_channels()
    #fetch overprovisioned lambdas
    get_lambda_functions()
    #Ec2 instances with cpu<30% for last 3 days
    get_ec2_underutilised()
    #checking on instance scheduler 
    instance_scheduler()
    #checking on ASG Scheduler
    asg_scheduler()
    #fetch Idle mediaconnect flows
    get_Idle_MediaConnect_Flow()
    #fetch obsolete snapshots
    get_obsolete_Snapshots()
    #fetch obsolete images
    get_obsolete_Images()
    #fetch idle RDS instances
    get_idle_RDS_Instances()
    #fetch underutilized dynamodb
    get_unused_dynamodb()
    get_instances__latest_generation()
    write_to_file(idle_resources)

def asg_scheduler():
    Flag=is_lambda_present("ASGSchedulerMain")
    if Flag==False:
        idle_resources.append({'Cloud':'AWS','Region':'NA','Availability Zone':'NA','Resource':'AWS Account','Status':"ASG Scheduler not Installed",'Group':"ASG Scheduler",'Action':"Install ASG Scheduler"})
        print("ASG Scheduler not Installed")
    if Flag==True:
        idle_resources.append({'Cloud':'AWS','Region':'NA','Availability Zone':'NA','Resource':'AWS Account','Status':"ASG Scheduler Installed",'Group':"ASG Scheduler",'Action':"No Action"})
        for region in region_names:
            ec2_client=aws_mag_con.client("autoscaling",region)
            paginator = ec2_client.get_paginator('describe_auto_scaling_groups')
            response_iterator = paginator.paginate()
            for page in response_iterator:
                for asg in page['AutoScalingGroups']:
                    arn=asg['AutoScalingGroupARN']
                    asg_name=asg['AutoScalingGroupName']
                    az=asg['AvailabilityZones']
                    tag_flag=False
                    for tag in asg['Tags']:
                        if tag['Key']=="Schedule":
                            tag_flag=True
                            break
                    if tag_flag==False:
                        idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':az,'Resource':arn,'Status':"ASG has No Schedule Tag",'Group':"ASG Scheduler",'Action':"No Action"})
        print("ASG Scheduler Installed, Listing of auto scaling groups with no Schedule tag completed")

def instance_scheduler():
    Flag=is_lambda_present("InstanceSchedulerMain")
    if Flag==False:
        idle_resources.append({'Cloud':'AWS','Region':'NA','Availability Zone':'NA','Resource':'AWS Account','Status':"Instance Scheduler not Installed",'Group':"Instance Scheduler",'Action':"Install Instance Scheduler"})
        print("Instance Scheduler not Installed")
    if Flag==True:
        idle_resources.append({'Cloud':'AWS','Region':'NA','Availability Zone':'NA','Resource':'AWS Account','Status':"Instance Scheduler Installed",'Group':"Instance Scheduler",'Action':"No Action"})
        for region in region_names:
            ec2_client=aws_mag_con.client("ec2",region)
            paginator = ec2_client.get_paginator('describe_instances')
            response_iterator = paginator.paginate()
            for page in response_iterator:
                for instances in page['Reservations']:
                    for instance in instances['Instances']:
                        instance_id=instance['InstanceId']
                        az=instance['Placement']['AvailabilityZone']
                        tag_flag=False
                        try:
                            for tag in instance['Tags']:
                                if tag['Key']=="Schedule":
                                    tag_flag=True
                                    break
                        except:
                            tag_flag=False
                        
                        if tag_flag==False:
                            #ec2 instance does not have arn so construct one
                            arn="arn:aws:ec2:"+region+":"+account_id+":Instance:"+instance_id
                            idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':az,'Resource':arn,'Status':"EC2 Instance has No Schedule Tag",'Group':"Instance Scheduler",'Action':"No Action"})
       
        for region in region_names:
            rds_client=aws_mag_con.client("rds",region)
            paginator = rds_client.get_paginator('describe_db_instances')
            response_iterator = paginator.paginate()
            for page in response_iterator:
                for db in page['DBInstances']:
                    arn=db['DBInstanceArn']
                    tag_flag=False
                    for tag in db['TagList']:
                        if tag['Key']=="Schedule":
                            tag_flag=True
                            break
                    if tag_flag==False:
                        idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':az,'Resource':arn,'Status':"RDS Instance has No Schedule Tag",'Group':"Instance Scheduler",'Action':"No Action"})

        print("Instance Scheduler Installed, Listing of Ec2 and RDS instances with no scheduler tag completed")

def is_lambda_present(functionName):
    for region in region_names:
        client=aws_mag_con.client("lambda",region)
        paginator = client.get_paginator('list_functions')
        response_iterator = paginator.paginate()
        for page in response_iterator:
            for function in page['Functions']:
                FN=function['FunctionName']
                if functionName in FN:
                    return True
    
    return False

def get_ec2_underutilised():
    for region in region_names:
        ec2 = aws_mag_con.client('ec2',region)
        response=ec2.describe_instances()
        for instances in response['Reservations']:
            for instance in instances['Instances']:
                instance_id=instance['InstanceId']
                state=instance['State']['Name']
                az=instance['Placement']['AvailabilityZone']
                if state=="running":

                    #if instance is not spot then executes, otherwise skip to next instance
                    if instance_id not in spot:
                        cpu_p100_values=get_cpu_statistics(instance_id,region)
                        
                        count=0
                        for value in cpu_p100_values:
                            if float(value)<30:
                                if float(value)==-1:
                                    pass
                                else:
                                    count=count+1

                        #ignoring entries with -1
                        if count==0:
                            pass      
                        else:
                            #ec2 instance does not have arn so construct one
                            arn="arn:aws:ec2:"+region+":"+account_id+":Instance:"+instance_id
                            idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':az,'Resource':arn,'Status':'CPUUtilization<30 for last 3 days','Group':'EC2 underutilized Instance','Action':'No Action'})
    print("Listing of Underutilized Ec2 Instances (whose cpu<30% for last 3 days) completed")

def all_spot():

    for region in region_names:
        ec2 = aws_mag_con.client('ec2',region)
        #gets info of all spot instances in that region
        response = ec2.describe_instances(
            Filters=[{
                    'Name': 'instance-lifecycle',
                    'Values': ['spot']
                }, 
            ]
            )
        for group in response['Reservations']:
            for instance in group['Instances']:
                spot.append(instance['InstanceId'])

 
def get_cpu_statistics(instance_id,region):

    today = DT.date.today()
    three_days_before= today - DT.timedelta(days=3)
    
    #get today date to be passed as end date
    end_date=int(today.strftime("%d"))
    end_month=int(today.strftime("%m"))
    end_year=int(today.strftime("%Y"))
    
    #get date of 3 days ago as start date
    start_date=int(three_days_before.strftime("%d"))
    start_month=int(three_days_before.strftime("%m"))
    start_year=int(three_days_before.strftime("%Y"))

    #retreives CPU utilization of instance with extended statistics p100
    cloudwatch_client=aws_mag_con.client("cloudwatch",region)
    response = cloudwatch_client.get_metric_statistics(
    Namespace='AWS/EC2',
    MetricName='CPUUtilization',
    Dimensions=[
        {
        'Name': 'InstanceId',
        'Value': instance_id
        },
    ],
    StartTime=DT.datetime(start_year,start_month,start_date),
    EndTime=DT.datetime(end_year,end_month,end_date),
    Period=86400,#1day=86400sec
    Statistics=[
        'Average',
    ],
    ExtendedStatistics=[
        'p100',
    ],
    Unit='Percent'
    )
    
    p100_values=[]
        
    #store p100 value of 3 days to array
    i=0
    while i<3:
        try:
            p100_values.append((str(response['Datapoints'][i]['ExtendedStatistics']['p100'])))
        except:
            p100_values.append(-1)

        i=i+1
    return p100_values

def get_lambda_functions():
    for region in region_names:
        client = aws_mag_con.client('compute-optimizer',region)
        response = client.get_lambda_function_recommendations()
        for func in response['lambdaFunctionRecommendations']:
            for reason in func['findingReasonCodes']:
                if reason =="MemoryOverprovisioned":
                    arn=func['functionArn']
                    resource=func['functionArn'].split(":")[-2]
                    idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':'','Resource':arn,'Status':"Memory Overprovisioned",'Group':"Lambda Overprovisioned",'Action':"No Action"})
    print("Listing of Over Provisioned Lambda functions completed")
                    
def get_medialive_channels():
    for region in region_names:
        try:
            medialive_client = aws_mag_con.client('medialive',region_name=region) 
            paginator = medialive_client.get_paginator('list_channels')
            medialive_page = paginator.paginate()
            for channel_page in medialive_page:
                if len(channel_page['Channels'])>0:
                    for each_channel in channel_page['Channels']:
                        if each_channel['State']=="IDLE":
                            for inp in each_channel['InputAttachments']:
                                inp_arn="arn:aws:medialive:"+region+":"+account_id+":input:"+inp['InputId']
                                idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':'','Resource':inp_arn,'Status':"Attached to IDLE Channel",'Group':'Medialive Idle Inputs','Action':'Delete'})

                            idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':'','Resource':each_channel['Arn'],'Status':each_channel['State'],'Group':'Medialive Idle Channels','Action':'Delete'})
                        else:
                            nwIn=get_metrics(each_channel['Id'],region,'NetworkIn')
                            nwOut=get_metrics(each_channel['Id'],region,'NetworkOut')
                            if nwIn<=0.0 or nwOut<=0.0:
                                for inp in each_channel['InputAttachments']:
                                    inp_arn="arn:aws:medialive:"+region+":"+account_id+":input:"+inp['InputId']
                                    idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':'','Resource':inp_arn,'Status':'NetworkwIn/NetworkOut of Attached Channel is 0 Bytes','Group':'Medialive Unused Inputs','Action':'Delete'})

                                idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':'','Resource':each_channel['Arn'],'Status':'NetworkwIn/NetworkOut of Channel is 0 Bytes','Group':'Medialive Unused Channel','Action':'Delete'})                   

        except botocore.exceptions.EndpointConnectionError as e:
            pass
        except botocore.exceptions.SSLError as e:
            pass
        except Exception as e:
            print(e)

    print("Listing of IDLE Medialive Channels completed")
    
def get_metrics(channelid,region,metric):
    datapoints=get_nwIn_nwOut(channelid,region,metric,'AWS/MediaLive')
    if datapoints==[]:
        dp=get_nwIn_nwOut(channelid,region,metric,'MediaLive')
        if dp==[]:
            return 0.0
        else:
            return dp[0]['Average']
    return datapoints[0]['Average']

def get_nwIn_nwOut(channelid,region,metric,namespace):
    start=DT.datetime.now()-DT.timedelta(days=3)
    end=DT.datetime.now()
    cloudwatch = aws_mag_con.resource('cloudwatch',region)
    metric = cloudwatch.Metric(namespace,metric)
    response = metric.get_statistics(
    Dimensions=[
        {
            'Name': 'ChannelId',
            'Value': channelid,
        },
        {
            "Name": "Pipeline",
            "Value": "0"
        },
    ],
    StartTime=start,
    EndTime=end,
    Period=86400,
    Statistics=['Average'],
    Unit='Megabits/Second',
    ) 
    return response['Datapoints']

def get_medialive_inputs():
    for region in region_names:
        try:
            medialive_client = aws_mag_con.client('medialive',region_name=region) 
            paginator = medialive_client.get_paginator('list_inputs')
            medialive_page = paginator.paginate()
            for input_page in medialive_page:
                if len(input_page['Inputs'])>0:
                    for each_input in input_page['Inputs']:  
                        if each_input['State']=="DETACHED":
                            idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':'','Resource':each_input['Arn'],'Status':each_input['State'],'Group':'Medialive Detached Inputs','Action':'Delete'})
        except botocore.exceptions.EndpointConnectionError as e:
            pass
        except botocore.exceptions.SSLError as e:
            pass
        except Exception as e:
            print(e)
    print("Listing of IDLE Medialive Inputs completed")

def get_s3_DeletePreviousVersions_disabled():
    s3_cli=aws_mag_con.client("s3")
    for bucket in s3:
        flag=False
        try:
            response1 = s3_cli.get_bucket_versioning(Bucket=bucket['Name'])
            if response1['Status']=='Enabled':
                try:
                    response = s3_cli.get_bucket_lifecycle_configuration(Bucket=bucket['Name'])
                    for rule in response['Rules']:                        
                        if 'Filter' not in rule.keys() and 'NoncurrentVersionExpiration' in rule.keys() and rule['Status']=='Enabled':
                            flag=True
                            break 
                except:
                    flag=False

                if flag==False:
                    arn="arn:aws:s3:::"+bucket['Name']
                    idle_resources.append({'Cloud':'AWS','Region':bucket['Region'],'Availability Zone':'','Resource':arn,'Status':"DeletePreviousVersions Disabled",'Group':"S3 DeletePreviousVersions",'Action':'Enable DeletePreviousVersions'})
        except:
            continue
    print("Listing of S3 Buckets with DeletePreviousVersions Disabled Completed")

def get_s3_IncompleteUpload_delete_disabled():

    s3_cli=aws_mag_con.client("s3")
    for bucket in s3:
        flag=False
        try:
            response = s3_cli.get_bucket_lifecycle_configuration(Bucket=bucket['Name'])
            for rule in response['Rules']:

                if 'Filter' not in rule.keys() and 'AbortIncompleteMultipartUpload' in rule.keys() and rule['Status']=='Enabled':
                    flag=True
                    break
        except:
            flag=False

        if flag==False:
            arn="arn:aws:s3:::"+bucket['Name']
            idle_resources.append({'Cloud':'AWS','Region':bucket['Region'],'Availability Zone':'','Resource':arn,'Status':"Delete IncompleteUpload Disabled",'Group':"S3 IncompleteUpload",'Action':'Enable Delete IncompleteUpload'})
    print("Listing of S3 Buckets with IncompleteUpload Disabled Completed")
            
               
def get_EIP_ELB():
    TA_client = aws_mag_con.client('support')
    response = TA_client.describe_trusted_advisor_checks(
    language='en'
    )
    for check in response['checks']:
        if check['name']=="Idle Load Balancers":
            checkId=check['id']
            list_idle_ELB_EIP_resources(TA_client,checkId,"Delete","Idle Load Balancers","elb")
            print("Listing of IDLE Load Balancers Completed")    
        
        elif check['name']=="Unassociated Elastic IP Addresses":
            checkId=check['id']
            list_idle_ELB_EIP_resources(TA_client,checkId,"Delete","Unassociated EIP","eip")
            print("Listing of Unattached EIP Completed")


        
def list_idle_ELB_EIP_resources(TA_client,checkId,action,group,type):
    response1 = TA_client.describe_trusted_advisor_check_result(
    checkId=checkId)

    if type=="elb":
        for resource in response1['result']['flaggedResources']:
            az=[]
            #try-except block : trusted advisor data may not be refreshed error might arise in searching elb
            try:
                azs=all_elb['ids'][resource['metadata'][1]]['azs']
                for az1 in azs:
                    az.append(az1)
                idle_resources.append({'Cloud':'AWS','Region':resource['metadata'][0],'Availability Zone':az,'Resource':all_elb['ids'][resource['metadata'][1]]['arn'],'Status':resource['metadata'][2],'Group':group,'Action':action})
            except:
                pass

    elif type=="eip":
        for resource in response1['result']['flaggedResources']:
            #eip does not have arn so construct one
            #try-except block : trusted advisor data may not be refreshed, error might arise in searching for eip
            try:
                arn="arn:aws:ec2:"+resource['metadata'][0]+":"+account_id+":address:"+eip_allocations['ids'][resource['metadata'][1]]
                idle_resources.append({'Cloud':'AWS','Region':resource['metadata'][0],'Availability Zone':'','Resource':arn,'Status':"Unassociated",'Group':group,'Action':action})
            except:
                pass

def get_available_ebs():
    for region in region_names:
        ec2_client = aws_mag_con.client('ec2',region)
        paginator = ec2_client.get_paginator('describe_volumes')
        response_iterator = paginator.paginate()
        for page in response_iterator:
            for volume in page['Volumes']:
                if volume['Attachments']==[]:
                    #ebs does not have arn so construct one
                    arn="arn:aws:ec2:"+region+":"+account_id+":volume:"+volume['VolumeId']
                    idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':volume['AvailabilityZone'],'Resource':arn,'Status':volume['State'],'Group':'Unattached EBS Volumes','Action':"Delete"})
    print("Listing of Available EBS Completed")

def get_cwLogs():
    for region in region_names:
        try:
            client=aws_mag_con.client("logs",region)
            paginator = client.get_paginator('describe_log_groups')
            response_iterator = paginator.paginate()
            for page in response_iterator:
                for log in page['logGroups']:
                    arn=log['arn']
                    try:
                        retention=log['retentionInDays']
                    except:
                        retention="NeverExpire"
                    if retention=="NeverExpire":
                        idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':'','Resource':arn,'Status':"Retention: "+str(retention)+" Days",'Group':'Cloudwatch Logs with retention>7days','Action':"Modify Retention to 7 days"})
                    elif retention>7:
                        idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':'','Resource':arn,'Status':"Retention: "+str(retention) +" Days",'Group':'Cloudwatch Logs with retention>7days','Action':"Modify Retention to 7 days"})
        except Exception as e:
            print(e)
    print("Listing of Cloudwatch Logs with Retention >7 days Completed")
            
def get_ASG_on_demand():    
    for region in region_names:
        ASG_client = aws_mag_con.client('autoscaling', region)
        paginator = ASG_client.get_paginator('describe_auto_scaling_groups')
        response_iterator = paginator.paginate()
        try:
            for page in response_iterator:
                for each_asg in page['AutoScalingGroups']:
                    on_demand_percent=each_asg['MixedInstancesPolicy']['InstancesDistribution']['OnDemandPercentageAboveBaseCapacity']
                    if on_demand_percent!=0:
                        resource_arn=each_asg['AutoScalingGroupARN']
                        azs=each_asg['AvailabilityZones']
                        idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':azs,'Resource':resource_arn,'Status':"on demand",'Group':"ASG",'Action':"change to spot"})
        except KeyError:
            pass
        except Exception as e:
            print(e)

    print("Listing of On-demand ASG Completed")

def get_RDS_instance_type():
    for region in region_names:
        RDS_client = aws_mag_con.client('rds', region)
        paginator = RDS_client.get_paginator('describe_db_instances')
        response_iterator = paginator.paginate()
        for page in response_iterator:
            for each_rds in page['DBInstances']:
                ins_type=each_rds['DBInstanceClass']
                if ins_type.startswith("db.t")==False:
                    resource_arn=each_rds['DBInstanceArn']
                    azs=each_rds['AvailabilityZone']
                    idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':azs,'Resource':resource_arn,'Status':"non t-series",'Group':"RDS",'Action':"convert to t-series"})
    print("Listing of RDS Non-t series Instances Completed")

def get_EC_instance_type():
    for region in region_names:
        EC_client=aws_mag_con.client('elasticache', region)
        paginator = EC_client.get_paginator('describe_cache_clusters')
        response_iterator = paginator.paginate()
        for page in response_iterator:
            for each_ec in page['CacheClusters']:
                node_type=each_ec['CacheNodeType']
                azs=each_ec['PreferredAvailabilityZone']
                resource_arn=each_ec['ARN']
                if node_type.startswith("cache.t")==False:
                    idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':azs,'Resource':resource_arn,'Status':"non t-series",'Group':"EC",'Action':"convert to t-series"})
    print("Listing of Elasticache Non-t series Instances Completed")

def get_DocDB_instance_type():
    for region in region_names:       
        DocDB_cli=aws_mag_con.client('docdb', region)
        paginator = DocDB_cli.get_paginator('describe_db_instances')
        response_iterator = paginator.paginate()
        for page in response_iterator:
            for each_docdb in page['DBInstances']:
                ins_type=each_docdb['DBInstanceClass']
                azs=each_docdb['AvailabilityZone']
                resource_arn=each_docdb['DBInstanceArn']
                if ins_type.startswith("db.t")==False:
                    idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':azs,'Resource':resource_arn,'Status':"non t-series",'Group':"DocDB",'Action':"convert to t-series"})
    print("Listing of DocumentDB Non-t series Instances Completed")

def get_MemDB_instance_type():
    for region in region_names:
        try:
            MemDB_cli=aws_mag_con.client('memorydb', region)
            Memdb_response = MemDB_cli.describe_clusters()
            k=int(len(Memdb_response['Clusters']))
            if k>0:
                for instance in Memdb_response['Clusters']:
                    ins_type=instance['NodeType']
                    resource_arn=instance['ARN']
                    if ins_type.startswith("db.t")==False:
                        idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':azs,'Resource':resource_arn,'Status':"non t-series",'Group':"MemDB",'Action':"convert to t-series"})
                                    
            else:
               pass
        except botocore.exceptions.SSLError as e:
            pass
        except botocore.exceptions.EndpointConnectionError as e:
            pass
        except Exception as e:
            print(e)
    print("Listing of MemoryDB Non-t series Instances Completed")

                
def get_RDS_replica():
    for region in region_names:
        RDS_client = aws_mag_con.client('rds', region)
        paginator = RDS_client.get_paginator('describe_db_clusters')
        response_iterator = paginator.paginate()
        for page in response_iterator:
            for each_rds in page['DBClusters']:
                if each_rds['Engine']!="docdb":
                    n=len(each_rds['DBClusterMembers'])
                    if n>1:
                        resource_arn=each_rds['DBClusterArn']
                        azs=each_rds['AvailabilityZones']
                        idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':azs,'Resource':resource_arn,'Status':"replica",'Group':"RDS",'Action':"delete replica"})
    print("Listing of RDS with replica's Completed")

def get_EC_replica():
    for region in region_names:
        EC_client=aws_mag_con.client('elasticache', region)
        paginator = EC_client.get_paginator('describe_cache_clusters')
        response_iterator = paginator.paginate()
        for page in response_iterator:
            for each_ec in page['CacheClusters']:
                azs=each_ec['PreferredAvailabilityZone']
                node_num=each_ec['ARN'].split("-")[-1]
                resource_arn=each_ec['ARN']
                if node_num!="001":
                        idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':azs,'Resource':resource_arn,'Status':"replica",'Group':"EC",'Action':"delete replica"})
    print("Listing of Elasticache with replica's Completed")
                        
def get_DocDB_replica():    
    for region in region_names:   
        DocDB_cli=aws_mag_con.client('docdb', region)
        paginator = DocDB_cli.get_paginator('describe_db_clusters')
        response_iterator = paginator.paginate()
        for page in response_iterator:
            for each_docdb in page['DBClusters']:
                if each_docdb['Engine']=="docdb":
                    n=len(each_docdb['DBClusterMembers'])
                    if n>1:
                        resource_arn=each_docdb['DBClusterArn']
                        azs=each_docdb['AvailabilityZones']
                        idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':azs,'Resource':resource_arn,'Status':"replica",'Group':"DocDB",'Action':"delete replica"})
    print("Listing of DocumentDB with replica's Completed")

def get_MemDB_replica():
    for region in region_names:
        try:
            MemDB_cli=aws_mag_con.client('memorydb', region)
            Memdb_response = MemDB_cli.describe_clusters()
            k=int(len(Memdb_response['Clusters']))
            if k>0:
                for instance in Memdb_response['Clusters']:
                    for shard in instance['Shards']:
                        n=shard['NumberOfNodes']
                        az=[]
                        if n>1:
                            for node in shard['Nodes']:
                                node_num=node['Name'].split("-")[-1]
                                if node_num!="001":
                                    az.append(node['AvailabilityZone'])
                            resource_arn=instance['ARN']
                            idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':az,'Resource':resource_arn,'Status':"replica",'Group':"MemDB",'Action':"delete replica"})


            else:
                pass
        except Exception as e:
                pass
    print("Listing of MemoryDB with replica's Completed")
    
def get_Idle_MediaConnect_Flow():
    for region in region_names:
        try:
            mediaconnect_client = aws_mag_con.client('mediaconnect', region)
            paginator = mediaconnect_client.get_paginator('list_flows')
            mediaconnect_response = paginator.paginate()
            for page in mediaconnect_response:
                for each_flow in page['Flows']:
                    azs=each_flow['AvailabilityZone']
                    resource_arn=each_flow['FlowArn']
                    if each_flow['Status']=='STANDBY':
                        idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':azs,'Resource':resource_arn,'Status':"idle",'Group':"Mediaconnect",'Action':"Delete"})
                    else:
                        bitrate=get_source_bitrate(region,resource_arn)
                        if bitrate==0.0:
                            idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':azs,'Resource':resource_arn,'Status':"idle",'Group':"Mediaconnect",'Action':"Delete"})
        except botocore.exceptions.SSLError as e:
            pass
        except botocore.exceptions.EndpointConnectionError as e:
            pass
        except Exception as e:
            print(e)
    print("Listing of Idle MediaConnect Flow Completed")

def get_source_bitrate(region,flow_arn):
    # flow_response = mediaconnect_client.describe_flow(FlowArn=resource_arn)
    cloudwatch_client=aws_mag_con.client("cloudwatch", region)
    end_date=int(Today.strftime("%d"))
    end_month=int(Today.strftime("%m"))
    end_year=int(Today.strftime("%Y"))
    start_date=int(three_days_ago.strftime("%d"))
    start_month=int(three_days_ago.strftime("%m"))
    start_year=int(three_days_ago.strftime("%Y"))
    response = cloudwatch_client.get_metric_statistics(
            Namespace='AWS/MediaConnect',
            MetricName='SourceBitRate',
            Dimensions=[
                {
                'Name': 'FlowARN',
                'Value': flow_arn
                },
            ],
            StartTime=DT.datetime(start_year,start_month,start_date),
            EndTime=DT.datetime(end_year,end_month,end_date),
            Period=86400,#1day=86400sec
            Statistics=[
                'Average'
            ],
            Unit='Bits/Second'
            )
    try:
        bit_rate=response['Datapoints'][0]['Average']
    except Exception as e:
        print(e)
        pass
    return bit_rate

        
def get_obsolete_Snapshots():
    for region in region_names:
        try:
            ec2_client = aws_mag_con.client('ec2',region)
            paginator = ec2_client.get_paginator('describe_snapshots')
            snapshot_response = paginator.paginate(OwnerIds=[account_id])
            for page in snapshot_response:
                for each_snapshot in page['Snapshots']:
                    resource_arn=each_snapshot['SnapshotId']
                    start_time=each_snapshot['StartTime']
                    age=find_age(start_time)
                    azs=region
                    if age>180:
                        idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':azs,'Resource':resource_arn,'Status':"Obsolete Snapshots",'Group':"EC2/Snapshots",'Action':"Delete Snapshots"})
        except Exception as e:
            print(e)
            pass
    print("Listing of Obsolete Snapshots Completed")
                   
def get_obsolete_Images():
    for region in region_names:
        try:
            ec2_client = aws_mag_con.client('ec2',region)
            image_response = ec2_client.describe_images(Owners=[account_id])
            for image in image_response['Images']:
                creation_time=image['CreationDate']
                launch_time=DT.datetime.fromisoformat(creation_time[:-1]).astimezone(pytz.utc)
                resource_arn=image['ImageId']
                azs=region
                age=find_age(launch_time)
                if age>180: #days
                    ins_response = ec2_client.describe_instances()
                    if ins_response['Reservations']==[]:
                        idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':azs,'Resource':resource_arn,'Status':"Obsolete Images",'Group':"EC2/AMI",'Action':'Delete AMI'})
                    else:
                        continue



        except Exception as e:
            print(e)
            pass
    print("Listing of Obsolete Images Completed")

def find_age(start_time):
    current_time=DT.datetime.now()
    date2=pytz.utc.localize(current_time)
    time_diff=date2-start_time
    days=time_diff.days
    return days

def get_idle_RDS_Instances():
    for region in region_names:
        try:
            rds_client = aws_mag_con.client('rds',region)
            rds_paginator = rds_client.get_paginator('describe_db_instances')
            rds_response_iterator = rds_paginator.paginate()
            for page in rds_response_iterator:
                for instance in page['DBInstances']:
                        resource_arn=instance['DBInstanceIdentifier']
                        azs=instance['AvailabilityZone']
                        if instance['Engine']!="docdb":
                            connections_count=find_rds_dbconnections(resource_arn,region)
                            if connections_count==0.0:
                                idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':azs,'Resource':resource_arn,'Status':"Idle RDS Instances",'Group':"RDS",'Action':'Delete RDS Instance'})
        except UnboundLocalError:
            pass
        except botocore.exceptions.EndpointConnectionError as e:
            pass
        except Exception as e:
            print(e)

    print("Listing of Idle RDS Instances Completed")
    
def find_rds_dbconnections(ins_id,region):
    cloudwatch_client=aws_mag_con.client("cloudwatch", region)
    end_date=int(Today.strftime("%d"))
    end_month=int(Today.strftime("%m"))
    end_year=int(Today.strftime("%Y"))
    start_date=int(seven_days_ago.strftime("%d"))
    start_month=int(seven_days_ago.strftime("%m"))
    start_year=int(seven_days_ago.strftime("%Y"))
    response = cloudwatch_client.get_metric_statistics(
            Namespace='AWS/RDS',
            MetricName='DatabaseConnections',
            Dimensions=[
                {
                'Name': 'DBInstanceIdentifier',
                'Value': ins_id
                },
            ],
            StartTime=DT.datetime(start_year,start_month,start_date),
            EndTime=DT.datetime(end_year,end_month,end_date),
            Period=86400,#1day=86400sec
            Statistics=[
                'Average'
            ],
            Unit='Count'
            )
    try:
        db_connections=response['Datapoints'][0]['Average']
    except Exception as e:
        #print(region,ins_id,e)
        pass
    return db_connections

def get_unused_dynamodb():
    for region in region_names:
        try:
            db_client = aws_mag_con.client('dynamodb', region)
            db_paginator = db_client.get_paginator('list_tables')
            db_response_iterator = db_paginator.paginate()
            for page in db_response_iterator:
                for db in page['TableNames']:
                    table_name=db
                    resource_arn="arn:aws:dynamodb:"+region+":"+account_id+":table/"+table_name
                    azs=region
                    RCU=find_db_rcu(table_name,region)
                    WCU=find_db_wcu(table_name,region)
                    if RCU==0 and WCU==0:
                        idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':azs,'Resource':resource_arn,'Status':"Under utilised Dynamodb",'Group':"Dynamodb",'Action':'Auto Scale Dynamodb'})

        except Exception as e:
            print(e)
            pass
    print("Listing of under used Dynamodb Completed")
    
def find_db_rcu(table_name,region):
    cloudwatch_client=aws_mag_con.client("cloudwatch", region)
    end_date=int(Today.strftime("%d"))
    end_month=int(Today.strftime("%m"))
    end_year=int(Today.strftime("%Y"))
    start_date=int(ninty_days_ago.strftime("%d"))
    start_month=int(ninty_days_ago.strftime("%m"))
    start_year=int(ninty_days_ago.strftime("%Y"))
    response = cloudwatch_client.get_metric_statistics(
            Namespace='AWS/DynamoDB',
            MetricName='ConsumedReadCapacityUnits',
            Dimensions=[
                {
                'Name': 'TableName',
                'Value': table_name
                },
            ],
            StartTime=DT.datetime(start_year,start_month,start_date),
            EndTime=DT.datetime(end_year,end_month,end_date),
            Period=60*60*24*90,#1day=86400sec
            Statistics=[
                'Maximum'
            ],
            Unit='Count'
            )
    try:
        table_rcu=response['Datapoints'][0]['Maximum']
    except Exception as e:
        print(e)
        pass
    return table_rcu

def find_db_wcu(table_name,region):
    cloudwatch_client=aws_mag_con.client("cloudwatch", region)
    end_date=int(Today.strftime("%d"))
    end_month=int(Today.strftime("%m"))
    end_year=int(Today.strftime("%Y"))
    start_date=int(ninty_days_ago.strftime("%d"))
    start_month=int(ninty_days_ago.strftime("%m"))
    start_year=int(ninty_days_ago.strftime("%Y"))
    response = cloudwatch_client.get_metric_statistics(
            Namespace='AWS/DynamoDB',
            MetricName='ConsumedWriteCapacityUnits',
            Dimensions=[
                {
                'Name': 'TableName',
                'Value': table_name
                },
            ],
            StartTime=DT.datetime(start_year,start_month,start_date),
            EndTime=DT.datetime(end_year,end_month,end_date),
            Period=60*60*24*90,#1day=86400sec
            Statistics=[
                'Maximum'
            ],
            Unit='Count'
            )
    try:
        table_wcu=response['Datapoints'][0]['Maximum']
    except Exception as e:
        print(e)
        pass
    return table_wcu

def get_nat_gateway():
    for region in region_names:
        ec2_client = aws_mag_con.client('ec2', region)
        vpc={}
        paginator = ec2_client.get_paginator('describe_nat_gateways')
        response_iterator = paginator.paginate()
        for page in response_iterator:
            for each_nat in page['NatGateways']:
                cur_vpc=each_nat['VpcId']
                if cur_vpc in vpc:
                    vpc[cur_vpc].append(each_nat['SubnetId'])
                else:
                    vpc[cur_vpc]=[each_nat['SubnetId']]
        for item in vpc:
            if len(vpc[item])>1:
                response = ec2_client.describe_nat_gateways(Filters=[
                        {
                            'Name': 'subnet-id',
                            'Values': vpc[item]
                        }
                    ])
                for each_nat1 in response['NatGateways']:
                    subnet_id=each_nat1['SubnetId']
                    resource_arn=each_nat1['NatGatewayId']
                    subnet_response = ec2_client.describe_subnets(SubnetIds=[subnet_id])
                    azs=subnet_response['Subnets'][0]['AvailabilityZone']
                    idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':azs,'Resource':resource_arn,'Status':"Multiple NAT in single VPC",'Group':"NAT Gateway",'Action':'Route to single NAT Gateway'})
    
    print("Listing of NAT Gateway Completed")
   
def get_instances_latest_generation():
    for region in region_names:
        rds_client = aws_mag_con.client('rds', 'us-east-1')
        try:
            instance_paginator = rds_client.get_paginator('describe_db_instances')
            instance_response_iterator = instance_paginator.paginate()
            for page in instance_response_iterator:
                for each_instance in page['DBInstances']:
                    Engine_name=each_instance['Engine']                          
                    Instance_class=each_instance['DBInstanceClass']
                    resource_arn=each_instance['DBInstanceIdentifier']
                    Engine_version=each_instance['EngineVersion']
                    azs=each_instance['AvailabilityZone']
                    gen_response = rds_client.describe_orderable_db_instance_options(
                        Engine=Engine_name,
                        EngineVersion=Engine_version,
                        DBInstanceClass=Instance_class)
                    n=len(gen_response['OrderableDBInstanceOptions'])
                    for i in range(n):
                # print(resource_arn,gen_response)
                        if gen_response['OrderableDBInstanceOptions'][i]['DBInstanceClass']!=Instance_class:
                            idle_resources.append({'Cloud':'AWS','Region':region,'Availability Zone':azs,'Resource':resource_arn,'Status':"Old genration Instances",'Group':"RDS",'Action':'Upgrade Instances to latest generation'})
        except Exception as e:
            print(e)
            pass
    print("Listing of Old Generation Instances Completed")

      


#write list of idle resources to file
def write_to_file(idle):
    headers=['Cloud','Region','Availability Zone','Resource','Status','Group','Action']
    with open('preoptimization.csv','w')as f1:
        writer=csv.writer(f1)
        dictwriter=csv.DictWriter(f1,fieldnames=headers)
        writer.writerow(headers)
        for item in idle:
            dictwriter.writerow(item)
    print("Please find the complete report in file preoptimization.csv")

def fetch_all_eip_allocations():
    for region in region_names:
        client=aws_mag_con.client("ec2",region)
        response = client.describe_addresses()
        for eip in response['Addresses']:
            eip_allocations['ids'][eip['PublicIp']]=eip['AllocationId']
def fetch_all_elb():
    for region in region_names:
        client=aws_mag_con.client("elb",region)
        paginator = client.get_paginator('describe_load_balancers')
        response_iterator = paginator.paginate()
        for page in response_iterator:
            for load_balancer in page['LoadBalancerDescriptions']:
                #classic load balancer does not have arn so construct one
                arn="arn:aws:elasticloadbalancing:"+region+":"+account_id+":loadbalancer/"+load_balancer['LoadBalancerName']
                all_elb['ids'][load_balancer['LoadBalancerName']]={'arn':arn,'azs':load_balancer['AvailabilityZones']}
    
    for region in region_names:
        client=aws_mag_con.client("elbv2",region)
        paginator = client.get_paginator('describe_load_balancers')
        response_iterator = paginator.paginate()
        for page in response_iterator:
            for load_balancer in page['LoadBalancers']:
                all_elb['ids'][load_balancer['LoadBalancerName']]={'arn':load_balancer['LoadBalancerArn'],'azs':load_balancer['AvailabilityZones']}

def list_all_s3():
    s3_cli=aws_mag_con.client("s3")
    response=s3_cli.list_buckets()
    for bucket in response['Buckets']:
        response1 = s3_cli.get_bucket_location(Bucket=bucket['Name'])
        if response1['LocationConstraint']==None:
            region="us-east-1"
        else:
            region=response1['LocationConstraint']
        s3.append({'Name':bucket['Name'],'Region':region})

def get_regions():
    ec2_resource = aws_mag_con.resource('ec2','us-east-1')
    for each_item in ec2_resource.meta.client.describe_regions()['Regions']:
        region_names.append(each_item['RegionName'])

    
if __name__=='__main__':
    #get list of region names
    get_regions()
    #fetch all EIP allocations Id's based on their public Ip       
    fetch_all_eip_allocations()
    #fetch all elb and their availability zones
    fetch_all_elb()
    #fetch all s3 bucket name and their regions
    list_all_s3()
    main()
