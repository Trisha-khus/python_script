import boto3
import csv
import sys
import time

old_replication_grp=""

def main(old_replication_grp,vpc_id):
    idle_resources=get_idle_resources_list()
    noncurrentversion_rule=[{
                'ID': 'DeletePreviousVersions',
                'Filter': {},
                'Status': 'Enabled',
                'NoncurrentVersionExpiration': {
                    'NoncurrentDays': 10
                    }
                }]
    multipartupload_rule=[{
        'ID': 'IncompleteUpload',
        'Filter': {},
        'Status': 'Enabled',
        'AbortIncompleteMultipartUpload': {
            'DaysAfterInitiation': 10
            }
        }]

    # S3 add lifecycle rule for deleting Incomplete multipartuploads
    for resource in idle_resources:
        region=resource['Region']
        resource_arn=resource['Resource']
        if resource['Group']=="S3 IncompleteUpload" and resource['Action']!="No Action":
            s3_add_lifecycle(resource_arn,multipartupload_rule)
    
    print("IncompleteUpload delete Lifecycle addition to S3 Buckets completed")

    # S3 add lifecycle rule for deleting Non current versions
    for resource in idle_resources:
        region=resource['Region']
        resource_arn=resource['Resource']

        if resource['Group']=="S3 DeletePreviousVersions" and resource['Action']!="No Action":
            s3_add_lifecycle(resource_arn,noncurrentversion_rule)
    
    print("DeletePreviousVersions Lifecycle addition to S3 Buckets completed")

    #Change cloudwatch logs retention to 7 days
    for resource in idle_resources:
        region=resource['Region']
        resource_arn=resource['Resource']

        if resource['Group']=="Cloudwatch Logs with retention>7days":
            put_new_retention(region,resource_arn)
    
    print("Cloudwatch logs retention changing to 7 days completed")

    #Delete unattached ebs
    for resource in idle_resources:
        region=resource['Region']
        resource_arn=resource['Resource']

        if resource['Group']=="Unattached EBS Volumes" and resource['Action']=="Delete":
            delete_ebs(region,resource_arn)
        
    print("Deletion of unattached EBS volumes completed")

    #Delete unassociated eip
    for resource in idle_resources:
        region=resource['Region']
        resource_arn=resource['Resource']
        
        if resource['Group']=="Unassociated EIP" and resource['Action']=="Delete":
            delete_eip(region,resource_arn)

    print("Deletion of Unassociated EIP completed")

    #Delete Idle elb
    for resource in idle_resources:
        region=resource['Region']
        resource_arn=resource['Resource']

        if resource['Group']=="Idle Load Balancers" and resource['Status']!='Low request count' and resource['Action']=="Delete":
            delete_load_balancer(region,resource_arn)
        
    print("Deletion of IDLE Load Balancers completed")

    #Delete Idle/Unused Medialive Inputs and channels
    for resource in idle_resources:
        region=resource['Region']
        resource_arn=resource['Resource']

        if (resource['Group']=='Medialive Unused Channel' or resource['Group']=='Medialive Idle Channels')and resource['Action']=="Delete":
            delete_medialive_channel(region,resource_arn)

    print("Deletion of IDLE Medialive Channels completed")
    
    #wait for a min to make sure medialive channels are deleted completely
    time.sleep(60)

    for resource in idle_resources:
        region=resource['Region']
        resource_arn=resource['Resource']  

        if (resource['Group']=="Medialive Detached Inputs" or resource['Group']=="Attached to IDLE Channel" or resource['Group']=='Medialive Unused Inputs') and resource['Action']=="Delete":
            delete_medialive_input(region,resource_arn)

    print("Deletion of IDLE Medialive Inputs completed")
    
    #convert on-demand asg to spot
    for resource in idle_resources:
        region=resource['Region']
        if resource['Status']=="on demand" and resource['Action']!="No Action":
            asg_name=resource['Resource'].split("/")[1]
            convert_to_spot(region,asg_name)
    print ("On-demand Auto scaling groups converted to Spot completed")

    #delete replica's in RDS,Elasticache,DocDb,MemoryDb
    for resource in idle_resources:
        if resource['Status']=="replica" and resource['Action']!="No Action":
            delete_replicas(resource)
    print("Deletion of replica Instances in RDS,DocDB,MemoryDB completed")
    
    for resource in idle_resources:
        if resource['Status']=="replica" and resource['Group']=="EC":
            try:
                ec_client = aws_mag_con.client('elasticache',region)
                replication_grp1=(resource['Resource'].split(":")[-1]).split("-")[:-1]
                replication_grp="-".join(replication_grp1)
                if resource['Action']=="delete replica":
                    if old_replication_grp!=replication_grp:
                        old_replication_grp=replication_grp
                        delete_replica_EC(region,replication_grp,ec_client)
                        
            except Exception as e:
                print(e)
                pass
    print("Deletion of replica Instances in ElastiCache Completed")
    
    for resource in idle_resources:
        region=resource['Region']
        if resource['Status']=="idle" and resource['Group']=="Mediaconnect":
            flow_arn= resource['Resource']
            med_con_client = aws_mag_con.client('mediaconnect', region)
            if resource['Action']=="Delete":
                try:
                    response = med_con_client.delete_flow(
                                FlowArn=flow_arn
                                )
                except Exception as e:
                    print(e)
                    pass
    print("Deletion of idle MediaConnect Flow completed")

    for resource in idle_resources:
        region=resource['Region']
        if resource['Status']=="Obsolete Snapshots" and resource['Group']=="EC2/Snapshots":
            snapshot_id=resource['Resource']
            ec2_client = aws_mag_con.client('ec2', region)
            if resource['Action']=="Delete Snapshots":
                try:
                    response = ec2_client.delete_snapshot(SnapshotId=snapshot_id)
                except Exception as e:
                    print(e)
                    pass
    print("Deletion of Obsolete Snapshots completed ")

    for resource in idle_resources:
        region=resource['Region']
        if resource['Status']=="Obsolete Images" and resource['Group']=="EC2/AMI":
            ami_id=  resource['Resource']
            ec2_client = aws_mag_con.client('ec2', region)
            if resource['Action']=="Delete AMI":
                try:
                    response = ec2_client.deregister_image(
                            ImageId=ami_id)
                except Exception as e:
                    print(e)
                    pass
    print("Deregistration of obsolete Images completed")

    for resource in idle_resources:
        region=resource['Region']
        if resource['Status']=="Idle RDS Instances" and resource['Group']=="RDS":
            instance_identifier=resource['Resource']
            rds_client = aws_mag_con.client('rds',region)
            if resource['Action']=="Delete RDS Instance":
                try:
                    response = rds_client.delete_db_instance(
                        DBInstanceIdentifier=instance_identifier)
                except Exception as e:
                    print(e)
                    pass
    print("Deletion of Idle RDS Instances completed")

    for resource in idle_resources:
        region=resource['Region']
        if resource['Status']=="Under utilised Dynamodb" and resource['Group']=="Dynamodb":
            table_name=resource['Resource'].split("/")[-1]
            db_client = aws_mag_con.client('dynamodb', region)
            if resource['Action']=="Auto Scale Dynamodb":
                auto_scale_table(db_client,table_name,region)

    print("auto scaling of Dynamodb completed" )

    for resource in idle_resources:
        region=resource['Region']
        if resource['Status']=="Multiple NAT in single VPC" and resource['Group']=="NAT Gateway":
            nat_id=resource['Resource']
            if resource['Action']=="Route to single NAT Gateway":
                ec2_client = aws_mag_con.client('ec2',region)
                ec2_response = ec2_client.describe_nat_gateways(
                    NatGatewayIds=[nat_id])
                cur_vpc_id=ec2_response['NatGateways'][0]['VpcId']
                if cur_vpc_id==vpc_id:
                            convert_to_single_nat(nat_id,ec2_client,cur_vpc_id)
                vpc_id=cur_vpc_id
    print("Converting multiple NAT in single VPC to Single NAT Completed")

