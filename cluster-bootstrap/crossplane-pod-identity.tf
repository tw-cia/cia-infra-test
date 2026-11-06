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

# Each Crossplane provider gets its own ServiceAccount, named after its
# ProviderRevision (e.g. "provider-aws-s3-<hash>"). That hash is derived
# from the package digest, so it's stable as long as the pinned version in
# manifests/crossplane-providers doesn't change, but it WILL change on the
# next version bump -- check `kubectl get sa -n crossplane-system` and
# update these names when upgrading a provider.
locals {
  crossplane_provider_service_accounts = [
    "provider-aws-s3-63d4b64062f4",
    "provider-aws-iam-d17ce2593cf0",
    "provider-aws-lambda-b7fd61963371",
  ]
}

resource "aws_eks_pod_identity_association" "crossplane_providers" {
  for_each = toset(local.crossplane_provider_service_accounts)

  cluster_name    = module.eks.cluster_name
  namespace       = "crossplane-system"
  service_account = each.value
  role_arn        = aws_iam_role.crossplane_providers.arn
}
