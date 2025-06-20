import os
import copy
import utils
import shutil
import logging
import argparse

from tabulate import tabulate

# TODO
# 1 - Actually write the ordering function
# 2 - Implement reload option so the games/tools list can be refreshed
# 3 - Strikethrough feature
# 4 - Think about what to log. Right now, the only process being fully logged is the renaming
# 5 - After renaming, I need to reload games
# 6 - After ordering, I need to reload games
# 7 - Submenu for ordering: A-Z, Z-A, divided and not divided by category
# 8 - Add requirements.txt and complete README 

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(utils.join_with_script_path("app.log"), encoding="utf-8"),
        logging.StreamHandler()
    ]
)

def list_files(items):
    """
    Lists games/tools, sorted by creation/last modified date.
    """
    if len(items) == 0:
        return logging.warning("No games/tools were found")
        
    print(tabulate(
      [[row_idx + 1, items[row_idx]["name"], items[row_idx]["date"]] for row_idx in range(len(items))],
      headers=['#', 'File name', 'Date']
    ))

def rename_files(items):
    """
    Renames ISO files in the given directory based on their PARAM.SFO titles.
    """
    isos = [item for item in items if item["category"] == utils.SearchQueries.ISO]
    for iso in isos:
        iso_path, file_name, dir = iso["path"], iso["name"], iso["directory"]
        
        if file_name != isos[0]["name"]:
            logging.info("==========================================")
        
        logging.info(f"Processing renaming for '{iso_path}'")

        # Extract PARAM.SFO from the ISO
        try:
            sfo = utils.extract_sfo(iso_path)
            sfo_path, temp_dir = sfo[0], sfo[1]
            if not os.path.isfile(sfo_path): raise
            logging.info(f"Successfully extracted PARAM.SFO from ISO")
        except Exception as e:
            utils.log_warning_with_error(f"Error extracting PARAM.SFO from '{iso_path}', skipping", e)
            continue
          
        # Get TITLE param from PARAM.SFO
        try:
            title = utils.parse_sfo(sfo_path, "TITLE")
            logging.info(f"Successfully parsed PARAM.SFO: TITLE = '{title}'")
        except Exception as e:
            utils.log_warning_with_error(f"Error getting TITLE from '{sfo_path}', skipping", e)
            continue
        
        # Sanitize TITLE before renaming
        try:    
            sanitized_title = utils.sanitize_filename(title)
            logging.info(f"Successfully sanitized TITLE to: '{sanitized_title}'")
        except Exception as e:
            utils.log_warning_with_error(f"Error sanitizing TITLE = '{title}' from '{sfo_path}', skipping", e)
            continue
        
        # Rename the ISO
        try:
            new_file_name = sanitized_title + utils.SearchQueries.ISO.value
            new_iso_path = os.path.join(dir, new_file_name)
            os.rename(iso_path, new_iso_path)
            logging.info(f"Done! Renamed '{file_name}' to '{new_file_name}'")
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            utils.log_warning_with_error(f"Error renaming '{file_name}' to '{new_file_name}', skipping", e)
            continue

def reorder_files(items):
    """
    Orders files alphabetically.
    """
    try:
        new_items = copy.deepcopy(items)
        new_items.sort(key=lambda item: utils.sanitize_filename_ordering(item))
        list_files(new_items)
    except Exception as e:
        utils.log_warning_with_error(f"Error ordering files alphabetically", e)

def main():
    """
    Main function to display a menu and handle user input.
    """
    parser = argparse.ArgumentParser(description="Manage your PSP library")
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Directory containg a known PSP structure",
    )
    
    args = parser.parse_args()
    input_dir = args.input
    
    if not os.path.isdir(input_dir):
        logging.error(f"Directory '{input_dir}' does not exist")
        return
      
    directory = utils.PSP(input_dir)

    while True:
        choice = utils.render_menu(
            [f"Current directory: {input_dir}", f"Total games/tools: {len(directory.items)}"],
            ["List", "Rename", "Order", "Reload drive", "Exit"]
        )
        
        if choice == "1":
            list_files(directory.items)
        elif choice == "2":
            rename_files(directory.items)
        elif choice == "3":
            reorder_files(directory.items)
        elif choice == "4":
            pass
        elif choice == "5":
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again")
        
if __name__ == "__main__":
  try:
      main()
  except Exception as e:
      logging.error(e)
      exit()