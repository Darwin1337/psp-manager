import gc
import os
import re
import sys
import struct
import logging
import pycdlib
import binascii
import platform

from enum import Enum
from datetime import datetime

class SearchQueries(Enum):
    """
    Describes relevant files for searching purposes
    KEY = EXTENSION (except for directory)
    """
    ISO = ".iso"
    DIR = "dir"
    
class Folders(Enum):
    """
    Describes known directories that have relevant files
    KEY = PATH_TO_DIR, [SEARCH_QUERY_1, SEARCH_QUERY_2, ...]
    """
    ISO = "ISO", [SearchQueries.ISO]
    GAME = "PSP\\GAME", [SearchQueries.DIR, SearchQueries.ISO]
    
class PSP:
    def __init__(self, path):
        self.path = path
        self.directories = self.read_directories()
        self.items = self.load_directories()

    def read_directories(self):
        """
        Returns every potentially relevant directory based on the input
        """
        directories = []
        for folder in Folders:
            directories.append({
                "name": folder.name,
                "path": os.path.join(self.path, folder.value[0]),
                "queries": folder.value[1]
            })
        return directories
      
    def load_directories(self):
        """
        Goes through all directories and returns every relevant file/directory
        """
        items = []
        for directory in self.directories:
            for query in directory["queries"]:
                items.extend(filter_directory(parse_directory(directory["path"]), query))
        items.sort(key=lambda item: item["timestamp"], reverse=True)
        return items

def render_menu(headers, content):
    """
    Renders headers and content of an interactive menu using print().
    """
    for idx in range(len(headers)):
        print(("\n" if idx == 0 else "") + headers[idx])
        
    for idx in range(len(content)):
        print((f"\n{idx + 1}. " if idx == 0 else f"{idx + 1}. ") + content[idx])
        
    choice = input("\nEnter your choice: ")
    print()
    return choice

def log_warning_with_error(str, e):
    """
    Logs both an error and a warning when an exception is caught.
    """
    logging.warning(e)
    logging.warning(str)

def get_creation_date(path_to_file, query):
    """
    Try to get the date that a file/directory was created/last modified at, based on query.
    Credits: Mark Amery - https://stackoverflow.com/a/39501288
    """
    if query == SearchQueries.ISO:
        if platform.system() == "Windows":
            return os.path.getctime(path_to_file)
        else:
            stat = os.stat(path_to_file)
            return stat.st_birthtime
    elif query == SearchQueries.DIR:
        return os.path.getmtime(path_to_file)
    else: raise Exception()

def parse_directory(dir):
    """
    Retrieves files or directories from a directory.
    """
    return [] if not os.path.isdir(dir) else [{ "name": item, "path": os.path.join(dir, item), "directory": dir} for item in os.listdir(dir)]

def filter_directory(dir, query):
    """
    Filters an array of files or directories based on query.
    Returns their names, paths, and creation/last modified dates.
    """
    def process_file(file, is_valid):
        name, path, dir = file["name"], file["path"], file["directory"]
        if is_valid(path):
            try:
                file_creation_date = get_creation_date(path, query)
                to_readable_date = datetime.fromtimestamp(file_creation_date).strftime("%d-%m-%Y %H:%M:%S")
            except:
                raise Exception(f"Could not retrieve {"creation" if query == SearchQueries.ISO else "last modified"} date for: {path}")
              
            return {
                "category": query,
                "name": name,
                "path": path,
                "timestamp": file_creation_date,
                "date": to_readable_date,
                "directory": dir
            }
        return None

    if query == SearchQueries.ISO:
        is_valid = lambda path: os.path.isfile(path) and path.lower().endswith(SearchQueries.ISO.value)
    elif query == SearchQueries.DIR:
        is_valid = os.path.isdir
    else:
        return []

    result = [process_file(file, is_valid) for file in dir]
    return [item for item in result if item is not None]
  
def join_with_script_path(file):
    """
    Returns a path for a temporary folder in the directory of the script.
    """
    return os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])), file)

def extract_sfo(iso_path):
    """
    Extracts the PARAM.SFO file from a given ISO file using pycdlib.
    """
    iso = pycdlib.PyCdlib()
    temp_dir = join_with_script_path("temp")
    
    with open(iso_path, "rb") as b:
        iso.open_fp(b)
        os.makedirs(temp_dir, exist_ok=True)
        extracted_file_path = os.path.join(temp_dir, "PARAM.SFO")
        
        with open(extracted_file_path, "wb") as f:
            iso.get_file_from_iso_fp(f, iso_path="/PSP_GAME/PARAM.SFO")
        iso.close()
    return extracted_file_path, temp_dir

def parse_sfo(sfo_path, param):
    """
    Parses the PARAM.SFO file and retrieves the value of the specified parameter.
    Credits: Marshall Ward - https://github.com/marshallward/devita
    """
    with open(sfo_path, "rb") as sfo_file:
        header_raw = sfo_file.read(20)
        header = struct.unpack("<4s4BIII", header_raw)
        param_names, param_values = ["SFO File Signature", "SFO File Version"], []

        param_values.append(header[0].decode("utf-8"))
        param_values.append(".".join([str(h) for h in header[1:5]]))

        name_table_start = header[5]
        data_table_start = header[6]
        n_params = header[7]

        def_table_bytes = 16 * n_params
        name_table_bytes = data_table_start - name_table_start
        def_table_padding = name_table_start - 20 - def_table_bytes

        assert def_table_padding >= 0

        def_table = []
        for _ in range(n_params):
            def_rec_raw = sfo_file.read(16)
            def_record = struct.unpack("<HHIII", def_rec_raw)
            def_table.append(def_record)

        sfo_file.read(def_table_padding)

        for e in range(n_params):
            try:
                p_name_bytes = def_table[e + 1][0] - def_table[e][0]
            except IndexError:
                p_name_bytes = name_table_bytes - def_table[e][0]
            p_name = sfo_file.read(p_name_bytes).decode("utf-8")
            param_names.append(p_name.rstrip("\x00"))

        for e in range(n_params):
            v_type = def_table[e][1]
            v_total = def_table[e][3]
            value_raw = sfo_file.read(v_total)

            if v_type in (0x0204, 0x0004):
                value = value_raw.decode("utf-8").rstrip("\x00")
            elif v_type == 0x0404:
                value_ascii = binascii.hexlify(value_raw[::-1]).decode("utf-8")
                value = int(value_ascii, 16)
            else:
                value = None

            param_values.append(value)

        sfo_data = dict(zip(param_names, param_values))
        return sfo_data.get(param)

def sanitize_filename(filename):
    """
    Sanitizes a filename by removing invalid characters.
    """
    if not filename: return None
    sanitized = re.sub(r'[<>:"/\\|?*]', "", filename)
    sanitized = " ".join(sanitized.split())
    return sanitized.strip().rstrip(".")
  
def sanitize_filename_ordering(file):
    """
    Sanitizes a filename for better alphabetical ordering.
    """
    filename = file["name"]
    filename = filename.lower()
    filename = filename[:-len(file["category"].value)] if file["category"] != SearchQueries.DIR else filename
    filename = re.sub(r"[^a-zA-Z0-9]", "", filename)
    return filename