def delete_replicas(resource):
    region=resource['Region']
    if resource['Status']=="replica" and resource['Group']=="RDS":
        cluster_name=resource['Resource']
        rds_client = aws_mag_con.client('rds',region)
        rds_response = rds_client.describe_db_clusters(Filters=[
                            {
                                'Name': 'db-cluster-id',
                                'Values': [cluster_name]
                            },
                        ],)
        n=len(rds_response['DBClusters'][0]['DBClusterMembers'])
        if resource['Action']=="delete replica":
            for i in range(0,n):
                if rds_response['DBClusters'][0]['DBClusterMembers'][i]['IsClusterWriter']==False:
                    reader_instance=rds_response['DBClusters'][0]['DBClusterMembers'][i]['DBInstanceIdentifier']
                    delete_replica_RDS(region,reader_instance,rds_client)

   
            
    elif resource['Status']=="replica" and resource['Group']=="DocDB":
        cluster_name=resource['Resource']
        try:
            docdb_client = aws_mag_con.client('docdb',region)
            docdb_response = docdb_client.describe_db_clusters(
                    Filters=[
                        {
                            'Name': 'db-cluster-id',
                            'Values': [cluster_name]
                            }
                    ]) 
            n=len(docdb_response['DBClusters'][0]['DBClusterMembers'])
            if resource['Action']=="delete replica":
                for i in range(0,n):
                    if docdb_response['DBClusters'][0]['DBClusterMembers'][i]['IsClusterWriter']==False:
                        reader_instance=docdb_response['DBClusters'][0]['DBClusterMembers'][i]['DBInstanceIdentifier']
                        delete_replica_Docdb(region,reader_instance,docdb_client)
        except Exception as e:
            print(e)


    elif resource['Status']=="replica" and resource['Group']=="MemDB":
        cluster_name=resource['Resource'].split("/")[-1]
        memdb_client = aws_mag_con.client('memorydb', region)
        if resource['Action']=="delete replica":
            delete_replica_Memdb(region,cluster_name,memdb_client)   


