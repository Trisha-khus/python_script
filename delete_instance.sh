#!/bin/bash
INPUT_FILE='instancelist.csv'
IFS=','

read -p "Enter the profile name: " profile

while read instance_id region
do
echo "Instance_id: $instance_id"
echo "Region: $region"

aws ec2 describe-instance-attribute --region $region --instance-id $instance_id --attribute disableApiTermination --profile $profile

check=$(echo $?)

echo $check


if [ $check -eq 0 ]; then

  state=$(aws ec2 describe-instances --query "Reservations[*].Instances[*].[State.Name]" --o text --instance-id $instance_id --region $region --profile $profile)
  echo "INSTANCE STATE: $state"

  if [[ "$state" == "stopped" ]]; then

    echo "Disabling api termination protection"
    aws ec2 modify-instance-attribute --region $region --instance-id $instance_id --no-disable-api-termination --profile $profile
    
    eip=$(aws ec2 --region $region --profile $profile describe-instances --filters "Name=instance-state-name,Values=stopped" "Name=instance-id,Values=$instance_id" --query 'Reservations[*].Instances[*].[PublicIpAddress]' --output text)
    
    echo "EIP : $eip"

    volumeid=$(aws ec2 --region $region --profile $profile describe-instances --filters "Name=instance-state-name,Values=stopped" "Name=instance-id,Values=$instance_id" --query 'Reservations[*].Instances[*].BlockDeviceMappings[1].Ebs.VolumeId' --output text)
    
    echo "vOLUME ID: $volumeid"
    
    
    if [ "$eip" ]; then
      allocationid=$(aws ec2 describe-addresses  --public-ips $eip --profile $profile --region $region  --query 'Addresses[*].AllocationId' --output text)
    else
      echo "No EIP found"
    fi

    echo "AllocationID : $allocationid"

    echo "Terminating instance $instance_id "
    aws ec2 terminate-instances --region $region --instance-id $instance_id --profile $profile

    check1=$(echo $?)

    if [ $check1 -eq 0 ]; then

      echo "Terminated instance $instance_id" >> terminationlist.log

      sleep 5
    
      if [ "$volumeid" ]; then
    
        aws ec2 delete-volume --volume-id $volumeid --region $region --profile $profile
      fi
    
      if [ "$allocationid" ]; then
    
        aws ec2 release-address --region $region --allocation-id $allocationid --profile $profile
    
      fi   
    fi

  else
    echo "Keep the instance $instance_id in stopped state to terminate"
  fi

else
  echo "counldn't delete instance..may does not exist"
fi
done < $INPUT_FILE

