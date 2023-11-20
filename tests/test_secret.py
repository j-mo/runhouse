import os

import pytest

import runhouse as rh
from runhouse.resources.blobs import file
from runhouse.resources.secrets.utils import load_config

test_secret_values = {"secret_key": "secret_val"}


def assert_delete_local(secret, contents: bool = False):
    secret.delete(contents=contents) if contents else secret.delete()
    with pytest.raises(Exception) as e:
        rh.secret(name=secret.name)
        assert isinstance(e, Exception)
    if contents and secret.path:
        assert not os.path.exists(os.path.expanduser(secret.path))


# ------- BASE/CUSTOM SECRETS TEST ------- #


@pytest.mark.localtest
def test_create_delete_secret_from_name_local():
    secret_name = "~/custom_secret"
    local_secret = rh.secret(name=secret_name, values=test_secret_values).save()
    del local_secret

    reloaded_secret = rh.secret(name=secret_name)
    assert reloaded_secret.values == test_secret_values

    assert_delete_local(reloaded_secret)


@pytest.mark.rnstest
def test_create_secret_from_name_vault():
    secret_name = "vault_secret"
    vault_secret = rh.secret(name=secret_name, values=test_secret_values).save()
    del vault_secret

    reloaded_secret = rh.secret(name=secret_name)
    assert reloaded_secret.values == test_secret_values

    assert_delete_local(reloaded_secret)


@pytest.mark.clustertest
def test_secret_to(ondemand_cpu_cluster):
    secret_name = "test_secret"
    secret = rh.secret(name=secret_name, values=test_secret_values)

    secret.to(ondemand_cpu_cluster)
    remote_secret = ondemand_cpu_cluster.get(secret_name)
    assert remote_secret.values == test_secret_values

    assert_delete_local(secret)


# ------- PROVIDER SECRETS TEST ------- #


def test_error_multiple_truths():
    provider = "custom_provider"
    path = "~/custom_provider/config.json"
    with pytest.raises(Exception) as e:
        rh.provider_secret(provider=provider, path=path, values=test_secret_values)
        assert isinstance(e, Exception)


@pytest.mark.rnstest
def test_custom_provider_secret():
    provider = "custom_provider1"
    custom_secret = rh.provider_secret(provider=provider, values=test_secret_values)

    path = "~/.rh/tests/custom_provider/config.json"
    custom_secret = custom_secret.write(path=path)
    assert custom_secret.values == test_secret_values
    assert os.path.exists(os.path.expanduser(path))

    custom_secret.save()
    assert load_config(provider)

    del custom_secret
    reloaded_secret = rh.provider_secret(name=provider)
    assert reloaded_secret.values == test_secret_values

    assert_delete_local(reloaded_secret, contents=True)
    assert not reloaded_secret.in_vault()


# Provider Secrets
gcp_secret_values = {
    "client_id": "test_client_id",
    "client_secret": "test_client_secret",
}

aws_secret_values = {
    "access_key": "test_access_key",
    "secret_key": "test_secret_key",
}

azure_secret_values = {"subscription_id": "test_subscription_id"}
lambda_secret_values = {"api_key": "test_api_key"}
github_secret_values = {"oauth_token": "test_oauth_token"}
huggingface_secret_values = {"token": "test_token"}

ssh_secret_values = {
    "public_key": "test_public_key",
    "private_key": "test_private_key",
}

provider_params = [
    ("aws", "credentials", aws_secret_values),
    ("gcp", "credentials.json", gcp_secret_values),
    ("azure", "clouds.config", azure_secret_values),
    ("lambda", "lambda_key", lambda_secret_values),
    ("github", "hosts.yml", github_secret_values),
    ("huggingface", "token", huggingface_secret_values),
    ("ssh", "id_rsa", ssh_secret_values),
    ("sky", "sky-key", ssh_secret_values),
]