def delete_medialive_channel(region,medialve_ch_arn):
    ch_id=medialve_ch_arn.split(":")[-1]
    client=aws_mag_con.client("medialive",region)
    try:
        response = client.delete_channel(
        ChannelId=ch_id
        )
    except Exception as e:
        print(f"Deletion of Medialive Channel {medialve_ch_arn} failed Because,")
        print(e)

def delete_medialive_input(region,medialive_inp_arn):
    inp_id=medialive_inp_arn.split(":")[-1]
    client=aws_mag_con.client("medialive",region)
    try:
        response = client.delete_input(
        InputId=inp_id
        )
    except Exception as e:
        print(f"Deletion of Medialive Input {medialive_inp_arn} failed Because,")
        print(e)

def delete_load_balancer(region,load_balancer_arn):
    client=aws_mag_con.client("elbv2",region)
    try:
        response = client.delete_load_balancer(LoadBalancerArn=load_balancer_arn)   
    except:
        try:
            load_balancer_name=load_balancer_arn.split("loadbalancer/")[-1]
            #classic load balancer deletion
            client=aws_mag_con.client("elb",region)
            response = client.delete_load_balancer(LoadBalancerName=load_balancer_name)
        except Exception as e:
            print(f"Deletion of ELB {load_balancer_arn} failed Because,")
            print(e)        
    
