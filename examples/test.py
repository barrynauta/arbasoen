import shutil

# Copy the LaTeX skeleton from GDrive
#shutil.copy("/content/drive/MyDrive/Arbasoen/test.tex", "/content/pedigree.tex")

# Copy an additional image from GDrive
shutil.copy("/content/drive/MyDrive/Arbasoen/arbasoen.jpg", "/content/arbasoen.jpg")
def build_skeleton(tex_content, gedcom_config, tr):
    with open("/content/drive/MyDrive/Arbasoen/test.tex", "r", encoding="utf-8") as f:
        template = f.read()
    return template.replace("{{CONTENT}}", tex_content, 1)