import os
import json
from configparser import ConfigParser
import boto3
import csv
import sys
from pathlib import Path
import datetime as DT


dates_list=[]#list of 3 days dates
region_names=[]
instances_list=[]
today = DT.date.today()
day_one= today - DT.timedelta(days=3)
day_two= today - DT.timedelta(days=2)
day_three=today - DT.timedelta(days=1)
dates_list.append(day_one)
dates_list.append(day_two)
dates_list.append(day_three)

config = ConfigParser()


def parse_configs_and_get_instance_meta(conn,rootdir):
    Instances_data=[]
    Instances_data.append(['InstanceID','Region','Type'])
    
    instance = region =  ""
    
    for dir in Path(rootdir).iterdir():
        if dir.is_dir():
            flag_ini = flag_json = False
            for file in Path(dir).iterdir():
                #if file has .json extension
                if os.path.basename(file) == "metadata.json":
                    instance = region  = ""
                    instance, region = data_from_json(file)
                    flag_json = True
                #if file has .ini extension
                if os.path.basename(file) == "player_1.ini":
                    instance_type=""
                    instance_type = data_from_ini(file)
                    flag_ini = True

                
                if flag_json and flag_ini:
                    instance_valid=instance_exists(instance,region)
                    if instance_valid==True:
                        Instances_data.append([instance,region,instance_type])
                    flag_json = flag_ini = False


    cpu_lessthan_20(conn,Instances_data)

def instance_exists(instance,region):
    ec2_client = conn.client('ec2', region_name=region)

    try:
        response = ec2_client.describe_instance_status(InstanceIds=[instance])
        if response['InstanceStatuses'][0]['InstanceState']['Name']=="running":
            return True
        else:
            return False
    except :
        return False
        
def cpu_lessthan_20(conn,Instances_data):
    Instances_data=Instances_data[1:]
    for instance in Instances_data:
        #print(instance)
        cpu_p99_values=get_cpu_statistics(conn,instance[0],instance[1])
        count=0
        for value in cpu_p99_values:
            if float(value)<20:
                count=count+1
                
        if count==3:
            instances_list.append({'Instance ID':instance[0],'Region':instance[1],'Type':instance[2],'CPUUtilization ('+str(day_one)+')':cpu_p99_values[0],'CPUUtilization ('+str(day_two)+')':cpu_p99_values[1],'CPUUtilization ('+str(day_three)+')':cpu_p99_values[2]})

            #print(instances_list)
    headerList=['Instance ID','Region','Type','CPUUtilization ('+str(day_one)+')','CPUUtilization ('+str(day_two)+')','CPUUtilization ('+str(day_three)+')']
    with open('Instances_comp_new.csv','w', newline='\n') as f1:
        writer=csv.writer(f1)
        dictwriter=csv.DictWriter(f1,fieldnames=headerList)
        writer.writerow(headerList)
        for item in instances_list:
            dictwriter.writerow(item)

def get_cpu_statistics(conn,instance_id,region):
    #get today date to be passed as end date
    end_date=int(today.strftime("%d"))
    end_month=int(today.strftime("%m"))
    end_year=int(today.strftime("%Y"))
    #get date of 3 days ago as start date
    start_date=int(day_one.strftime("%d"))
    start_month=int(day_one.strftime("%m"))
    start_year=int(day_one.strftime("%Y"))

    #retreives CPU utilization of instance with extended statistics p99
    cloudwatch_client=conn.client("cloudwatch",region)
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
        'p99',
    ],
    Unit='Percent'
    )
    
    p99_values=[-1]*3
        
    #store p99 value of 3 days to array
    i=0
    #print(response)
    while i<3:
        try:
            date_match=response['Datapoints'][i]['Timestamp']
            pos=get_pos(date_match)
            p99_values[pos]=(str(response['Datapoints'][i]['ExtendedStatistics']['p99']))
        except:
            pass

        i=i+1
    p99_values = [str(x) for x in p99_values]
    return p99_values

def get_pos(date_match):
    
    date_match=date_match.date()
    #print(date_match)
    if date_match in dates_list:
        pos=dates_list.index(date_match)
        return pos
  

def data_from_ini(file):
    #fetch foldername which is customer name
    customer_name = os.path.split(file)[-2].split("/")[-1]
    #if cloud_address from file customername.amagi.tv has matching customername it is player otherwise DD
    config.read(file)
    if config.get('cloud_params','cloud_address').split(".")[0] == customer_name.split("_")[0]:
        instance_type="PLAYER"
    else:
        instance_type="DD"

    return instance_type

def data_from_json(file):
    data = json.load(open(file))
    region = data['region'] 
    instance = data['instanceId']
    return instance, region


def get_connection():
    return boto3.session.Session(profile_name=sys.argv[1])


conn = get_connection()
parse_configs_and_get_instance_meta(conn,sys.argv[2])
