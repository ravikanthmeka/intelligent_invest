resource "aws_iam_role" "trading_agent_role" {
  name = "trading-agent-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

# Attach SSM Managed Instance policy
resource "aws_iam_role_policy_attachment" "ssm_policy" {
  role       = aws_iam_role.trading_agent_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Bedrock Inline Policy
resource "aws_iam_role_policy" "bedrock_policy" {
  name = "trading-agent-bedrock-policy"
  role = aws_iam_role.trading_agent_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:Converse",
          "bedrock:ConverseStream",
          "bedrock:ListFoundationModels",
          "bedrock:GetFoundationModel"
        ]
        Resource = "*"
      }
    ]
  })
}

# Instance profile
resource "aws_iam_instance_profile" "trading_agent_profile" {
  name = "trading-agent-ec2-profile"
  role = aws_iam_role.trading_agent_role.name
}
