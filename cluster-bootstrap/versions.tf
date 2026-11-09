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
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.35"
    }
    kubectl = {
      source  = "gavinbunney/kubectl"
      version = ">= 1.14"
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

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name, "--region", var.region]
  }
}

# kubectl_manifest (unlike kubernetes_manifest) doesn't need the CRD at plan
# time, so the Argo CD Application can be created in the same apply that
# installs Argo CD.
provider "kubectl" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
  load_config_file       = false

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name, "--region", var.region]
  }
}
