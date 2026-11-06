# IAM role for the Crossplane AWS family providers, assumed via EKS Pod
# Identity (not IRSA/OIDC). Starting with AdministratorAccess since
# provider-aws-iam needs to manage IAM resources itself, which
# PowerUserAccess explicitly denies.

resource "aws_iam_role" "crossplane_providers" {
  name = "${local.name}-crossplane-providers"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "pods.eks.amazonaws.com"
        }
        Action = ["sts:AssumeRole", "sts:TagSession"]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "crossplane_providers_admin" {
  role       = aws_iam_role.crossplane_providers.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

# Each provider's ServiceAccount name is pinned via a DeploymentRuntimeConfig
# (serviceAccountTemplate.metadata.name in manifests/crossplane-providers),
# so these names are stable across provider version bumps -- no more
# ProviderRevision hash to track.
locals {
  crossplane_provider_service_accounts = [
    "provider-aws-s3",
    "provider-aws-iam",
    "provider-aws-lambda",
    "provider-aws-cloudfront",
    "provider-aws-route53",
  ]
}

resource "aws_eks_pod_identity_association" "crossplane_providers" {
  for_each = toset(local.crossplane_provider_service_accounts)

  cluster_name    = module.eks.cluster_name
  namespace       = "crossplane-system"
  service_account = each.value
  role_arn        = aws_iam_role.crossplane_providers.arn
}
