# Argo CD repository credentials, authenticated with a GitHub App.
# Argo CD discovers repositories from Secrets labelled secret-type=repository.

resource "kubernetes_secret_v1" "argocd_repo" {
  count = var.enable_argocd ? 1 : 0

  metadata {
    name      = "argocd-repo-github-app"
    namespace = var.argocd_namespace

    labels = {
      "argocd.argoproj.io/secret-type" = "repository"
    }
  }

  data = {
    type                    = "git"
    url                     = var.argocd_repo_url
    githubAppID             = var.argocd_github_app_id
    githubAppInstallationID = var.argocd_github_app_installation_id
    githubAppPrivateKey     = file(var.argocd_github_app_private_key_path)
  }

  lifecycle {
    precondition {
      condition = alltrue([
        var.argocd_repo_url != null,
        var.argocd_github_app_id != null,
        var.argocd_github_app_installation_id != null,
        var.argocd_github_app_private_key_path != null,
      ])
      error_message = "argocd_repo_url, argocd_github_app_id, argocd_github_app_installation_id and argocd_github_app_private_key must be set when enable_argocd is true."
    }
  }

  depends_on = [aws_eks_capability.argocd]
}
