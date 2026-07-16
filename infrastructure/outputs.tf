output "vpc_id" {
  value       = aws_vpc.trading_vpc.id
  description = "The ID of the VPC"
}

output "subnet_id" {
  value       = aws_subnet.public_subnet.id
  description = "The ID of the Subnet"
}

output "instance_id" {
  value       = aws_instance.trading_instance.id
  description = "The ID of the EC2 Instance"
}

output "instance_public_ip" {
  value       = aws_instance.trading_instance.public_ip
  description = "The public IP of the EC2 Instance"
}

output "ssm_connect_command" {
  value       = "aws ssm start-session --target ${aws_instance.trading_instance.id}"
  description = "Command to connect to the instance securely using AWS SSM Session Manager"
}

output "ssm_vnc_forward_command" {
  value       = "aws ssm start-session --target ${aws_instance.trading_instance.id} --document-name AWS-StartPortForwardingSession --parameters --% \"{\\\"portNumber\\\":[\\\"5900\\\"],\\\"localPortNumber\\\":[\\\"5900\\\"]}\""
  description = "Command to port-forward the IB Gateway VNC graphical interface to your local computer"
}

output "ssm_dashboard_forward_command" {
  value       = "aws ssm start-session --target ${aws_instance.trading_instance.id} --document-name AWS-StartPortForwardingSession --parameters --% \"{\\\"portNumber\\\":[\\\"8501\\\"],\\\"localPortNumber\\\":[\\\"8501\\\"]}\""
  description = "Command to port-forward the Streamlit Web UI dashboard to your local computer"
}
