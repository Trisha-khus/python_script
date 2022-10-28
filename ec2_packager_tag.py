import boto3
import jmespath
import datetime,pytz
from tabulate import tabulate

aws_mag_con=boto3.session.Session(profile_name="300584868574") #300584868574/cpdevelop
ec2_resource = aws_mag_con.resource('ec2','us-east-1')
#get list of region names
region_names=[]
for each_item in ec2_resource.meta.client.describe_regions()['Regions']:
    region_names.append(each_item['RegionName'])
table=[['Account','InstanceId','InstanceName','InstanceSize','State','AZ','AMGID','Tag','AgeOfInstance(Hours)']]

def find_age(launch_date):

    date1=launch_date
    now=datetime.datetime.now()
    date2=pytz.utc.localize(now)
    
    #print(date1)
    
    #print(date2)
    
    diff = date2 - date1
    days, seconds = diff.days, diff.seconds
    hours = days * 24 + seconds // 3600
    #print(f"Age of Instance: {hours} Hours")

    
    
    return hours



def main():
    
    print("Instance details with tag key:k8s.io/cluster-autoscaler/node-template/label/role value:packager which is older than 24 Hours")
    #print(region_names)
    #print("[OwnerID,  InstanceId,  InstanceType,  State,   AZ,   Name,    Key:k8s.io/cluster-autoscaler/node-template/label/role]  ")
    for region in region_names:
        ec2 = aws_mag_con.client('ec2',region)
        paginator = ec2.get_paginator('describe_instances')
        ec2_pages=paginator.paginate()
        for page in ec2_pages:
            myData = jmespath.search("Reservations[].Instances[].[NetworkInterfaces[0].OwnerId, InstanceId, [Tags[?Key=='Name'].Value] [0][0], InstanceType, State.Name, Placement.AvailabilityZone,[Tags[?Key=='AMGID'].Value] [0][0],[Tags[?Key=='k8s.io/cluster-autoscaler/node-template/label/role'].Value] [0][0]]", page)
            #print(f"Number of Instances in region {region}:{len(myData)}")
          
            i=0
            
            while i<len(myData):
                if myData[i][7]=='packager' or myData[i][7]=='Packager':
                    list1=[]            
                    #print(myData[i])
                    
                    response=ec2.describe_instances(
                        InstanceIds=[
                            myData[i][1]
                        ]
                    )
                    launch_date=response['Reservations'][0]['Instances'][0]['LaunchTime']
                   
                    age=find_age(launch_date)
                    if age>24:
                        list1=myData[i]
                        list1.append(age)
                        table.append(list1)
                        #print(table)

                  
                    #print(list1)
                else:
                    pass
                
                i=i+1

if __name__=='__main__':
    main()
    table2=tabulate(table, headers='firstrow', tablefmt='grid')
    print(table2)

