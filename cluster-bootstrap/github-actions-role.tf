# IAM role assumable (via GitHub OIDC) only by workflows running on the
# main branch of the configured repository. The org uses immutable OIDC
# subject claims (repo:<org>@<org-id>/<repo>@<repo-id>:ref:...), so the IDs
# are part of the trust condition.

locals {
  github_oidc_url = "https://token.actions.githubusercontent.com"
}

# An account can only have one OIDC provider per URL. Set
# github_oidc_provider_arn to reuse one that already exists (and in all but
# one workspace sharing the same account).
resource "aws_iam_openid_connect_provider" "github" {
  count = var.github_oidc_provider_arn == null ? 1 : 0

  url            = local.github_oidc_url
  client_id_list = ["sts.amazonaws.com"]
}

locals {
  github_oidc_provider_arn = coalesce(
    var.github_oidc_provider_arn,
    try(aws_iam_openid_connect_provider.github[0].arn, null),
  )
}

resource "aws_iam_role" "github_actions" {
  name = "${local.name}-github-actions"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Federated = local.github_oidc_provider_arn }
        Action    = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
            # Jobs using `environment:` get an environment sub instead of a
            # ref sub, so trust both. Restrict the environment's deployment
            # branches to main (and required reviewers) in the repo settings.
            "token.actions.githubusercontent.com:sub" = [
              "repo:${var.github_org}@${var.github_org_id}/${var.github_repo}@${var.github_repo_id}:ref:refs/heads/main",
              "repo:${var.github_org}@${var.github_org_id}/${var.github_repo}@${var.github_repo_id}:environment:${var.github_environment}",
            ]
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "github_actions" {
  for_each = toset(var.github_actions_policy_arns)

  role       = aws_iam_role.github_actions.name
  policy_arn = each.value
}

# Cluster-admin inside Kubernetes for the GitHub Actions role (EKS access
# entry, not aws-auth). Kubernetes API access is separate from the IAM
# policies above.
resource "aws_eks_access_entry" "github_actions" {
  cluster_name  = module.eks.cluster_name
  principal_arn = aws_iam_role.github_actions.arn
}

resource "aws_eks_access_policy_association" "github_actions_admin" {
  cluster_name  = module.eks.cluster_name
  principal_arn = aws_eks_access_entry.github_actions.principal_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }
}
