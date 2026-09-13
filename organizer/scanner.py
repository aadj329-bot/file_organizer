import os

def list_files(folder):
    for item in os.listdir(folder):
        path = os.path.join(folder, item)
        if os.path.isfile(path):
            yield item, path