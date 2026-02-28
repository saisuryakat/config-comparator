"""
Backend for config-comparator: fetch DeployConfig, resolve paths, fetch and merge YAML, semantic diff.
"""
import re
from typing import Any, Dict, List, Optional, Tuple
import requests
import yaml


# DeployConfig URL normalization: convert GitHub web URL to raw URL when possible
def _normalize_deploy_config_url(url: str) -> str:
    url = url.strip()
    # Already raw
    if "raw.githubusercontent.com" in url:
        return url
    # GitHub blob URL: .../repo/blob/branch/path -> raw: .../repo/branch/path
    m = re.match(r"(https?://)github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)", url)
    if m:
        return f"https://raw.githubusercontent.com/{m.group(2)}/{m.group(3)}/{m.group(4)}/{m.group(5)}"
    return url


def _repo_to_raw_base(repository: str) -> str:
    """Convert repository URL like https://github.com/user/repo to raw base."""
    repository = repository.rstrip("/")
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(\.git)?$", repository)
    if m:
        return f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}"
    return repository


def fetch_deploy_config(url: str) -> Tuple[Optional[str], Optional[List[str]]]:
    """
    Fetch DeployConfig YAML from URL. Returns (repository_url, config_paths) or (None, None) on error.
    """
    url = _normalize_deploy_config_url(url)
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = yaml.safe_load(r.text)
        if not data:
            return None, None
        repo = data.get("repository")
        paths = (data.get("config") or {}).get("paths")
        if isinstance(paths, list):
            return repo, paths
        return repo, None
    except Exception:
        return None, None


def resolve_path(
    template: str,
    physical_environment: str,
    opsrepo_folder: str,
    logical_env: str,
) -> str:
    """Replace ${physicalEnvironment}, ${opsrepo_folder}, ${logicalEnv} in path template."""
    return (
        template.replace("${physicalEnvironment}", physical_environment)
        .replace("${opsrepo_folder}", opsrepo_folder)
        .replace("${logicalEnv}", logical_env)
    )


def default_api_name_from_paths(paths: List[str]) -> Optional[str]:
    """From config.paths[0] file path, return filename without extension (e.g. orders-api-v1)."""
    if not paths:
        return None
        # first path is e.g. ${physicalEnvironment}/${opsrepo_folder}/${logicalEnv}/orders-api-v1.yaml
    first = paths[0]
    filename = first.split("/")[-1]
    if "." in filename:
        return filename.rsplit(".", 1)[0]
    return filename


def default_api_file_from_paths(paths: List[str]) -> Optional[str]:
    """From config.paths[0], return filename with extension (e.g. orders-api-v1.yaml)."""
    if not paths:
        return None
    return paths[0].split("/")[-1]


def fetch_yaml_from_repo(
    repo_raw_base: str,
    branch: str,
    path: str,
) -> Optional[Dict[str, Any]]:
    """Fetch a single YAML file from repo raw base; returns parsed dict or None."""
    url = f"{repo_raw_base}/{branch}/{path}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return None
        return yaml.safe_load(r.text) or {}
    except Exception:
        return None


def deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge override into base (override wins). Returns new dict."""
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def build_merged_config(
    deploy_config_url: str,
    branch: str,
    physical_environment: str,
    opsrepo_folder: str,
    logical_env: str,
    api_yaml_filename: Optional[str] = None,
) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Fetch DeployConfig, resolve paths (optionally substituting API filename), fetch and merge YAMLs.
    Returns (merged_config_dict, error_message). error_message is None on success.
    """
    repo, paths = fetch_deploy_config(deploy_config_url)
    if repo is None or paths is None:
        return None, "Could not fetch or parse DeployConfig from URL."

    raw_base = _repo_to_raw_base(repo)
    resolved_paths: List[str] = []
    for i, t in enumerate(paths):
        p = resolve_path(t, physical_environment, opsrepo_folder, logical_env)
        # Only first path is the API-specific file; allow overriding its filename
        if api_yaml_filename and i == 0 and "/" in p:
            parts = p.rsplit("/", 1)
            resolved_paths.append(f"{parts[0]}/{api_yaml_filename}")
        else:
            resolved_paths.append(p)

    # Merge: paths[0] has highest priority, so apply in reverse order (path[0] last)
    merged: Dict[str, Any] = {}
    for path in reversed(resolved_paths):
        content = fetch_yaml_from_repo(raw_base, branch, path)
        if content is not None:
            merged = deep_merge(merged, content)
    return merged, None


def flatten_to_dot_paths(obj: Any, prefix: str = "") -> Dict[str, str]:
    """Flatten nested dict to dot-path -> string representation of leaf value."""
    out: Dict[str, str] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else k
            out.update(flatten_to_dot_paths(v, key))
    elif isinstance(obj, list):
        out[prefix] = yaml.safe_dump(obj, default_flow_style=True).strip()
    else:
        out[prefix] = str(obj) if obj is not None else ""
    return out


def semantic_diff(
    left: Dict[str, Any], right: Dict[str, Any]
) -> Tuple[List[Tuple[str, str, str]], List[Tuple[str, str]], List[Tuple[str, str]]]:
    """
    Compare two merged configs. Returns:
    - changed: [(path, left_val, right_val)]
    - only_left: [(path, value)]
    - only_right: [(path, value)]
    """
    left_flat = flatten_to_dot_paths(left)
    right_flat = flatten_to_dot_paths(right)
    changed: List[Tuple[str, str, str]] = []
    only_left: List[Tuple[str, str]] = []
    only_right: List[Tuple[str, str]] = []
    all_keys = set(left_flat) | set(right_flat)
    for key in sorted(all_keys):
        lv = left_flat.get(key)
        rv = right_flat.get(key)
        if key not in right_flat:
            only_left.append((key, lv))
        elif key not in left_flat:
            only_right.append((key, rv))
        elif lv != rv:
            changed.append((key, lv, rv))
    return changed, only_left, only_right
