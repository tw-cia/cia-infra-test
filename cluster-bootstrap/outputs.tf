output "environment" {
  description = "Environment (current Terraform workspace)."
  value       = local.environment
}

output "vpc_id" {
  value = module.vpc.vpc_id
}

output "private_subnet_ids" {
  value = module.vpc.private_subnets
}

output "public_subnet_ids" {
  value = module.vpc.public_subnets
}

output "nat_public_ips" {
  value = module.vpc.nat_public_ips
}

output "cluster_name" {
  value = module.eks.cluster_name
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "configure_kubectl" {
  description = "Command to configure kubectl for this cluster."
  value       = "aws eks update-kubeconfig --region ${var.region} --name ${module.eks.cluster_name}"
}

output "argocd_server_url" {
  description = "URL of the managed Argo CD server."
  value       = one(aws_eks_capability.argocd[*].configuration[0].argo_cd[0].server_url)
}

output "github_actions_role_arn" {
  description = "ARN of the IAM role assumable by GitHub Actions on the trusted repo's main branch."
  value       = aws_iam_role.github_actions.arn
}

output "readonly_role_arn" {
  description = "ARN of the read-only IAM role (AWS ReadOnlyAccess + EKS view)."
  value       = aws_iam_role.readonly.arn
}
