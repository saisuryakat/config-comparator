# Config Comparator

Semantic YAML diff tool: compare two **merged** configs (left vs right) built from a config-repo using DeployConfig paths.

## Run

Create and use a virtual environment (run all commands from the project root):

```bash
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows
pip3 install -r requirements.txt
python3 -m streamlit run app.py
```

## Usage

1. **File 1 (left)** and **File 2 (right):** Fill fields in order (DeployConfig URL first).  
2. Leave **all** File 2 fields empty to compare **preprod/cert** (left) vs **prod/prod** (right) for the same API.  
3. Click **Compare Configs**. The app shows what’s being compared, then the semantic diff (Changed / Only in left / Only in right).

## Fields (per side)

- **DeployConfig.yaml URL** – Web or raw URL (e.g. GitHub raw). Required.
- **Api Name** – Optional; default from `config.paths[0]` filename without extension.
- **Physical Environment** – Dropdown: preprod, prod.
- **LogicalEnv** – Dropdown: cert, cert0, sct, perf.
- **Api Operations yaml file name** – Optional; default from `config.paths[0]` with extension.
- **Branch** – Config-repo branch (default: master).
- **opsrepo_folder** – Entity folder (e.g. api-gb01, api-in01). Required.

Variables in DeployConfig paths (`${physicalEnvironment}`, `${opsrepo_folder}`, `${logicalEnv}`) are resolved from these inputs.
