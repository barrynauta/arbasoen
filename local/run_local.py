"""Local driver for the arbasoen notebook: replaces the Colab glue (cells 3, 5, 19, 20).

Usage:  python3 local/run_local.py <gedcom.ged> [--public]
        --public: privacy edition for publication. The first two generations are replaced by a
        notice and dropped from the breadcrumbs, anyone presumed living (no death, born in the last
        100 years) is shown by name only in child lists, and the skeleton loses the living family's
        own chapter, and gains the CC BY 4.0 licence page
        (licentie_publiek.tex next to the skeleton). Output gets a -public suffix.
Needs:  a venv with ged4py, python-dateutil, unidecode (python3 -m venv local/venv && local/venv/bin/pip install ged4py python-dateutil unidecode),
        LuaLaTeX + makeindex on PATH (MacTeX), and the Drive folder Arbasoen/doc with nauta-dejonge.tex and includes/ images/ places/.
It extracts the notebook's code cells 6 to 16 and 18 (everything except the Colab widgets, download and apt-get cells),
runs them with the same gedcom_config as skeleton_helper.py, injects the body into the skeleton, and runs
lualatex, makeindex, lualatex, lualatex in local/build/. Output: local/build/pedigree.pdf.
"""
import os, sys, shutil, subprocess, time
S = os.path.dirname(os.path.abspath(__file__))
DOC = "/Users/barrynauta/Library/CloudStorage/GoogleDrive-barry@nauta.be/My Drive/Arbasoen/doc"
GED = next(a for a in sys.argv[1:] if not a.startswith("--"))
PUBLIC = "--public" in sys.argv
BUILD = os.path.join(S, "build")

gedcom_config = {'mode': 'script', 'source': 'gdrive', 'gdrive_path': GED,
                 'start_id': '@I2@', 'language': 'nl', 'skip_first_gen': True, 'evidence_cutoff': True}
if PUBLIC:
    gedcom_config.update({'privacy_generations': 2, 'privacy_living_years': 100})
gedcom_file = GED
ok = " ✅ "; nok = " ❌ "; fire = " 🔥 "; info = " ℹ️ "

os.makedirs(BUILD, exist_ok=True)
for folder in ("includes", "images", "places"):
    dst = os.path.join(BUILD, folder)
    if not os.path.islink(dst):
        if os.path.isdir(dst): shutil.rmtree(dst)
        os.symlink(os.path.join(DOC, folder), dst)   # read-only use of the Drive assets
os.chdir(BUILD)   # the generator checks includes/<id>.tex relative to the cwd, like /content in Colab

t0 = time.time()
import json
nb = json.load(open(os.path.join(os.path.dirname(S), "arbasoen.ipynb"), encoding="utf-8"))
core = "\n".join("".join(nb["cells"][i]["source"]) for i in [6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 18])
exec(compile(core, "core.py", "exec"))          # cells 6-16, 18: defines classes, loads persons, builds generations, tr, generate_documentation
print(f"{ok}core loaded: {len(persons)} persons, {len(families)} families, {len(ahnen_map)} ancestors in {time.time()-t0:.1f}s")

tex_content = generate_documentation(generations, families, ahnen_map, persons)
SKELETON = os.path.join(DOC, "nauta-dejonge.tex")
skeleton = open(SKELETON, encoding="utf-8").read()
assert r"\include{generated_pedigree}" in skeleton
if PUBLIC:
    # the living family's own chapter stays out of the public edition (the title photo stays in)
    skeleton = skeleton.replace(r"\include{includes/kinderen_nauta_de_jonge}", "% left out: privacy", 1)
    # licence page (CC BY 4.0) only in the public edition; text kept next to the skeleton
    licence = open(os.path.join(DOC, "licentie_publiek.tex"), encoding="utf-8").read()
    skeleton = skeleton.replace("\\end{titlepage}\n", "\\end{titlepage}\n" + licence, 1)
    skeleton = skeleton.replace("\\normalsize\n\\clearpage",
                                "\\noindent Personen uit de jongste generaties zijn om privacyredenen weggelaten.\n\\normalsize\n\\clearpage", 1)
full_tex = skeleton.replace(r"\include{generated_pedigree}", tex_content, 1)

open(os.path.join(BUILD, "pedigree.tex"), "w", encoding="utf-8").write(full_tex)
print(f"{ok}pedigree.tex written: {len(full_tex):,} chars")

def run(cmd):
    r = subprocess.run(cmd, cwd=BUILD, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return r.returncode
lua = ["lualatex", "--shell-escape", "-interaction=nonstopmode", "-file-line-error", "pedigree.tex"]
for label, cmd in [("pass 1", lua), ("makeindex", ["makeindex", "pedigree"]), ("pass 2", lua), ("pass 3", lua)]:
    t = time.time(); rc = run(cmd); print(f"{ok if rc == 0 else nok}{label} rc={rc} {time.time()-t:.0f}s")
pdf = os.path.join(BUILD, "pedigree.pdf")
print(f"{ok if os.path.exists(pdf) else nok}{pdf} {os.path.getsize(pdf)/1e6:.1f} MB" if os.path.exists(pdf) else f"{nok}no pdf")

# --- local only: publish to the Desktop -------------------------------------
# The Colab notebook has no Desktop and no ghostscript, so this lives here and
# not in the notebook. The Drive copy stays manual on purpose: the shared file
# keeps its old name so the link that was sent out keeps working, and that is a
# decision to take per release, not something to automate.
if os.path.exists(pdf):
    import re as _re
    stem = os.path.splitext(os.path.basename(SKELETON))[0]           # nauta-dejonge
    m = _re.match(r"(\d{8})", os.path.basename(GED))                 # date of the export
    stamp = m.group(1) if m else time.strftime("%Y%m%d")
    desktop = os.path.expanduser("~/Desktop")
    suffix = "-public" if PUBLIC else ""
    full = os.path.join(desktop, f"{stem}-{stamp}{suffix}.pdf")
    small = os.path.join(desktop, f"{stem}-{stamp}{suffix}-small.pdf")

    shutil.copy2(pdf, full)
    print(f"{ok}{full} {os.path.getsize(full)/1e6:.1f} MB")

    if shutil.which("gs"):
        t = time.time()
        rc = subprocess.run(["gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.7",
                             "-dPDFSETTINGS=/ebook", "-dNOPAUSE", "-dQUIET", "-dBATCH",
                             f"-sOutputFile={small}", pdf],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
        if rc == 0 and os.path.exists(small):
            print(f"{ok}{small} {os.path.getsize(small)/1e6:.1f} MB "
                  f"({os.path.getsize(small)/os.path.getsize(full):.0%} of full, {time.time()-t:.0f}s)")
        else:
            print(f"{nok}ghostscript rc={rc}, no small version")
    else:
        print(f"{info}ghostscript not on PATH, skipping the small version")
