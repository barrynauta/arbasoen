# Arbasoen


[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/barrynauta/arbasoen/blob/main/arbasoen.ipynb)


Generates a PDF (via LaTeX) pedigree file (ahnentafel) from GEDCOM files. This implies the result starts with one person and works its way 'up' → ancestors.
Uses colab (or probably any other python notebook). 
Free GPU runtime. Demos provided, no need to connect your gdrive, just click and watch the result.

Questions? Contact me at [barry@nauta.be](mailto:barry@nauta.be)

## Examples

The following [examples](/examples) are available (based on arbasoen v1.0.0):
- `kennedy_nl.pdf` - Kennedy family tree in Dutch.
- `kennedy_en.pdf` - Kennedy family tree in English.
- `royals92_en.pdf` - Royal 92 family tree in English.

## User manual
Although the colab cells should provide all the information, there is a dedicated [user manual](user_manual.md) available as well.

### Short version

* Select one of the demo files and give it a try
* Upload your own gedcom file and watch the result (set the start_id first!)
* Use a python script located on your gdrive for parameter setting and additional execution. See [skeleton_helper.py](examples/skeleton_helper.py) as example
  
## License
MIT License, see the [LICENSE](LICENSE) file
