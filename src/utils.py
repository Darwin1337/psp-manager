import os
import re
import platform
import subprocess
import struct
import binascii
import logging
from datetime import datetime
from enum import Enum

class SearchTypes(Enum):
    ISO = ".iso"
    DIR = "dir"

def extract_sfo(iso_path, temp_dir):
    """
    Extracts the PARAM.SFO file from a given ISO file using 7-Zip.
    """
    try:
        extract_command = ["7z", "x", iso_path, "PSP_GAME/PARAM.SFO", f"-o{temp_dir}", "-y"]
        subprocess.run(extract_command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logging.info(f"Successfully extracted PARAM.SFO from {iso_path}")
        return os.path.join(temp_dir, "PSP_GAME", "PARAM.SFO")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error extracting PARAM.SFO from {iso_path}: {e}")
        return None

def parse_sfo(sfo_path, param):
    """
    Parses the PARAM.SFO file and retrieves the value of the specified parameter.
    Credits: Marshall Ward - https://github.com/marshallward/devita
    """
    try:
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
            logging.info(f"Successfully parsed PARAM.SFO: {param} = {sfo_data.get(param)}")
            return sfo_data.get(param)
    except Exception as e:
        logging.error(f"Error parsing PARAM.SFO: {e}")
        return None

def sanitize_filename(filename):
    """
    Sanitizes a filename by removing invalid characters.
    """
    try:
        if not filename: return None
        sanitized = re.sub(r'[<>:"/\\|?*]', "", filename)
        logging.debug(f"Sanitized filename: {filename} -> {sanitized}")
        return sanitized.strip().rstrip(".")
    except:
        logging.error(f"Error sanitizing file name: {filename}")
        return None
  
def creation_date(path_to_file, query):
    """
    Try to get the date that a file/directory was created/last modified at, based on query.
    Credits: Mark Amery - https://stackoverflow.com/a/39501288
    """
    try:
        if query == SearchTypes.ISO:
            if platform.system() == "Windows":
                return os.path.getctime(path_to_file)
            else:
                stat = os.stat(path_to_file)
                return stat.st_birthtime
        elif query == SearchTypes.DIR:
            return os.path.getmtime(path_to_file)
        else: raise Exception()
    except:
        logging.error(f"Error getting creation date of: {path_to_file}")
        return None

def parse_directory(dir):
    """
    Retrieves files or directories from a directory.
    """
    return [] if not os.path.isdir(dir) else [{ "name": item, "path": os.path.join(dir, item)} for item in os.listdir(dir)]
  
def filter_directory(dir, query):
    """
    Filters an array of files or directories based on query.
    Returns their names, paths, and creation/last modified dates.
    """
    def process_file(file, is_valid):
        name, path = file["name"], file["path"]
        if is_valid(path):
            try:
                file_creation_date = creation_date(path, query)
                to_readable_date = datetime.fromtimestamp(file_creation_date).strftime("%Y-%m-%d %H:%M:%S")
            except:
                raise Exception(f"Could not retrieve {"creation" if query == SearchTypes.ISO else "last modified"} date for: {path}")
              
            return {
                "name": name,
                "path": path,
                "timestamp": file_creation_date,
                "date": to_readable_date,
            }
        return None

    if query == SearchTypes.ISO:
        is_valid = lambda path: os.path.isfile(path) and path.lower().endswith(SearchTypes.ISO.value)
    elif query == SearchTypes.DIR:
        is_valid = os.path.isdir
    else:
        return []

    result = [process_file(file, is_valid) for file in dir]
    return [item for item in result if item is not None]