# kcl test ./... -- mirrors scripts/tests/test_iamrole.py's level of
# coverage (no CFR/behaviour test suite exists for IAMRole anywhere in this
# repo yet -- see tests/test_equivalence.py's docstring). Runs directly
# against composeIamRole() instead -- no Docker, no render.
import json
import iamrole

irByName = lambda items: [{str:any}] -> {str:{str:any}} {
    {item["metadata"]["annotations"]["krm.kcl.dev/composition-resource-name"]: item for item in items if "metadata" in item}
}

irComposite = lambda items: [{str:any}] -> {str:any} {
    [item for item in items if not ("metadata" in item)][0]
}

irOxr = lambda spec: {str:any} -> {str:any} {
    {"spec": spec, "status": {}}
}

test_composes_role_and_policy_attachments = lambda {
    spec = {
        "roleName": "laz-lambda-example-role"
        "description": "Example Lambda execution role"
        "trustedService": "lambda.amazonaws.com"
        "managedPolicyArns": ["arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"]
    }
    items = iamrole.composeIamRole(irOxr(spec), {})
    byName = irByName(items)

    role = byName["role"]
    assert role.metadata.annotations["crossplane.io/external-name"] == "laz-lambda-example-role"
    assert role.spec.forProvider.description == "Example Lambda execution role"
    assumeRolePolicy = json.decode(role.spec.forProvider.assumeRolePolicy)
    assert assumeRolePolicy.Statement[0].Principal == {"Service": "lambda.amazonaws.com"}
    assert assumeRolePolicy.Statement[0].Action == "sts:AssumeRole"

    attachment = byName["policy-attachment-0"]
    assert attachment.spec.forProvider.policyArn == "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
    assert attachment.spec.forProvider.role == "laz-lambda-example-role"
}

test_role_name_matches_spec = lambda {
    spec = {"roleName": "totally-different-role-name", "trustedService": "lambda.amazonaws.com"}
    items = iamrole.composeIamRole(irOxr(spec), {})
    role = irByName(items)["role"]
    assert role.metadata.annotations["crossplane.io/external-name"] == "totally-different-role-name"
}

test_omits_policy_attachments_when_no_managed_policy_arns = lambda {
    spec = {"roleName": "laz-lambda-example-role", "trustedService": "lambda.amazonaws.com"}
    items = iamrole.composeIamRole(irOxr(spec), {})
    byName = irByName(items)
    assert sorted([k for k in byName]) == ["role"]
}

test_does_not_surface_role_arn_when_role_not_yet_observed = lambda {
    spec = {"roleName": "laz-lambda-example-role", "trustedService": "lambda.amazonaws.com"}
    items = iamrole.composeIamRole(irOxr(spec), {})
    composite = irComposite(items)
    assert composite.status == {}
}

test_surfaces_role_arn_once_known = lambda {
    spec = {"roleName": "laz-lambda-example-role", "trustedService": "lambda.amazonaws.com"}
    ocds = {
        "role": {
            "Resource": {
                "status": {
                    "atProvider": {"arn": "arn:aws:iam::123456789012:role/laz-lambda-example-role"}
                }
            }
        }
    }
    items = iamrole.composeIamRole(irOxr(spec), ocds)
    composite = irComposite(items)
    assert composite.status.roleArn == "arn:aws:iam::123456789012:role/laz-lambda-example-role"
}
