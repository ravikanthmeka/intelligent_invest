variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "The target AWS region for deployment"
}

variable "vpc_cidr" {
  type        = string
  default     = "10.0.0.0/16"
  description = "CIDR block for the trading system VPC"
}

variable "subnet_cidr" {
  type        = string
  default     = "10.0.1.0/24"
  description = "CIDR block for the public subnet"
}

variable "instance_type" {
  type        = string
  default     = "t3.small"
  description = "EC2 Instance type (t3.small recommended to support JVM-based IB Gateway and Python agents)"
}

variable "repo_url" {
  type        = string
  default     = "https://github.com/your-username/intelligent_invest.git"
  description = "The Git repository URL of your trading system"
}
