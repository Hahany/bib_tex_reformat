The new version of glass.bib and the reformatting program:
The program can format your .bib file as follows:
1. The key is the first author’s last name + year + a short summary of the title (generated automatically using natural language processing; this summary is added only when the key duplicates a previous one).
2. Keep the key and title on the same line.
3. All keys use lowercase characters.
Program usage: python format_bib.py <your bib file>

This program will deduplicate entries based on the title.

based  on the packages:
sys
re
bibtexparser
<<<<<<< HEAD
bibtexparser
=======
bibtexparser.model 
>>>>>>> 6f57a794e2b70cc6196a9ecd888f3467397f4526
string
spacy