terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}
provider "aws" {
  region = var.region
  default_tags { tags = { Project = "TradingAgents-CN", ManagedBy = "Terraform" } }
}
variable "region" {
  type    = string
  default = "ap-northeast-3"
}
variable "name" {
  type    = string
  default = "tradingagents"
}
variable "instance_type" {
  type    = string
  default = "t3.large"
}
variable "ssh_public_key_path" {
  type        = string
  description = "Path to your SSH public key, not the private key."
}
variable "admin_cidr" {
  type        = string
  description = "Your public IPv4 with /32, allowed to access SSH."
  validation {
    condition     = can(cidrnetmask(var.admin_cidr)) && endswith(var.admin_cidr, "/32")
    error_message = "Provide one IPv4 address with /32."
  }
}
data "aws_availability_zones" "available" { state = "available" }
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}
resource "aws_vpc" "app" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_hostnames = true
  tags                 = { Name = var.name }
}
resource "aws_subnet" "app" {
  vpc_id            = aws_vpc.app.id
  cidr_block        = "10.42.1.0/24"
  availability_zone = data.aws_availability_zones.available.names[0]
}
resource "aws_internet_gateway" "app" { vpc_id = aws_vpc.app.id }
resource "aws_route_table" "app" {
  vpc_id = aws_vpc.app.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.app.id
  }
}
resource "aws_route_table_association" "app" {
  subnet_id      = aws_subnet.app.id
  route_table_id = aws_route_table.app.id
}
resource "aws_security_group" "app" {
  name_prefix = "${var.name}-"
  vpc_id      = aws_vpc.app.id
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_key_pair" "app" {
  key_name_prefix = "${var.name}-"
  public_key      = file(pathexpand(var.ssh_public_key_path))
}
resource "aws_instance" "app" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  subnet_id                   = aws_subnet.app.id
  vpc_security_group_ids      = [aws_security_group.app.id]
  associate_public_ip_address = true
  key_name                    = aws_key_pair.app.key_name
  user_data_replace_on_change = true
  user_data = templatefile("${path.module}/bootstrap.sh.tftpl", {
    compose_b64 = filebase64("${path.module}/compose.yaml")
    nginx_b64   = filebase64("${path.module}/../../nginx/nginx.conf")
  })
  root_block_device {
    volume_size           = 80
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = false
  }
  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }
  dynamic "credit_specification" {
    for_each = startswith(var.instance_type, "t3") ? [1] : []
    content { cpu_credits = "standard" }
  }
  tags       = { Name = var.name }
  depends_on = [aws_route_table_association.app]
  lifecycle {
    prevent_destroy = true
    # Bootstrap runs only on first boot; deploy application updates over SSH.
    ignore_changes = [ami, user_data]
  }
}
resource "aws_eip" "app" {
  domain   = "vpc"
  instance = aws_instance.app.id
}
output "public_ip" { value = aws_eip.app.public_ip }
output "ssh_tunnel" {
  value = "ssh -i <private-key-path> -N -L 8080:127.0.0.1:80 ubuntu@${aws_eip.app.public_ip}"
}
output "web_url" { value = "http://${aws_eip.app.public_ip}" }
