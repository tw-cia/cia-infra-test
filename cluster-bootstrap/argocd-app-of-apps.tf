# Root Argo CD Application that syncs everything under manifests/apps.
# Applied only after the Argo CD capability (which installs the Application
# CRD), the repo credentials and the in-cluster target exist.

resource "kubectl_manifest" "app_of_apps" {
  count = var.enable_argocd ? 1 : 0

  yaml_body = file("${path.module}/../manifests/apps/app-of-apps.yaml")

  depends_on = [
    aws_eks_capability.argocd,
    kubernetes_secret_v1.argocd_repo,
    kubernetes_secret_v1.argocd_in_cluster,
    kubernetes_config_map_v1.argocd_cm,
  ]
}
