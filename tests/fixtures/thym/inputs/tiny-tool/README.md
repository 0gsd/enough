# tiny

Count the words of a text file, or list its commonest words.

    tiny count notes.txt            # 42
    tiny count notes.txt --lines    # 7
    tiny top notes.txt -n 2         # the: 5, and: 3

Words are runs of letters, compared without case. A file that cannot be read is named on standard error,
with exit status 1. `TINY_ENCODING` names the encoding to read with (UTF-8 when unset).

Python 3.10 or later, standard library only.
