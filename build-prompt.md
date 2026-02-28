
Here’s a single, implementation-ready prompt you can paste into Agent mode. It uses Option 2 (add/remove/change), fixes (A), confirms branch/URL/repo and diff format, and adds the comparison summary.

---

## Config Comparator – Implementation spec

**Goal:** Build a **config-comparator** app: Streamlit UI + Python backend that compares two **merged** configs (left vs right) using a **semantic YAML diff** (key-level). Each side is built by merging files from the config-repo using that side’s DeployConfig and resolved paths.

---

### UI layout

- **Two input sets:** **File 1 (left)** and **File 2 (right)**.
- **One action:** **Compare Configs** runs the comparison and shows the diff.
- **After clicking Compare:** Before showing the diff, display a **short comparison summary** so the user knows exactly what was compared (e.g. “Left: preprod / api-gb01 / cert / orders-api (branch main)” vs “Right: prod / api-gb01 / prod / orders-api (branch main)”).

**Inputs per side (same for File 1 and File 2):**

| Field | Required | Description / default |
|-------|----------|------------------------|
| Api Name | No | e.g. `orders-api`, `products-api`. Default: from that side’s `config.paths[0]` filename **without** extension (e.g. `orders-api-v1`). |
| Physical Environment | Yes* | `preprod` or `prod`. |
| LogicalEnv | Yes* | e.g. `cert`, `cert0`, `sct` (preprod) or `prod` (prod). |
| Api Operations yaml file name | No | e.g. `orders-api-v1.yaml`. Default: filename **with** extension from that side’s `config.paths[0]`. |
| Branch | Yes* | Config-repo branch (e.g. `master`, `feature_branch`). |
| DeployConfig.yaml URL | Yes* | Web or raw URL of the API’s DeployConfig. |
| opsrepo_folder | Yes* | Entity folder (e.g. `api-gb01`, `api-in01`). |

\*For File 2, “required” means: if the user leaves **all** File 2 inputs empty, the app applies the default for File 2 (see below). If any File 2 field is filled, the user must provide all required fields for File 2 (no partial defaulting).

---

### Default when File 2 is completely empty

If **every** File 2 input is blank:

- **File 1:** Use user values with **Physical Environment** = `preprod`, **LogicalEnv** = `cert`.
- **File 2:** Copy all values from File 1, then override:
  - **Physical Environment** = `prod`
  - **LogicalEnv** = `prod`

So with File 2 empty, the app compares **preprod/cert (left)** vs **prod/prod (right)** for the same API, branch, DeployConfig URL, and opsrepo_folder. When File 2 is defaulted, both sides use the **same** Branch and DeployConfig URL (and thus same repo).

---

### Variable resolution (per side)

When resolving that side’s `config.paths`:

- `${physicalEnvironment}` → that side’s Physical Environment.
- `${opsrepo_folder}` → that side’s opsrepo_folder.
- `${logicalEnv}` → that side’s LogicalEnv.

Use a single slash in the common-api path: `${physicalEnvironment}/common-api-v1.yaml`.

---

### Backend flow (on “Compare Configs”)

1. **Resolve inputs:** Apply File 2 default if all File 2 fields are empty.
2. **Comparison summary:** Before any diff, show a small summary, e.g.:
   - **Left:** `[Physical Env] / [opsrepo_folder] / [LogicalEnv] / [Api name or file]` (and branch / DeployConfig source if helpful).
   - **Right:** same for File 2.
   So the user is never confused about what was compared.
3. **Per side (File 1 and File 2):**
   - Fetch that side’s DeployConfig URL; parse `config.paths`.
   - Resolve path templates with that side’s physicalEnvironment, opsrepo_folder, logicalEnv.
   - Fetch each resolved path from the config-repo (that side’s branch; repo from DeployConfig).
   - **Merge** in list order: `paths[0]` highest priority, then `paths[1]`, etc. (deep merge).
4. **Diff:** Compute a **semantic YAML diff** between the two merged configs.
5. **Output:** Show the diff using **add/remove/change** (see below), after the summary.

---

### Diff format (Option 2: add/remove/change)

Present the semantic diff in three groups:

1. **Changed** – Key exists on both sides; values differ. Show: **key path**, **left value**, **right value**.
2. **Only in left** – Key only in File 1 (e.g. cert). Show: **key path**, **value**.
3. **Only in right** – Key only in File 2 (e.g. prod). Show: **key path**, **value**.

Use dot-style key paths for nested keys (e.g. `messaging.mq.hostname`, `kubernetes.resources.limits.memory`). Render in Streamlit as three sections or tables. Optionally support a “Flat list” or “Export” view (key path + left | right) for copy-paste.

---

### Repo and branch

- Each side uses the **repository** and **branch** from its own inputs (when File 2 is defaulted, both use File 1’s DeployConfig URL and branch, so same repo and branch for both sides).
- If in the future you support different DeployConfig URLs per side, each side would use the `repository` from its own DeployConfig; the current spec assumes one repo when File 2 is defaulted.

---

### Use cases covered

- Compare cert vs prod (same API): leave File 2 empty.
- Compare cert vs prod (different API): fill both sides.
- Compare any nonprod logical env (cert/cert0/sct) vs prod or vs another nonprod: fill both sides with desired Physical Environment and LogicalEnv.

---

You can hand this prompt to Agent mode to implement the config-comparator; the summary requirement and Option 2 diff are included and the File-2 default rule is fixed to (A).


Here are the spec updates to apply when you implement (e.g. in Agent mode). In Ask mode I’m not editing any files; this is the text to use in your prompt/spec.

---

## UI changes to apply

### 1. Field order (DeployConfig URL first)

Use this order for **both** File 1 and File 2:

1. **DeployConfig.yaml URL** (required; drives defaults for Api Name and Api Operations file name)
2. **Api Name** (optional; default from `config.paths[0]` filename without extension)
3. **Physical Environment** (required*)
4. **LogicalEnv** (required*)
5. **Api Operations yaml file name** (optional; default from `config.paths[0]` with extension)
6. **Branch** (required*; default `master`)
7. **opsrepo_folder** (required*)
8. **Compare Configs** button

\*Same “required” and defaulting rules as before (e.g. File 2 can be fully defaulted when all blank).

---

### 2. Physical Environment – dropdown

- **Control type:** Dropdown (selectbox).
- **Options (in order):** `preprod`, `prod`.
- **Required** for the side (File 1 or File 2) unless File 2 is fully defaulted.

---

### 3. LogicalEnv – dropdown, fixed options

- **Control type:** Dropdown (selectbox).
- **Options (in this order):** `cert`, `cert0`, `sct`, `perf`.
- **Required** for the side unless File 2 is fully defaulted.

---

### 4. Branch – editable, default `master`

- **Control type:** Editable text input (e.g. `st.text_input` in Streamlit).
- **Default value:** `master`.
- User can change it to any branch (e.g. `main`, `feature/xyz`).

---

### Summary for the prompt

Add this block to your implementation spec:

**UI field order (File 1 and File 2):**  
1) DeployConfig.yaml URL, 2) Api Name, 3) Physical Environment, 4) LogicalEnv, 5) Api Operations yaml file name, 6) Branch, 7) opsrepo_folder. Then the Compare Configs button.

**Widgets:**  
- **Physical Environment:** dropdown with options `preprod`, `prod`.  
- **LogicalEnv:** dropdown with options `cert`, `cert0`, `sct`, `perf` (in that order).  
- **Branch:** editable text input, default value `master`.