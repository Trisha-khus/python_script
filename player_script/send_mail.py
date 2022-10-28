import json
from configparser import ConfigParser
import boto3
import os
import smtplib
import socket
import datetime as DT
import sys
import csv
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from os.path import basename
from email.encoders import encode_base64
import traceback
import logging

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh = logging.FileHandler('/tmp/mailer.log')
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(fh)

msgsubject="Player and DD CPU Utilization Report"
msgtxt="Please find the attached report of player and DD,\nwhose CPU Utilization is less than 20% for last 3 consecutive days"
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


def parse_configs_and_get_instance_meta(folders,conn):
    Instances_data=[]
    Instances_data.append(['InstanceID','Region','Type'])
    for folder in folders:
        instance = region = instance_type= ""
        json_file=folder+"/metadata.json"
        ini_file=folder+"/player_1.ini"
        try:
            file1 = s3_cli.get_object(Bucket=sys.argv[2], Key=json_file)
        except Exception as e:
            continue
            
        contents1 = file1['Body'].read()
        instance, region=data_from_json(contents1)
        try:
            file2 = s3_cli.get_object(Bucket=sys.argv[2], Key=ini_file)
            instance_type=data_from_ini(file2,folder)
        except Exception as e:
            continue
        instance_valid,instance_name,instance_size=instance_exists(instance,region)
        if instance!="" and instance_valid==True:    
            Instances_data.append([instance_name,instance,instance_size,region,instance_type])

    instances_list=cpu_lessthan_20(conn,Instances_data)
    headerList=['Instance Name','Instance ID','Instance size','Region','Type','CPUUtilization ('+str(day_one)+')','CPUUtilization ('+str(day_two)+')','CPUUtilization ('+str(day_three)+')']
    outfile1="player_dd_cpu<20.csv"
    with open(outfile1,'w', newline='\n') as f1:
        writer=csv.writer(f1)
        dictwriter=csv.DictWriter(f1,fieldnames=headerList)
        writer.writerow(headerList)
        for item in instances_list:
            dictwriter.writerow(item)
    if len(instances_list)>1:
        send_mail(msgsubject, msgtxt, outfile1)

def cpu_lessthan_20(conn,Instances_data):
    Instances_data=Instances_data[1:]
    for instance in Instances_data:
        #print(instance)
        cpu_p99_values=get_cpu_statistics(conn,instance[1],instance[3])
        count=0
        for value in cpu_p99_values:
            if float(value)<20:
                count=count+1
                
        if count==3:
            instances_list.append({'Instance Name':instance[0],'Instance ID':instance[1],'Instance size':instance[2],'Region':instance[3],'Type':instance[4],'CPUUtilization ('+str(day_one)+')':cpu_p99_values[0],'CPUUtilization ('+str(day_two)+')':cpu_p99_values[1],'CPUUtilization ('+str(day_three)+')':cpu_p99_values[2]})
    
    return instances_list

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
  

def data_from_ini(contents,folder):
    config.read_string(contents['Body'].read().decode())
    if config.get('cloud_params','cloud_address').split(".")[0] == folder.split("_")[0]: 
        instance_type="PLAYER"
    else:
        instance_type="DD"

    return instance_type

def data_from_json(contents):
    data = json.loads(contents.decode("utf-8"))
    region = data['region'] 
    instance = data['instanceId']
    return instance, region

def instance_exists(instance,region):
    ec2_client = conn.client('ec2', region_name=region)
    instance_name = instance_size = ""
    try:
        response = ec2_client.describe_instances(InstanceIds=[instance])
        if response['Reservations'][0]['Instances'][0]['State']['Name']=="running":
            for tag in response['Reservations'][0]['Instances'][0]['Tags']:
                if tag['Key']=='Name':
                    instance_name=tag['Value']
                    break
            instance_size=response['Reservations'][0]['Instances'][0]['InstanceType']
            return True,instance_name,instance_size
        else:
            return False,"",""
    except :
        return False, "", ""

def send_mail (msgsubject, msgtxt, outfile1=''):

    config_file= "/var/lib/jenkins/scripts/Player_DD_CPUUtilization_Monitoring/mailer.cfg"          
    config = ConfigParser()
    config.read(config_file)
    error=0

    msg = MIMEMultipart('mixed')
    msg['Subject'] = msgsubject
    msg['From'] = config.get("mail","mail_from")
    if (not msg['From'] or msg['From']==None or msg['From']==''):
        logger.error ("From address not defined to send mail. Check mail configurations.")
        error=1

    msg.preamble = msgtxt

    if config.get("mail","mail_enable")=='1':
        for j in config.get("mail","mail_to").split(','):
            msg.add_header('To', j)
    else:
        return

    if (not msg.get_all('To') or msg.get_all('To')==None or msg.get_all('To')==['']): 
        logger.error ("No recipients found to send mail. Check mail configurations.")
        error=1
    email_content = """
                    <head>
                      <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
                      <title>html title</title>
                      <style type="text/css" media="screen">
                      table, th, td {
                      border: 1px solid black;
		      border-collapse: collapse;
                      }       
                      </style>
                    </head>
                    <body>
                      %s
                    </body>
                    """ % msgtxt

    msg.attach(MIMEText(email_content, 'HTML'))

    ## Attach the file outfile1
    if os.path.isfile(outfile1):
        part1 = MIMEBase('application', "octet-stream")
        part1.set_payload(open(outfile1, "rb").read())
        encode_base64(part1)
        part1.add_header('Content-Disposition', 'attachment; filename="%s"' % basename(outfile1))
        msg.attach(part1)
    
    mail_host=config.get("mail","mail_host")
    mail_port=config.get("mail","mail_port")
    mail_user=config.get("mail","mail_user")
    mail_pass=config.get("mail","mail_pass")

    if error == 0 :
        try:
            s=smtplib.SMTP(mail_host,mail_port)
            s.starttls()
        except socket.error:
            logger.error ("Socket error when trying to connect to SMTP server. Check mail configurations.")
            return
        except:
            logger.error ("Error connecting to SMTP server. Check mail configurations.")
            return

        try:
            s.login(mail_user, mail_pass)
        except smtplib.SMTPAuthenticationError:
            s.quit()
            logger.error ("Authentication error. Could not send mail. Check mail configurations.")
            return
        try:
            s.sendmail(msg['From'], msg.get_all('To'), msg.as_string())
        except:
            s.quit()
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logger.error ("Error sending mail. Check mail configurations." )
            logger.error(traceback.format_exception(exc_type, exc_value, exc_traceback))
            return

def get_connection():
    return boto3.session.Session(profile_name=sys.argv[1]) #300584868574

folders=[]
conn = get_connection()
s3_cli = conn.client('s3')
paginator = s3_cli.get_paginator('list_objects_v2')
result = paginator.paginate(Bucket=sys.argv[2])
for page in result:
    if "Contents" in page:
        for key in page[ "Contents" ]:
            keyString = key[ "Key" ].split("/")[0]
            folders.append(keyString)

#remove duplicates
folders=list(set(folders))
parse_configs_and_get_instance_meta(folders,conn)
