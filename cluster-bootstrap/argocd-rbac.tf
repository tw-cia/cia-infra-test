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
    name      = "argocd-capability-role"
  }
}

# AWS's AmazonEKSArgoCDPolicy (namespace-scoped to argocd) does not cover
# patch/update on Argo's own CRs, so the controller can reconcile but can
# never write status back onto Application/AppProject/ApplicationSet
# objects in its own namespace. Confirmed via kube-apiserver audit logs:
# "cannot patch resource \"applications\" in API group \"argoproj.io\" in
# the namespace \"argocd\"".

resource "kubernetes_role_v1" "argocd_self_write" {
  count = var.enable_argocd ? 1 : 0

  metadata {
    name      = "argocd-self-write"
    namespace = var.argocd_namespace
  }

  rule {
    api_groups = ["argoproj.io"]
    resources  = ["applications", "applicationsets", "appprojects"]
    verbs      = ["get", "list", "watch", "create", "update", "patch", "delete"]
  }

  depends_on = [aws_eks_capability.argocd]
}

resource "kubernetes_role_binding_v1" "argocd_self_write" {
  count = var.enable_argocd ? 1 : 0

  metadata {
    name      = "argocd-self-write"
    namespace = var.argocd_namespace
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = kubernetes_role_v1.argocd_self_write[0].metadata[0].name
  }

  subject {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Group"
    name      = "argocd-capability-role"
  }
}
