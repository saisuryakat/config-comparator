"""
Config Comparator – Streamlit UI.
Compare two merged configs (left vs right) with semantic YAML diff.
"""
import difflib
import yaml
import streamlit as st
from backend import (
    build_merged_config,
    default_api_file_from_paths,
    default_api_name_from_paths,
    fetch_deploy_config,
    semantic_diff,
)

PHYSICAL_ENVS = ["preprod", "prod"]
LOGICAL_ENVS = ["cert", "prod", "cert0", "sct", "perf"]


def _is_file2_empty(url2: str, ops2: str) -> bool:
    """File 2 is 'use defaults' when its required identifiers are blank (URL and opsrepo)."""
    return not (url2 or "").strip() and not (ops2 or "").strip()


def _render_side(
    side: str,
    default_branch: str = "master",
) -> dict:
    label = "File 1 (left)" if side == "1" else "File 2 (right)"
    # File 2 defaults to prod/prod when left blank; File 1 stays preprod/cert
    default_physical_index = 1 if side == "2" else 0   # prod for File 2, preprod for File 1
    default_logical_index = 1 if side == "2" else 0   # prod for File 2, cert for File 1
    with st.container():
        st.markdown(f"<h4 style='margin-bottom: 0.25rem;'>{label}</h4>", unsafe_allow_html=True)
        deploy_url = st.text_input(
            "DeployConfig.yaml URL",
            key=f"deploy_url_{side}",
            placeholder="https://raw.githubusercontent.com/.../DeployConfig.yaml",
        )
        physical = st.selectbox(
            "Physical Environment",
            options=PHYSICAL_ENVS,
            index=default_physical_index,
            key=f"physical_{side}",
        )
        logical = st.selectbox(
            "Logical Environment",
            options=LOGICAL_ENVS,
            index=default_logical_index,
            key=f"logical_{side}",
        )
        branch = st.text_input(
            "Branch",
            value=default_branch,
            key=f"branch_{side}",
        )
        opsrepo_folder = st.text_input(
            "opsrepo_folder",
            key=f"opsrepo_{side}",
            placeholder="e.g. api-gb01, api-in01",
        )
        # Optional overrides UI removed; always infer from DeployConfig instead.
        api_name = None
        api_file = None
    return {
        "deploy_url": deploy_url,
        "api_name": api_name,
        "physical": physical,
        "logical": logical,
        "api_file": api_file or None,
        "branch": branch or default_branch,
        "opsrepo_folder": opsrepo_folder,
    }


def _ensure_defaults_from_deploy_config(params: dict) -> dict:
    """If api_name or api_file missing, fetch DeployConfig and set from config.paths[0]."""
    if params.get("api_file") and params.get("api_name"):
        return params
    repo, paths = fetch_deploy_config(params["deploy_url"])
    if not paths:
        return params
    if not params.get("api_file"):
        params["api_file"] = default_api_file_from_paths(paths)
    if not params.get("api_name"):
        params["api_name"] = default_api_name_from_paths(paths)
    return params