@pytest.mark.parametrize("provider,path,values", provider_params)
def test_local_provider_secrets(provider, path, values):
    test_path = os.path.join("~/.rh/tests", path)
    test_name = "_" + provider
    provider_secret = rh.provider_secret(
        name=test_name, provider=provider, values=values
    )
    provider_secret.write(path=test_path)
    assert os.path.exists(os.path.expanduser(test_path))

    local_secret = rh.provider_secret(name=test_name, provider=provider, path=test_path)
    assert local_secret.values == values

    delete_contents = provider not in ["ssh", "sky"]
    assert_delete_local(local_secret, contents=delete_contents)


@pytest.mark.rnstest
@pytest.mark.parametrize("provider,path,values", provider_params)
def test_vault_provider_secrets(provider, path, values):
    test_name = "_" + provider
    rh.provider_secret(name=test_name, provider=provider, values=values).save()

    reloaded_secret = rh.provider_secret(name=test_name)
    assert reloaded_secret.values == values

    delete_contents = provider not in ["ssh", "sky"]
    assert_delete_local(reloaded_secret, contents=delete_contents)
    assert not reloaded_secret.in_vault()


@pytest.mark.clustertest
@pytest.mark.parametrize("provider,path,values", provider_params)
def test_provider_secret_to_cluster(provider, path, values, ondemand_cpu_cluster):
    test_path = os.path.join("~/.rh/tests", path)
    test_name = "_" + provider
    local_secret = rh.provider_secret(name=test_name, provider=provider, values=values)
    remote_secret = local_secret.to(ondemand_cpu_cluster, path=test_path)

    assert remote_secret.path.system == ondemand_cpu_cluster
    assert remote_secret.values == local_secret.values
    assert remote_secret.path.exists_in_system()

    delete_contents = provider not in ["ssh", "sky"]
    remote_secret.delete(contents=delete_contents)
    assert_delete_local(local_secret, contents=delete_contents)


# ------- ENV VAR SECRETS TEST ------- #
env_var_map = {
    "ENV_VAR1": "env_value",
    "ENV_VAR2": "env_value2",
}


def _get_env_var_value(env_var):
    import os

    return os.environ[env_var]


@pytest.mark.rnstest
def test_vault_env_var_secret():
    name = "_env_var_secret"
    rh.env_var_secret(name=name, values=env_var_map).save()

    reloaded_secret = rh.env_var_secret(name=name)
    assert reloaded_secret.values == env_var_map

    reloaded_secret.delete()
    assert not reloaded_secret.in_vault()


def test_secret_from_env_vars():
    for key, val in env_var_map.items():
        os.environ[key] = val
    env_secret = rh.env_var_secret(env_vars=list(env_var_map.keys()))
    assert env_secret.values == env_var_map


def test_set_env_var_secret():
    env_secret = rh.env_var_secret(values=env_var_map)
    env_secret.set()
    for key, val in env_var_map.items():
        assert os.environ[key] == val
        del os.environ[key]


@pytest.mark.clustertest
def test_env_var_secret_to(ondemand_cpu_cluster):
    name = "_env_var_secret"
    env = rh.env()  # base env
    env_secret = rh.env_var_secret(name=name, values=env_var_map)
    env_secret.to(ondemand_cpu_cluster, env)

    assert ondemand_cpu_cluster.get(env_secret.name).values == env_var_map

    get_env_var_fn = rh.function(_get_env_var_value).to(ondemand_cpu_cluster, env)
    for key, val in env_var_map.items():
        assert get_env_var_fn(key) == val


# Other Secrets functionality tests


@pytest.mark.clustertest
def test_sync_secrets(ondemand_cpu_cluster):
    aws_secret = rh.provider_secret(
        provider="aws",
        name="_aws",
        values=aws_secret_values,
    ).write(path="~/.rh/tests/aws_creds")

    ondemand_cpu_cluster.sync_secrets([aws_secret])
    remote_file = file(path=aws_secret.path, system=ondemand_cpu_cluster)

    assert remote_file.exists_in_system()
    assert aws_secret._from_path(remote_file) == aws_secret_values

    assert_delete_local(aws_secret, contents=True)
    remote_file.rm()