def s3_add_lifecycle(bucket_arn,lifecycle_rule):
    bucket_name=bucket_arn.split(":")[-1]
    client=aws_mag_con.client("s3")
    try:
        response = client.get_bucket_lifecycle_configuration(
        Bucket=bucket_name)
        response['Rules'].append(lifecycle_rule[0])
        new_rule=response['Rules'] 
        response = client.put_bucket_lifecycle_configuration(
        Bucket=bucket_name,
        LifecycleConfiguration={
                'Rules': new_rule
        },
        )
    except:
        try:
            response = client.put_bucket_lifecycle_configuration(
            Bucket=bucket_name,
            LifecycleConfiguration={
                    'Rules': lifecycle_rule
            },
            )
        except Exception as e:
            print(f"Updation of S3 {bucket_arn} failed Because,")
            print(e)


def delete_eip(region,addressarn):
    address=addressarn.split(":")[-1]
    client=aws_mag_con.client("ec2",region)
    try:
        response = client.release_address(AllocationId=address)
    except Exception as e:
        print(f"Deletion of EIP {addressarn} failed, Because,")
        print(e)
            
def delete_ebs(region,volumearn):
    volumeid=volumearn.split(":")[-1]
    client=aws_mag_con.client("ec2",region)
    try:
        response = client.delete_volume(VolumeId=volumeid)
    except Exception as e:
        print(f"Deletion of EBS {volumearn} failed, Because,")
        print(e)

     
def put_new_retention(region,log_arn):
    log_name=log_arn.split(":")[-2]
    client=aws_mag_con.client("logs",region)
    try:
        response = client.put_retention_policy(logGroupName=log_name,retentionInDays=7)
    except Exception as e:
        print(f"Updation of log {log_arn} failed Because,")
        print(e)
       
def convert_to_spot(row,region,status):            
    try:
        if row!="":
            if status=="on demand":
                asg_name=row['Resource'].split("/")[1]
                asg_client = aws_mag_con.client('autoscaling', region)
                asg_response = asg_client.update_auto_scaling_group(
                    AutoScalingGroupName=asg_name,
                    MixedInstancesPolicy={
                        'InstancesDistribution':{
                            'OnDemandPercentageAboveBaseCapacity': 0
                        }
                    })
        
    except Exception as e:
        print(f"Conversion of on-demand {asg_name} to spot failed, Because")
        print(e)
        

def delete_replica_RDS(region,reader_instance,rds_client):
    try:
        rds_instance_response = rds_client.delete_db_instance(
        DBInstanceIdentifier=reader_instance,
        SkipFinalSnapshot=True)
    except Exception as e:
        print(f"RDS replica {reader_instance} deletion failed, Because")
        print(e)
        
            
def delete_replica_EC(region,reader_instance,ec_client):
    try:
        multiaz_response = ec_client.modify_replication_group(
                    ReplicationGroupId=reader_instance,
                    MultiAZEnabled=False,
                    AutomaticFailoverEnabled=False,
                    ApplyImmediately=True)
        time.sleep(90)

        ec_response=ec_client.decrease_replica_count(
                ReplicationGroupId=reader_instance,
                NewReplicaCount=0,
                ApplyImmediately=True)

        
    except Exception as e:
        print(f"Elasticache replica {reader_instance} deletion failed, Because")
        print(e)
        

def delete_replica_Docdb(region,reader_instance,docdb_client):
    try:
        docdb_instance_response = docdb_client.delete_db_instance(
        DBInstanceIdentifier=reader_instance)
    except Exception as e:
        print(f"DocDB replica {reader_instance} deletion failed, Because")
        print(e)
        
def delete_replica_Memdb(region,cluster_name,memdb_client):
    try:
        memdb_response = memdb_client.update_cluster(
                                ClusterName=cluster_name,
                                ReplicaConfiguration={
                                    'ReplicaCount': 1
                                }
                )
    except Exception as e:
        print(f"MemoryDB replica of {cluster_name} deletion failed, Because")
        print(e)
        
