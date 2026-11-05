# The Argo CD capability's EKS access entry grants no Kubernetes RBAC by
# default (least privilege). AWS's managed access policies cover write access
# to the argocd namespace and application namespaces, but not the cluster-wide
# read access Argo CD needs to discover and health-check arbitrary resource
# types for its resource cache. Every EKS access entry is implicitly bound to
# a Kubernetes group named "eks-access-entry:<principal-arn>", so grant that
# group read-only access to everything instead of chasing individual missing
# resource kinds.

resource "kubernetes_cluster_role_v1" "argocd_read_all" {
  count = var.enable_argocd ? 1 : 0

  metadata {
    name = "argocd-read-all"
  }

  rule {
    api_groups = ["*"]
    resources  = ["*"]
    verbs      = ["get", "list", "watch"]
  }
}

resource "kubernetes_cluster_role_binding_v1" "argocd_read_all" {
  count = var.enable_argocd ? 1 : 0

  metadata {
    name = "argocd-read-all"
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = kubernetes_cluster_role_v1.argocd_read_all[0].metadata[0].name
  }

  subject {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Group"
    name      = "eks-access-entry:${aws_iam_role.argocd_capability[0].arn}"
  }
}