def main():
    st.set_page_config(page_title="Config Comparator", layout="wide")
    st.markdown(
        "<h2 style='margin-bottom: 0.25rem;'>Config Comparator</h2>",
        unsafe_allow_html=True,
    )
    st.caption("Semantic YAML diff: compare merged configs (left vs right)")

    col1, col2 = st.columns(2)
    with col1:
        p1 = _render_side("1")
    with col2:
        p2 = _render_side("2")

    st.markdown("---")
    compare = st.button("Compare Configs")

    if not compare:
        st.stop()

    # Resolve File 2 default when File 2's required fields (URL, opsrepo) are blank
    file2_empty = _is_file2_empty(p2["deploy_url"], p2["opsrepo_folder"])
    if file2_empty:
        p1_resolved = {
            **p1,
            "physical": "preprod",
            "logical": "cert",
        }
        p2_resolved = {
            **p1,
            "physical": "prod",
            "logical": "prod",
            "deploy_url": p1["deploy_url"],
            "branch": p1["branch"],
            "api_name": p1["api_name"],
            "api_file": p1["api_file"],
            "opsrepo_folder": p1["opsrepo_folder"],
        }
    else:
        p1_resolved = {**p1}
        p2_resolved = {**p2}

    # Required fields for the side we're actually using
    for label, pr in [("File 1 (left)", p1_resolved), ("File 2 (right)", p2_resolved)]:
        if not (pr.get("deploy_url") or "").strip():
            st.error(f"{label}: DeployConfig.yaml URL is required.")
            st.stop()
        if not (pr.get("opsrepo_folder") or "").strip():
            st.error(f"{label}: opsrepo_folder is required.")
            st.stop()

    # Ensure API name/file defaults from DeployConfig when not provided
    p1_resolved = _ensure_defaults_from_deploy_config(p1_resolved)
    p2_resolved = _ensure_defaults_from_deploy_config(p2_resolved)

    # Comparison summary
    left_summary = (
        f"**Left:** {p1_resolved['physical']} / {p1_resolved['opsrepo_folder']} / "
        f"{p1_resolved['logical']} / {p1_resolved.get('api_name') or p1_resolved.get('api_file') or '—'} "
        f"(branch: {p1_resolved['branch']})"
    )
    right_summary = (
        f"**Right:** {p2_resolved['physical']} / {p2_resolved['opsrepo_folder']} / "
        f"{p2_resolved['logical']} / {p2_resolved.get('api_name') or p2_resolved.get('api_file') or '—'} "
        f"(branch: {p2_resolved['branch']})"
    )
    st.info(f"Comparing: {left_summary}  \nvs  \n{right_summary}")

    with st.spinner("Fetching and merging configs..."):
        merged1, err1 = build_merged_config(
            p1_resolved["deploy_url"],
            p1_resolved["branch"],
            p1_resolved["physical"],
            p1_resolved["opsrepo_folder"],
            p1_resolved["logical"],
            p1_resolved.get("api_file"),
        )
        merged2, err2 = build_merged_config(
            p2_resolved["deploy_url"],
            p2_resolved["branch"],
            p2_resolved["physical"],
            p2_resolved["opsrepo_folder"],
            p2_resolved["logical"],
            p2_resolved.get("api_file"),
        )

    if err1:
        st.error(f"File 1 (left): {err1}")
        st.stop()
    if err2:
        st.error(f"File 2 (right): {err2}")
        st.stop()

    # Show the fully merged configs before computing the semantic diff
    with st.expander("Deep merged configs (left & right)", expanded=False):
        left_yaml = yaml.safe_dump(merged1, sort_keys=False)
        right_yaml = yaml.safe_dump(merged2, sort_keys=False)

        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("**Left merged config**")
            st.code(left_yaml, language="yaml")
        with col_r:
            st.markdown("**Right merged config**")
            st.code(right_yaml, language="yaml")

        # Line-level YAML diff (similar to git unified diff)
        diff_lines = list(
            difflib.unified_diff(
                left_yaml.splitlines(),
                right_yaml.splitlines(),
                fromfile="left.yaml",
                tofile="right.yaml",
                lineterm="",
            )
        )
        st.markdown("**YAML diff (unified)**")
        if diff_lines:
            st.code("\n".join(diff_lines), language="diff")
        else:
            st.caption("No line-level differences in the merged YAML.")

    changed, only_left, only_right = semantic_diff(merged1, merged2)

    st.subheader("Semantic diff (add / remove / change)")

    if not changed and not only_left and not only_right:
        st.success("No differences. Both merged configs are identical.")
        st.stop()

    col_c, col_l, col_r = st.columns(3)
    with col_c:
        st.markdown("**Changed** (key in both, value differs)")
        if changed:
            for path, lv, rv in changed:
                st.text(path)
                st.caption(f"Left:  {lv[:80]}{'…' if len(lv) > 80 else ''}")
                st.caption(f"Right: {rv[:80]}{'…' if len(rv) > 80 else ''}")
                st.divider()
        else:
            st.caption("—")
    with col_l:
        st.markdown("**Only in left**")
        if only_left:
            for path, val in only_left:
                st.text(path)
                st.caption(f"{val[:80]}{'…' if len(val) > 80 else ''}")
                st.divider()
        else:
            st.caption("—")
    with col_r:
        st.markdown("**Only in right**")
        if only_right:
            for path, val in only_right:
                st.text(path)
                st.caption(f"{val[:80]}{'…' if len(val) > 80 else ''}")
                st.divider()
        else:
            st.caption("—")


if __name__ == "__main__":
    main()
