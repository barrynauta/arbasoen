# Arbasoen – User Manual

> **Arbasoen** generates a PDF pedigree (Ahnentafel) from a GEDCOM file, using LaTeX as the intermediary format. It runs as a Google Colab notebook.

---

## Table of Contents

1. [Getting started](#1-getting-started)
2. [The Project Configuration Hub](#2-the-project-configuration-hub)
3. [Advanced Mode – Remote Scripting](#3-advanced-mode--remote-scripting)
4. [Step 2 – Generate the PDF](#4-step-2--generate-the-pdf)
5. [Customising the output](#5-customising-the-output)
6. [Troubleshooting](#6-troubleshooting)

---

## 1. Getting started

Open the notebook in Google Colab via the GitHub badge or the direct link. To run the application, use **Runtime → Run all**. The notebook will install necessary dependencies like `ged4py`, `python-dateutil`, and `unidecode` automatically before stopping at the **Project Configuration Hub** for your input.

---

## 2. The Project Configuration Hub

The primary interface has been unified into a single hub. You must first select your **Workflow Mode**.

| Option | Description |
|---|---|
| **1) Demo Files** | Uses pre-loaded examples (Harry Potter, Kennedy, or Royals 92). The **Start ID** is set automatically. |
| **2) Local Upload** | Allows you to upload a `.ged` file from your computer. You must manually enter the **Start ID**. |
| **3) GDrive Script** | The "Expert" mode. Points to a `.py` file on your Google Drive that automates the entire project. |

### Global Fields
- **Language** – Choose between English or Dutch. In **Script Mode**, this dropdown is disabled as the script manages the language.
- **Start ID** – The GEDCOM identifier (e.g., `@I2@`) for the root person. This is grayed out in Demo/Script modes as they provide their own IDs.
- **Skip first generation** – Omit the root person and start the pedigree with their parents.

Press **🚀 Initialize Project** to confirm your settings and prepare the environment.

---

## 3. Advanced Mode – Remote Scripting

When using **Mode 3 (GDrive Script)**, the notebook executes your Python script (e.g., `skeleton_helper.py`) to handle complex setups.

### Script Capabilities
Your script can automate several tasks that the manual interface cannot:
1. **Asset Management** – Automatically copy folders (like `images/`, `places/`, or `includes/`) from GDrive to the local `/content/` folder.
2. **Configuration Injection** – By defining a `get_project_settings()` function, the script tells the notebook exactly which GEDCOM file to use and which Start ID to target.
3. **Template Substitution** – By defining a `build_skeleton()` function, the script takes the generated genealogy text and injects it into a custom `.tex` template.

### Including External Files
The system allows you to include external `.tex` snippets for specific individuals. It automatically looks for files in the `includes/` folder named after the stripped GEDCOM ID (e.g., `@I2@` becomes `includes/I2.tex`).

---

## 4. Step 2 – Generate the PDF

After initialization, run the remaining cells:
1. **Parsing** – The notebook reads the GEDCOM and builds the ancestor tree based on the provided Start ID.
2. **Write LaTeX** – Merges your data with the skeleton. If a `build_skeleton` function was loaded from your script, it is used automatically; otherwise, the built-in template is used.
3. **Compile & Download** – Calls LuaLaTeX to produce `pedigree.pdf` and triggers an automatic browser download.

---

## 5. Customising the output

### Images & Portraits
Images referenced in your LaTeX file must be present in `/content/` during compilation. It is recommended to use your Python script to synchronize these folders from GDrive using `shutil.copytree`.

### Custom Snippets
To add detailed biographies or extra formatting for a specific person, create a `.tex` file with their ID (e.g., `I2.tex`) in your `includes/` directory. The notebook will attempt to include it automatically using `\InputIfFileExists`.

---

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `NameError: name 'ok' is not defined` | Variables cleared during a runtime reset | Re-run the **Project Configuration Hub** cell to re-define icons. |
| `ModuleNotFoundError: ged4py` | Colab runtime was restarted | Run the Hub cell; it includes the `!pip install` commands. |
| `TraitError` in Hub UI | Incompatible widget children | Ensure the UI uses `widgets.HTML` instead of the raw IPython display object. |
| `SyntaxError` in f-string | Braces evaluated as variables | In Python f-strings, you must use `{{ }}` to produce literal `{ }` for LaTeX. |
| ID or Language not updating | `get_project_settings` missing | Ensure your `.py` file defines the `get_project_settings()` function. |
