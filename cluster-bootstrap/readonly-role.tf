# Read-only role: ReadOnlyAccess across AWS plus view-only access to the EKS
# cluster's Kubernetes API (AmazonEKSViewPolicy -- no secrets, no writes).

data "aws_caller_identity" "current" {}

resource "aws_iam_role" "readonly" {
  name = "${local.name}-readonly"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        # Defaults to this account's root, i.e. any principal in the account
        # that is itself allowed to call sts:AssumeRole on this role.
        Principal = {
          AWS = coalescelist(
            var.readonly_trusted_principal_arns,
            ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"],
          )
        }
        Action = "sts:AssumeRole"
      },
      {
        # GitHub Actions (OIDC) from this repo on any ref (PRs, branches).
        # Safe because the role is read-only; the sub uses the org's
        # immutable-claim format, same as the github-actions role.
        Effect    = "Allow"
        Principal = { Federated = local.github_oidc_provider_arn }
        Action    = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:${var.github_org}@${var.github_org_id}/${var.github_repo}@${var.github_repo_id}:*"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "readonly" {
  role       = aws_iam_role.readonly.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

resource "aws_eks_access_entry" "readonly" {
  cluster_name  = module.eks.cluster_name
  principal_arn = aws_iam_role.readonly.arn
}

resource "aws_eks_access_policy_association" "readonly_view" {
  cluster_name  = module.eks.cluster_name
  principal_arn = aws_eks_access_entry.readonly.principal_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSViewPolicy"

  access_scope {
    type = "cluster"
  }
}
