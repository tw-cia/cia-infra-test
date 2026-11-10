# Inputs for the "dev" workspace.
# Usage: terraform workspace select dev && terraform apply -var-file=environments/dev.tfvars

prefix_name = "cia"
region      = "ap-southeast-1"

vpc_cidr            = "10.0.0.0/16"
kubernetes_version  = "1.37"
node_instance_types = ["t3.medium"]
node_desired_size   = 2
node_min_size       = 1
node_max_size       = 4

# Managed Argo CD capability (requires an IAM Identity Center instance)
enable_argocd = true
argocd_idc_instance_arn = "arn:aws:sso:::instance/ssoins-69871294d6700676"
argocd_idc_region      = "eu-central-1"
argocd_admin_group_ids = ["e3944862-6071-705c-e5ac-0ca278d57524"]
argocd_repo_url = "https://github.com/tw-cia/cia-infra-test"
argocd_github_app_id = "5625212"
argocd_github_app_installation_id = "180077008"
argocd_github_app_private_key_path = "./cia-test-argocd.2026-11-05.private-key.pem"
