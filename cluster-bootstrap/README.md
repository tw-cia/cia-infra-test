# cluster-bootstrap

Creates a VPC (2 public + 2 private subnets, 2 NAT gateways) and an EKS cluster using the
`terraform-aws-modules/vpc/aws` and `terraform-aws-modules/eks/aws` modules.

## Inputs
- `prefix_name` (required) – resource name prefix
- `region` – AWS region (default `us-east-1`)
- Environment = the Terraform **workspace**; resources are named `<prefix_name>-<workspace>`.

## Usage
```sh
terraform init
terraform workspace new dev      # or: terraform workspace select dev
terraform apply -var-file=environments/dev.tfvars
```

Per-environment inputs live in `environments/<workspace>.tfvars`. To add one, copy
`dev.tfvars` to e.g. `prod.tfvars`, adjust values, then
`terraform workspace new prod && terraform apply -var-file=environments/prod.tfvars`.
