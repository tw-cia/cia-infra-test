terraform {
  required_version = ">= 1.10.0"

  # Backend blocks can't use variables, so these values are literal.
  # Each workspace is stored under env:/<workspace>/cluster-bootstrap/terraform.tfstate
  backend "s3" {
    bucket       = "cia-infra-storage"
    key          = "cluster-bootstrap/terraform.tfstate"
    region       = "ap-southeast-1"
    encrypt      = true
    use_lockfile = true # S3-native state locking (Terraform >= 1.10)
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.23"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Environment = local.environment
      Project     = var.prefix_name
      ManagedBy   = "terraform"
    }
  }
}
