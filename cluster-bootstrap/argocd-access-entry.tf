# The ARGOCD capability auto-creates an EKS access entry for its IAM role,
# with no Kubernetes RBAC groups attached (confirmed via the authenticator
# logs: real requests authenticate with groups=[]). AWS's managed access
# policies (AmazonEKSArgoCDClusterPolicy/Policy) cover some permissions
# through a separate mechanism, but not the cluster-wide read access Argo CD
# needs for resource discovery. Bring that pre-existing access entry under
# Terraform management to assign it a Kubernetes group, which the ClusterRole
# binding in argocd-rbac.tf grants read access to.
#
# The access entry itself already exists (created by the capability), so it
# must be imported rather than created:
#   terraform import 'aws_eks_access_entry.argocd_capability[0]' \
#     "${local.name}:${aws_iam_role.argocd_capability[0].arn}"

resource "aws_eks_access_entry" "argocd_capability" {
  count = var.enable_argocd ? 1 : 0

  cluster_name  = module.eks.cluster_name
  principal_arn = aws_iam_role.argocd_capability[0].arn
  type          = "STANDARD"

  kubernetes_groups = [
    "argocd-capability-role",
  ]

  depends_on = [aws_eks_capability.argocd]
}
