"""
skeleton_helper.py  –  Arbasoen remote Python skeleton (mode 3)
================================================================
Store this file on your Google Drive at:
    Arbasoen/doc/skeleton_helper.py

In the notebook's "LaTeX Skeleton Source" cell (cell 19):
    Skeleton  →  3) Remote Python script (GDrive)
    GDrive path → /content/drive/MyDrive/Arbasoen/doc/skeleton_helper.py

What this script does when executed by the notebook
----------------------------------------------------
1. Mounts Google Drive (if not already mounted).
2. Reads  Arbasoen/doc/nauta-dejonge.tex  from your Drive and replaces
   the  \\include{generated_pedigree}  line with the placeholder {{CONTENTS}}.
3. Copies the asset folders  includes/  images/  places/  (siblings of the
   .tex file) into /content/ so LuaLaTeX can find them.
4. Defines  build_skeleton(tex_content, gedcom_config, tr)  which the
   notebook's "Write latex file" cell (cell 20) calls automatically.
"""

import os
import shutil
from IPython.display import display, HTML

# ── Configuration ──────────────────────────────────────────────────────────────
_TEX_FILE      = "/content/drive/MyDrive/Arbasoen/doc/nauta-dejonge.tex"
_ASSET_FOLDERS = ["includes", "images", "places"]          # relative to doc/
_PLACEHOLDER   = "{{CONTENTS}}"
_INCLUDE_PAT   = r"\include{generated_pedigree}"           # exact string to replace
# ──────────────────────────────────────────────────────────────────────────────


ok  = "✅"
nok = "❌"
info = "ℹ️"
fire = "🔥"

# Add this to your skeleton_helper.py on GDrive
def get_project_settings():
    """Tells the notebook which GEDCOM to use and how to configure it."""
    print(f"{info} Applying project settings from script...")
    return {
        'gedcom_path': '/content/drive/MyDrive/Arbasoen/gedcom/20241031.ged',
        'start_id': '@I2@',
        'language': 'nl',
        'skip_first_gen': True
    }

def _mount_drive():
    """Mount Google Drive if not already mounted."""
    if not os.path.isdir("/content/drive/MyDrive"):
        print("💾 Mounting Google Drive …")
        from google.colab import drive
        drive.mount("/content/drive")
    else:
        print(f"{info} Google Drive already mounted.")


def _load_tex(path: str) -> str:
    """Read the .tex file and swap \\include{generated_pedigree} → {{CONTENTS}}."""
    if not os.path.isfile(path):
        print(f"{nok} Error: Could not find LaTeX file at {path}")
        raise FileNotFoundError(f"LaTeX skeleton not found on Drive: {path}")
    
    print(f"{info} Reading LaTeX skeleton from GDrive...")
    with open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()

    if _INCLUDE_PAT in raw:
        raw = raw.replace(_INCLUDE_PAT, _PLACEHOLDER, 1)
        print(f"{ok} Replaced \\include{{generated_pedigree}} with {_PLACEHOLDER}")
    else:
        # Fallback: maybe the file already uses the placeholder
        if _PLACEHOLDER in raw:
            print(f"{info} File already contains {_PLACEHOLDER} – no replacement needed.")
        else:
            print(
                f"⚠️  Neither '\\include{{generated_pedigree}}' nor '{_PLACEHOLDER}' "
                f"found in {path}.\n"
                f"    The generated pedigree content will be MISSING from the PDF!"
            )
    return raw


def _copy_assets(tex_path: str, folders: list[str], dest: str = "/content") -> None:
    """Copy asset folders (siblings of the .tex file) into dest."""
    print(f"{info} Copying")
    doc_dir = os.path.dirname(tex_path)
    for folder in folders:
        src = os.path.join(doc_dir, folder)
        dst = os.path.join(dest, folder)
        if not os.path.isdir(src):
            print(f"⚠️  Asset folder not found, skipping: {src}")
            continue
        if os.path.isdir(dst):
            shutil.rmtree(dst)            # remove stale copy
        shutil.copytree(src, dst)
        n = sum(len(fs) for _, _, fs in os.walk(dst))
        print(f"{ok} Copied  {folder}/  →  {dst}/  ({n} files)")


# ── Run immediately when the notebook executes this file ──────────────────────
_mount_drive()

print(f"\n📄 Loading skeleton: {_TEX_FILE}")
_skeleton_raw = _load_tex(_TEX_FILE)
print(f"   {len(_skeleton_raw):,} characters loaded.")

print(f"\n📁 Copying asset folders to /content/ …")
_copy_assets(_TEX_FILE, _ASSET_FOLDERS)


# ── build_skeleton() – called by cell 20 ──────────────────────────────────────
def build_skeleton(tex_content: str, gedcom_config: dict, tr) -> str:
    """
    Replace {{CONTENTS}} in the downloaded skeleton with the generated
    pedigree body and return the complete LaTeX document string.

    Parameters
    ----------
    tex_content   : pedigree body produced by generate_documentation()
    gedcom_config : dict with at least {'language': 'en'|'nl', …}
    tr            : Translations instance (unused here – language already
                    baked into the .tex file – but kept for API compatibility)
    """
    if _PLACEHOLDER not in _skeleton_raw:
        raise ValueError(
            f"Placeholder '{_PLACEHOLDER}' is missing from the loaded skeleton.\n"
            f"Check that nauta-dejonge.tex contains either "
            f"'\\include{{generated_pedigree}}' or '{_PLACEHOLDER}'."
        )

    full_tex = _skeleton_raw.replace(_PLACEHOLDER, tex_content, 1)
    return full_tex


print(
    f"\n{ok} build_skeleton() is ready.\n"
    f"   The notebook will call it automatically when writing the LaTeX file."
)