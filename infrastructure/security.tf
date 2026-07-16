resource "aws_security_group" "trading_sg" {
  name        = "trading-agent-sg"
  description = "Security group for the trading agent EC2 instance"
  vpc_id      = aws_vpc.trading_vpc.id

  # Ingress rules (commented out for security; access via SSM port forwarding is recommended)
  # ingress {
  #   from_port   = 22
  #   to_port     = 22
  #   protocol    = "tcp"
  #   cidr_blocks = ["0.0.0.0/0"] # Change to your IP range
  #   description = "SSH Access"
  # }

  # ingress {
  #   from_port   = 5900
  #   to_port     = 5900
  #   protocol    = "tcp"
  #   cidr_blocks = ["0.0.0.0/0"] # Change to your IP range
  #   description = "VNC Access to IB Gateway GUI"
  # }

  # Ingress rule for Streamlit Web UI (commented out for security; uncomment to expose to public)
  # ingress {
  #   from_port   = 8501
  #   to_port     = 8501
  #   protocol    = "tcp"
  #   cidr_blocks = ["0.0.0.0/0"]
  #   description = "Streamlit Web UI Dashboard"
  # }

  # Egress: allow all outbound internet traffic (required for yfinance and Bedrock APIs)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "trading-agent-sg"
  }
}
