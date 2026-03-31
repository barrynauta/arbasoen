# Arbasoen – User Manual

> **Arbasoen** generates a PDF pedigree (Ahnentafel) from a GEDCOM file, using LaTeX as the intermediary format. It runs as a Google Colab notebook.

---

## Table of Contents

1. [Getting started](#1-getting-started)
2. [Step 1 – GEDCOM source](#2-step-1--gedcom-source)
3. [Step 2 – LaTeX skeleton](#3-step-2--latex-skeleton)
4. [Step 3 – Generate the PDF](#4-step-3--generate-the-pdf)
5. [Customising the output](#5-customising-the-output)
6. [Troubleshooting](#6-troubleshooting)

---

## 1. Getting started

Open the notebook in Google Colab by clicking the badge at the top of the notebook, or navigate directly to:

```
https://colab.research.google.com/github/barrynauta/arbasoen/blob/main/arbasoen.ipynb
```

Once open, run the cells top to bottom. The easiest way is to use **Runtime → Run all** from the Colab menu. The two configuration forms (GEDCOM source and LaTeX skeleton) will stop and wait for your input before continuing.

---

## 2. Step 1 – GEDCOM source

The first form lets you choose where the GEDCOM file comes from.

| Option | Description |
|---|---|
| **1) Demo files** | Pre-loaded example trees (Harry Potter, Kennedy, Royals 92). Good for a first test run. |
| **2) File upload** | Upload a `.ged` file directly from your computer. |
| **3) Local GDrive** | Read a `.ged` file from your Google Drive. You will be asked to authorise Drive access. |

### Fields

- **Start Index** – the GEDCOM individual ID of the person at the root of the pedigree (e.g. `@I0@`). For demo files this is filled in automatically.
- **Language** – output language for prose text: English or Dutch.
- **Skip first generation** – when checked, the root person is omitted and the pedigree starts with their parents.

Press **🚀 Process** to confirm. For GDrive, the notebook will mount your Drive automatically.

---

## 3. Step 2 – LaTeX skeleton

The second form (in the *LaTeX and PDF generation* section) controls the document structure that wraps the generated pedigree content.

| Option | Description |
|---|---|
| **1) Local skeleton (built-in)** | Uses the hardcoded skeleton inside the notebook. No extra setup needed. |
| **2) Remote LaTeX file (GDrive)** | Downloads a `.tex` file from your Drive and uses it as the document template. |
| **3) Remote Python script (GDrive)** | Downloads and executes a `.py` file from your Drive. |

Press **✅ Apply** to confirm.

### Option 2 – Remote LaTeX file

Your `.tex` file must contain a placeholder where the generated pedigree content should be inserted. The default placeholder is:

```
{{CONTENT}}
```

You can change this in the **Placeholder** field. A warning is shown if the placeholder is not found in the file.

**Minimal example `test.tex`:**

```latex
\documentclass[a4paper,10pt,openany]{book}
\usepackage[dutch]{babel}
\usepackage{graphicx}
% ... other packages ...
\begin{document}

\begin{titlepage}
    \centering
    \vspace*{2cm}
    {\Huge\bfseries Stamboom}\\[2cm]
    \includegraphics[width=0.6\textwidth]{arbasoen.jpg}\\
    \vfill
    {\large \today}
\end{titlepage}

\tableofcontents
\mainmatter
\chapter{Stamboom}
{{CONTENT}}
\printindex
\backmatter
\end{document}
```

### Option 3 – Remote Python script

The script is executed inside the notebook's environment, so it has access to all variables (`gedcom_config`, `tr`, etc.) and can do anything Python can — download images, copy files from Drive, install packages, and so on.

If the script defines a function called `build_skeleton`, that function will be called to produce the final LaTeX document string:

```python
def build_skeleton(tex_content, gedcom_config, tr):
    # tex_content  – the generated pedigree body (LaTeX string)
    # gedcom_config – dict with 'language', 'start_id', etc.
    # tr           – translation object, use tr.t('key') for translated strings
    ...
    return full_latex_string
```

If no `build_skeleton` function is defined, the script is treated as an asset-download step only, and the built-in local skeleton is used for the document structure.

**Example `test.py`:**

```python
import shutil

# Copy assets from Google Drive to /content/ so LuaLaTeX can find them
shutil.copy("/content/drive/MyDrive/Arbasoen/arbasoen.jpg", "/content/arbasoen.jpg")

def build_skeleton(tex_content, gedcom_config, tr):
    with open("/content/drive/MyDrive/Arbasoen/test.tex", "r", encoding="utf-8") as f:
        template = f.read()
    return template.replace("{{CONTENT}}", tex_content, 1)
```

---

## 4. Step 3 – Generate the PDF

Once both forms are filled in, the remaining cells run automatically:

1. **Write LaTeX file** – combines the skeleton with the generated pedigree content and writes `pedigree.tex`.
2. **Compile PDF** – calls LuaLaTeX (installed on the fly) to compile `pedigree.tex` into `pedigree.pdf`.
3. **Download** – the resulting PDF is downloaded to your browser automatically.

---

## 5. Customising the output

### Title page
Add a title page to your `.tex` skeleton using a `titlepage` environment (see the example above). Place it before `\tableofcontents`.

### Images
Images referenced in your LaTeX file must be present in `/content/` when LuaLaTeX runs. Copy them there in your Python script using `shutil.copy` from GDrive, or download them with `requests`.

### Language
The language setting controls both the prose generated by the notebook (birth, death, marriage sentences) and the LaTeX `babel` package used in the built-in skeleton. Supported values are `en` (English) and `nl` (Dutch).

### Fonts
The built-in skeleton uses **EB Garamond**. To use a different font in a custom skeleton, replace the `\setmainfont` block and ensure the font is available to LuaLaTeX (either a system font or one you install in the Python script).

---

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Placeholder "{{CONTENT}}" not found` | Your `.tex` file is missing the placeholder | Add `{{CONTENT}}` at the position where content should appear |
| `File not found: /content/drive/...` | Drive not mounted or wrong path | Check the path in the form; make sure the file exists in Drive |
| `build_skeleton` not called | Function not defined in your script | Check for syntax errors in your `.py` file; the function name must be exactly `build_skeleton` |
| LuaLaTeX compilation error | LaTeX error in skeleton or generated content | Check `pedigree.tex` in the Colab file browser for the error line |
| PDF not downloaded | Browser blocked the download | Allow pop-ups / automatic downloads for `colab.research.google.com` |
| Start Index not found | Wrong GEDCOM ID for the root person | Open the `.ged` file in a text editor and find the correct `@I...@` identifier |
