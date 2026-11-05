variable "prefix_name" {
  description = "Prefix used to name all resources (e.g. \"cia\")."
  type        = string
}

variable "region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "ap-southeast-1"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "kubernetes_version" {
  description = "EKS Kubernetes version."
  type        = string
  default     = "1.31"
}

variable "node_instance_types" {
  description = "Instance types for the default managed node group."
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_desired_size" {
  description = "Desired number of worker nodes."
  type        = number
  default     = 1
}

variable "node_min_size" {
  description = "Minimum number of worker nodes."
  type        = number
  default     = 1
}

variable "node_max_size" {
  description = "Maximum number of worker nodes."
  type        = number
  default     = 4
}

variable "enable_argocd" {
  description = "Enable the managed Argo CD EKS capability."
  type        = bool
  default     = true
}

variable "argocd_namespace" {
  description = "Kubernetes namespace for the Argo CD capability."
  type        = string
  default     = "argocd"
}

variable "argocd_idc_instance_arn" {
  description = "ARN of the IAM Identity Center instance used to sign in to Argo CD (required when enable_argocd = true)."
  type        = string
  default     = null
}

variable "argocd_idc_region" {
  description = "Region of the IAM Identity Center instance."
  type        = string
  default     = "eu-central-1"
}

variable "argocd_admin_group_ids" {
  description = "IAM Identity Center group IDs granted the Argo CD ADMIN role."
  type        = list(string)
  default     = []
}
