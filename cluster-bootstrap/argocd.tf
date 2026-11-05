# Managed Argo CD (EKS Capability). AWS runs Argo CD outside the cluster;
# sign-in is via IAM Identity Center.

data "aws_iam_policy_document" "argocd_assume" {
  count = var.enable_argocd ? 1 : 0

  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]

    principals {
      type        = "Service"
      identifiers = ["capabilities.eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "argocd_capability" {
  count = var.enable_argocd ? 1 : 0

  name               = "${local.name}-argocd-capability"
  assume_role_policy = data.aws_iam_policy_document.argocd_assume[0].json
}

resource "aws_eks_capability" "argocd" {
  count = var.enable_argocd ? 1 : 0

  cluster_name              = module.eks.cluster_name
  capability_name           = "argocd"
  type                      = "ARGOCD"
  role_arn                  = aws_iam_role.argocd_capability[0].arn
  delete_propagation_policy = "RETAIN"

  configuration {
    argo_cd {
      namespace = var.argocd_namespace

      aws_idc {
        idc_instance_arn = var.argocd_idc_instance_arn
        idc_region       = var.argocd_idc_region
      }

      dynamic "rbac_role_mapping" {
        for_each = var.argocd_admin_group_ids

        content {
          role = "ADMIN"

          identity {
            id   = rbac_role_mapping.value
            type = "SSO_GROUP"
          }
        }
      }
    }
  }

  lifecycle {
    precondition {
      condition     = var.argocd_idc_instance_arn != null
      error_message = "argocd_idc_instance_arn must be set when enable_argocd is true."
    }
  }

  depends_on = [module.eks]
}
