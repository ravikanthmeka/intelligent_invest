data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

resource "aws_instance" "trading_instance" {
  ami                  = data.aws_ami.amazon_linux_2023.id
  instance_type        = var.instance_type
  subnet_id            = aws_subnet.public_subnet.id
  vpc_security_group_ids = [aws_security_group.trading_sg.id]
  iam_instance_profile = aws_iam_instance_profile.trading_agent_profile.name

  # Bootstrapping script
  user_data = templatefile("${path.module}/templates/userdata.sh", {
    repo_url   = var.repo_url
    aws_region = var.aws_region
  })

  root_block_device {
    volume_size           = 30
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }

  tags = {
    Name = "trading-agent-instance"
  }
}
