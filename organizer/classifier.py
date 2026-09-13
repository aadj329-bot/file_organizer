import os

def get_extension(filename):
    _, ext = os.path.splitext(filename)
    return ext.lower().replace(".", "")

def classify(ext, lookup):
    return lookup.get(ext, "Misc")