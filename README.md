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

## User maual
Although the colab cells should provide all the information, there is a dedicated [user manual](user_manual.md) available as well.

### Short version

* Copy the test.tex, test.py and arbasoen.jpg file to a directory in your gdrive
* Analyse the test.py file. I know it is safe, but this is your responsibility, VALIDATE!
* Adapt the test,py file to your liking
* Adapt the proposed paths in the colab script to point to the correct file
* Hit and run!
  
## License
MIT License, see the [LICENSE](LICENSE) file
