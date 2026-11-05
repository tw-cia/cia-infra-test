# Registers this EKS cluster as Argo CD's "in-cluster" deploy target.
# The managed capability runs outside the cluster, so unlike self-hosted
# Argo CD it has no implicit local-cluster entry; it must be registered by
# EKS cluster ARN, same as any other target cluster.

resource "kubernetes_secret_v1" "argocd_in_cluster" {
  count = var.enable_argocd ? 1 : 0

  metadata {
    name      = "in-cluster"
    namespace = var.argocd_namespace

    labels = {
      "argocd.argoproj.io/secret-type" = "cluster"
    }
  }

  data = {
    name    = "in-cluster"
    server  = module.eks.cluster_arn
    project = "default"
  }

  depends_on = [aws_eks_capability.argocd]
}
