import datetime
from json.decoder import JSONDecodeError
from logging import exception
from pathlib import Path
import os
from xlwt import Workbook
import json
from configparser import ConfigParser
import boto3
import sys
import botocore

config = ConfigParser()

wb = Workbook()

sheet1 = wb.add_sheet('Sheet 1')

Today = datetime.date.today()
month_ago = Today - datetime.timedelta(days=30)

j = 0

aws_mag_con=boto3.session.Session(profile_name="cpprod") 
ec2_resource = aws_mag_con.resource('ec2', 'us-east-1')

string1 = ['Host', 'instanceId', 'Region', 'private_ip', 'Network_out_sum', 'Type']

for item in string1:
    
    sheet1.write(0, j, item)
    j = j+1
    


def main(rootdir) :
    
    k = 0

    for path in Path(rootdir).iterdir():
        filename = os.path.join(rootdir, path)
        file2 = filename.split('/')[6]
        k = k+1
        sheet1.write(k , 0, file2)

        if path.is_dir():
        
            for file in Path(path).iterdir():
                    if os.path.splitext(file)[1] == ".json":
                    
                        filename1 = os.path.join(filename, file)
                        if filename1.split("/")[7] == "metadata.json":
                            with open(filename1, "r") as f:
                                        try:    
                                            data = json.load(f)
                                            region = data['region']
                                            instance_id = data['instanceId']
                                                
                                            if verify_spot(instance_id,region)==False:
                                                net_out_sum=get_network_out(instance_id,region)
                                                print(net_out_sum)
                                                sheet1.write(k, 1, instance_id )
                                                sheet1.write(k, 2, region)
                                                sheet1.write(k, 3, data['privateIp'])
                                                sheet1.write(k, 4, net_out_sum)

                                                      
                                                        
                                

                                        except(JSONDecodeError):
                                            continue

                                        except botocore.exceptions.ClientError:
                                                            error_code = sys.exc_info()[1].response['Error']['Code']
                                                            if error_code == 'InvalidInstanceID.NotFound':
                                                                pass                

                                        
                
                    if os.path.splitext(file)[1] == ".ini":
                        filename1 = os.path.join(filename, file)
                        if filename1.split("/")[7] == "player_1.ini":
                            cn = filename1.split("/")[6]
                            print(cn)
                            customer_name = cn.split("_")[0]
                            config.read(filename1)
                            if config.get('cloud_params','cloud_address').split(".")[0] == customer_name: 
                                    sheet1.write(k, 5, "PLAYER")    
                            else:
                                    sheet1.write(k, 5, "DD")

                
                                                                 

                                    

    wb.save('report_cpu_ut.xls') 


def verify_spot(instance_id,region):

    ec2 = aws_mag_con.client('ec2',region)
 
    response = ec2.describe_instances(
        Filters=[{
                'Name': 'instance-lifecycle',
                'Values': ['spot']
            }, 
        ]
        )
    # print(response)
    response=str(response)

    if instance_id in response:
        return True
    else:
        return False 

def get_network_out(instance_id,region):

    end_date=int(Today.strftime("%d"))
    end_month=int(Today.strftime("%m"))
    end_year=int(Today.strftime("%Y"))
    #get date of 7 days ago as start date
    start_date=int(month_ago.strftime("%d"))
    start_month=int(month_ago.strftime("%m"))
    start_year=int(month_ago.strftime("%Y"))

    cloudwatch_client=aws_mag_con.client("cloudwatch",region)
    response = cloudwatch_client.get_metric_statistics(
    Namespace='AWS/EC2',
    MetricName='NetworkOut',
    Dimensions=[
        {
        'Name': 'InstanceId',
        'Value': instance_id
        },
    ],
    StartTime=datetime.datetime(start_year,start_month,start_date),
    EndTime=datetime.datetime(end_year,end_month,end_date),
    Period=86400,
    Statistics=[
        'Sum',
    ],
    Unit='Bytes'
    )
    try:
        net_out_sum = response['Datapoints'][0]['Sum']
        return net_out_sum 
    except:
        pass                     
                                   
if __name__=='__main__':
    rootdir = '/home/trishal/Boto3/scripts/report/'
    main(rootdir)

  