def auto_scale_table(db_client,table_name,region):
    db_response = db_client.update_table(
    TableName=table_name,
    BillingMode='PROVISIONED',
    ProvisionedThroughput={
        'ReadCapacityUnits': 1,
        'WriteCapacityUnits': 1
    }
    )
    
    db1_client = aws_mag_con.client('application-autoscaling', region)
    target_rd_response = db1_client.register_scalable_target(
    ServiceNamespace='dynamodb',
    ResourceId='table/'+table_name,
    ScalableDimension='dynamodb:table:ReadCapacityUnits',
    MinCapacity=1,
    MaxCapacity=10
    )

    target_wr_response = db1_client.register_scalable_target(
    ServiceNamespace='dynamodb',
    ResourceId='table/'+table_name,
    ScalableDimension='dynamodb:table:WriteCapacityUnits',
    MinCapacity=1,
    MaxCapacity=10
    )
    
    read_response = db1_client.put_scaling_policy(
        PolicyName=table_name+'-scaling-policy',
        ServiceNamespace='dynamodb',
        ResourceId='table/'+table_name,
        ScalableDimension='dynamodb:table:ReadCapacityUnits',
        PolicyType='TargetTrackingScaling',
        TargetTrackingScalingPolicyConfiguration={
        'TargetValue': 70,
        'PredefinedMetricSpecification': {
            'PredefinedMetricType': 'DynamoDBReadCapacityUtilization'
            }
        }
        )

    write_response = db1_client.put_scaling_policy(
        PolicyName=table_name+'-scaling-policy',
        ServiceNamespace='dynamodb',
        ResourceId='table/'+table_name,
        ScalableDimension='dynamodb:table:WriteCapacityUnits',
        PolicyType='TargetTrackingScaling',
        TargetTrackingScalingPolicyConfiguration={
        'TargetValue': 70.0,
        'PredefinedMetricSpecification': {
            'PredefinedMetricType': 'DynamoDBWriteCapacityUtilization'
            }
        }
        )

def convert_to_single_nat(nat_id,ec2_client,cur_vpc_id):
    subnet_list=[]
    nat_list={}
    try:
        subnet_response = ec2_client.describe_subnets(
                Filters=[
                    {
                        'Name': 'vpc-id',
                        'Values': [cur_vpc_id]
                    }
                ]
                )
        for each_subnet in subnet_response['Subnets']:
            subnet_list.append(each_subnet['SubnetId'])
        for subnet_id in subnet_list:
            route_table_response = ec2_client.describe_route_tables(
                    Filters=[
                        {
                            'Name': 'association.subnet-id',
                            'Values': [subnet_id]
                        }
                    ]
            )
            if route_table_response['RouteTables']!=[]:
                try:
                    for i in range(len(route_table_response['RouteTables'][0]['Routes'])):
                        try:
                            nat_id=route_table_response['RouteTables'][0]['Routes'][i]['NatGatewayId']
                            if nat_id in nat_list:
                                nat_list[nat_id].append(route_table_response['RouteTables'][0]['Associations'][0]['RouteTableId'])
                            else:
                                nat_list[nat_id]=route_table_response['RouteTables'][0]['Associations'][0]['RouteTableId']
                            # nat_list.append(route_table_response['RouteTables'][0]['Routes'][i]['NatGatewayId'])
                        except Exception as e:
                            print(e)
                            continue
                except Exception as e:
                            print(e)
                            continue
 
        for each_nat in nat_list:
            if each_nat==nat_id:
                route_response = ec2_client.replace_route(
                DestinationCidrBlock='0.0.0.0/0',
                NatGatewayId=cur_nat,
                RouteTableId=nat_list[each_nat])
                del_nat_response = ec2_client.delete_nat_gateway(NatGatewayId=each_nat)
            else:
                cur_nat=each_nat
    except Exception as e:
        print(e)
        pass


def get_idle_resources_list():
    with open('preoptimization.csv','r')as f1:
        reader = csv.DictReader(f1)
        idle_resources=list(reader)
        return idle_resources

if __name__=='__main__':
    old_replication_grp=""
    vpc_id=""
    aws_mag_con=boto3.session.Session(profile_name=sys.argv[1])
    main(old_replication_grp,vpc_id)
