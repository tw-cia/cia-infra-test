# Least-privilege write access for the laz-testing Application's
# destination namespace. CreateNamespace=true needs cluster-scope create on
# Namespace itself; everything else Argo CD deploys into laz-testing needs
# full mutate rights scoped to that one namespace. Add one block like this
# per destination namespace rather than granting cluster-admin.

resource "kubernetes_cluster_role_v1" "argocd_create_namespace" {
  count = var.enable_argocd ? 1 : 0

  metadata {
    name = "argocd-create-namespace"
  }

  rule {
    api_groups = [""]
    resources  = ["namespaces"]
    verbs      = ["get", "create"]
  }
}

resource "kubernetes_cluster_role_binding_v1" "argocd_create_namespace" {
  count = var.enable_argocd ? 1 : 0

  metadata {
    name = "argocd-create-namespace"
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = kubernetes_cluster_role_v1.argocd_create_namespace[0].metadata[0].name
  }

  subject {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Group"
    name      = "argocd-capability-role"
  }
}

resource "kubernetes_namespace_v1" "laz_testing" {
  count = var.enable_argocd ? 1 : 0

  metadata {
    name = "laz-testing"
  }
}

resource "kubernetes_role_v1" "argocd_deploy_laz_testing" {
  count = var.enable_argocd ? 1 : 0

  metadata {
    name      = "argocd-deploy"
    namespace = kubernetes_namespace_v1.laz_testing[0].metadata[0].name
  }

  rule {
    api_groups = ["*"]
    resources  = ["*"]
    verbs      = ["*"]
  }
}

resource "kubernetes_role_binding_v1" "argocd_deploy_laz_testing" {
  count = var.enable_argocd ? 1 : 0

  metadata {
    name      = "argocd-deploy"
    namespace = kubernetes_namespace_v1.laz_testing[0].metadata[0].name
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = kubernetes_role_v1.argocd_deploy_laz_testing[0].metadata[0].name
  }

  subject {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Group"
    name      = "argocd-capability-role"
  }
}
