import boto3
import csv

session = boto3.Session(profile_name='300584868574')

regions = []
ec2_cli = session.client('ec2', 'us-east-1')

ec2_response = ec2_cli.describe_regions()
for region in ec2_response['Regions']:
    regions.append(region['RegionName'])
# csv_fields=["resource_arn"]
with open("list_untagged_volume.csv", 'w') as f:
        # csvwriter = csv.DictWriter(csvfile, delimiter=',', 
        #                     fieldnames="")
        csvwriter = csv.writer(f)
        # csvwriter.writeheader()
f.close()

def main():
    for region in regions:
        list_resources=[]
        #print (region)
        client=boto3.client("resourcegroupstaggingapi",region)
        paginator = client.get_paginator('get_resources')
        response_iterator = paginator.paginate(
            ResourceTypeFilters=[
                "ec2:volume"
    ],
        )
        for page in response_iterator:
            for resource in page['ResourceTagMappingList']:
                tag_list=[]
                for tag in resource['Tags']:
                    tag_list.append(tag['Key'])
                    resource_arn = resource['ResourceARN']
                if "AMGID" in tag_list:
                    pass
                else:
                    list_resources.append(resource['ResourceARN'])
                    with open("list_untagged_volume.csv", 'a') as wfile: 
                        wfile.write(resource_arn +"\n")
                    wfile.close()
    
         #print(list_resources)
    tag_volume()

def tag_volume():
    with open('list_untagged_volume.csv') as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        for item in csv_reader:
            volume_id = item[0].split("/")[1]
            region = item[0].split(":")[3]
            # print(region,volume_id)
            ec2_cli=session.client('ec2', region)
            try:
                vol_response = ec2_cli.describe_volumes(VolumeIds=[volume_id])
                if vol_response['Volumes'][0]['Attachments'] !=[]:
                    instance_id = vol_response['Volumes'][0]['Attachments'][0]['InstanceId']
                    ec2_response=ec2_cli.describe_instances(InstanceIds=[instance_id])
                    for ins_tag in ec2_response['Reservations'][0]['Instances'][0]['Tags']:
                        if ins_tag['Key']=="AMGID":
                            amgid=ins_tag['Value']
                            ec2_re= session.resource('ec2', region)
                            tag_volume = ec2_re.Volume(volume_id)
                            tag_response = tag_volume.create_tags(
                                Tags=[
                            {
                                'Key': 'AMGID',
                                'Value': amgid
                            },
                            ]
                            )
                            print("{} is tagged with {} which is attached to {} present in {}".format(volume_id,amgid,instance_id,region))
                        else:
                            continue
                else:
                    continue
            except Exception as e:
                #print(e)
                pass

if __name__=='__main__':
    main()
    

        

        
        
