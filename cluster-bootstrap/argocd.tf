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

resource "kubernetes_config_map_v1" "argocd_cm" {
  count = var.enable_argocd ? 1 : 0

  metadata {
    name      = "argocd-cm"
    namespace = var.argocd_namespace

    labels = {
      "app.kubernetes.io/name"    = "argocd-cm"
      "app.kubernetes.io/part-of" = "argocd"
    }
  }

  data = {
    "ui.bannercontent" = "CIA Infra Test v1.0"
    "application.resourceTrackingMethod" = "annotation"
    "resource.exclusions" = <<-EOT
      - apiGroups:
        - "*"
        kinds:
        - ProviderConfigUsage
      - apiGroups:
        - admissionregistration.k8s.io
        kinds:
        - MutatingAdmissionPolicy
        - MutatingAdmissionPolicyBinding
      - apiGroups:
        - resource.k8s.io
        kinds:
        - "*"
    EOT

    "resource.customizations" = <<-EOT
      "*.upbound.io/*":
        health.lua: |
          health_status = {
            status = "Progressing",
            message = "Provisioning ..."
          }

          local function contains (table, val)
            for i, v in ipairs(table) do
              if v == val then
                return true
              end
            end
            return false
          end

          local has_no_status = {
            "ClusterProviderConfig",
            "ProviderConfig",
            "ProviderConfigUsage"
          }

          if obj.status == nil or next(obj.status) == nil and contains(has_no_status, obj.kind) then
            health_status.status = "Healthy"
            health_status.message = "Resource is up-to-date."
            return health_status
          end

          if obj.status == nil or next(obj.status) == nil or obj.status.conditions == nil then
            if (obj.kind == "ProviderConfig" or obj.kind == "ClusterProviderConfig") and obj.status.users ~= nil then
              health_status.status = "Healthy"
              health_status.message = "Resource is in use."
              return health_status
            end
            return health_status
          end

          for i, condition in ipairs(obj.status.conditions) do
            if condition.type == "LastAsyncOperation" then
              if condition.status == "False" then
                health_status.status = "Degraded"
                health_status.message = condition.message
                return health_status
              end
            end

            if condition.type == "Synced" then
              if condition.status == "False" then
                health_status.status = "Degraded"
                health_status.message = condition.message
                return health_status
              end
            end

            if condition.type == "Ready" then
              if condition.status == "True" then
                health_status.status = "Healthy"
                health_status.message = "Resource is up-to-date."
              end
            end
          end

          return health_status

      "*.crossplane.io/*":
        health.lua: |
          health_status = {
            status = "Progressing",
            message = "Provisioning ..."
          }

          local function contains (table, val)
            for i, v in ipairs(table) do
              if v == val then
                return true
              end
            end
            return false
          end

          local has_no_status = {
            "Composition",
            "CompositionRevision",
            "DeploymentRuntimeConfig",
            "ClusterProviderConfig",
            "ProviderConfig",
            "ProviderConfigUsage"
          }
          if obj.status == nil or next(obj.status) == nil and contains(has_no_status, obj.kind) then
              health_status.status = "Healthy"
              health_status.message = "Resource is up-to-date."
            return health_status
          end

          if obj.status == nil or next(obj.status) == nil or obj.status.conditions == nil then
            if (obj.kind == "ProviderConfig" or obj.kind == "ClusterProviderConfig") and obj.status.users ~= nil then
              health_status.status = "Healthy"
              health_status.message = "Resource is in use."
              return health_status
            end
            return health_status
          end

          for i, condition in ipairs(obj.status.conditions) do
            if condition.type == "LastAsyncOperation" then
              if condition.status == "False" then
                health_status.status = "Degraded"
                health_status.message = condition.message
                return health_status
              end
            end

            if condition.type == "Synced" then
              if condition.status == "False" then
                health_status.status = "Degraded"
                health_status.message = condition.message
                return health_status
              end
            end

            if condition.type == "Installed" then
              if condition.status == "False" then
                health_status.status = "Degraded"
                health_status.message = condition.message
                return health_status
              end
            end

            if contains({"Ready", "Healthy", "Offered", "Established", "ValidPipeline", "RevisionHealthy"}, condition.type) then
              if condition.status == "True" or (condition.type == "Established" and condition.reason == "InactiveManagedResource") then
                health_status.status = "Healthy"
                health_status.message = "Resource is up-to-date."
              end
            end
          end

          return health_status
    EOT
  }

  depends_on = [aws_eks_capability.argocd]
}
